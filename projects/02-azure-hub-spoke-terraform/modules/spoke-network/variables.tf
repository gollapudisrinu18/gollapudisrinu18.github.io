variable "name" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "address_space" {
  type = string
  validation {
    condition     = can(cidrhost(var.address_space, 0))
    error_message = "address_space must be a valid CIDR block."
  }
}

variable "workload_subnet_prefix" {
  type = string
}

variable "private_endpoint_subnet_prefix" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
