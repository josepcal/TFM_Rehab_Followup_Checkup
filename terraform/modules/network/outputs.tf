output "vpc_name" {
  description = "Name of the VPC network"
  value       = google_compute_network.vpc.name
}

output "vpc_id" {
  description = "Self-link of the VPC network"
  value       = google_compute_network.vpc.id
}

output "public_subnet_id" {
  description = "Self-link of the public subnet"
  value       = google_compute_subnetwork.public.id
}

output "public_subnet_cidr" {
  description = "CIDR range of the public subnet"
  value       = google_compute_subnetwork.public.ip_cidr_range
}

output "private_subnet_id" {
  description = "Self-link of the private subnet"
  value       = google_compute_subnetwork.private.id
}

output "private_subnet_cidr" {
  description = "CIDR range of the private subnet"
  value       = google_compute_subnetwork.private.ip_cidr_range
}
