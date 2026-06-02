resource "google_service_account" "postgresql" {
  account_id   = "${var.environment}-postgresql-sa"
  display_name = "PostgreSQL VM Service Account (${var.environment})"
  project      = var.project_id
}

resource "google_project_iam_member" "postgresql_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.postgresql.email}"
}

resource "google_project_iam_member" "postgresql_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.postgresql.email}"
}

resource "google_project_iam_member" "postgresql_storage" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.postgresql.email}"
}

resource "google_compute_instance" "postgresql" {
  name         = "${var.environment}-postgresql"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  tags = ["postgresql"]

  labels = {
    environment = var.environment
    project     = "keycloak-nginx"
    role        = "postgresql"
  }

  boot_disk {
    initialize_params {
      image = var.vm_image
      size  = 50  # Larger disk for database
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
    email  = google_service_account.postgresql.email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }
}

# Persistent data disk for PostgreSQL data directory
resource "google_compute_disk" "postgresql_data" {
  name   = "${var.environment}-postgresql-data-disk"
  type   = "pd-ssd"
  zone   = var.zone
  size   = 100
  project = var.project_id

  labels = {
    environment = var.environment
    project     = "keycloak-nginx"
    role        = "postgresql-data"
  }
}

resource "google_compute_attached_disk" "postgresql_data" {
  instance    = google_compute_instance.postgresql.id
  disk        = google_compute_disk.postgresql_data.id
  device_name = "postgresql-data"
}

resource "null_resource" "postgresql_backup_on_destroy" {
  # Re-trigger if VM changes
  triggers = {
    instance_id   = google_compute_instance.postgresql.id
    db_password   = var.keycloak_db_password
    db_name       = var.keycloak_database
    db_user       = var.keycloak_db_user
    zone          = var.zone
    project_id    = var.project_id
    instance_name = google_compute_instance.postgresql.name
  }

  # Runs BEFORE the VM is destroyed
  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      mkdir -p ./backups
      TIMESTAMP=$(date +%Y%m%d_%H%M%S)
      BACKUP_FILE="./backups/${self.triggers.db_name}_$TIMESTAMP.dump"
      
      echo "Creating backup before destroy: $BACKUP_FILE"
      
      gcloud compute ssh ${self.triggers.instance_name} \
        --zone=${self.triggers.zone} \
        --project=${self.triggers.project_id} \
        --tunnel-through-iap \
        --command="sudo -u postgres pg_dump -F c ${self.triggers.db_name}" \
        > "$BACKUP_FILE"
      
      if [ -s "$BACKUP_FILE" ]; then
        echo "✓ Backup saved: $BACKUP_FILE ($(du -h " $BACKUP_FILE" | cut -f1))"
      else
        echo "✗ Backup failed — file is empty"
        exit 1
      fi
    EOT

    on_failure = continue  # don't block destroy if backup fails
  }
}


locals {
  startup_script = <<-SCRIPT
    #!/bin/bash
    set -euo pipefail

    # Install PostgreSQL
    apt-get update -y
    apt-get install -y postgresql postgresql-contrib

    # Wait up to 60s for the data disk to attach
    for i in {1..30}; do
      if [ -e /dev/disk/by-id/google-postgresql-data ]; then
        DATA_DISK=/dev/disk/by-id/google-postgresql-data
        break
      fi
      echo "Waiting for data disk... ($i/30)"
      sleep 2
    done

    if [ -z "$${DATA_DISK:-}" ]; then
      echo "ERROR: data disk never appeared, aborting"
      exit 1
    fi

    # Format if it doesn't already have a filesystem
    if ! blkid "$DATA_DISK" > /dev/null 2>&1; then
      mkfs.ext4 -F "$DATA_DISK"
    fi

    # Mount
    mkdir -p /data/postgresql
    if ! mount | grep -q /data/postgresql; then
      mount "$DATA_DISK" /data/postgresql
    fi

    # fstab using UUID for stability
    UUID=$(blkid -s UUID -o value "$DATA_DISK")
    if ! grep -q "$UUID" /etc/fstab; then
      echo "UUID=$UUID /data/postgresql ext4 defaults,nofail 0 2" >> /etc/fstab
    fi

    # Set permissions
    chown -R postgres:postgres /data/postgresql
    chmod 700 /data/postgresql

    # Stop PostgreSQL before reconfiguring
    systemctl stop postgresql || true

    # Initialize new data directory only if not already done
    if [ ! -f /data/postgresql/main/PG_VERSION ]; then
      rm -rf /data/postgresql/main
      sudo -u postgres /usr/lib/postgresql/15/bin/initdb -D /data/postgresql/main
    fi

    # ---------------------------------------------------------------
    # IMPORTANT: On Debian/Ubuntu, PostgreSQL reads its config from
    # /etc/postgresql/15/main/ EVEN WHEN data_directory points elsewhere.
    # So we edit the Debian config, not the data dir config.
    # ---------------------------------------------------------------

    # Point Debian config to new data directory
    sed -i "s|data_directory = '.*'|data_directory = '/data/postgresql/main'|" /etc/postgresql/15/main/postgresql.conf

    # Fix listen_addresses in Debian config (this is what PostgreSQL ACTUALLY reads)
    sed -i "s|#listen_addresses = 'localhost'|listen_addresses = '0.0.0.0'|" /etc/postgresql/15/main/postgresql.conf
    sed -i "s|^listen_addresses = 'localhost'|listen_addresses = '0.0.0.0'|" /etc/postgresql/15/main/postgresql.conf

    # Tune PostgreSQL in Debian config
    if ! grep -q "# Keycloak tuning" /etc/postgresql/15/main/postgresql.conf; then
      cat >> /etc/postgresql/15/main/postgresql.conf <<EOF

# Keycloak tuning
max_connections = 200
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
EOF
    fi

    # Allow Keycloak VM connections in Debian pg_hba.conf (idempotent)
    if ! grep -q "${var.keycloak_vm_cidr}" /etc/postgresql/15/main/pg_hba.conf; then
      cat >> /etc/postgresql/15/main/pg_hba.conf <<EOF
# Allow connections from Keycloak VM
host    ${var.keycloak_database}    ${var.keycloak_db_user}    ${var.keycloak_vm_cidr}    md5
EOF
    fi

    # Verify configs before starting
    echo "=== listen_addresses in Debian config ==="
    grep listen_addresses /etc/postgresql/15/main/postgresql.conf

    echo "=== pg_hba.conf entries ==="
    grep -v "^#" /etc/postgresql/15/main/pg_hba.conf | grep -v "^$"

    # Start PostgreSQL with new config
    systemctl start postgresql
    sleep 5

    # Verify it's listening on 0.0.0.0
    echo "=== Listening ports ==="
    ss -tlnp | grep 5432

    # Set postgres superuser password
    sudo -u postgres psql -c "ALTER USER postgres PASSWORD '${var.postgres_password}';"

    # Create Keycloak database and user (idempotent)
    sudo -u postgres psql <<EOF
SELECT 'CREATE DATABASE ${var.keycloak_database}' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${var.keycloak_database}')\gexec
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${var.keycloak_db_user}') THEN
    CREATE USER ${var.keycloak_db_user} WITH PASSWORD '${var.keycloak_db_password}';
  END IF;
END
\$\$;
ALTER ROLE ${var.keycloak_db_user} SET client_min_messages TO warning;
GRANT ALL PRIVILEGES ON DATABASE ${var.keycloak_database} TO ${var.keycloak_db_user};
\c ${var.keycloak_database}
GRANT ALL ON SCHEMA public TO ${var.keycloak_db_user};
EOF

    systemctl enable postgresql
    systemctl restart postgresql

    echo "PostgreSQL setup complete"
  SCRIPT
}