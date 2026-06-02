resource "google_service_account" "nginx" {
  account_id   = "${var.environment}-nginx-sa"
  display_name = "Nginx VM Service Account (${var.environment})"
  project      = var.project_id
}

resource "google_project_iam_member" "nginx_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.nginx.email}"
}

resource "google_project_iam_member" "nginx_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.nginx.email}"
}

resource "google_compute_address" "nginx" {
  name    = "${var.environment}-nginx-ip"
  region  = var.region
  project = var.project_id
}

resource "google_compute_instance" "nginx" {
  name         = "${var.environment}-nginx"
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  tags = ["nginx"]

  labels = {
    environment = var.environment
    project     = "keycloak-nginx"
    role        = "nginx"
  }

  boot_disk {
    initialize_params {
      image = var.vm_image
      size  = 20
      type  = "pd-ssd"
    }
  }

  network_interface {
    subnetwork = var.subnet_id
    access_config {
      nat_ip = google_compute_address.nginx.address
    }
  }

  metadata = {
    ssh-keys               = "${var.ssh_user}:${var.ssh_public_key}"
    startup-script         = local.startup_script
    block-project-ssh-keys = "true"
  }

  service_account {
    email  = google_service_account.nginx.email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }
}

locals {
  startup_script = <<-SCRIPT
    #!/bin/bash
    set -euo pipefail

    apt-get update -y
    apt-get install -y nginx certbot python3-certbot-nginx

    # Write Nginx config for Keycloak reverse proxy
    cat > /etc/nginx/sites-available/keycloak <<EOF
    server {
        listen 80;
        server_name ${var.domain};

        location / {
            return 301 https://\$host\$request_uri;
        }
    }

    server {
        listen 443 ssl;
        server_name ${var.domain};

        ssl_certificate     /etc/letsencrypt/live/${var.domain}/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/${var.domain}/privkey.pem;
        ssl_protocols       TLSv1.2 TLSv1.3;
        ssl_ciphers         HIGH:!aNULL:!MD5;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Frame-Options SAMEORIGIN always;
        add_header X-Content-Type-Options nosniff always;

        location / {
            proxy_pass          http://${var.keycloak_internal_ip}:8080;
            proxy_set_header    Host \$host;
            proxy_set_header    X-Real-IP \$remote_addr;
            proxy_set_header    X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header    X-Forwarded-Proto \$scheme;
            proxy_read_timeout  90;
            proxy_connect_timeout 90;
            proxy_buffer_size   128k;
            proxy_buffers       4 256k;
            proxy_busy_buffers_size 256k;
        }
    }
    EOF

    ln -sf /etc/nginx/sites-available/keycloak /etc/nginx/sites-enabled/keycloak
    rm -f /etc/nginx/sites-enabled/default

    # Obtain Let's Encrypt certificate (non-interactive)
    # NOTE: domain DNS must resolve to this IP before certbot will succeed
    certbot --nginx \
      --non-interactive \
      --agree-tos \
      --email ${var.ssl_cert_email} \
      --domains ${var.domain} \
      --redirect 

    # Enable auto-renewal
    systemctl enable certbot.timer || true
    (crontab -l 2>/dev/null; echo "0 3 * * * /usr/bin/certbot renew --quiet") | crontab -

    nginx -t && systemctl enable nginx && systemctl restart nginx
  SCRIPT
}
