#!/usr/bin/env python3
"""Smoke test for a running Mansoor OnCall stack, driven through the Grafana plugin proxy (admin basic auth)
and the engine's public API. It creates its own integrations, contact point, alert rule, schedule, token and
outgoing webhook, walks an alert group through its lifecycle, and removes what it created in Grafana.
Prints one PASS/FAIL line per check and exits non-zero on any failure.

Environment:
  GRAFANA_URL         default http://localhost:3000
  ENGINE_URL          engine as reachable from this machine, default http://localhost:8081
  ENGINE_URL_INTERNAL engine as it appears in integration URLs (BASE_URL), default = ENGINE_URL
  GRAFANA_ADMIN       user:password, default oncall:oncall
  WEBHOOK_LISTENER    URL the engine can POST to for the outgoing-webhook check; unset skips that check
  METRICS_SECRET      PROMETHEUS_EXPORTER_SECRET of the engine; unset skips the metrics check
  WEBHOOK_HITS_FILE   file the listener appends one line per hit to (used with WEBHOOK_LISTENER)
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

GRAFANA = os.environ.get("GRAFANA_URL", "http://localhost:3000")
ENGINE = os.environ.get("ENGINE_URL", "http://localhost:8081")
ENGINE_INTERNAL = os.environ.get("ENGINE_URL_INTERNAL", ENGINE)
PLUGIN = f"{GRAFANA}/api/plugins/grafana-oncall-app/resources"
ADMIN = base64.b64encode(os.environ.get("GRAFANA_ADMIN", "oncall:oncall").encode()).decode()
WEBHOOK_LISTENER = os.environ.get("WEBHOOK_LISTENER")
METRICS_SECRET = os.environ.get("METRICS_SECRET")
WEBHOOK_HITS_FILE = os.environ.get("WEBHOOK_HITS_FILE", "")

results = []


def call(method, url, body=None, headers=None, auth="admin", expect=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    if auth == "admin":
        h["Authorization"] = f"Basic {ADMIN}"
    elif auth:
        h["Authorization"] = auth
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    raw = r.read().decode()
                    return r.status, (json.loads(raw) if raw else None)
            except TimeoutError:
                print(f"  (timeout on {method} {url.split('/resources')[-1][:60]}, attempt {attempt + 1})", flush=True)
        return 599, "timeout"
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw[:200]


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)
    return ok


def wait_for(fn, seconds=60, every=3):
    deadline = time.time() + seconds
    while time.time() < deadline:
        v = fn()
        if v:
            return v
        time.sleep(every)
    return None


stamp = str(int(time.time()))[-6:]

# 1. plugin connection and sync
st, status = call("GET", f"{PLUGIN}/plugin/status")
conn = (status or {}).get("pluginConnection") or {}
check(
    "plugin: engine reachable, token and URLs valid",
    st == 200 and conn and all(v.get("ok") for v in conn.values()),
    f"http={st} checks={list(conn)}",
)
st, users = call("GET", f"{PLUGIN}/users/?perpage=100")
usernames = [u["username"] for u in users.get("results", [])] if st == 200 else []
check("users synced from Grafana", st == 200 and "oncall" in usernames, f"{len(usernames)} users")
me_id = next((u["pk"] for u in users.get("results", []) if u["username"] == "oncall"), None)

# 2. integrations: Grafana Alerting (contact points via provisioning API) and a generic webhook
st, ga = call(
    "POST",
    f"{PLUGIN}/alert_receive_channels/",
    {"integration": "grafana_alerting", "verbal_name": f"fp-ga-{stamp}", "team": None},
)
check("create Grafana Alerting integration", st in (200, 201) and ga.get("id"), f"http={st}")
ga_id = ga.get("id")
st, _ = call(
    "POST",
    f"{PLUGIN}/alert_receive_channels/{ga_id}/create_contact_point/",
    {"datasource_uid": "grafana", "contact_point_name": f"fp-cp-{stamp}"},
)
check("create contact point from OnCall", st in (200, 201), f"http={st}")
st, cps = call("GET", f"{PLUGIN}/alert_receive_channels/contact_points/")
check(
    "list Grafana contact points (provisioning API)",
    st == 200 and any(d.get("uid") == "grafana" and f"fp-cp-{stamp}" in d.get("contact_points", []) for d in cps),
    f"http={st}",
)
st, prov = call("GET", f"{GRAFANA}/api/v1/provisioning/contact-points")
entry = next((c for c in prov if c["name"] == f"fp-cp-{stamp}"), None) if st == 200 else None
check(
    "contact point visible in Grafana, type oncall, not provisioned-locked",
    entry is not None and entry["type"] == "oncall" and not entry.get("provenance"),
    f"provenance={entry.get('provenance') if entry else None}",
)
st, conn = call("GET", f"{PLUGIN}/alert_receive_channels/{ga_id}/connected_contact_points/")
check(
    "plugin reports the contact point as connected",
    st == 200 and any(cp["name"] == f"fp-cp-{stamp}" for d in conn for cp in d["contact_points"]),
)
st, wh = call(
    "POST",
    f"{PLUGIN}/alert_receive_channels/",
    {"integration": "webhook", "verbal_name": f"fp-webhook-{stamp}", "team": None},
)
check("create generic webhook integration", st in (200, 201) and wh.get("id"), f"http={st}")
wh_id = wh.get("id")

# 3. Grafana Alerting really fires: alert rule -> contact point -> OnCall
st, folder = call("POST", f"{GRAFANA}/api/folders", {"title": f"fp-{stamp}"})
folder_uid = folder.get("uid") if st == 200 else None
rule = {
    "title": f"fp-always-firing-{stamp}",
    "ruleGroup": "fp",
    "folderUID": folder_uid,
    "condition": "C",
    "for": "10s",
    "orgID": 1,
    "noDataState": "OK",
    "execErrState": "Error",
    "notification_settings": {"receiver": f"fp-cp-{stamp}"},
    "data": [
        {
            "refId": "A",
            "relativeTimeRange": {"from": 600, "to": 0},
            "datasourceUid": "__expr__",
            "model": {"refId": "A", "type": "math", "expression": "1"},
        },
        {
            "refId": "C",
            "datasourceUid": "__expr__",
            "model": {
                "refId": "C",
                "type": "threshold",
                "expression": "A",
                "conditions": [{"evaluator": {"type": "gt", "params": [0]}}],
            },
        },
    ],
}
st, created_rule = call(
    "POST", f"{GRAFANA}/api/v1/provisioning/alert-rules", rule, headers={"X-Disable-Provenance": "true"}
)
check(
    "create an always-firing Grafana alert rule routed to that contact point",
    st in (200, 201),
    f"http={st} {str(created_rule)[:120] if st not in (200, 201) else ''}",
)
rule_uid = created_rule.get("uid") if st in (200, 201) else None
# rule group interval: make it evaluate every 10s
if folder_uid:
    call(
        "PUT",
        f"{GRAFANA}/api/v1/provisioning/folder/{folder_uid}/rule-groups/fp",
        {"interval": 10},
        headers={"X-Disable-Provenance": "true"},
    )


def ga_alert_groups():
    st, d = call("GET", f"{PLUGIN}/alertgroups/?integration={ga_id}")
    return d.get("results") if st == 200 and d.get("results") else None


ags = wait_for(ga_alert_groups, seconds=180, every=5)
check(
    "Grafana alert delivered to OnCall as an alert group (real evaluation)",
    ags is not None,
    f"{len(ags) if ags else 0} groups after wait",
)
ga_alert_group = ags[0]["pk"] if ags else None

# 4. webhook integration ingestion and alert group lifecycle
st, _ = call(
    "POST",
    wh["integration_url"].replace(ENGINE_INTERNAL, ENGINE),
    {"title": f"fp webhook alert {stamp}", "message": "functional pass", "state": "alerting"},
    auth=None,
)
check("generic webhook payload accepted", st == 200, f"http={st}")


def wh_alert_groups():
    st, d = call("GET", f"{PLUGIN}/alertgroups/?integration={wh_id}")
    return d.get("results") if st == 200 and d.get("results") else None


wags = wait_for(wh_alert_groups, seconds=60, every=3)
check("webhook alert became an alert group", wags is not None)
ag = wags[0]["pk"] if wags else None
if ag:
    st, d = call("POST", f"{PLUGIN}/alertgroups/{ag}/acknowledge/")
    check("acknowledge", st == 200 and d.get("status") == 1, f"http={st}")
    st, d = call("POST", f"{PLUGIN}/alertgroups/{ag}/unacknowledge/")
    check("unacknowledge", st == 200 and d.get("status") == 0, f"http={st}")
    st, d = call("POST", f"{PLUGIN}/alertgroups/{ag}/silence/", {"delay": 3600})
    check("silence 1h", st == 200 and d.get("status") == 3, f"http={st}")
    st, d = call("POST", f"{PLUGIN}/alertgroups/{ag}/unsilence/")
    check("unsilence", st == 200 and d.get("status") == 0, f"http={st}")
    st, d = call("POST", f"{PLUGIN}/alertgroups/{ag}/resolve/")
    check("resolve", st == 200 and d.get("status") == 2, f"http={st}")
    st, d = call("POST", f"{PLUGIN}/resolution_notes/", {"alert_group": ag, "text": "functional pass note"})
    check("resolution note", st in (200, 201), f"http={st}")
    st, d = call("GET", f"{PLUGIN}/alertgroups/{ag}/")
    check(
        "alert group timeline recorded",
        st == 200 and len(d.get("render_after_resolve_report_json") or []) >= 3,
        f"{len(d.get('render_after_resolve_report_json') or []) if st == 200 else 0} entries",
    )

# 5. escalation chain + route -> notification attempt to a user
# (no provider configured: must fail gracefully, not crash)
st, ch = call("POST", f"{PLUGIN}/escalation_chains/", {"name": f"fp-chain-{stamp}", "team": None})
check("create escalation chain", st in (200, 201), f"http={st}")
chain_id = ch.get("id")
st, pol = call(
    "POST",
    f"{PLUGIN}/escalation_policies/",
    {"escalation_chain": chain_id, "step": 13, "notify_to_users_queue": [me_id], "important": False},
)
check("add 'notify users' step", st in (200, 201), f"http={st} {str(pol)[:100] if st not in (200, 201) else ''}")
st, routes = call("GET", f"{PLUGIN}/channel_filters/?alert_receive_channel={wh_id}")
default_route = routes[0]["id"] if st == 200 and routes else None
st, _ = call(
    "PUT",
    f"{PLUGIN}/channel_filters/{default_route}/",
    {
        "escalation_chain": chain_id,
        "alert_receive_channel": wh_id,
        "filtering_term": None,
        "is_default": True,
        "notify_in_slack": False,
    },
)
check("attach chain to the webhook integration's default route", st == 200, f"http={st}")
st, before = call("GET", f"{PLUGIN}/alertgroups/?integration={wh_id}")
known = {g["pk"] for g in (before.get("results") if st == 200 else []) or []}
st, _ = call(
    "POST",
    wh["integration_url"].replace(ENGINE_INTERNAL, ENGINE),
    {"title": f"fp escalate {stamp}", "message": "escalation pass", "state": "alerting"},
    auth=None,
)


def escalated():
    st, d = call("GET", f"{PLUGIN}/alertgroups/?integration={wh_id}")
    for g in (d.get("results") if st == 200 else []) or []:
        if g["pk"] not in known:
            st2, full = call("GET", f"{PLUGIN}/alertgroups/{g['pk']}/")
            log = full.get("render_after_resolve_report_json") or []
            blob = json.dumps(log).lower()
            if "notif" in blob or "escalat" in blob or "trigger" in blob:
                return log
    return None


esc = wait_for(escalated, seconds=120, every=5)
check(
    "escalation ran and logged a notification attempt for the user",
    esc is not None,
    (json.dumps(esc)[:300] if esc else "no escalation log within 120s"),
)

# 6. schedules: web schedule + rotation, who is on call
st, sched = call(
    "POST",
    f"{PLUGIN}/schedules/",
    {
        "name": f"fp-schedule-{stamp}",
        "type": 2,
        "team": None,
        "slack_channel_id": None,
        "user_group": None,
        "notify_oncall_shift_freq": 1,
        "mention_oncall_next": False,
        "mention_oncall_start": True,
        "enable_web_overrides": True,
        "notify_empty_oncall": 1,
    },
)
check("create web schedule", st in (200, 201), f"http={st} {str(sched)[:100] if st not in (200, 201) else ''}")
sched_id = sched.get("id")
start = time.strftime("%Y-%m-%dT00:00:00", time.gmtime(time.time() - 86400))
shift_end = time.strftime("%Y-%m-%dT00:00:00", time.gmtime(time.time()))
st, shift = call(
    "POST",
    f"{PLUGIN}/oncall_shifts/",
    {
        "schedule": sched_id,
        "type": 2,
        "priority_level": 1,
        "shift_start": start,
        "shift_end": shift_end,
        "rotation_start": start,
        "frequency": 0,
        "interval": 1,
        "by_day": None,
        "rolling_users": [[me_id]],
        "start_rotation_from_user_index": 0,
        "week_start": "MO",
        "until": None,
        "name": "fp rotation",
    },
)
check(
    "create daily rotation with the admin user",
    st in (200, 201),
    f"http={st} {str(shift)[:120] if st not in (200, 201) else ''}",
)
today = time.strftime("%Y-%m-%d", time.gmtime())
st, cur = call("GET", f"{PLUGIN}/schedules/{sched_id}/filter_events/?type=final&date={today}&days=1")
on_call = [u.get("pk") for ev in (cur.get("events") or []) for u in (ev.get("users") or [])] if st == 200 else []
check("schedule reports the admin as on call now", st == 200 and me_id in on_call, f"http={st} users={len(on_call)}")

# 7. public API with a token: list, ack, direct paging, who is on call
st, tok = call("POST", f"{PLUGIN}/tokens/", {"name": f"fp-{stamp}"})
check("create public API token", st in (200, 201) and tok.get("token"), f"http={st}")
token = tok.get("token")
st, pub = call("GET", f"{ENGINE}/api/v1/alert_groups/", auth=token)
check("public API lists alert groups", st == 200 and pub.get("count", 0) >= 1, f"http={st}")
st, esc_resp = call(
    "POST",
    f"{ENGINE}/api/v1/escalation/",
    {"users": [{"id": me_id, "important": False}], "title": f"fp direct page {stamp}", "message": "public API paging"},
    auth=token,
)
check(
    "direct paging through the public API creates an alert group", st in (200, 201) and esc_resp.get("id"), f"http={st}"
)
st, shifts = call(
    "GET",
    f"{ENGINE}/api/v1/schedules/{sched_id}/final_shifts/"
    f"?start_date={time.strftime('%Y-%m-%d', time.gmtime())}"
    f"&end_date={time.strftime('%Y-%m-%d', time.gmtime(time.time() + 86400))}",
    auth=token,
)
check("public API final_shifts answers who is on call", st == 200 and len(shifts.get("results", [])) >= 1, f"http={st}")

# 8. outgoing webhook to a listener the engine can reach
if WEBHOOK_LISTENER:
    st, ow = call(
        "POST",
        f"{PLUGIN}/webhooks/",
        {
            "name": f"fp-outgoing-{stamp}",
            "url": WEBHOOK_LISTENER,
            "http_method": "POST",
            "trigger_type": "1",
            "data": json.dumps({"event": "{{ event.type }}", "group": "{{ alert_group_id }}"}),
            "forward_all": False,
            "is_webhook_enabled": True,
            "team": None,
            "integration_filter": [wh_id],
        },
    )
    check(
        "create outgoing webhook (alert group created)",
        st in (200, 201),
        f"http={st} {str(ow)[:120] if st not in (200, 201) else ''}",
    )
    st, _ = call(
        "POST",
        wh["integration_url"].replace(ENGINE_INTERNAL, ENGINE),
        {"title": f"fp outgoing {stamp}", "message": "outgoing webhook pass", "state": "alerting"},
        auth=None,
    )

    def outgoing_hit():
        try:
            return open(WEBHOOK_HITS_FILE).read().count('"group"')
        except (FileNotFoundError, OSError):
            return 0

    hits_before = outgoing_hit()
    got = wait_for(lambda: outgoing_hit() > hits_before, seconds=60, every=3)
    check("outgoing webhook delivered to the listener", bool(got), f"hits={outgoing_hit()}")

# 9. metrics exporter
if METRICS_SECRET:
    req = urllib.request.Request(f"{ENGINE}/metrics/", headers={"Authorization": f"Bearer {METRICS_SECRET}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            check("prometheus exporter serves alert group metrics", "alert_groups_total" in body, f"{len(body)} bytes")
    except urllib.error.HTTPError as e:
        check("prometheus exporter serves alert group metrics", False, f"http={e.code}")

# 10. disconnect + cleanup of the Grafana side
st, d = call(
    "POST",
    f"{PLUGIN}/alert_receive_channels/{ga_id}/disconnect_contact_point/",
    {"datasource_uid": "grafana", "contact_point_name": f"fp-cp-{stamp}"},
)
check(
    "disconnect refused while an alert rule still uses the contact point, with a clear message",
    st == 400 and "still used" in str(d),
    f"http={st} {str(d)[:90]}",
)
if rule_uid:
    call("DELETE", f"{GRAFANA}/api/v1/provisioning/alert-rules/{rule_uid}", headers={"X-Disable-Provenance": "true"})
if folder_uid:
    call("DELETE", f"{GRAFANA}/api/folders/{folder_uid}")
st, _ = call(
    "POST",
    f"{PLUGIN}/alert_receive_channels/{ga_id}/disconnect_contact_point/",
    {"datasource_uid": "grafana", "contact_point_name": f"fp-cp-{stamp}"},
)
check("disconnect contact point after the rule is gone", st == 200, f"http={st}")
st, prov = call("GET", f"{GRAFANA}/api/v1/provisioning/contact-points")
check("Grafana has no leftover fp contact point", st == 200 and not any(c["name"] == f"fp-cp-{stamp}" for c in prov))

print("\n== summary ==")
passed = sum(1 for _, ok, _ in results if ok)
print(f"{passed}/{len(results)} checks passed")
for name, ok, detail in results:
    if not ok:
        print("  FAILED:", name, detail)
sys.exit(0 if passed == len(results) else 1)
