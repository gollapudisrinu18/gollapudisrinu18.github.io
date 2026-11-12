# Remote state in Azure Storage. Values are supplied at init time:
#   terraform init -backend-config=backend.hcl
# Use `terraform init -backend=false` for validation without Azure access.
terraform {
  backend "azurerm" {}
}
