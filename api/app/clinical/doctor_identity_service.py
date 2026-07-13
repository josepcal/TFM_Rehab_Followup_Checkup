from uuid import UUID

from sqlalchemy import select

from app.clinical.models import Doctor


class DoctorIdentityService:
    """Clinical service boundary for resolving the authenticated doctor.

    Modules outside `clinical` must not query `clinical.doctor` directly; they
    resolve the acting doctor through this service.
    """

    def __init__(self, db):
        self.db = db

    def current_doctor_id(self) -> UUID | None:
        """Return the doctor id bound to the request identity, if any.

        Returns None when the request has no identity bound (RLS context not
        established) or when the identity is not registered as a doctor.
        """
        identity_id = self.db.info.get("identity_id")
        if identity_id is None:
            return None
        return self.db.scalar(
            select(Doctor.id).where(Doctor.identity_id == UUID(str(identity_id)))
        )
