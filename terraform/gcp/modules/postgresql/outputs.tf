output "internal_ip" {
  description = "Internal IP address of the PostgreSQL VM"
  value       = google_compute_instance.postgresql.network_interface[0].network_ip
}

output "instance_name" {
  description = "Name of the PostgreSQL Compute instance"
  value       = google_compute_instance.postgresql.name
}

output "service_account_email" {
  description = "Service account email used by the PostgreSQL VM"
  value       = google_service_account.postgresql.email
}

output "data_disk_id" {
  description = "Self-link of the persistent PostgreSQL data disk"
  value       = google_compute_disk.postgresql_data.id
}
