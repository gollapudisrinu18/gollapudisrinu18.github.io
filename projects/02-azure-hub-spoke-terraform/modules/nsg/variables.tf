variable "name" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "subnet_ids" {
  type        = map(string)
  description = "Map of label => subnet ID to associate with this NSG. Keys must be known at plan time."
  default     = {}
}

variable "rules" {
  type = map(object({
    priority                   = number
    direction                  = string
    access                     = string
    protocol                   = string
    destination_port_range     = string
    source_address_prefix      = string
    destination_address_prefix = string
  }))
  default = {}

  validation {
    condition     = alltrue([for r in values(var.rules) : r.priority >= 100 && r.priority <= 4096])
    error_message = "NSG rule priority must be between 100 and 4096."
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}
