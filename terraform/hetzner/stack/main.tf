# --- Capa stack (efímera) ---
# VM que corre el stack de la app. SIN IP pública: solo alcanzable desde la edge
# por la red privada. Monta el volumen persistente (datos) y levanta el compose.

# Hetzner identifies SSH keys by the fingerprint of their content, not just by name —
# uploading the same public key under a second name is rejected as a duplicate. Reuse
# the key already uploaded by another layer (e.g. the edge) if present; otherwise create it.
data "hcloud_ssh_keys" "existing" {
  with_selector = "project=ftm"
}

locals {
  existing_key = try(
    [for k in data.hcloud_ssh_keys.existing.ssh_keys : k if k.public_key == var.ssh_public_key][0],
    null
  )
  ssh_key_id = local.existing_key != null ? local.existing_key.id : hcloud_ssh_key.stack[0].id
}

resource "hcloud_ssh_key" "stack" {
  count      = local.existing_key == null ? 1 : 0
  name       = var.ssh_key_name
  public_key = var.ssh_public_key
  labels     = var.labels
}

# --- Firewall: NADA desde internet. Solo desde la edge (red privada). ---
# Sin IP pública el server ya es inalcanzable desde fuera; el firewall es la
# segunda capa (defensa en profundidad).
resource "hcloud_firewall" "stack" {
  name   = "ftm-prod-stack-fw"
  labels = var.labels

  # bff (8000), keycloak (8080) and MinIO S3 API (9000) — only from the edge private IP.
  # MinIO 9000 is needed for presigned browser uploads/downloads proxied by the edge.
  # (MinIO console 9001 is never published, so it stays unreachable.)
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "8000"
    source_ips = ["${var.edge_private_ip}/32"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "8080"
    source_ips = ["${var.edge_private_ip}/32"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "9000"
    source_ips = ["${var.edge_private_ip}/32"]
  }
}

# --- Stack VM: SIN IP pública ---
resource "hcloud_server" "stack" {
  name         = "ftm-prod-stack"
  server_type  = var.server_type
  image        = var.image
  location     = local.location
  ssh_keys     = [local.ssh_key_id]
  firewall_ids = [hcloud_firewall.stack.id]
  labels       = var.labels

  # No public IP at all — the stack is unreachable from the internet by construction.
  public_net {
    ipv4_enabled = false
    ipv6_enabled = false
  }

  network {
    network_id = local.network_id
    ip         = var.stack_private_ip
  }

  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    volume_device    = local.volume_linux_device
    age_private_key  = var.age_private_key
    repo_url         = var.repo_url
    repo_ref         = var.repo_ref
    domain           = var.domain
    stack_private_ip = var.stack_private_ip
    subnet_gateway   = var.subnet_gateway
  })
}

# --- Adjuntar el volumen persistente (datos) ---
resource "hcloud_volume_attachment" "data" {
  volume_id = local.volume_id
  server_id = hcloud_server.stack.id
  automount = false # cloud-init mounts it explicitly at /mnt/ftm-data
}
