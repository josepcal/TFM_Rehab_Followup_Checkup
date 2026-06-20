from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    app_env: str = "dev"            # dev | prod
    auth_mode: str = "dev"          # dev | keycloak

    database_url: str = "postgresql://ftm_app:thisIsMyFTMAppDBPassword123@localhost:5432/appdb"

    keycloak_issuer: str = "http://localhost:8080/realms/ftm"
    keycloak_jwks_url: str = "http://localhost:8080/realms/ftm/protocol/openid-connect/certs"

    wav_bucket: str = ""            # vacío => almacenamiento local (dev)
    wav_local_dir: str = "/tmp/ftm-recordings"

    storage_backend: Literal["local", "s3"] = "local"
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket: str = ""
    s3_region: str = "eu-west-1"
    s3_force_path_style: bool = False

    llm_api_key: str = ""
    llm_model: str = "claude-3-5-sonnet-latest"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # Blindaje: el atajo de auth de desarrollo NUNCA debe correr en producción.
    if s.app_env == "prod" and s.auth_mode != "keycloak":
        raise RuntimeError("AUTH_MODE='dev' no está permitido con APP_ENV='prod'")
    return s
