variable "resource_group_name" {
  type = string
}

variable "hub_name" {
  type = string
}

variable "hub_id" {
  type = string
}

variable "spoke_name" {
  type = string
}

variable "spoke_id" {
  type = string
}

variable "hub_has_gateway" {
  type        = bool
  description = "Set true only when the hub has a VPN/ExpressRoute gateway."
  default     = false
}
