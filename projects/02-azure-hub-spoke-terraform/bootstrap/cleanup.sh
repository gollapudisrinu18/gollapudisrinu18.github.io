#!/usr/bin/env bash
# Destroys the lab, then deletes the state resource group.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
(cd "$HERE/../envs/lab" && terraform destroy -auto-approve)
az group delete -n "${RG:-rg-tfstate-lab}" --yes --no-wait
echo "Lab destroyed; state resource group deletion started."
