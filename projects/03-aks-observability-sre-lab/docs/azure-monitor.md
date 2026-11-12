# Azure Monitor and Log Analytics integration

The local stack uses open-source Prometheus and Grafana. On AKS the same
metrics, rules and dashboard move to Azure-managed services.

## 1. Enable managed Prometheus, Grafana and Container Insights

```bash
RG=rg-sre-lab; AKS=aks-sre-lab; LOC=centralindia
az monitor account create -g $RG -n amw-sre-lab -l $LOC                      # Azure Monitor workspace
az grafana create -g $RG -n grafana-sre-lab -l $LOC                           # Azure Managed Grafana
az monitor log-analytics workspace create -g $RG -n law-sre-lab -l $LOC

AMW_ID=$(az monitor account show -g $RG -n amw-sre-lab --query id -o tsv)
GRAFANA_ID=$(az grafana show -g $RG -n grafana-sre-lab --query id -o tsv)
LAW_ID=$(az monitor log-analytics workspace show -g $RG -n law-sre-lab --query id -o tsv)

az aks update -g $RG -n $AKS --enable-azure-monitor-metrics \
  --azure-monitor-workspace-resource-id $AMW_ID --grafana-resource-id $GRAFANA_ID
az aks enable-addons -g $RG -n $AKS -a monitoring --workspace-resource-id $LAW_ID
```

Billable: Azure Monitor workspace ingestion, Managed Grafana instance, Log Analytics ingestion and retention.

## 2. Scrape the service

```bash
kubectl create namespace sre-lab
kubectl apply -f k8s/checkout-api.yaml
kubectl apply -f k8s/azure-managed-prometheus-podmonitor.yaml
```

## 3. Load the SLO rules

Azure Monitor runs Prometheus rules as *Prometheus rule groups*. The recording
and alert expressions in `prometheus/rules/slo-rules.yaml` can be used as-is.
Create one rule group per YAML group (portal: Azure Monitor workspace →
Rule groups, or ARM/Bicep resource `Microsoft.AlertsManagement/prometheusRuleGroups`),
scope it to the cluster, and attach an action group for the page.

```bash
az monitor action-group create -g $RG -n ag-oncall --short-name oncall \
  --action email oncall oncall@example.com
```

## 4. Dashboard

Import `grafana/dashboards/checkout-slo.json` into Azure Managed Grafana and
select the Azure Monitor workspace Prometheus data source.

## 5. Traces to Application Insights

Either keep the OpenTelemetry Collector and switch its exporter to
`azuremonitor` (see `otel-collector/config.yaml`), or use the Azure Monitor
OpenTelemetry Distro in the service (`azure-monitor-opentelemetry` with
`APPLICATIONINSIGHTS_CONNECTION_STRING`). Keep the connection string in a
Kubernetes secret sourced from Key Vault, not in the manifest.

## 6. Useful KQL (Log Analytics)

```kusto
// Slow checkout requests from container logs (gunicorn access log)
ContainerLogV2
| where PodNamespace == "sre-lab" and ContainerName == "checkout-api"
| where LogMessage has "POST /api/checkout"
| summarize requests = count() by bin(TimeGenerated, 1m)

// Pod restarts during the incident window
KubePodInventory
| where Namespace == "sre-lab"
| summarize restarts = max(PodRestartCount) by Name, bin(TimeGenerated, 5m)

// Dependency latency from Application Insights
AppDependencies
| where AppRoleName == "checkout-api" and Name == "inventory.lookup"
| summarize p95 = percentile(DurationMs, 95) by bin(TimeGenerated, 1m)
```
