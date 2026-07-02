# --- Capa persistente (nunca se destruye) ---
# Recursos de larga vida que sobreviven a los apagados del stack:
# volumen de datos, IP flotante, red privada y su subnet.
# Doble protección: prevent_destroy (Terraform) + delete_protection (Hetzner).

# --- Red privada (edge <-> stack, tráfico biométrico nunca sale a internet) ---
resource "hcloud_network" "ftm" {
  name              = "ftm-prod-net"
  ip_range          = var.network_ip_range
  delete_protection = true
  labels            = var.labels

  lifecycle {
    prevent_destroy = true
  }
}

resource "hcloud_network_subnet" "ftm" {
  network_id   = hcloud_network.ftm.id
  type         = "cloud"
  network_zone = var.network_zone
  ip_range     = var.subnet_ip_range
}

# --- Volumen de datos (Postgres + MinIO). Solo DATOS: sin secretos, sin cert TLS. ---
# Zone-bound: vive en var.location; el stack VM debe crearse en la misma location.
resource "hcloud_volume" "data" {
  name              = "ftm-prod-data"
  size              = var.volume_size
  location          = var.location
  format            = "ext4"
  delete_protection = true
  labels            = var.labels

  lifecycle {
    prevent_destroy = true
  }
}

# --- IP flotante (la mantiene la edge VM always-on; el DNS apunta aquí) ---
resource "hcloud_floating_ip" "ftm" {
  type              = "ipv4"
  home_location     = var.location
  name              = "ftm-prod-fip"
  description        = "FTM prod public entry — held by the always-on edge VM"
  delete_protection = true
  labels            = var.labels

  lifecycle {
    prevent_destroy = true
  }
}

# --- DNS ---
# NOTA: la gestión DNS NO está en el provider hcloud. Hetzner DNS usa el provider
# separado `timohirt/hetznerdns` (comunidad). Para no acoplar esta capa a un provider
# externo en el MVP, el registro A se gestiona manualmente (o en una capa DNS aparte)
# apuntando `var.domain` a hcloud_floating_ip.ftm.ip_address (ver outputs).
# Si se adopta el provider DNS, añadir aquí:
#   resource "hetznerdns_record" "a" {
#     zone_id = var.dns_zone_id
#     name    = "@"
#     type    = "A"
#     value   = hcloud_floating_ip.ftm.ip_address
#     ttl     = 300
#   }
