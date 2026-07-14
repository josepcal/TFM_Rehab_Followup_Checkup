"""Clinical service boundary for the worker's view of a recording.

The worker needs two facts about a recording before it may process it: the patient's
pseudonym, and whether consent is still active. Both answers require walking
``recording → program_exercise → rehab_program → diagnostic`` into ``clinical`` — and the
pseudonym lookup ends on ``clinical.pseudonym_map``, the most sensitive table in the
system.

That walk belongs here, not in the worker. ``ConsentService`` cannot serve this case: it
derives the patient from the JWT identity in ``db.info`` and raises HTTP errors, which is
right for a request but meaningless for a background job. This service answers the same
domain questions from a ``recording_id``, for a caller with no principal.

The session passed in must already hold the ``ftm_worker`` role (``system_session()``);
this service does not widen anyone's access, it only puts the query where the domain is.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clinical.models import Diagnostic, PatientConsent, ProgramExercise, PseudonymMap, RehabProgram
from app.recording.models import ExerciseRecording


class RecordingContextService:
    """Resolves the clinical context of a recording for system (non-HTTP) callers."""

    def __init__(self, db: Session):
        self.db = db

    def _patient_and_program(self, recording_id: UUID):
        """Walk the recording up to its diagnostic. Returns (patient_id, program_id) or None."""
        return self.db.execute(
            select(Diagnostic.patient_id, RehabProgram.id)
            .join(RehabProgram, RehabProgram.diagnostic_id == Diagnostic.id)
            .join(ProgramExercise, ProgramExercise.program_id == RehabProgram.id)
            .join(
                ExerciseRecording,
                ExerciseRecording.program_exercise_id == ProgramExercise.id,
            )
            .where(ExerciseRecording.recording_id == recording_id)
        ).first()

    def pseudonym_for(self, recording_id: UUID) -> UUID | None:
        """Return the patient's pseudonym for a recording, or None if it cannot be resolved.

        This is the only place outside `clinical` that needs `pseudonym_map`; keeping the
        lookup here means the mapping between a patient and their pseudonym is read in one
        auditable spot rather than joined ad hoc from another module.
        """
        context = self._patient_and_program(recording_id)
        if context is None:
            return None
        return self.db.scalar(
            select(PseudonymMap.pseudonym_id).where(
                PseudonymMap.patient_id == context.patient_id
            )
        )

    def has_active_consent(self, recording_id: UUID) -> bool:
        """Return True if the recording's patient still consents to processing.

        ``clinical.patient_consent`` is an append-only trail with no UNIQUE constraint
        (migration 0012 drops it on purpose), so a (patient, programme) pair can hold
        several rows. The current state is therefore the MOST RECENT row, not "any row
        with withdrawn_at IS NULL" — asking the latter lets an orphaned active row (e.g.
        from a duplicate grant) mask a subsequent withdrawal.

        No consent row at all ⇒ no consent (RGPD art. 7.3: withdrawal must be as effective
        as granting, and absence of a grant is not a grant).
        """
        context = self._patient_and_program(recording_id)
        if context is None:
            return False

        latest = self.db.scalar(
            select(PatientConsent)
            .where(PatientConsent.patient_id == context.patient_id)
            .where(PatientConsent.rehab_program_id == context.id)
            .order_by(PatientConsent.granted_at.desc())
            .limit(1)
        )
        return latest is not None and latest.withdrawn_at is None
