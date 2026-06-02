output "nginx_external_ip" {
  description = "External IP address of the Nginx VM"
  value       = module.nginx.external_ip
}

output "keycloak_internal_ip" {
  description = "Internal IP address of the Keycloak VM"
  value       = module.keycloak.internal_ip
}

output "postgresql_internal_ip" {
  description = "Internal IP address of the PostgreSQL VM"
  value       = module.postgresql.internal_ip
}

output "vpc_name" {
  description = "Name of the VPC network"
  value       = module.network.vpc_name
}
