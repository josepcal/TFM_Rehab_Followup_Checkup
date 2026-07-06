variable "hcloud_token" {
  description = "Hetzner Cloud API token — set via TF_VAR_hcloud_token, never commit."
  type        = string
  sensitive   = true
}

variable "location" {
  description = "Hetzner location for the data volume (zone-bound). The stack VM MUST live here to attach it."
  type        = string
  default     = "nbg1" # Nürnberg — EU (Germany), GDPR data residency
}

variable "network_zone" {
  description = "Hetzner network zone for the private subnet."
  type        = string
  default     = "eu-central"
}

variable "network_ip_range" {
  description = "IP range of the whole private network (RFC1918)."
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_ip_range" {
  description = "IP range of the private subnet where edge + stack VMs live."
  type        = string
  default     = "10.0.1.0/24"
}

variable "edge_private_ip" {
  description = "Private IP of the always-on edge VM. Default route (NAT gateway) for the no-public-IP stack points here so the stack reaches the internet through the edge."
  type        = string
  default     = "10.0.1.10"
}

variable "volume_size" {
  description = "Size of the persistent data volume in GB (Postgres + MinIO objects). Min 10."
  type        = number
  default     = 20
}

variable "domain" {
  description = "Domain name whose A record points at the floating IP."
  type        = string
}

variable "dns_zone_id" {
  description = "Hetzner DNS zone ID for the domain (managed outside hcloud provider)."
  type        = string
  default     = ""
}

variable "labels" {
  description = "Common labels applied to all persistent resources."
  type        = map(string)
  default = {
    project     = "ftm"
    environment = "prod"
    layer       = "persistent"
  }
}
