variable "name" {
  type        = string
  description = "Hub VNet name."
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "address_space" {
  type        = string
  description = "Hub address space in CIDR notation, for example 10.0.0.0/16."
  validation {
    condition     = can(cidrhost(var.address_space, 0))
    error_message = "address_space must be a valid CIDR block."
  }
}

variable "subnets" {
  type        = map(string)
  description = "Subnet name => CIDR. Shared services live in the hub."
  default     = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}
