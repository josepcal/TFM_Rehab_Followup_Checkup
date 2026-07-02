terraform {
  # Estado LOCAL para el MVP (un solo operador). Cada capa (persistent/edge/stack)
  # tiene su propio directorio y por tanto su propio terraform.tfstate — el
  # aislamiento de estado entre capas es por directorio.
  #
  # IMPORTANTE: el state de la capa persistente contiene los IDs de recursos que
  # NUNCA deben perderse. Hacer backup de este fichero (o migrar a un backend
  # remoto S3-compatible) antes de operar en serio.
  #
  # Para backend remoto (recomendado fuera del MVP), sustituir por:
  #   backend "s3" {
  #     bucket                      = "ftm-tfstate"
  #     key                         = "hetzner/persistent/terraform.tfstate"
  #     region                      = "eu-central-1"
  #     endpoints                   = { s3 = "https://<minio-or-provider-endpoint>" }
  #     skip_credentials_validation = true
  #     skip_region_validation      = true
  #     use_path_style              = true
  #   }
  backend "local" {}
}
