#!/bin/sh
# Deploys (or re-deploys) everything onto a small single-node cluster in one go:
#   1. the OnCall chart with the laptop-sized values (dev/helm-kind.yml)
#   2. Loki, Mimir, Alloy, datasources and dashboards (dev/observability/install.sh)
# Re-runnable: helm upgrade --install everywhere, so a recreated cluster is back in one command.
#
# Usage: dev/deploy-all.sh [kube-context] [namespace]     (defaults: current context, oncall)
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/.." && pwd)
CTX=${1:-$(kubectl config current-context)}
NS=${2:-oncall}
RELEASE=oncall

echo ">> OnCall ($RELEASE in namespace $NS on $CTX)"
helm upgrade --install "$RELEASE" "$ROOT/helm/oncall" --kube-context "$CTX" --namespace "$NS" --create-namespace \
  -f "$HERE/helm-kind.yml" --wait --timeout 20m

echo ">> logs, metrics, dashboards"
"$HERE/observability/install.sh" "$CTX" "$RELEASE"

echo ">> plugin status"
kubectl --context "$CTX" -n "$NS" port-forward svc/"$RELEASE"-grafana 3999:80 >/dev/null 2>&1 &
PF=$!
sleep 4
PW=$(kubectl --context "$CTX" -n "$NS" get secret "$RELEASE"-grafana -o jsonpath='{.data.admin-password}' | base64 -d)
n=0
until [ $n -ge 12 ]; do
  out=$(curl -s -u "admin:$PW" http://localhost:3999/api/plugins/grafana-oncall-app/resources/plugin/status || true)
  echo "$out" | grep -q '"oncall_token":{"ok":true' && break
  sleep 10; n=$((n+1))
done
kill $PF 2>/dev/null || true
echo "$out" | python3 -c 'import sys, json
d = json.load(sys.stdin).get("pluginConnection", {})
bad = [k for k, v in d.items() if not v.get("ok")]
print("plugin connection: all green" if d and not bad else f"plugin connection NOT green: {bad or d}")'
echo "done. Grafana: kubectl --context $CTX -n $NS port-forward svc/$RELEASE-grafana 3001:80  ->  http://localhost:3001 (admin / secret $RELEASE-grafana)"
