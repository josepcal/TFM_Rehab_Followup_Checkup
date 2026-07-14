output "internal_ip" {
  description = "Internal IP of the app VM"
  value       = google_compute_instance.app.network_interface[0].network_ip
}

output "service_account_email" {
  description = "Email of the app VM service account"
  value       = google_service_account.app.email
}

output "recordings_bucket" {
  description = "Name of the recordings (WAV) bucket"
  value       = google_storage_bucket.recordings.name
}
