output "edge_server_id" {
  description = "Edge VM server ID."
  value       = hcloud_server.edge.id
}

output "edge_public_ip" {
  description = "Edge VM's own public IPv4 (distinct from the floating IP)."
  value       = hcloud_server.edge.ipv4_address
}

output "edge_private_ip" {
  description = "Edge VM private IP — nginx origin inside the private network."
  value       = var.edge_private_ip
}

output "floating_ip_address" {
  description = "Floating IP now assigned to the edge VM — DNS A record target."
  value       = local.floating_ip_address
}
