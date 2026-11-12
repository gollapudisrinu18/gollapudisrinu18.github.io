variable "zone_name" {
  type        = string
  description = "Private DNS zone, for example privatelink.blob.core.windows.net."
}

variable "resource_group_name" {
  type = string
}

variable "linked_vnet_ids" {
  type        = map(string)
  description = "Map of VNet label => VNet ID to link to the zone."
}

variable "tags" {
  type    = map(string)
  default = {}
}
