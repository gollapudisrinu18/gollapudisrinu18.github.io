output "id" {
  value = azurerm_virtual_network.hub.id
}

output "name" {
  value = azurerm_virtual_network.hub.name
}

output "subnet_ids" {
  value = { for k, s in azurerm_subnet.this : k => s.id }
}
