variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "zone" {
  description = "GCP zone"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "subnet_id" {
  description = "Self-link of the private subnet"
  type        = string
}

variable "machine_type" {
  description = "Compute Engine machine type"
  type        = string
  default     = "e2-medium"
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

variable "keycloak_admin_user" {
  description = "Keycloak admin username"
  type        = string
  default     = "admin"
}

variable "keycloak_admin_password" {
  description = "Keycloak admin password"
  type        = string
  sensitive   = true
}

variable "nginx_subnet_cidr" {
  description = "CIDR of the public (Nginx) subnet — used only for documentation/reference"
  type        = string
}

variable "postgresql_internal_ip" {
  description = "Internal IP of the PostgreSQL VM"
  type        = string
}

variable "keycloak_database" {
  description = "PostgreSQL database name for Keycloak"
  type        = string
  default     = "keycloak"
}

variable "keycloak_db_user" {
  description = "PostgreSQL user for Keycloak"
  type        = string
  default     = "keycloak"
}

variable "keycloak_db_password" {
  description = "PostgreSQL password for Keycloak user"
  type        = string
  sensitive   = true
}
