output "zone_id" {
  value = azurerm_private_dns_zone.this.id
}

output "zone_name" {
  value = azurerm_private_dns_zone.this.name
}

output "linked_vnets" {
  value = keys(azurerm_private_dns_zone_virtual_network_link.this)
}
