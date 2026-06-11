variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region (EU for RGPD)"
  type        = string
}

variable "zone" {
  description = "GCP zone"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, prod)"
  type        = string
}

variable "subnet_id" {
  description = "Private subnet ID (same as Keycloak/Postgres)"
  type        = string
}

variable "machine_type" {
  description = "Machine type for the app VM (api + worker)"
  type        = string
  default     = "e2-medium"
}

variable "vm_image" {
  description = "Boot disk image"
  type        = string
}

variable "ssh_user" {
  description = "SSH username for VM access"
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key content"
  type        = string
}

variable "postgresql_internal_ip" {
  description = "Internal IP of the PostgreSQL VM"
  type        = string
}

variable "keycloak_internal_ip" {
  description = "Internal IP of the Keycloak VM (for JWKS fetch)"
  type        = string
}

variable "domain" {
  description = "Public domain (used to build the expected token issuer)"
  type        = string
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

variable "app_db_password_secret" {
  description = "Secret Manager secret NAME holding the app DB password"
  type        = string
}

variable "llm_api_key_secret" {
  description = "Secret Manager secret NAME holding the LLM API key"
  type        = string
}

variable "api_image" {
  description = "Full Artifact Registry image reference for the FTM api/worker (e.g. europe-west1-docker.pkg.dev/PROJECT/ftm/ftm-api:latest)"
  type        = string
}
