#!/usr/bin/env bash
# Creates the billable Azure resources used by this lab: a resource group,
# an Azure Container Registry (Basic) and a small AKS cluster attached to it.
# Run `scripts/azure-cleanup.sh` afterwards to delete everything.
set -euo pipefail
LOCATION=${LOCATION:-centralindia}
RG=${RG:-rg-aks-delivery-lab}
ACR=${ACR:-acraksdelivery$RANDOM}     # must be globally unique, lowercase
AKS=${AKS:-aks-delivery-lab}

az group create -n "$RG" -l "$LOCATION" -o none
az acr create -g "$RG" -n "$ACR" --sku Basic -o none
az aks create -g "$RG" -n "$AKS" \
  --node-count 2 --node-vm-size Standard_B2s \
  --enable-managed-identity --attach-acr "$ACR" \
  --generate-ssh-keys -o none
for ns in orders-dev orders-qa orders-prod; do
  az aks command invoke -g "$RG" -n "$AKS" --command "kubectl create namespace $ns" -o none || true
done
echo "Created RG=$RG ACR=$ACR AKS=$AKS"
echo "Set these in the 'aks-delivery' variable group: acrName=$ACR aksResourceGroup=$RG aksClusterName=$AKS"
