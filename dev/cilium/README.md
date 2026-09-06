# Cilium as the CNI, with its own etcd

`install.sh` builds the local kind cluster the way our platform runs: Cilium is the CNI and the
kube-proxy replacement, and Cilium keeps its state (identities, nodes, services) in a dedicated etcd
instead of the Kubernetes etcd or CRDs.

```bash
dev/cilium/install.sh oncall                      # kind cluster "oncall" + etcd + Cilium
helm install oncall ./helm/oncall -n oncall --create-namespace -f dev/helm-kind.yml --kube-context kind-oncall --wait --timeout 15m
dev/observability/install.sh kind-oncall oncall   # Loki, Mimir, Alloy, dashboards (Cilium's included)
```

Order matters: the cluster is created with `disableDefaultCNI` and `kubeProxyMode: none`
(`dev/kind-cilium.yaml`), so nothing gets a pod IP until Cilium is up; the etcd therefore runs on
the control-plane node's host network (`etcd.yaml`, ports 2479/2480 because the Kubernetes etcd
owns 2379/2380), and Cilium is installed last with `k8sServiceHost` and `etcd.endpoints` set to that
node's IP by the script.

What `values.yaml` turns on: `kubeProxyReplacement`, `etcd.enabled` + `identityAllocationMode:
kvstore`, Prometheus metrics for the agent, the operator and Hubble, Hubble relay and UI, and the
Cilium dashboards as ConfigMaps (the Grafana sidecar from `dev/observability/oncall-dashboards.yaml`
loads them into a "Cilium" folder). Alloy scrapes the agent (`cilium-agent`), `hubble` and
`cilium-operator` jobs into Mimir.

Check it:

```bash
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium status   # KVStore: Ok, etcd: 1/1 connected
kubectl -n kube-system port-forward svc/hubble-ui 12000:80              # http://localhost:12000
```

Demo layout, not production: one etcd member, no TLS, data under `/var/lib/cilium-etcd` on the
node. For production run a three-member etcd with TLS and set `etcd.ssl=true` with the
`cilium-etcd-secrets` Secret, as described in the Cilium external-etcd guide.
