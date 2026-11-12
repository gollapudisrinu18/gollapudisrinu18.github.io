#!/usr/bin/env bash
# Billable: Function App (Flex Consumption), storage account, Application Insights.
set -euo pipefail
RG=${RG:-rg-func-orders-lab}; LOC=${LOC:-centralindia}
SA=${SA:-stfuncorders$RANDOM}; APP=${APP:-func-orders-$RANDOM}
az group create -n "$RG" -l "$LOC" -o none
az storage account create -g "$RG" -n "$SA" -l "$LOC" --sku Standard_LRS -o none
az functionapp create -g "$RG" -n "$APP" --storage-account "$SA" \
  --flexconsumption-location "$LOC" --runtime python --runtime-version 3.11 -o none
cd "$(dirname "$0")/../src"
func azure functionapp publish "$APP"
echo "Deployed $APP. Send messages with:"
echo "  AZURE_STORAGE_CONNECTION_STRING=\$(az storage account show-connection-string -g $RG -n $SA -o tsv) bash scripts/send-test-messages.sh"
