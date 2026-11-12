locals {
  blob_zone = "privatelink.blob.core.windows.net"
}

resource "azurerm_resource_group" "lab" {
  name     = "rg-${var.prefix}-network"
  location = var.location
  tags     = var.tags
}

module "hub" {
  source              = "../../modules/hub-network"
  name                = "vnet-${var.prefix}-hub"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  address_space       = var.hub_address_space
  subnets             = var.hub_subnets
  tags                = var.tags
}

module "spoke" {
  source                         = "../../modules/spoke-network"
  for_each                       = var.spokes
  name                           = "vnet-${var.prefix}-${each.key}"
  location                       = azurerm_resource_group.lab.location
  resource_group_name            = azurerm_resource_group.lab.name
  address_space                  = each.value.address_space
  workload_subnet_prefix         = each.value.workload_subnet_prefix
  private_endpoint_subnet_prefix = each.value.private_endpoint_subnet_prefix
  tags                           = var.tags
}

module "peering" {
  source              = "../../modules/vnet-peering"
  for_each            = var.spokes
  resource_group_name = azurerm_resource_group.lab.name
  hub_name            = module.hub.name
  hub_id              = module.hub.id
  spoke_name          = module.spoke[each.key].name
  spoke_id            = module.spoke[each.key].id
}

module "workload_nsg" {
  source              = "../../modules/nsg"
  for_each            = var.spokes
  name                = "nsg-${var.prefix}-${each.key}-workload"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  subnet_ids          = { workload = module.spoke[each.key].workload_subnet_id }
  rules = {
    allow-https-from-hub = {
      priority                   = 200
      direction                  = "Inbound"
      access                     = "Allow"
      protocol                   = "Tcp"
      destination_port_range     = "443"
      source_address_prefix      = var.hub_address_space
      destination_address_prefix = "*"
    }
    deny-internet-inbound = {
      priority                   = 4000
      direction                  = "Inbound"
      access                     = "Deny"
      protocol                   = "*"
      destination_port_range     = "*"
      source_address_prefix      = "Internet"
      destination_address_prefix = "*"
    }
  }
  tags = var.tags
}

module "pe_nsg" {
  source              = "../../modules/nsg"
  for_each            = var.spokes
  name                = "nsg-${var.prefix}-${each.key}-pe"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  subnet_ids          = { pe = module.spoke[each.key].private_endpoint_subnet_id }
  rules = {
    allow-https-from-vnets = {
      priority                   = 200
      direction                  = "Inbound"
      access                     = "Allow"
      protocol                   = "Tcp"
      destination_port_range     = "443"
      source_address_prefix      = "VirtualNetwork"
      destination_address_prefix = "*"
    }
  }
  tags = var.tags
}

module "blob_dns" {
  source              = "../../modules/private-dns"
  zone_name           = local.blob_zone
  resource_group_name = azurerm_resource_group.lab.name
  linked_vnet_ids = merge(
    { hub = module.hub.id },
    { for k in var.dns_linked_spokes : k => module.spoke[k].id }
  )
  tags = var.tags
}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

# Synthetic storage account reachable only through its private endpoint.
resource "azurerm_storage_account" "data" {
  name                            = "st${var.prefix}${random_string.suffix.result}"
  resource_group_name             = azurerm_resource_group.lab.name
  location                        = azurerm_resource_group.lab.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = false
  allow_nested_items_to_be_public = false
  tags                            = var.tags
}

module "blob_pe" {
  source              = "../../modules/private-endpoint"
  name                = "pe-${var.prefix}-blob"
  location            = azurerm_resource_group.lab.location
  resource_group_name = azurerm_resource_group.lab.name
  subnet_id           = module.spoke["app"].private_endpoint_subnet_id
  target_resource_id  = azurerm_storage_account.data.id
  subresource_name    = "blob"
  private_dns_zone_id = module.blob_dns.zone_id
  tags                = var.tags
}
