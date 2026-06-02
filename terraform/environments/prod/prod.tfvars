# Prod environment — non-sensitive values only
# Set sensitive vars via environment:
#   export TF_VAR_keycloak_admin_password="..."
#   export TF_VAR_postgres_password="..."
#   export TF_VAR_keycloak_db_password="..."

project_id              = "your-gcp-project-id"
region = "europe-west1"
zone   = "europe-west1-b"
environment             = "prod"
domain                  = "auth.example.com"
ssl_cert_email          = "ops@example.com"
keycloak_admin_user     = "admin"
keycloak_database       = "keycloak"
keycloak_db_user        = "keycloak"
nginx_machine_type      = "e2-small"
keycloak_machine_type   = "e2-standard-2"
postgresql_machine_type = "e2-standard-4"
vm_image                = "debian-cloud/debian-12"
ssh_user                = "gcpuser"
ssh_public_key          = "ssh-rsa AAAA... your-public-key-here"

app_machine_type = "e2-medium"
app_database     = "ftm"
app_db_user      = "ftm_app"

# Imagen que construirás y subirás a Artifact Registry (ver paso 8)
api_image = "europe-west1-docker.pkg.dev/TU_PROJECT/ftm/ftm-api:latest"

# Secretos: se pasan por TF_VAR_* (no se commitean) y aterrizan en Secret Manager
# export TF_VAR_app_db_password=...
# export TF_VAR_llm_api_key=...