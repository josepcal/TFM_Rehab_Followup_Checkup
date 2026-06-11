# Terraform — GCP VM with PostgreSQL, for Alembic from your local PC

Provisions a GCP Compute Engine VM running PostgreSQL, exposed over a static
external IP so you can run [Alembic](https://alembic.sqlalchemy.org/) migrations
**from your local machine** against it.

## What it creates

| Resource | Detail |
|---|---|
| VM machine type | `e2-medium` — 2 vCPU / **4 GB RAM** |
| Boot disk | **50 GB** `pd-ssd` (SSD) |
| External IP | Reserved **static** address |
| Firewall | SSH (22) + PostgreSQL (5432) |
| Software | PostgreSQL server; creates `db_name` owned by `db_user` |

Alembic, Python, and your migration code all live on your **local PC** — the VM
only runs the database.

## Prerequisites

- Terraform >= 1.5 and `gcloud` authenticated (`gcloud auth application-default login`)
- A GCP project with the Compute Engine API enabled
- An SSH key pair (`ssh-keygen -t ed25519`)
- Locally: `pip install alembic sqlalchemy psycopg2-binary`

## Deploy

```bash
cp terraform.tfvars.example terraform.tfvars
# edit: project_id, ssh_public_key_path, db_password
# IMPORTANT: set allowed_ssh_cidr and allowed_db_cidr to your IP (curl ifconfig.me)

export TF_VAR_db_password='a-strong-secret'   # keeps the password out of the file

terraform init
terraform apply
```

`terraform output database_url` shows the connection string (password masked).

## Run Alembic locally

```bash
# Point Alembic at the remote DB via the external IP from the outputs:
export DATABASE_URL="postgresql+psycopg2://appuser:YOUR_PASSWORD@<external-ip>:5432/appdb"

alembic init migrations
# in migrations/env.py, read the URL from the env var, e.g.:
#   config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

alembic revision --autogenerate -m "init"
alembic upgrade head
```

Quick connectivity check before migrating:

```bash
psql "$DATABASE_URL"
```

## Security notes

- **Lock down 5432.** The defaults leave `allowed_db_cidr = 0.0.0.0/0`, which
  exposes your database to the entire internet. Set it to `YOUR.IP/32`. If your
  ISP gives you a dynamic IP, you'll need to update it when it changes.
- **DB password in metadata:** the password is rendered into the VM startup
  script and is therefore readable in instance metadata by anyone with project
  access. Acceptable for a throwaway box; use Secret Manager for anything real.
- Same applies to `allowed_ssh_cidr` for port 22.

## Cost note

`pd-ssd` is pricier than `pd-balanced`. If SSD speed isn't essential, change
`type = "pd-ssd"` to `"pd-balanced"` in `main.tf`.

## Teardown

```bash
terraform destroy
```
