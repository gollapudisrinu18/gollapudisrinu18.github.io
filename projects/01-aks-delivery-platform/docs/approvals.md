# Environments and approvals

Approvals in Azure Pipelines are **checks on an Environment**, not YAML. The
pipeline's deployment jobs target three Environments:

| Environment | Check | Who approves |
|---|---|---|
| `orders-dev` | none | automatic |
| `orders-qa` | Branch control (main only) | automatic |
| `orders-prod` | Approval + Branch control | release approver group |

## Set up in the portal

1. **Pipelines → Environments → New environment**: create `orders-dev`, `orders-qa`, `orders-prod` (Resource: None).
2. Open `orders-prod` → **⋯ → Approvals and checks → + → Approvals**. Add your approver group, set a timeout (for example 24 hours) and enable "Approver can't approve their own run" if needed.
3. Add **Branch control** on `orders-qa` and `orders-prod` with allowed branches `refs/heads/main`.
4. **Project settings → Service connections → New → Azure Resource Manager (workload identity federation)**. Name it `sc-aks-delivery` and scope it to the lab resource group.
5. **Pipelines → Library → + Variable group** `aks-delivery` with `acrName`, `aksResourceGroup`, `aksClusterName`.

## Set up from the CLI (optional)

```bash
az extension add --name azure-devops
az devops configure --defaults organization=https://dev.azure.com/<org> project=<project>
az pipelines variable-group create --name aks-delivery \
  --variables acrName=<acr> aksResourceGroup=rg-aks-delivery-lab aksClusterName=aks-delivery-lab
```

Environments are created automatically the first time a deployment job runs
against them; add the approval check before the first run reaches Production.
