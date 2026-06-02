variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "zone" {
  description = "GCP zone"
  type        = string
}

variable "region" {
  description = "GCP region (needed for static IP reservation)"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "subnet_id" {
  description = "Self-link of the public subnet"
  type        = string
}

variable "machine_type" {
  description = "Compute Engine machine type"
  type        = string
  default     = "e2-small"
}

variable "vm_image" {
  description = "Boot disk image"
  type        = string
  default     = "debian-cloud/debian-12"
}

variable "ssh_user" {
  description = "SSH username"
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key content"
  type        = string
}

variable "domain" {
  description = "Domain name for Nginx vhost and SSL certificate"
  type        = string
}

variable "ssl_cert_email" {
  description = "Email for Let's Encrypt certificate registration"
  type        = string
}

variable "keycloak_internal_ip" {
  description = "Internal IP of the Keycloak VM for upstream proxy config"
  type        = string
}
