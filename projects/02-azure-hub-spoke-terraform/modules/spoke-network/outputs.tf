output "id" {
  value = azurerm_virtual_network.spoke.id
}

output "name" {
  value = azurerm_virtual_network.spoke.name
}

output "workload_subnet_id" {
  value = azurerm_subnet.workload.id
}

output "private_endpoint_subnet_id" {
  value = azurerm_subnet.private_endpoints.id
}
