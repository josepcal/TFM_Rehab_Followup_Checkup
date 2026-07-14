resource "google_service_account" "keycloak" {
  account_id   = "${var.environment}-keycloak-sa"
  display_name = "Keycloak VM Service Account (${var.environment})"
  project      = var.project_id
}

# Minimal permissions — only logging and monitoring
resource "google_project_iam_member" "keycloak_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.keycloak.email}"
}

resource "google_project_iam_member" "keycloak_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.keycloak.email}"
}

resource "google_compute_instance" "keycloak" {
  name         = "${var.environment}-keycloak"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  tags = ["keycloak"]

  labels = {
    environment = var.environment
    project     = "keycloak-nginx"
    role        = "keycloak"
  }

  boot_disk {
    initialize_params {
      image = var.vm_image
      size  = 20
      type  = "pd-ssd"
    }
  }

  network_interface {
    subnetwork = var.subnet_id
    # No access_config block = no external IP (private subnet)
  }

  metadata = {
    ssh-keys               = "${var.ssh_user}:${var.ssh_public_key}"
    startup-script         = local.startup_script
    block-project-ssh-keys = "true"
  }

  service_account {
    email  = google_service_account.keycloak.email
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

    # Install Docker
    apt-get update -y
    apt-get install -y docker.io
    systemctl enable docker
    systemctl start docker

    # Install PostgreSQL client for health checks
    apt-get install -y postgresql-client

    # Write systemd unit for Keycloak
    cat > /etc/systemd/system/keycloak.service <<EOF
    [Unit]
    Description=Keycloak Identity Provider
    After=docker.service
    Requires=docker.service

    [Service]
    Restart=always
    ExecStartPre=-/usr/bin/docker stop keycloak
    ExecStartPre=-/usr/bin/docker rm keycloak
    ExecStart=/usr/bin/docker run --rm \
      --name keycloak \
      -p 8080:8080 \
      -e KEYCLOAK_ADMIN=${var.keycloak_admin_user} \
      -e KEYCLOAK_ADMIN_PASSWORD=${var.keycloak_admin_password} \
      -e KC_DB=postgres \
      -e KC_DB_URL=jdbc:postgresql://${var.postgresql_internal_ip}:5432/${var.keycloak_database} \
      -e KC_DB_USERNAME=${var.keycloak_db_user} \
      -e KC_DB_PASSWORD=${var.keycloak_db_password} \
      -e KC_PROXY=edge \
      -e KC_HTTP_ENABLED=true \
      quay.io/keycloak/keycloak:24.0 \
      start --hostname-strict=false

    [Install]
    WantedBy=multi-user.target
    EOF

    systemctl daemon-reload
    systemctl enable keycloak
    systemctl start keycloak
  SCRIPT
}
