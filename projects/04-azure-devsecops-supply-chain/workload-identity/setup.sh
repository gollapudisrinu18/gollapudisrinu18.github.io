#!/usr/bin/env bash
# Microsoft Entra Workload ID + Azure Key Vault for the demo app on AKS.
# Billable: Key Vault operations (pennies), the AKS cluster you already run.
set -euo pipefail
RG=${RG:-rg-supplychain-lab}
AKS=${AKS:-aks-supplychain-lab}
KV=${KV:-kv-supply-$RANDOM}
LOC=${LOC:-centralindia}
NS=supplychain
SA=demo-app
IDENTITY=id-demo-app

# 1. Cluster features: OIDC issuer, workload identity, Secrets Store CSI driver
az aks update -g "$RG" -n "$AKS" --enable-oidc-issuer --enable-workload-identity -o none
az aks enable-addons -g "$RG" -n "$AKS" --addons azure-keyvault-secrets-provider -o none || true
ISSUER=$(az aks show -g "$RG" -n "$AKS" --query oidcIssuerProfile.issuerUrl -o tsv)

# 2. Key Vault with RBAC, a synthetic secret, and a signing key for cosign
az keyvault create -g "$RG" -n "$KV" -l "$LOC" --enable-rbac-authorization true -o none
ME=$(az ad signed-in-user show --query id -o tsv)
KV_ID=$(az keyvault show -n "$KV" --query id -o tsv)
az role assignment create --assignee "$ME" --role "Key Vault Administrator" --scope "$KV_ID" -o none
sleep 20
az keyvault secret set --vault-name "$KV" -n app-db-password --value "synthetic-$(openssl rand -hex 8)" -o none
az keyvault key create --vault-name "$KV" -n cosign-signing --kty EC --curve P-256 -o none

# 3. User-assigned managed identity with read access to secrets only
az identity create -g "$RG" -n "$IDENTITY" -o none
CLIENT_ID=$(az identity show -g "$RG" -n "$IDENTITY" --query clientId -o tsv)
PRINCIPAL_ID=$(az identity show -g "$RG" -n "$IDENTITY" --query principalId -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
  --role "Key Vault Secrets User" --scope "$KV_ID" -o none

# 4. Federate the Kubernetes service account with the identity
az identity federated-credential create -g "$RG" --identity-name "$IDENTITY" -n fic-demo-app \
  --issuer "$ISSUER" --subject "system:serviceaccount:$NS:$SA" --audience api://AzureADTokenExchange -o none

TENANT=$(az account show --query tenantId -o tsv)
echo "Fill workload-identity/k8s/*.yaml with:"
echo "  CLIENT_ID=$CLIENT_ID  TENANT_ID=$TENANT  KEYVAULT_NAME=$KV"
echo "Cosign key: azurekms://$KV.vault.azure.net/cosign-signing"
