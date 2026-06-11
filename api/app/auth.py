from functools import lru_cache

import httpx
from fastapi import Depends, Header, HTTPException
from jose import jwt

from app.config import get_settings
from app.context import current_user, current_role

settings = get_settings()
REALM_ROLES = ("medical", "patient", "technician", "admin")


@lru_cache
def _jwks() -> dict:
    return httpx.get(settings.keycloak_jwks_url, timeout=10).json()


def _decode(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    key = next((k for k in _jwks()["keys"] if k["kid"] == header["kid"]), None)
    if key is None:
        raise HTTPException(401, "clave de firma desconocida (JWKS)")
    return jwt.decode(
        token,
        key,
        algorithms=[key.get("alg", "RS256")],
        issuer=settings.keycloak_issuer,
        options={"verify_aud": False},
    )


def _role(claims: dict) -> str:
    roles = claims.get("realm_access", {}).get("roles", [])
    return next((r for r in REALM_ROLES if r in roles), "none")


def current_principal(
    authorization: str | None = Header(default=None),
    x_dev_role: str | None = Header(default=None),
) -> dict:
    # --- Atajo de desarrollo (bloqueado en prod por get_settings) ---
    if settings.auth_mode == "dev":
        sub, role = "dev-user", (x_dev_role or "medical")
        current_user.set(sub)
        current_role.set(role)
        return {"sub": sub, "role": role}

    # --- Keycloak (OIDC) ---
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "falta el bearer token")
    claims = _decode(authorization.split(" ", 1)[1])
    role = _role(claims)
    current_user.set(claims["sub"])
    current_role.set(role)
    return {"sub": claims["sub"], "role": role}


def require_role(*allowed: str):
    def dep(principal: dict = Depends(current_principal)) -> dict:
        if principal["role"] not in allowed:
            raise HTTPException(403, f"rol '{principal['role']}' no autorizado")
        return principal
    return dep
