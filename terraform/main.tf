module "network" {
  source = "./modules/network"

  project_id  = var.project_id
  region      = var.region
  environment = var.environment
}

module "postgresql" {
  source = "./modules/postgresql"

  project_id              = var.project_id
  zone                    = var.zone
  environment             = var.environment
  subnet_id               = module.network.private_subnet_id
  machine_type            = var.postgresql_machine_type
  vm_image                = var.vm_image
  ssh_user                = var.ssh_user
  ssh_public_key          = var.ssh_public_key
  postgres_password       = var.postgres_password
  keycloak_database       = var.keycloak_database
  keycloak_db_user        = var.keycloak_db_user
  keycloak_db_password    = var.keycloak_db_password
  keycloak_vm_cidr        = module.network.private_subnet_cidr

  app_database           = var.app_database              # NUEVO
  app_db_user            = var.app_db_user               # NUEVO
  app_db_password_secret = "${var.environment}-app-db-password"  # NUEVO
  app_vm_cidr            = module.network.private_subnet_cidr     # NUEVO

  depends_on = [module.network]

}

module "keycloak" {
  source = "./modules/keycloak"

  project_id               = var.project_id
  zone                     = var.zone
  environment              = var.environment
  subnet_id                = module.network.private_subnet_id
  machine_type             = var.keycloak_machine_type
  vm_image                 = var.vm_image
  ssh_user                 = var.ssh_user
  ssh_public_key           = var.ssh_public_key
  keycloak_admin_user      = var.keycloak_admin_user
  keycloak_admin_password  = var.keycloak_admin_password
  nginx_subnet_cidr        = module.network.public_subnet_cidr
  postgresql_internal_ip   = module.postgresql.internal_ip
  keycloak_database        = var.keycloak_database
  keycloak_db_user         = var.keycloak_db_user
  keycloak_db_password     = var.keycloak_db_password

  depends_on = [module.network, module.postgresql]

}

module "nginx" {
  source = "./modules/nginx"

  project_id           = var.project_id
  region               = var.region
  zone                 = var.zone
  environment          = var.environment
  subnet_id            = module.network.public_subnet_id
  machine_type         = var.nginx_machine_type
  vm_image             = var.vm_image
  ssh_user             = var.ssh_user
  ssh_public_key       = var.ssh_public_key
  domain               = var.domain
  ssl_cert_email       = var.ssl_cert_email
  keycloak_internal_ip = module.keycloak.internal_ip
  app_internal_ip      = module.app.internal_ip          # NUEVO

  depends_on = [module.network, module.keycloak, module.app]

}
