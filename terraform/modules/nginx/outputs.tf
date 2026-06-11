output "external_ip" {
  description = "Static external IP address of the Nginx VM"
  value       = google_compute_address.nginx.address
}

output "instance_name" {
  description = "Name of the Nginx Compute instance"
  value       = google_compute_instance.nginx.name
}

output "service_account_email" {
  description = "Service account email used by the Nginx VM"
  value       = google_service_account.nginx.email
}
