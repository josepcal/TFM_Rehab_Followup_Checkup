resource "google_compute_network" "vpc" {
  name                    = "${var.environment}-keycloak-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id

  description = "VPC for Keycloak + Nginx deployment (${var.environment})"
}

resource "google_compute_subnetwork" "public" {
  name          = "${var.environment}-public-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id
  project       = var.project_id

  description = "Public subnet for Nginx VM"
}

resource "google_compute_subnetwork" "private" {
  name                     = "${var.environment}-private-subnet"
  ip_cidr_range            = "10.0.2.0/24"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  project                  = var.project_id
  private_ip_google_access = true

  description = "Private subnet for Keycloak VM"
}

# Allow HTTP/HTTPS from internet to Nginx
resource "google_compute_firewall" "allow_http_https" {
  name    = "${var.environment}-allow-http-https"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["nginx"]

  description = "Allow HTTP/HTTPS traffic to Nginx VM only"
}

# Allow Nginx to reach Keycloak on port 8080 (internal only)
resource "google_compute_firewall" "allow_keycloak_from_nginx" {
  name    = "${var.environment}-allow-keycloak-from-nginx"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }

  source_tags = ["nginx"]
  target_tags = ["keycloak"]

  description = "Allow Keycloak port 8080 from Nginx only — never open to internet"
}

# Allow Keycloak to reach PostgreSQL on port 5432 (internal only)
resource "google_compute_firewall" "allow_postgresql_from_keycloak" {
  name    = "${var.environment}-allow-postgresql-from-keycloak"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }

  source_tags = ["keycloak"]
  target_tags = ["postgresql"]

  description = "Allow PostgreSQL port 5432 from Keycloak only — never open to internet"
}

# SSH access — restrict source_ranges in production
resource "google_compute_firewall" "allow_ssh" {
  name    = "${var.environment}-allow-ssh"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"] # IAP range — use IAP for SSH instead of direct exposure
  target_tags   = ["nginx", "keycloak", "postgresql"]

  description = "Allow SSH via IAP tunnel only"
}

# Cloud NAT for private subnet outbound (for Keycloak Docker pulls etc.)
resource "google_compute_router" "router" {
  name    = "${var.environment}-router"
  region  = var.region
  network = google_compute_network.vpc.id
  project = var.project_id
}

resource "google_compute_router_nat" "nat" {
  name                               = "${var.environment}-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"
  project                            = var.project_id

  subnetwork {
    name                    = google_compute_subnetwork.private.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
}

# Nginx -> App (API) en 8000
resource "google_compute_firewall" "allow_app_from_nginx" {
  name    = "${var.environment}-allow-app-from-nginx"
  network = google_compute_network.vpc.name
  project = var.project_id
  allow { protocol = "tcp"; ports = ["8000"] }
  source_tags = ["nginx"]
  target_tags = ["app"]
  description = "Allow API port 8000 from Nginx only"
}

# App -> PostgreSQL en 5432
resource "google_compute_firewall" "allow_postgresql_from_app" {
  name    = "${var.environment}-allow-postgresql-from-app"
  network = google_compute_network.vpc.name
  project = var.project_id
  allow { protocol = "tcp"; ports = ["5432"] }
  source_tags = ["app"]
  target_tags = ["postgresql"]
  description = "Allow PostgreSQL from App VM only"
}

# App -> Keycloak en 8080 (validación JWKS)
resource "google_compute_firewall" "allow_keycloak_from_app" {
  name    = "${var.environment}-allow-keycloak-from-app"
  network = google_compute_network.vpc.name
  project = var.project_id
  allow { protocol = "tcp"; ports = ["8080"] }
  source_tags = ["app"]
  target_tags = ["keycloak"]
  description = "Allow Keycloak JWKS from App VM only"
}