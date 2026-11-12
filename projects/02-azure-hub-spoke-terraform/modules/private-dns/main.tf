resource "azurerm_private_dns_zone" "this" {
  name                = var.zone_name
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

# One link per VNet that must resolve records in this zone. A VNet without a
# link falls back to public DNS for the same name - the misconfiguration
# reproduced in this lab.
resource "azurerm_private_dns_zone_virtual_network_link" "this" {
  for_each              = var.linked_vnet_ids
  name                  = "link-${each.key}"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.this.name
  virtual_network_id    = each.value
  registration_enabled  = false
  tags                  = var.tags
}
