# --- Capa stack (efímera) ---
# VM que corre el stack de la app. SIN IP pública: solo alcanzable desde la edge
# por la red privada. Monta el volumen persistente (datos) y levanta el compose.

resource "hcloud_ssh_key" "stack" {
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

  # bff (8000) y keycloak (8080) solo desde la IP privada de la edge.
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
}

# --- Stack VM: SIN IP pública ---
resource "hcloud_server" "stack" {
  name         = "ftm-prod-stack"
  server_type  = var.server_type
  image        = var.image
  location     = local.location
  ssh_keys     = [hcloud_ssh_key.stack.id]
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
  })
}

# --- Adjuntar el volumen persistente (datos) ---
resource "hcloud_volume_attachment" "data" {
  volume_id = local.volume_id
  server_id = hcloud_server.stack.id
  automount = false # cloud-init mounts it explicitly at /mnt/ftm-data
}
