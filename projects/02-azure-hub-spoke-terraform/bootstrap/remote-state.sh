#!/usr/bin/env bash
# Creates the storage account that holds Terraform remote state and writes
# envs/lab/backend.hcl. Uses Entra ID auth (no storage keys in config).
set -euo pipefail
LOCATION=${LOCATION:-centralindia}
RG=${RG:-rg-tfstate-lab}
SA=${SA:-sttfstate$RANDOM$RANDOM}
CONTAINER=tfstate
HERE=$(cd "$(dirname "$0")" && pwd)

az group create -n "$RG" -l "$LOCATION" -o none
az storage account create -g "$RG" -n "$SA" -l "$LOCATION" \
  --sku Standard_LRS --min-tls-version TLS1_2 \
  --allow-blob-public-access false -o none
az storage account blob-service-properties update -g "$RG" --account-name "$SA" \
  --enable-versioning true --enable-delete-retention true --delete-retention-days 7 -o none

USER_ID=$(az ad signed-in-user show --query id -o tsv)
SA_ID=$(az storage account show -g "$RG" -n "$SA" --query id -o tsv)
az role assignment create --assignee "$USER_ID" \
  --role "Storage Blob Data Contributor" --scope "$SA_ID" -o none
sleep 20   # role assignment propagation
az storage container create --account-name "$SA" -n "$CONTAINER" --auth-mode login -o none

cat > "$HERE/../envs/lab/backend.hcl" <<HCL
resource_group_name  = "$RG"
storage_account_name = "$SA"
container_name       = "$CONTAINER"
key                  = "hub-spoke-lab.tfstate"
use_azuread_auth     = true
HCL
echo "Remote state ready: $SA/$CONTAINER. Wrote envs/lab/backend.hcl"
