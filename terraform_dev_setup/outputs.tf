output "external_ip" {
  description = "Static external IP of the VM."
  value       = google_compute_address.vm_ip.address
}

output "ssh_command" {
  description = "Copy-paste command to connect (for admin/debugging)."
  value       = "ssh ${var.ssh_user}@${google_compute_address.vm_ip.address}"
}

output "database_url" {
  description = "Connection string to set as DATABASE_URL on your LOCAL PC for Alembic."
  value       = var.enable_postgres ? "postgresql+psycopg2://${var.db_user}:****@${google_compute_address.vm_ip.address}:5432/${var.db_name}" : "n/a"
}
