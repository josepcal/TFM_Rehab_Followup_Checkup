output "network_id" {
  description = "Private network ID — consumed by edge and stack layers."
  value       = hcloud_network.ftm.id
}

output "subnet_ip_range" {
  description = "Private subnet range where edge + stack VMs allocate their private IPs."
  value       = hcloud_network_subnet.ftm.ip_range
}

output "volume_id" {
  description = "Data volume ID — attached by the stack VM."
  value       = hcloud_volume.data.id
}

output "volume_linux_device" {
  description = "Stable device path of the data volume for mounting in cloud-init."
  value       = hcloud_volume.data.linux_device
}

output "floating_ip_id" {
  description = "Floating IP ID — assigned to the edge VM."
  value       = hcloud_floating_ip.ftm.id
}

output "floating_ip_address" {
  description = "Floating IPv4 address — DNS A record target."
  value       = hcloud_floating_ip.ftm.ip_address
}

output "location" {
  description = "Location the volume lives in — the stack VM MUST use this to attach it."
  value       = var.location
}

output "network_zone" {
  description = "Network zone of the private subnet."
  value       = var.network_zone
}
