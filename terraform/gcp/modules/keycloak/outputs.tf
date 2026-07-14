output "internal_ip" {
  description = "Internal IP address of the Keycloak VM"
  value       = google_compute_instance.keycloak.network_interface[0].network_ip
}

output "instance_name" {
  description = "Name of the Keycloak Compute instance"
  value       = google_compute_instance.keycloak.name
}

output "service_account_email" {
  description = "Service account email used by the Keycloak VM"
  value       = google_service_account.keycloak.email
}
