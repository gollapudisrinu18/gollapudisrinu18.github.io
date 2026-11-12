# Terraform native tests with a mocked azurerm provider.
# Run from envs/lab:  terraform init -backend=false && terraform test
mock_provider "azurerm" {}
mock_provider "random" {}

run "default_links_every_spoke" {
  command = plan

  assert {
    condition     = length(module.blob_dns.linked_vnets) == 3
    error_message = "Expected hub, app and data to be linked to the blob zone."
  }

  assert {
    condition     = contains(module.blob_dns.linked_vnets, "app")
    error_message = "The app spoke must be linked to the privatelink.blob zone."
  }

  assert {
    condition     = azurerm_storage_account.data.public_network_access_enabled == false
    error_message = "Storage must not allow public network access."
  }
}

run "misconfig_drops_app_link" {
  command = plan

  variables {
    dns_linked_spokes = ["data"]
  }

  assert {
    condition     = !contains(module.blob_dns.linked_vnets, "app")
    error_message = "Misconfiguration scenario should leave the app spoke unlinked."
  }
}

run "rejects_bad_prefix" {
  command = plan

  variables {
    prefix = "Bad_Prefix"
  }

  expect_failures = [var.prefix]
}
