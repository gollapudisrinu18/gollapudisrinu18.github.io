#!/usr/bin/env bash
# Deletes the lab resource group and everything in it (ACR, AKS, node pools).
set -euo pipefail
RG=${RG:-rg-aks-delivery-lab}
az group delete -n "$RG" --yes --no-wait
echo "Deletion of $RG started. Check with: az group exists -n $RG"
