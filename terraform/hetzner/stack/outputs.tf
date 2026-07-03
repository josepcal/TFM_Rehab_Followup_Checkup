output "stack_server_id" {
  description = "Stack VM server ID."
  value       = hcloud_server.stack.id
}

output "stack_private_ip" {
  description = "Stack VM private IP — nginx on the edge proxies here."
  value       = var.stack_private_ip
}

output "has_public_ip" {
  description = "Sanity check — must be false. The stack VM has no public IP."
  value       = false
}
