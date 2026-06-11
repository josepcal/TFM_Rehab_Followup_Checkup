# Copy to terraform.tfvars and fill in your values.
# Dev environment — non-sensitive values only
# Set sensitive vars via environment:
#   export TF_VAR_db_password="..."


project_id              = "terraform-project-496514"
region                  = "europe-west1"
zone                    = "europe-west1-b"

ssh_public_key_path = "~/.ssh/id_ed25519.pub"

# Strongly recommended: restrict SSH to your own IP instead of the whole internet.
allowed_ssh_cidr = "0.0.0.0/0" # e.g. "203.0.113.4/32"

# Local PostgreSQL on the VM.
enable_postgres = true
db_name         = "appdb"
db_user         = "appuser"
db_password     = "thisIsMyAppDBPassword123" # better: export TF_VAR_db_password=...

# Create appuser as a DB admin (superuser). Lets full-schema baselines that
# contain CREATE ROLE / OWNER / EXTENSION replay cleanly. Dev only.
db_user_admin = true


# Keep Postgres local-only (Alembic runs on the VM via localhost).
# Set to true only if a remote SQL client must reach the DB.
expose_postgres = true
# allowed_db_cidr = "203.0.113.4/32"
