#!/usr/bin/env bash
# DR drill on Azure Blob Storage with point-in-time restore (PITR).
# Billable: one Standard_LRS storage account with versioning, change feed and soft delete.
set -euo pipefail
RG=${RG:-rg-dr-drill-lab}; LOC=${LOC:-centralindia}
SA=${SA:-stdrdrill$RANDOM}; C=orders
cd "$(dirname "$0")/.."

az group create -n "$RG" -l "$LOC" -o none
az storage account create -g "$RG" -n "$SA" -l "$LOC" --sku Standard_LRS --kind StorageV2 \
  --min-tls-version TLS1_2 --allow-blob-public-access false -o none
# PITR requires versioning, change feed and blob soft delete (retention > restore days)
az storage account blob-service-properties update -g "$RG" -n "$SA" \
  --enable-versioning true --enable-change-feed true \
  --enable-delete-retention true --delete-retention-days 14 \
  --enable-restore-policy true --restore-days 7 -o none
az role assignment create --assignee "$(az ad signed-in-user show --query id -o tsv)" \
  --role "Storage Blob Data Contributor" --scope "$(az storage account show -g "$RG" -n "$SA" --query id -o tsv)" -o none
sleep 30

python dr/make_manifest.py /tmp/drill-data
az storage container create --account-name "$SA" -n "$C" --auth-mode login -o none
az storage blob upload-batch --account-name "$SA" -d "$C" -s /tmp/drill-data --auth-mode login -o none
sleep 60                                         # restore point must be after the upload
RESTORE_POINT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sleep 30
echo "Restore point: $RESTORE_POINT"

echo "--- Incident: deleting all blobs"
START=$(date +%s)
az storage blob delete-batch --account-name "$SA" -s "$C" --auth-mode login -o none
echo "Blobs left: $(az storage blob list --account-name "$SA" -c "$C" --auth-mode login --query 'length(@)' -o tsv)"

echo "--- Restore to $RESTORE_POINT"
az storage blob restore -g "$RG" -n "$SA" --time-to-restore "$RESTORE_POINT" -o none
rm -rf /tmp/drill-restored
az storage blob download-batch --account-name "$SA" -s "$C" -d /tmp/drill-restored --auth-mode login -o none
python dr/verify_dir.py --dir /tmp/drill-restored --manifest /tmp/drill-data.manifest.json
echo "Measured restore time (delete -> verified): $(( $(date +%s) - START )) s"
echo "Clean up with: az group delete -n $RG --yes --no-wait"
