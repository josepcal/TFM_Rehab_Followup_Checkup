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
  description = "Stack VM size (runs keycloak + 2x postgres + minio + bff + worker)."
  type        = string
  default     = "cpx32" # 4 vCPU / 8GB shared
}

variable "image" {
  description = "Base image for the stack VM."
  type        = string
  default     = "ubuntu-24.04"
}

variable "stack_private_ip" {
  description = "Static private IP for the stack VM inside the subnet."
  type        = string
  default     = "10.0.1.20"
}

variable "edge_private_ip" {
  description = "Edge VM private IP — the only source allowed to reach the stack."
  type        = string
  default     = "10.0.1.10"
}

variable "subnet_gateway" {
  description = "Gateway IP for the private NETWORK (Hetzner assigns the first host of the whole network range, e.g. 10.0.0.1 for 10.0.0.0/16 — NOT the subnet's first host). The no-public-IP stack uses this as its default route; the Hetzner network route then forwards to the edge NAT."
  type        = string
  default     = "10.0.0.1"
}

variable "ssh_public_key" {
  description = "SSH public key content for stack VM access."
  type        = string
}

variable "ssh_key_name" {
  description = "Name for the uploaded SSH key in Hetzner."
  type        = string
  default     = "ftm-prod-stack"
}

variable "age_private_key" {
  description = "age private key used by cloud-init to decrypt secrets.sops.yaml. Set via TF_VAR_age_private_key; never commit. Lands only in server metadata."
  type        = string
  sensitive   = true
}

variable "repo_url" {
  description = "Git URL the stack VM clones to get deploy/ (compose + encrypted secrets)."
  type        = string
}

variable "repo_ref" {
  description = "Git ref (branch/tag/commit) to check out on the stack VM."
  type        = string
  default     = "main"
}

variable "domain" {
  description = "Domain (for KC_HOSTNAME rendered into the stack .env)."
  type        = string
}

variable "labels" {
  description = "Common labels for stack resources."
  type        = map(string)
  default = {
    project     = "ftm"
    environment = "prod"
    layer       = "stack"
  }
}
