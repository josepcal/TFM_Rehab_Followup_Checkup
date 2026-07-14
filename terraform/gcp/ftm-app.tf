locals {
  app_db_password_secret = "${var.environment}-app-db-password"
  llm_api_key_secret     = "${var.environment}-llm-api-key"
}

# --- Artifact Registry (imágenes Docker de la app) ---
resource "google_artifact_registry_repository" "ftm" {
  location      = var.region
  repository_id = "ftm"
  format        = "DOCKER"
  project       = var.project_id
  description   = "FTM api/worker images"
}

# --- Secret Manager: valores vienen de TF_VAR_*, las VMs los leen en arranque ---
resource "google_secret_manager_secret" "app_db_password" {
  secret_id = local.app_db_password_secret
  project   = var.project_id
  replication { 
    auto {} 
  }
}
resource "google_secret_manager_secret_version" "app_db_password" {
  secret      = google_secret_manager_secret.app_db_password.id
  secret_data = var.app_db_password
}

resource "google_secret_manager_secret" "llm_api_key" {
  secret_id = local.llm_api_key_secret
  project   = var.project_id
  replication { 
    auto {} 
  }
}
resource "google_secret_manager_secret_version" "llm_api_key" {
  secret      = google_secret_manager_secret.llm_api_key.id
  secret_data = var.llm_api_key
}

# --- Permisos de lectura de secretos (least-privilege, por secreto) ---
# La VM de Postgres lee la password de la app para crear el rol ftm_app
resource "google_secret_manager_secret_iam_member" "pg_reads_appdb" {
  secret_id = google_secret_manager_secret.app_db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${module.postgresql.service_account_email}"
  project   = var.project_id
}
# La VM de la app lee la password de la app y la API key del LLM
resource "google_secret_manager_secret_iam_member" "app_reads_appdb" {
  secret_id = google_secret_manager_secret.app_db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${module.app.service_account_email}"
  project   = var.project_id
}
resource "google_secret_manager_secret_iam_member" "app_reads_llm" {
  secret_id = google_secret_manager_secret.llm_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${module.app.service_account_email}"
  project   = var.project_id
}

# --- Módulo app ---
module "app" {
  source = "./modules/app"

  project_id             = var.project_id
  region                 = var.region
  zone                   = var.zone
  environment            = var.environment
  subnet_id              = module.network.private_subnet_id
  machine_type           = var.app_machine_type
  vm_image               = var.vm_image
  ssh_user               = var.ssh_user
  ssh_public_key         = var.ssh_public_key
  postgresql_internal_ip = module.postgresql.internal_ip
  keycloak_internal_ip   = module.keycloak.internal_ip
  domain                 = var.domain
  app_database           = var.app_database
  app_db_user            = var.app_db_user
  app_db_password_secret = local.app_db_password_secret
  llm_api_key_secret     = local.llm_api_key_secret
  api_image              = var.api_image

  depends_on = [module.network, module.postgresql, module.keycloak]
}