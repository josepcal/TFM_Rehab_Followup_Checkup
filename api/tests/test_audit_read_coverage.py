"""Guard test: every GET that exposes personal/clinical data must be auditable.

Read auditing is opt-in per endpoint (``Depends(audit_read)``), which is precise
but easy to forget on a new endpoint. This test makes the omission fail CI: any
GET whose path is not on the explicit non-sensitive allowlist must carry the
marker. Adding a sensitive endpoint without it turns this red.

If a genuinely non-sensitive GET is added (a catalogue/reference read), add its
prefix to ``NON_SENSITIVE_GET_PREFIXES`` with a one-line justification — that is a
deliberate, reviewable decision, not a silent gap.
"""

from app.auth import audit_read
from app.main import app

# Paths that expose no personal or clinical data, so a read leaves no trail on
# purpose. Keep this list short and justified — it is the only escape hatch.
NON_SENSITIVE_GET_PREFIXES = (
    "/health",              # liveness probe
    "/exercises",           # static exercise catalogue
    "/analysis-functions",  # registered analysis function names
    "/norms",               # reference metric norms
)


def _is_exempt(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in NON_SENSITIVE_GET_PREFIXES)


def _get_routes():
    seen = set()
    for route in app.routes:
        methods = getattr(route, "methods", None)
        if not methods or "GET" not in methods or not hasattr(route, "dependant"):
            continue
        # Two routers register /recordings/{id}/metrics; only the first is reachable.
        if route.path in seen:
            continue
        seen.add(route.path)
        yield route


def test_sensitive_gets_are_audited():
    missing = [
        route.path
        for route in _get_routes()
        if not _is_exempt(route.path)
        and audit_read not in [d.call for d in route.dependant.dependencies]
    ]
    assert not missing, (
        "These sensitive GET endpoints lack Depends(audit_read) — reads of clinical "
        f"data would leave no audit trail: {missing}"
    )
