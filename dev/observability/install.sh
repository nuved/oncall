#!/bin/sh
# Installs the logging and metrics stack next to an OnCall release on a kind cluster:
#   Loki (single binary)  <- Alloy DaemonSet (every pod's logs)
#   Mimir (single process) <- Alloy (cAdvisor per node + the OnCall exporter)
# and provisions both as Grafana datasources in the OnCall release.
#
# Usage: dev/observability/install.sh [kube-context] [oncall-release]   (defaults: current context, oncall)
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
CTX=${1:-$(kubectl config current-context)}
RELEASE=${2:-oncall}
NS=observability
LOKI_CHART_VERSION=7.3.0
ALLOY_CHART_VERSION=1.12.1

helm repo add grafana https://grafana.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update grafana >/dev/null

kubectl --context "$CTX" create namespace "$NS" --dry-run=client -o yaml | kubectl --context "$CTX" apply -f -

echo ">> Loki"
helm upgrade --install loki grafana/loki --version "$LOKI_CHART_VERSION" \
  --kube-context "$CTX" --namespace "$NS" -f "$HERE/loki-values.yaml" --wait --timeout 10m

echo ">> Mimir"
kubectl --context "$CTX" apply -f "$HERE/mimir.yaml"
kubectl --context "$CTX" -n "$NS" rollout status statefulset/mimir --timeout=5m

echo ">> Alloy"
helm upgrade --install alloy grafana/alloy --version "$ALLOY_CHART_VERSION" \
  --kube-context "$CTX" --namespace "$NS" -f "$HERE/alloy-values.yaml" --wait --timeout 5m

echo ">> our dashboards as a ConfigMap (namespace of the $RELEASE release)"
RELEASE_NS=$(helm list --all-namespaces --kube-context "$CTX" -o json | python3 -c '
import sys, json
release = sys.argv[1]
print(next((x["namespace"] for x in json.load(sys.stdin) if x["name"] == release), ""))' "$RELEASE")
[ -n "$RELEASE_NS" ] || { echo "release $RELEASE not found in any namespace of $CTX" >&2; exit 1; }
kubectl --context "$CTX" -n "$RELEASE_NS" create configmap oncall-k8s-dashboards \
  --from-file="$HERE/dashboards" --dry-run=client -o yaml | kubectl --context "$CTX" apply -f -

echo ">> Grafana datasources and dashboards on the $RELEASE release"
helm upgrade "$RELEASE" "$ROOT/helm/oncall" --kube-context "$CTX" --namespace "$RELEASE_NS" --reuse-values \
  -f "$HERE/oncall-datasources.yaml" -f "$HERE/oncall-dashboards.yaml" --wait --timeout 10m

echo "done. Dashboards: folders Kubernetes, Kubernetes control plane, Logs."
echo "      Logs: Explore -> Loki -> {namespace=\"kube-system\"}   Metrics: Explore -> Mimir -> up"
