variable "location" {
  type    = string
  default = "centralindia"
}

variable "prefix" {
  type        = string
  description = "Short lowercase prefix used in resource names."
  default     = "hslab"
  validation {
    condition     = can(regex("^[a-z0-9]{3,8}$", var.prefix))
    error_message = "prefix must be 3-8 lowercase letters or digits."
  }
}

variable "hub_address_space" {
  type    = string
  default = "10.0.0.0/16"
}

variable "hub_subnets" {
  type = map(string)
  default = {
    "snet-shared-services" = "10.0.1.0/24"
    "snet-management"      = "10.0.2.0/24"
  }
}

variable "spokes" {
  description = "Spoke VNets keyed by short name."
  type = map(object({
    address_space                  = string
    workload_subnet_prefix         = string
    private_endpoint_subnet_prefix = string
  }))
  default = {
    app = {
      address_space                  = "10.1.0.0/16"
      workload_subnet_prefix         = "10.1.1.0/24"
      private_endpoint_subnet_prefix = "10.1.2.0/24"
    }
    data = {
      address_space                  = "10.2.0.0/16"
      workload_subnet_prefix         = "10.2.1.0/24"
      private_endpoint_subnet_prefix = "10.2.2.0/24"
    }
  }
}

variable "dns_linked_spokes" {
  type        = list(string)
  description = "Spokes linked to the privatelink.blob zone. Leaving out 'app' reproduces the DNS misconfiguration."
  default     = ["app", "data"]
}

variable "tags" {
  type = map(string)
  default = {
    project = "portfolio-hub-spoke-lab"
    owner   = "platform"
  }
}
