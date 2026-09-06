# Logs and metrics next to OnCall on a kind cluster

A small, complete observability loop for demos and local testing: every pod's logs land in Loki,
every node's container metrics and the OnCall exporter land in Mimir, and both are wired into the
Grafana that the OnCall chart installs.

```text
 pods (all namespaces) --logs--> Alloy (DaemonSet) --push--> Loki (single binary, local disk)
 kubelet + cAdvisor    --------> Alloy            --remote_write--> Mimir (single process, local disk)
 kube-state-metrics, node-exporter (from the OnCall chart's prometheus subchart) --> Alloy --> Mimir
 OnCall engine /metrics/ ------> Alloy            --remote_write--> Mimir
 Grafana (OnCall release) --datasources--> Loki, Mimir, and the chart's own Prometheus
```

What lands in Mimir, by job label: `cadvisor` (container CPU, memory, network per pod), `kubelet`
(running pods and containers, volume usage), `kube-state-metrics` (pod phases, restarts,
deployments, nodes, quotas), `prometheus-node-exporter` (node CPU, memory, disk, network) and
`oncall-exporter`. Only the cAdvisor and kubelet series are filtered down; the exporters are kept whole.

## Run it

```bash
kind create cluster --name oncall --image kindest/node:v1.37.0
helm install oncall ./helm/oncall -f dev/helm-kind.yml --wait --timeout 15m
dev/observability/install.sh kind-oncall oncall
kubectl port-forward svc/oncall-grafana 3001:80
```

Log in at <http://localhost:3001> as `admin` with
`kubectl get secret oncall-grafana -o jsonpath='{.data.admin-password}' | base64 -d`.

- Explore → **Loki** → `{namespace="default", container="oncall"}` shows the engine's request log.
- Explore → **Mimir** → `sum by (pod) (container_memory_working_set_bytes{namespace="default"})`
  shows memory per OnCall pod; `oncall_alert_groups_total` is the OnCall exporter.
- The OnCall Insights dashboard can read from either **Prometheus** (the chart's own, scraping
  the exporter) or **Mimir** (what Alloy remote-writes): pick it in the dashboard's datasource box.

## What each file does

- `loki-values.yaml`: Loki chart in `SingleBinary` mode, filesystem storage, 7-day retention;
  caches, MinIO and the canary are off.
- `mimir.yaml`: Mimir 3.x with `target: all` in one StatefulSet, filesystem blocks, 7-day retention.
- `alloy-values.yaml`: Alloy config. `loki.source.kubernetes` tails logs through the API (no host
  mounts); cAdvisor is scraped per node and the OnCall exporter once; both `remote_write` to Mimir.
- `oncall-datasources.yaml`: Grafana datasource provisioning for Loki and Mimir, applied to the
  OnCall release.
- `install.sh`: the four steps above in order, idempotent (`helm upgrade --install`).

## Sizing

Requests are set for a laptop kind node: Loki 256Mi, Mimir 256Mi, Alloy 128Mi per node. Memory
limits are 768Mi / 1Gi / 512Mi. Everything stores on the node's local disk through the default
`standard` StorageClass; deleting the kind cluster deletes the data.

## Not for production

Single replicas, local disks and no authentication are deliberate here. For a real environment
use the `loki` chart in simple-scalable or distributed mode with object storage, the
`mimir-distributed` chart, and put Alloy's `remote_write` and `loki.write` behind authenticated
endpoints.
