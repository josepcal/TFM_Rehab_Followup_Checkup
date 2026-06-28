"""RGPD consent endpoints (UC-05).

Authorization model:
- GET  /programs/{program_id}/consent          → patient only
- POST /programs/{program_id}/consent/grant    → patient only
- POST /programs/{program_id}/consent/withdraw → patient only
"""

import uuid

from fastapi import APIRouter, Depends, status

from app.auth import require_role
from app.clinical.consent_schemas import ConsentIn, ConsentOut, ConsentStatus
from app.clinical.consent_service import ConsentService
from app.db import get_db

router = APIRouter(tags=["consent"])


# ---------------------------------------------------------------------------
# GET /programs/{program_id}/consent
# ---------------------------------------------------------------------------


@router.get(
    "/programs/{program_id}/consent",
    response_model=ConsentStatus,
    status_code=status.HTTP_200_OK,
)
def get_consent_status(
    program_id: uuid.UUID,
    principal: dict = Depends(require_role("patient")),
    db=Depends(get_db),
) -> ConsentStatus:
    """Return the most recent consent status for the authenticated patient (UC-05)."""
    svc = ConsentService(db)
    row = svc.get_status(program_id)

    if row is None:
        return ConsentStatus(
            consent_id=None,
            program_id=program_id,
            granted=False,
            granted_at=None,
            withdrawn_at=None,
            consent_text=None,
        )

    return ConsentStatus(
        consent_id=row.consent_id,
        program_id=program_id,
        granted=row.granted and row.withdrawn_at is None,
        granted_at=row.granted_at,
        withdrawn_at=row.withdrawn_at,
        consent_text=row.consent_text,
    )


# ---------------------------------------------------------------------------
# POST /programs/{program_id}/consent/grant
# ---------------------------------------------------------------------------


@router.post(
    "/programs/{program_id}/consent/grant",
    response_model=ConsentOut,
    status_code=status.HTTP_200_OK,
)
def grant_consent(
    program_id: uuid.UUID,
    body: ConsentIn,
    principal: dict = Depends(require_role("patient")),
    db=Depends(get_db),
) -> ConsentOut:
    """Grant consent for the authenticated patient — always inserts a new row (UC-05)."""
    svc = ConsentService(db)
    row = svc.grant(program_id, body.consent_text)

    return ConsentOut(
        consent_id=row.consent_id,
        program_id=program_id,
        granted=True,
        granted_at=row.granted_at,
        withdrawn_at=None,
        consent_text=row.consent_text,
    )


# ---------------------------------------------------------------------------
# POST /programs/{program_id}/consent/withdraw
# ---------------------------------------------------------------------------


@router.post(
    "/programs/{program_id}/consent/withdraw",
    response_model=ConsentStatus,
    status_code=status.HTTP_200_OK,
)
def withdraw_consent(
    program_id: uuid.UUID,
    principal: dict = Depends(require_role("patient")),
    db=Depends(get_db),
) -> ConsentStatus:
    """Withdraw active consent — sets withdrawn_at on the most recent active row (UC-05)."""
    svc = ConsentService(db)
    row = svc.withdraw(program_id)  # raises 404 if no active row

    return ConsentStatus(
        consent_id=row.consent_id,
        program_id=program_id,
        granted=False,
        granted_at=row.granted_at,
        withdrawn_at=row.withdrawn_at,
        consent_text=row.consent_text,
    )
