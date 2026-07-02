# --- Capa edge (always-on) ---
# VM pequeña que corre nginx (TLS + reverse proxy), mantiene la IP flotante
# y es el ÚNICO host con IP pública. Habla con el stack por la red privada.

resource "hcloud_ssh_key" "edge" {
  name       = var.ssh_key_name
  public_key = var.ssh_public_key
  labels     = var.labels
}

# --- Firewall: solo 80/443 desde internet; SSH solo desde el operador ---
resource "hcloud_firewall" "edge" {
  name   = "ftm-prod-edge-fw"
  labels = var.labels

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "80"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = var.operator_ssh_cidrs
  }
}

# --- Edge VM ---
resource "hcloud_server" "edge" {
  name         = "ftm-prod-edge"
  server_type  = var.server_type
  image        = var.image
  location     = local.location
  ssh_keys     = [hcloud_ssh_key.edge.id]
  firewall_ids = [hcloud_firewall.edge.id]
  labels       = var.labels

  # Edge is the only host WITH a public IP.
  public_net {
    ipv4_enabled = true
    ipv6_enabled = true
  }

  network {
    network_id = local.network_id
    ip         = var.edge_private_ip
  }

  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    domain              = var.domain
    ssl_cert_email      = var.ssl_cert_email
    floating_ip_address = local.floating_ip_address
  })
}

# --- Asignar la IP flotante persistente a la edge VM ---
resource "hcloud_floating_ip_assignment" "edge" {
  floating_ip_id = local.floating_ip_id
  server_id      = hcloud_server.edge.id
}
