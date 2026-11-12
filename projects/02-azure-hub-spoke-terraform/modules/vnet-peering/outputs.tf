output "peering_ids" {
  value = [
    azurerm_virtual_network_peering.hub_to_spoke.id,
    azurerm_virtual_network_peering.spoke_to_hub.id,
  ]
}
