#!/usr/bin/env bash
# Verifies private DNS from inside the app spoke using a small test VM.
# Billable: one Standard_B1s VM while it exists. The script deletes it at the end.
set -euo pipefail
cd "$(dirname "$0")/../envs/lab"
RG=$(terraform output -raw resource_group_name)
FQDN=$(terraform output -raw storage_blob_fqdn)
PREFIX=${PREFIX:-hslab}
SUBNET_ID=$(az network vnet subnet show -g "$RG" --vnet-name "vnet-$PREFIX-app" -n snet-workload --query id -o tsv)

az vm create -g "$RG" -n vm-dnscheck --image Ubuntu2204 --size Standard_B1s \
  --subnet "$SUBNET_ID" --public-ip-address "" --nsg "" \
  --admin-username azureuser --generate-ssh-keys -o none
echo "Zone links:"
az network private-dns link vnet list -g "$RG" -z privatelink.blob.core.windows.net \
  --query "[].{link:name, vnet:virtualNetwork.id}" -o table
echo "nslookup from the app spoke:"
az vm run-command invoke -g "$RG" -n vm-dnscheck --command-id RunShellScript \
  --scripts "nslookup $FQDN" --query "value[0].message" -o tsv
az vm delete -g "$RG" -n vm-dnscheck --yes -o none
