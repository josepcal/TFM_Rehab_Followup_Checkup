terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

locals {
  # Privilege clause applied to db_user in the startup script.
  db_user_privileges = var.db_user_admin ? "SUPERUSER CREATEDB CREATEROLE" : "NOSUPERUSER NOCREATEDB NOCREATEROLE"
}

# Reserve a static external IP so the connection endpoint stays stable
# across reboots / recreations.
resource "google_compute_address" "vm_ip" {
  name         = "${var.vm_name}-ip"
  address_type = "EXTERNAL"
  region       = var.region
}

resource "google_compute_instance" "alembic_vm" {
  name         = var.vm_name
  machine_type = var.machine_type # e2-medium = 2 vCPU / 4 GB RAM
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = var.image
      size  = var.disk_size_gb # 50 GB
      type  = "pd-ssd"         # SSD persistent disk
    }
  }

  network_interface {
    network = "default"

    # access_config block = attach an external IP.
    access_config {
      nat_ip = google_compute_address.vm_ip.address
    }
  }

  # Inject your SSH public key so you can connect as var.ssh_user.
  metadata = {
    ssh-keys = "${var.ssh_user}:${file(var.ssh_public_key_path)}"
  }

  # Install PostgreSQL and provision the DB / app user.
  metadata_startup_script = templatefile("${path.module}/startup.sh.tftpl", {
    enable_postgres    = var.enable_postgres
    expose_postgres    = var.expose_postgres
    db_name            = var.db_name
    db_user            = var.db_user
    db_password        = var.db_password
    db_user_privileges = local.db_user_privileges
  })

  tags = ["ssh", "alembic"]

  labels = {
    purpose = "alembic-migrations"
  }
}
