# Creates both directions of a hub <-> spoke peering.
resource "azurerm_virtual_network_peering" "hub_to_spoke" {
  name                         = "peer-${var.hub_name}-to-${var.spoke_name}"
  resource_group_name          = var.resource_group_name
  virtual_network_name         = var.hub_name
  remote_virtual_network_id    = var.spoke_id
  allow_virtual_network_access = true
  allow_forwarded_traffic      = true
  allow_gateway_transit        = var.hub_has_gateway
}

resource "azurerm_virtual_network_peering" "spoke_to_hub" {
  name                         = "peer-${var.spoke_name}-to-${var.hub_name}"
  resource_group_name          = var.resource_group_name
  virtual_network_name         = var.spoke_name
  remote_virtual_network_id    = var.hub_id
  allow_virtual_network_access = true
  allow_forwarded_traffic      = true
  use_remote_gateways          = var.hub_has_gateway
}
