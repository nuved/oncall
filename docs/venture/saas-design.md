# Mansoor OnCall as a service            drafted-by: fable · 2026-09-06 · approved-by:

What we would sell, how tenants are kept apart, what we meter and charge for, and how people get
in. Grounded in the code as it is today (file references are to this repository). Nothing here is
built yet; the phased plan at the end turns it into backlog rows T-31..T-37.

## 1. The offer

Hosted on-call for small engineering teams (3 to 50 engineers) in the EU: a Grafana with Mansoor
OnCall installed, our notification engine behind it, phone and SMS included, data in the EU. The
buyer is the person who is tired of running PagerDuty-style tooling or a self-hosted Grafana just
for on-call. The wedge is price plus EU data handling plus the AI triage work already on the
backlog (T-15, T-21..T-23).

## 2. Tenancy: how customers are kept apart

OnCall was written as a multi-tenant engine. An `Organization` is keyed by `(stack_id, org_id)`
(`engine/apps/user_management/models/organization.py:114-251`), every query is scoped to it, API
tokens are per organization and user, and Grafana Cloud ran thousands of customers on exactly this
shape: one engine per region, one Grafana per customer. We reuse that shape.

| layer | per tenant | shared | why |
|---|---|---|---|
| Grafana + plugin | one instance in its own namespace, created by the tenancy operator (`Tenant` → `Workspace`) with ResourceQuota, NetworkPolicy (Cilium), RBAC | | the UI is where accidental leaks happen; a separate instance means there is no cross-tenant screen at all |
| OnCall engine + Celery | | one per region | designed for it; keeps cost per tenant near zero |
| PostgreSQL | rows scoped by organization; per-tenant data encryption key (see §6) | one cluster | operational simplicity; scoping is already in the code |
| Loki, Mimir | tenant ID = customer (`X-Scope-OrgID`) | one stack | Loki and Mimir are multi-tenant by design; a tenant can only query its own logs and metrics |
| Slack, Telegram, Twilio numbers | Slack workspace and Telegram bot connection per organization (already the model); phone numbers from a regional pool | | a Slack workspace can only be linked to one organization, so chat messages cannot cross tenants |

Two alternatives were considered and rejected for now. A Grafana organization per customer on a
shared Grafana is cheaper but weak: a Grafana server admin sees every org, and a plugin bug can
cross orgs. A full engine per tenant is the strongest isolation and the most expensive; it becomes
the "dedicated" tier in phase 3.

Leak prevention is a test, not a promise: a permission test suite that calls every public and
internal API endpoint with a token from organization A against objects of organization B and
expects 403 or 404 (T-33). Upstream has some of these; they become mandatory for every endpoint.

## 3. People, roles, teams

- Sign-in through Grafana's own OAuth (Google, GitHub, Microsoft, generic OIDC). Email invites use
  Grafana's invite flow; SCIM comes with the Business plan.
- Roles map to what OnCall already enforces: **Admin** and **Editor** can be on call and are the
  billable seats; **Viewer** cannot hold shifts (the engine refuses it) and is free, so managers,
  support and stakeholders can watch without paying.
- Teams are Grafana Teams, synced into OnCall. New teams default to
  `is_sharing_resources_to_all = false` (`apps/user_management/models/team.py:63`): their
  schedules, integrations and escalation chains are visible to members and admins only. Direct
  paging targets a team, so one team can page another without seeing its configuration.
- Alert payloads are the sensitive part inside a tenant (they carry whatever the monitoring system
  sends). Team-scoped integrations keep them team-private; a per-integration "redact payload
  fields" template covers the rest.

## 4. Pricing and what gets metered

| plan | price | seats | channels | telephony | retention |
|---|---|---|---|---|---|
| Free | €0 | up to 5 Admin/Editor seats, unlimited Viewers | email, Slack, Telegram, webhooks | none | 7 days |
| Team | €10 per Admin/Editor seat per month | unlimited | all, plus phone and SMS | included allowance per organization per month (e.g. 100 SMS or 50 call minutes), then prepaid credits at a country-based rate; hard cap the customer sets | 90 days |
| Business | €25 per seat | unlimited | all | larger allowance, same credits | 1 year, SSO/SCIM, audit log, dedicated engine option |

Seats are counted, not declared: the number of distinct Admin/Editor users in the organization
during the month, synced to Stripe nightly and billed pro rata. Telephony is metered from rows the
engine already writes: `PhoneCallRecord` (`apps/phone_notifications/models/phone_call.py`) with the
provider's duration and status from the Twilio callbacks, `SMSRecord`, and `EmailMessage`
(`apps/email/models.py`). A nightly job turns them into Stripe usage records; the same numbers go
to a "Usage" page next to Insights (the exporter already counts alert groups and notified users
per organization, `apps/metrics_exporter/metrics_collectors.py:57-69`).

Rules that protect the customer and us:

- Alerts never stop silently. A failed payment puts the organization in a 14-day grace period with
  notifications still flowing and admins warned daily; after that the organization goes read-only
  (no new alerts), never deleted without a further 30 days.
- Telephony fraud is real (SMS pumping, premium-rate numbers). Only verified numbers can be
  notified (OnCall already verifies them), calls go to a country allowlist per organization,
  every organization has a daily cap, and `BannedPhoneNumber` is used for abuse.
- Free tier has no telephony at all; a card on file unlocks it with a small starting credit.

## 5. Email that does not become spam

- Send through a transactional provider (Postmark or SES) from a dedicated sending domain
  (`alerts.<our-domain>`) with SPF, DKIM and DMARC; product and marketing mail use a different
  domain so alert reputation is never shared.
- Recipients are users who signed in through SSO, so the address is verified before the first mail.
- OnCall already limits volume by design: alerts are grouped into alert groups, and a notification
  policy fires once per step, not once per alert. On top: a per-user ceiling (for example 60 alert
  mails per hour, then a digest), and a per-organization ceiling that pages the organization's
  admin instead of mailing everyone.
- Bounces and complaints come back through the provider's webhook; a hard bounce or complaint
  disables the email channel for that user and tells the admins, instead of retrying.
- `List-Unsubscribe` on everything that is not an alert; alert mail explains where it comes from and
  how to change the notification policy.
- Inbound email integrations (`config_integrations/inbound_email.py`) get one random address per
  integration, never a guessable one.

## 6. Data protection

- EU hosting (Hetzner, OVH or an EU AWS region), a DPA with the subprocessor list (cloud, Twilio,
  email provider, Stripe), and an admin-visible data inventory: what OnCall stores is known
  (alert payloads, phone numbers, chat identities, tokens; see the data-model audit of 2026-09-04).
- Encryption at rest with a per-tenant data key under envelope encryption (backlog T-19 extended):
  Slack tokens today are plaintext in the database, so this is the first security item. Deleting a
  tenant then means destroying its key.
- Retention per plan enforced by a job (T-18): alert payloads, notification logs, call records.
- Traffic encrypted inside the cluster (Cilium's WireGuard node encryption) and at the edge.
- No secrets in logs: the Alloy pipeline drops known token patterns before Loki.
- Backups encrypted, restore rehearsed monthly, and an audit log of admin actions per organization
  (Business plan surface, but collected from day one).

## 7. Metrics that run the business

| metric | source |
|---|---|
| paying organizations and MRR | Stripe |
| activation: first schedule, first integration and first delivered notification within 7 days of signup | engine events |
| weekly active responders (acknowledged or resolved something) | `AlertGroupLogRecord` |
| notification delivery latency p95 and call success rate | `UserNotificationPolicyLogRecord`, `PhoneCallRecord` |
| telephony cost per organization vs. what it paid | Twilio usage + Stripe |
| infra cost per tenant | Mimir (namespace CPU/memory per Workspace) |
| churn and seats per organization over time | nightly seat sync |

`metric_now` for this bet would be paying organizations, target 10 within three months of launch.

## 8. Phases

1. **Foundation (4 to 6 weeks).** Shared engine on PostgreSQL, Grafana-per-tenant through the
   tenancy operator, Stripe seat billing, email plus Slack and Telegram, manual onboarding by us,
   the cross-tenant permission test suite. Free and Team plans without telephony.
2. **Telephony and metering.** Twilio numbers per region, verified numbers, allowlists and caps,
   credits, usage page, nightly usage records.
3. **Trust.** Per-tenant encryption keys, retention jobs, audit log, SSO/SCIM, DPA and inventory.
4. **Scale-up.** Dedicated engine tier, mobile push through our own Firebase project (T-17),
   status page, AI triage (T-15, T-23) as the paid differentiator.

## 9. Open questions for the operator

- Company and billing entity, VAT handling, and which EU provider hosts the first region.
- Whether the free tier should exist at launch or start as a 30-day trial (a free tier costs
  support time; a trial converts better for tooling like this).
- The telephony allowance and overage rate per country; the table above uses placeholders.
