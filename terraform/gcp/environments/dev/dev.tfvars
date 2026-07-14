# Dev environment — non-sensitive values only
# Set sensitive vars via environment:
#   export TF_VAR_keycloak_admin_password="..."
#   export TF_VAR_postgres_password="..."
#   export TF_VAR_keycloak_db_password="..."

project_id              = "terraform-project-496514"
region                  = "europe-west1"
zone                    = "europe-west1-b"
environment             = "dev"
domain                  = "josepcalmyfirstclaudeproject.duckdns.org"
ssl_cert_email          = "joseapelaezc@gmail.com"
keycloak_admin_user     = "admin"
keycloak_database       = "keycloak"
keycloak_db_user        = "keycloak"
nginx_machine_type      = "e2-small"
keycloak_machine_type   = "e2-medium"
postgresql_machine_type = "e2-standard-2"
vm_image                = "debian-cloud/debian-12"
ssh_user                = "joseapelaezc@gmail.com"
ssh_public_key          = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKEuVAx44Lmhh8NDe+FAgYJ6Z5OA9OtwxVbmgzKcC9SY joseapelaezc@gmail.com"

app_machine_type = "e2-medium"
app_database     = "ftm"
app_db_user      = "ftm_app"

# Imagen que construirás y subirás a Artifact Registry (ver paso 8)
api_image = "europe-west1-docker.pkg.dev/TU_PROJECT/ftm/ftm-api:latest"