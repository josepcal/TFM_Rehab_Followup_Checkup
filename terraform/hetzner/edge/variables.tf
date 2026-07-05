variable "hcloud_token" {
  description = "Hetzner Cloud API token — set via TF_VAR_hcloud_token, never commit."
  type        = string
  sensitive   = true
}

variable "persistent_state_path" {
  description = "Path to the persistent layer's local state file."
  type        = string
  default     = "../persistent/terraform.tfstate"
}

variable "server_type" {
  description = "Edge VM size — nginx reverse proxy is lightweight."
  type        = string
  default     = "cpx22" # 2 vCPU / 4GB shared, always-on
}

variable "image" {
  description = "Base image for the edge VM."
  type        = string
  default     = "ubuntu-24.04"
}

variable "edge_private_ip" {
  description = "Static private IP for the edge VM inside the subnet."
  type        = string
  default     = "10.0.1.10"
}

variable "ssh_public_key" {
  description = "SSH public key content for edge VM access."
  type        = string
}

variable "ssh_key_name" {
  description = "Name for the uploaded SSH key in Hetzner."
  type        = string
  default     = "ftm-prod-edge"
}

variable "operator_ssh_cidrs" {
  description = "CIDRs allowed to SSH the edge VM (restrict to operator IP)."
  type        = list(string)
}

variable "domain" {
  description = "Domain served by nginx (for certbot/TLS)."
  type        = string
}

variable "ssl_cert_email" {
  description = "Email for Let's Encrypt registration."
  type        = string
}

variable "labels" {
  description = "Common labels for edge resources."
  type        = map(string)
  default = {
    project     = "ftm"
    environment = "prod"
    layer       = "edge"
  }
}
