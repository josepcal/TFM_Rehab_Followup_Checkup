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
  default     = "e2-standard-2"
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

variable "postgres_password" {
  description = "PostgreSQL root (postgres) user password — set via TF_VAR_postgres_password"
  type        = string
  sensitive   = true
}

variable "keycloak_database" {
  description = "Database name for Keycloak"
  type        = string
  default     = "keycloak"
}

variable "keycloak_db_user" {
  description = "PostgreSQL user for Keycloak"
  type        = string
  default     = "keycloak"
}

variable "keycloak_db_password" {
  description = "PostgreSQL password for Keycloak user — set via TF_VAR_keycloak_db_password"
  type        = string
  sensitive   = true
}

variable "keycloak_vm_cidr" {
  description = "CIDR range of the Keycloak VM's subnet for pg_hba.conf"
  type        = string
}
