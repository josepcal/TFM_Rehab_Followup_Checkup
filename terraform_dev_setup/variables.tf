variable "project_id" {
  description = "Your GCP project ID."
  type        = string
}

variable "region" {
  description = "GCP region. europe-southwest1 = Madrid (low latency from Spain)."
  type        = string
  default     = "europe-southwest1"
}

variable "zone" {
  description = "GCP zone."
  type        = string
  default     = "europe-southwest1-a"
}

variable "vm_name" {
  description = "Name of the VM (and prefix for related resources)."
  type        = string
  default     = "alembic-vm"
}

variable "machine_type" {
  description = "e2-medium = 2 vCPU / 4 GB RAM."
  type        = string
  default     = "e2-medium"
}

variable "disk_size_gb" {
  description = "Boot disk size in GB."
  type        = number
  default     = 50
}

variable "image" {
  description = "Boot image. Debian 12 family auto-resolves to the latest build."
  type        = string
  default     = "debian-cloud/debian-12"
}

variable "ssh_user" {
  description = "Linux user created for SSH access."
  type        = string
  default     = "alembic"
}

variable "ssh_public_key_path" {
  description = "Path to your SSH PUBLIC key, e.g. ~/.ssh/id_ed25519.pub"
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed to SSH (port 22). LOCK THIS DOWN to your IP, e.g. 203.0.113.4/32."
  type        = string
  default     = "0.0.0.0/0"
}

variable "enable_postgres" {
  description = "Installs a local PostgreSQL server on the VM and creates the app DB + user."
  type        = bool
  default     = true
}

variable "db_name" {
  description = "Database created for Alembic to migrate against."
  type        = string
  default     = "appdb"
}

variable "db_user" {
  description = "Application DB user that owns db_name."
  type        = string
  default     = "appuser"
}

variable "db_password" {
  description = "Password for db_user. Set via terraform.tfvars or TF_VAR_db_password (do not commit)."
  type        = string
  sensitive   = true
}

variable "db_user_admin" {
  description = "Create db_user with SUPERUSER/CREATEDB/CREATEROLE. Needed to replay full-schema (pg_dump) baselines. Dev convenience — do not use in production."
  type        = bool
  default     = true
}

variable "expose_postgres" {
  description = "Open port 5432 so Alembic on your local PC can reach the DB over the external IP."
  type        = bool
  default     = true
}

variable "allowed_db_cidr" {
  description = "CIDR allowed to reach PostgreSQL (5432). LOCK THIS DOWN to your PC's IP, e.g. 203.0.113.4/32."
  type        = string
  default     = "0.0.0.0/0"
}
