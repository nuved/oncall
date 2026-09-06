#!/bin/sh
# Creates a kind cluster without the default CNI and without kube-proxy, starts the dedicated etcd
# for Cilium on the control-plane node, then installs Cilium pointed at that etcd.
#
# Usage: dev/cilium/install.sh [cluster-name]      (default: oncall)
# Afterwards: helm install oncall ./helm/oncall -f dev/helm-kind.yml --wait --timeout 15m
#             dev/observability/install.sh kind-<cluster-name> oncall
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
NAME=${1:-oncall}
CTX="kind-$NAME"
CILIUM_CHART_VERSION=1.20.1

if ! kind get clusters 2>/dev/null | grep -qx "$NAME"; then
  echo ">> kind cluster $NAME (no default CNI, no kube-proxy)"
  kind create cluster --name "$NAME" --config "$ROOT/dev/kind-cilium.yaml" --wait 60s
fi

helm repo add cilium https://helm.cilium.io >/dev/null 2>&1 || true
helm repo update cilium >/dev/null

echo ">> dedicated etcd for Cilium"
kubectl --context "$CTX" apply -f "$HERE/etcd.yaml"
kubectl --context "$CTX" -n kube-system rollout status statefulset/cilium-etcd --timeout=3m

IP=$(kubectl --context "$CTX" get nodes -l node-role.kubernetes.io/control-plane \
  -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
echo ">> Cilium $CILIUM_CHART_VERSION (API server $IP:6443, etcd http://$IP:2479)"
helm upgrade --install cilium cilium/cilium --version "$CILIUM_CHART_VERSION" \
  --kube-context "$CTX" --namespace kube-system -f "$HERE/values.yaml" \
  --set k8sServiceHost="$IP" --set "etcd.endpoints[0]=http://$IP:2479" \
  --wait --timeout 10m

kubectl --context "$CTX" wait --for=condition=Ready nodes --all --timeout=3m
kubectl --context "$CTX" -n kube-system rollout status daemonset/cilium --timeout=5m
kubectl --context "$CTX" -n kube-system rollout status deployment/coredns --timeout=5m
echo ">> cilium status"
kubectl --context "$CTX" -n kube-system exec ds/cilium -c cilium-agent -- cilium status --brief
kubectl --context "$CTX" -n kube-system exec ds/cilium -c cilium-agent -- cilium status | grep -E "KVStore|KubeProxyReplacement|Cilium:|Hubble:" || true
echo "done. Next: helm install oncall $ROOT/helm/oncall -f $ROOT/dev/helm-kind.yml --kube-context $CTX --wait --timeout 15m"
