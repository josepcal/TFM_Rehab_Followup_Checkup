variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west1"      # UE (Bélgica), RGPD; más barata que Madrid
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "europe-west1-b"
}

variable "environment" {
  description = "Deployment environment (dev, prod)"
  type        = string
}

variable "domain" {
  description = "Domain name for Nginx SSL/vhost config"
  type        = string
}

variable "ssl_cert_email" {
  description = "Email address for Let's Encrypt certificate"
  type        = string
}

variable "keycloak_admin_user" {
  description = "Keycloak admin username"
  type        = string
  default     = "admin"
}

variable "keycloak_admin_password" {
  description = "Keycloak admin password — set via TF_VAR_keycloak_admin_password"
  type        = string
  sensitive   = true
}

variable "ssh_public_key" {
  description = "SSH public key content for VM access (e.g. 'ssh-rsa AAAA...')"
  type        = string
}

variable "ssh_user" {
  description = "SSH username for VM access"
  type        = string
  default     = "gcpuser"
}

variable "nginx_machine_type" {
  description = "Machine type for the Nginx VM"
  type        = string
  default     = "e2-small"
}

variable "keycloak_machine_type" {
  description = "Machine type for the Keycloak VM"
  type        = string
  default     = "e2-medium"
}

variable "vm_image" {
  description = "Boot disk image for all VMs"
  type        = string
  default     = "debian-cloud/debian-12"
}

variable "postgresql_machine_type" {
  description = "Machine type for the PostgreSQL VM"
  type        = string
  default     = "e2-standard-2"
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

variable "app_machine_type" {
  description = "Machine type for the app VM"
  type        = string
  default     = "e2-medium"
}

variable "app_database" {
  description = "Application database name"
  type        = string
  default     = "ftm"
}

variable "app_db_user" {
  description = "Application DB login role (non-superuser, RLS-bound)"
  type        = string
  default     = "ftm_app"
}

variable "app_db_password" {
  description = "Password for the app DB role — set via TF_VAR_app_db_password"
  type        = string
  sensitive   = true
}

variable "llm_api_key" {
  description = "LLM provider API key — set via TF_VAR_llm_api_key"
  type        = string
  sensitive   = true
}

variable "api_image" {
  description = "Artifact Registry image ref for the FTM api/worker"
  type        = string
}