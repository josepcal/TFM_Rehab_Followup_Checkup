terraform {
  backend "gcs" {
    bucket = "your-tfstate-bucket-name"
    prefix = "keycloak-nginx/dev"
  }
}
