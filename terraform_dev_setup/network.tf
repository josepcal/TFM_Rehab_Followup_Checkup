# Allow SSH so you can connect to the VM and run Alembic.
resource "google_compute_firewall" "allow_ssh" {
  name          = "${var.vm_name}-allow-ssh"
  network       = "default"
  source_ranges = [var.allowed_ssh_cidr]
  target_tags   = ["ssh"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# Optional: open PostgreSQL (5432) to the internet. NOT needed when Alembic
# runs on this VM (it reaches the DB via localhost). Enable only for remote
# clients. Created only when expose_postgres = true.
resource "google_compute_firewall" "allow_postgres" {
  count         = var.expose_postgres ? 1 : 0
  name          = "${var.vm_name}-allow-postgres"
  network       = "default"
  source_ranges = [var.allowed_db_cidr]
  target_tags   = ["alembic"]

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }
}
