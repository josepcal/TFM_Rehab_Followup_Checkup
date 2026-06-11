resource "google_service_account" "app" {
  account_id   = "${var.environment}-app-sa"
  display_name = "FTM App VM Service Account (${var.environment})"
  project      = var.project_id
}

resource "google_project_iam_member" "app_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.app.email}"
}

resource "google_project_iam_member" "app_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.app.email}"
}

# Pull the api/worker image from Artifact Registry
resource "google_project_iam_member" "app_artifactregistry" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.app.email}"
}

# -----------------------------------------------------------------------------
# Object storage for recordings (WAV) — private, EU region, signed URLs only
# -----------------------------------------------------------------------------
resource "google_storage_bucket" "recordings" {
  name     = "${var.project_id}-${var.environment}-ftm-recordings"
  project  = var.project_id
  location = var.region

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.environment == "prod" ? false : true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition { age = 365 } # retención básica; ajústala a tu política clínica
    action { type = "Delete" }
  }

  labels = {
    environment = var.environment
    project     = "ftm"
    role        = "recordings"
  }
}

# The app VM can read/write/sign objects in the recordings bucket
resource "google_storage_bucket_iam_member" "app_recordings" {
  bucket = google_storage_bucket.recordings.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.app.email}"
}

# -----------------------------------------------------------------------------
# App VM (api + worker as Docker containers via systemd)
# -----------------------------------------------------------------------------
resource "google_compute_instance" "app" {
  name         = "${var.environment}-app"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  tags = ["app"]

  labels = {
    environment = var.environment
    project     = "ftm"
    role        = "app"
  }

  boot_disk {
    initialize_params {
      image = var.vm_image
      size  = 20
      type  = "pd-balanced" # más barato que pd-ssd para la VM de app
    }
  }

  network_interface {
    subnetwork = var.subnet_id
    # Sin access_config = sin IP externa (subred privada; sale por Cloud NAT)
  }

  metadata = {
    ssh-keys               = "${var.ssh_user}:${var.ssh_public_key}"
    startup-script         = local.startup_script
    block-project-ssh-keys = "true"
  }

  service_account {
    email  = google_service_account.app.email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }
}

locals {
  startup_script = <<-SCRIPT
    #!/bin/bash
    set -euo pipefail

    # Docker
    apt-get update -y
    apt-get install -y docker.io
    systemctl enable docker
    systemctl start docker

    # Autenticar Docker contra Artifact Registry usando la SA de la VM
    gcloud auth configure-docker ${var.region}-docker.pkg.dev --quiet

    # Leer secretos de Secret Manager (NO quedan en la metadata de la instancia)
    APP_DB_PASSWORD=$(gcloud secrets versions access latest --secret="${var.app_db_password_secret}")
    LLM_API_KEY=$(gcloud secrets versions access latest --secret="${var.llm_api_key_secret}")

    # Fichero de entorno (solo root)
    mkdir -p /etc/ftm
    cat > /etc/ftm/app.env <<EOF
    DATABASE_URL=postgresql://${var.app_db_user}:$${APP_DB_PASSWORD}@${var.postgresql_internal_ip}:5432/${var.app_database}
    KEYCLOAK_ISSUER=https://${var.domain}/realms/ftm
    KEYCLOAK_JWKS_URL=http://${var.keycloak_internal_ip}:8080/realms/ftm/protocol/openid-connect/certs
    WAV_BUCKET=${google_storage_bucket.recordings.name}
    LLM_API_KEY=$${LLM_API_KEY}
    APP_ENV=${var.environment}
    EOF
    chmod 600 /etc/ftm/app.env

    # --- API ---
    cat > /etc/systemd/system/ftm-api.service <<UNIT
    [Unit]
    Description=FTM API
    After=docker.service
    Requires=docker.service

    [Service]
    Restart=always
    ExecStartPre=-/usr/bin/docker stop ftm-api
    ExecStartPre=-/usr/bin/docker rm ftm-api
    ExecStartPre=/usr/bin/docker pull ${var.api_image}
    ExecStart=/usr/bin/docker run --rm --name ftm-api \
      -p 8000:8000 \
      --env-file /etc/ftm/app.env \
      ${var.api_image}

    [Install]
    WantedBy=multi-user.target
    UNIT

    # --- Worker (misma imagen, distinto comando) ---
    cat > /etc/systemd/system/ftm-worker.service <<UNIT
    [Unit]
    Description=FTM Worker
    After=docker.service
    Requires=docker.service

    [Service]
    Restart=always
    ExecStartPre=-/usr/bin/docker stop ftm-worker
    ExecStartPre=-/usr/bin/docker rm ftm-worker
    ExecStart=/usr/bin/docker run --rm --name ftm-worker \
      --env-file /etc/ftm/app.env \
      ${var.api_image} python -m app.worker

    [Install]
    WantedBy=multi-user.target
    UNIT

    systemctl daemon-reload
    systemctl enable ftm-api ftm-worker
    systemctl start ftm-api ftm-worker
  SCRIPT
}
