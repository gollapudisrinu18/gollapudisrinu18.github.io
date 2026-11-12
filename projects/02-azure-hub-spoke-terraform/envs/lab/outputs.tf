output "resource_group_name" {
  value = azurerm_resource_group.lab.name
}

output "storage_blob_fqdn" {
  value = "${azurerm_storage_account.data.name}.blob.core.windows.net"
}

output "blob_private_ip" {
  value = module.blob_pe.private_ip
}

# Input for tools/dns_check.py: which VNets are linked to which zones and
# which private records exist.
output "dns_model" {
  value = {
    vnets = concat(["hub"], keys(var.spokes))
    zones = {
      (module.blob_dns.zone_name) = {
        linked_vnets = module.blob_dns.linked_vnets
        records = {
          (azurerm_storage_account.data.name) = module.blob_pe.private_ip
        }
      }
    }
    public_cnames = {
      "${azurerm_storage_account.data.name}.blob.core.windows.net" = "${azurerm_storage_account.data.name}.${module.blob_dns.zone_name}"
    }
  }
}
