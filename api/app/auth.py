from functools import lru_cache

import httpx
from fastapi import Depends, Header, HTTPException, Request
try:
    from jose import JWTError, jwt
except ModuleNotFoundError:  # pragma: no cover - production image installs python-jose
    class JWTError(Exception):
        pass

    class _MissingJoseJwt:
        def get_unverified_header(self, _token):
            raise JWTError("python-jose is not installed")

        def decode(self, *_args, **_kwargs):
            raise JWTError("python-jose is not installed")

    jwt = _MissingJoseJwt()

from app.config import get_settings
from app.context import current_user, current_role

settings = get_settings()
REALM_ROLES = ("medical", "patient", "technician", "admin")


@lru_cache
def _jwks() -> dict:
    return httpx.get(settings.keycloak_jwks_url, timeout=10).json()


def _decode(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
        key = _find_jwk(header["kid"])
        if key is None:
            # Keycloak dev realms are often reimported, which rotates signing keys.
            # Refresh the cached JWKS once before rejecting the token.
            _jwks.cache_clear()
            key = _find_jwk(header["kid"])
        if key is None:
            raise HTTPException(401, "clave de firma desconocida (JWKS)")
        # Force RS256 explicitly — never derive the algorithm from the token header
        # or the JWK, which would open an algorithm-confusion path (e.g. a token
        # crafted with alg=none or a symmetric alg). Validate issuer AND audience;
        # the audience mapper on ftm-web injects settings.keycloak_audience into aud.
        return jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.keycloak_issuer,
            audience=settings.keycloak_audience,
            options={"verify_aud": True},
        )
    except HTTPException:
        raise
    except JWTError as exc:
        raise HTTPException(401, f"token Keycloak invalido: {exc}") from exc


def _find_jwk(kid: str) -> dict | None:
    return next((k for k in _jwks().get("keys", []) if k.get("kid") == kid), None)


def _role(claims: dict) -> str:
    roles = claims.get("realm_access", {}).get("roles", [])
    return next((r for r in REALM_ROLES if r in roles), "none")


def current_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    x_dev_role: str | None = Header(default=None),
) -> dict:
    # --- Atajo de desarrollo (bloqueado en prod por get_settings) ---
    if settings.auth_mode == "dev":
        sub, role = "dev-user", (x_dev_role or "medical")
        current_user.set(sub)
        current_role.set(role)
        # Publish the sub on request.state so AuditMiddleware can attribute the action
        # without re-decoding the token. request.state (unlike ContextVars) propagates
        # back to the middleware frame after the handler returns.
        request.state.auth_sub = sub
        return {"sub": sub, "role": role}

    # --- Keycloak (OIDC) ---
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "falta el bearer token")
    claims = _decode(authorization.split(" ", 1)[1])
    role = _role(claims)
    current_user.set(claims["sub"])
    current_role.set(role)
    # Only set after full signature/issuer/audience validation above — this is the
    # trusted sub the audit log must use, never a base64-decoded (unverified) claim.
    request.state.auth_sub = claims["sub"]
    return {"sub": claims["sub"], "role": role}


def require_role(*allowed: str):
    def dep(principal: dict = Depends(current_principal)) -> dict:
        if principal["role"] not in allowed:
            raise HTTPException(403, f"rol '{principal['role']}' no autorizado")
        return principal
    return dep
