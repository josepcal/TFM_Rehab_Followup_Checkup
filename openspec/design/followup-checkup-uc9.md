# Design: UC-09 Follow-up Check-up

## Technical Approach

Vertical slice clone of UC-08, targeting `clinical.followup_checkup` + `clinical.followup_checkup_report`. New `api/app/followup/` module isolates the domain; frontend mirrors the `ExerciseReportsPanel` pattern with an added multi-select report picker. Corrective Alembic migration neutralizes the legacy `reporting.followup_checkup` shape.

---

## Architecture Decisions

| Decision | Choice | Rejected | Rationale |
|---|---|---|---|
| Module placement | `api/app/followup/` (new) | Extend `api/app/reporting/` | Reporting is tightly coupled to recordings/metrics. Checkups link to reports, not recordings — different domain boundary. Mirrors how `recording`, `metrics`, `reporting` are each their own module. |
| patient_id derivation | Server-side join `RehabProgram → Diagnostic.patient_id` | Caller-supplied | `RehabProgram` has no direct `patient_id`; caller does not own that information; matches UC-08's `created_by` resolution via `db.info["identity_id"]`. |
| Report selection | Explicit `exercise_report_ids[]` (required, non-empty); UI pre-fills all in-period reports, doctor may deselect | Auto-collect server-side by period | Deterministic; avoids hidden server-side scan whose behaviour changes as new reports are added retrospectively. |
| Cross-program validation | 422 if any `exercise_report_id.rehab_program_id != checkup.rehab_program_id` | Silent ignore or 404 | FR-07 requires same rehab program; 422 is unambiguous contract violation, not a missing resource. |
| Mutability | Full PATCH/DELETE parity with UC-08 | Create+read only | AC-14 requires creation; UC-08 set the precedent for summary edits (PATCH) and cleanup (DELETE). Parity eliminates special-casing in the UI. |
| Legacy table | Corrective migration: rename `reporting.followup_checkup` → `reporting.followup_checkup_legacy`, add comment | DROP immediately | DROP is destructive and irreversible. Rename preserves any existing rows for inspection; `clinical.*` tables are canonical and unaffected. |

---

## Data Flow

### POST /followup-checkups

```
Client → POST /followup-checkups
         body: { rehab_program_id, exercise_report_ids[], period_start, period_end, summary? }
         |
         ├─ require_role("medical") → 403 if not medical
         ├─ _require_medical(principal) → 403 if not GP/specialist
         ├─ Validate period_end >= period_start → 422
         ├─ SELECT RehabProgram WHERE id = rehab_program_id → 404 if missing
         ├─ JOIN Diagnostic → resolve patient_id (NOT NULL guarantee)
         ├─ SELECT Doctor WHERE identity_id = db.info["identity_id"] → resolve created_by
         ├─ Validate each exercise_report_id.rehab_program_id == body.rehab_program_id → 422 on mismatch
         ├─ INSERT clinical.followup_checkup → db.flush() → materialize PK
         ├─ INSERT clinical.followup_checkup_report (one row per report_id)
         └─ return { followup_checkup_id }, 201
```

### GET /programs/{program_id}/followup-checkups

```
Client → GET /programs/{program_id}/followup-checkups
         |
         ├─ require_role("medical", "patient")
         ├─ _require_not_technician → 403
         ├─ Aggregate SELECT: checkup fields + report_count via outerjoin + doctor name
         │  WHERE followup_checkup.rehab_program_id = program_id
         │  (RLS fchk_staff / fchk_self filters transparently)
         └─ return list[CheckupListItem], 200
```

### GET /followup-checkups/{id}

```
Client → GET /followup-checkups/{id}
         ├─ require_role("medical", "patient") + _require_not_technician
         ├─ SELECT FollowupCheckup WHERE id = id → None → 404
         ├─ SELECT linked ExerciseReport rows via followup_checkup_report
         └─ return CheckupDetailOut (header + reports[]), 200
```

### PATCH /followup-checkups/{id}

```
Client → PATCH /followup-checkups/{id}   body: { summary }
         ├─ require_role("medical") + _require_medical
         ├─ SELECT FollowupCheckup → 404 if missing
         ├─ report.summary = body.summary
         └─ 204
```

### DELETE /followup-checkups/{id}

```
Client → DELETE /followup-checkups/{id}
         ├─ require_role("medical") + _require_medical
         ├─ SELECT FollowupCheckup → 404 if missing
         ├─ db.delete(checkup)  (cascade removes followup_checkup_report rows via DB ON DELETE CASCADE)
         └─ 204
```

---

## Backend Module Structure

### `api/app/followup/models.py`

```python
CLINICAL = "clinical"

class FollowupCheckup(Base):
    __tablename__ = "followup_checkup"
    __table_args__ = {"schema": CLINICAL}

    followup_checkup_id = Column(UUID(as_uuid=True), primary_key=True,
                                  server_default=text("gen_random_uuid()"))
    rehab_program_id    = Column(UUID(as_uuid=True),
                                  ForeignKey(f"{CLINICAL}.rehab_program.rehab_program_id"),
                                  nullable=False)
    patient_id          = Column(UUID(as_uuid=True), nullable=False)      # derived, NOT caller-supplied
    period_start        = Column(Date, nullable=False)
    period_end          = Column(Date, nullable=False)
    summary             = Column(Text, nullable=True)
    created_by          = Column(UUID(as_uuid=True),
                                  ForeignKey(f"{CLINICAL}.doctor.doctor_id"), nullable=True)
    created_at          = Column(DateTime(timezone=True), nullable=False,
                                  server_default=text("now()"))


class FollowupCheckupReport(Base):
    __tablename__ = "followup_checkup_report"
    __table_args__ = (
        PrimaryKeyConstraint("followup_checkup_id", "exercise_report_id"),
        {"schema": CLINICAL},
    )

    followup_checkup_id  = Column(UUID(as_uuid=True),
                                   ForeignKey(f"{CLINICAL}.followup_checkup.followup_checkup_id",
                                              ondelete="CASCADE"), nullable=False)
    exercise_report_id   = Column(UUID(as_uuid=True),
                                   ForeignKey(f"{CLINICAL}.exercise_report.exercise_report_id"),
                                   nullable=False)
```

The `patient_id` column is populated by the router after resolving `RehabProgram → Diagnostic.patient_id`; it is never accepted from the request body.

### `api/app/followup/schemas.py`

```python
class CheckupIn(BaseModel):
    rehab_program_id: uuid.UUID
    exercise_report_ids: list[uuid.UUID]
    period_start: date
    period_end: date
    summary: str | None = None

    @field_validator("exercise_report_ids")
    @classmethod
    def report_ids_not_empty(cls, v): ...  # at least one entry

    @model_validator(mode="after")
    def period_end_not_before_start(self): ...  # period_end >= period_start

class CheckupCreatedOut(BaseModel):
    followup_checkup_id: uuid.UUID

class CheckupListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    followup_checkup_id: uuid.UUID
    rehab_program_id: uuid.UUID
    period_start: date
    period_end: date
    summary: str | None
    created_by: uuid.UUID | None
    created_by_name: str | None
    report_count: int

class CheckupPatchIn(BaseModel):
    summary: str | None = None

class LinkedReportItem(BaseModel):
    exercise_report_id: uuid.UUID
    period_start: date
    period_end: date
    summary: str | None

class CheckupDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    followup_checkup_id: uuid.UUID
    rehab_program_id: uuid.UUID
    period_start: date
    period_end: date
    summary: str | None
    created_by: uuid.UUID | None
    reports: list[LinkedReportItem]
```

### `api/app/followup/router.py`

Router tag: `"followup"`. All five endpoints follow the same guards pattern as `reporting/router.py`. Cross-program validation logic:

```python
# After resolving RehabProgram, before inserting:
for report_id in body.exercise_report_ids:
    report = db.scalar(select(ExerciseReport).where(ExerciseReport.exercise_report_id == report_id))
    if report is None:
        raise HTTPException(404, f"exercise_report {report_id} not found")
    if report.rehab_program_id != body.rehab_program_id:
        raise HTTPException(422, f"exercise_report {report_id} does not belong to program {body.rehab_program_id}")
```

Patient resolution:

```python
from app.clinical.models import RehabProgram, Diagnostic

program = db.scalar(select(RehabProgram).where(RehabProgram.rehab_program_id == body.rehab_program_id))
if program is None:
    raise HTTPException(404, "rehab_program not found")
diagnostic = db.scalar(select(Diagnostic).where(Diagnostic.id == program.diagnostic_id))
patient_id = diagnostic.patient_id
```

### `api/app/main.py` change

```python
from app.followup.router import router as followup_router
# ...
for r in (..., reporting_router, followup_router):
    app.include_router(r)
```

---

## Migration Plan

### Corrective migration `0002_followup_clinical.py`

```python
def upgrade():
    # Neutralize legacy shape — do NOT DROP (data may exist)
    op.execute("""
        ALTER TABLE IF EXISTS reporting.followup_checkup
            RENAME TO followup_checkup_legacy;
        COMMENT ON TABLE reporting.followup_checkup_legacy
            IS 'Obsolete shape (uuid[], reporting schema). Superseded by clinical.followup_checkup + clinical.followup_checkup_report.';
    """)
    # clinical.followup_checkup and clinical.followup_checkup_report already exist
    # in the canonical DDL (bbdd_dev_setup/alembic/migrations/ftm_schema.sql).
    # This migration only ensures the API Alembic env knows about them.
    # No CREATE TABLE needed if the dev DB was initialized from the canonical DDL.

def downgrade():
    op.execute("""
        ALTER TABLE IF EXISTS reporting.followup_checkup_legacy
            RENAME TO followup_checkup;
    """)
```

The migration is idempotent: if `reporting.followup_checkup` does not exist (e.g., already renamed or never deployed), the `IF EXISTS` guard makes it a no-op.

---

## Frontend Module Structure

### `web/src/api/followupCheckups.ts`

```typescript
export type CheckupIn = {
  rehab_program_id: string;
  exercise_report_ids: string[];
  period_start: string;
  period_end: string;
  summary?: string | null;
};

export type CheckupListItem = {
  followup_checkup_id: string;
  rehab_program_id: string;
  period_start: string;
  period_end: string;
  summary?: string | null;
  created_by?: string | null;
  created_by_name?: string | null;
  report_count: number;
};

export type LinkedReportItem = {
  exercise_report_id: string;
  period_start: string;
  period_end: string;
  summary?: string | null;
};

export type CheckupDetailOut = Omit<CheckupListItem, "report_count"> & {
  reports: LinkedReportItem[];
};

export type FollowupCheckupsApi = {
  createCheckup: (body: CheckupIn) => Promise<{ followup_checkup_id: string }>;
  listProgramCheckups: (programId: string) => Promise<CheckupListItem[]>;
  getCheckupDetail: (checkupId: string) => Promise<CheckupDetailOut>;
  updateCheckup: (checkupId: string, summary: string) => Promise<void>;
  deleteCheckup: (checkupId: string) => Promise<void>;
};

export function createFollowupCheckupsApi(http: HttpClient): FollowupCheckupsApi { ... }
```

### `web/src/features/diagnostics/api.ts` change

```typescript
import type { FollowupCheckupsApi } from "../../api/followupCheckups";

export type DiagnosticFeatureApi = DiagnosticsApi & PatientsApi & ProgramsApi
  & CatalogApi & DoctorsApi & PatientPortalApi & RecordingsApi & AnalysisApi
  & ReportsApi & FollowupCheckupsApi;  // ← add intersection
```

### `web/src/features/diagnostics/hooks.ts` additions

```typescript
// Query keys: ["followup-checkups", programId] and ["followup-checkups", "detail", checkupId]

export function useProgramCheckups(api, programId?) { ... }
export function useCheckupDetail(api, checkupId?) { ... }
export function useCreateCheckup(api, programId) {
  // onSuccess: invalidate ["followup-checkups", programId]
}
// No dedicated useUpdateCheckup / useDeleteCheckup hooks needed —
// ExerciseReportsPanel uses direct api.* calls with manual invalidation; mirror that pattern.
```

### `web/src/features/diagnostics/components/FollowupCheckupPanel.tsx`

Component structure mirrors `ExerciseReportsPanel`:

- Props: `{ api: DiagnosticFeatureApi; programId: string }`
- State: `showCreateForm`, `periodStart`, `periodEnd`, `selectedReportIds: string[]`, `summary`, `formError`, `editingCheckupId`, `editingSummary`, `expandedCheckupId`, `deleteError`, `saveError`
- On mount / period change: fetch `api.listProgramReports(programId)` to populate the multi-select picker; pre-select all reports whose dates fall within `[periodStart, periodEnd]`
- Create form fields: period start (date), period end (date), multi-select of available exercise reports (checkbox list showing `period_start`–`period_end` and `recording_count`), optional summary textarea
- List: `CheckupCard` sub-component (same shape as `ReportCard`) with toggle-expand for linked report list, edit-summary inline, delete with confirm dialog
- All CSS uses existing `.detail-card`, `.v0-outline-button`, `.ghost-button`, `.form-grid-2`, `.field` classes — no new styles

### `web/src/features/diagnostics/components/RehabProgramPanel.tsx` change

```tsx
// Add alongside ExerciseReportsPanel toggle:
const [showCheckups, setShowCheckups] = useState(false);

<button type="button" className="v0-outline-button"
  onClick={() => setShowCheckups((v) => !v)}>
  {showCheckups ? "Hide Follow-up Check-ups" : "Show Follow-up Check-ups"}
</button>
{showCheckups ? <FollowupCheckupPanel programId={program.id} api={api} /> : null}
```

Import: `import { FollowupCheckupPanel } from "./FollowupCheckupPanel";`

---

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `api/app/followup/__init__.py` | Create | Empty package marker |
| `api/app/followup/models.py` | Create | `FollowupCheckup` + `FollowupCheckupReport` ORM |
| `api/app/followup/schemas.py` | Create | Pydantic v2 In/Out models with validators |
| `api/app/followup/router.py` | Create | 5 endpoints + `_require_medical` / `_require_not_technician` guards |
| `api/app/main.py` | Modify | Register `followup_router` |
| `api/migrations/versions/0002_followup_clinical.py` | Create | Rename legacy `reporting.followup_checkup` |
| `web/src/api/followupCheckups.ts` | Create | Typed API factory |
| `web/src/features/diagnostics/api.ts` | Modify | Add `FollowupCheckupsApi` to `DiagnosticFeatureApi` |
| `web/src/features/diagnostics/hooks.ts` | Modify | Add `useProgramCheckups`, `useCheckupDetail`, `useCreateCheckup` |
| `web/src/features/diagnostics/components/FollowupCheckupPanel.tsx` | Create | Panel with create form, list, summary edit |
| `web/src/features/diagnostics/components/RehabProgramPanel.tsx` | Modify | Mount `FollowupCheckupPanel` toggle |
| `api/tests/test_followup.py` | Create | Full endpoint test suite |

---

## Testing Strategy

Mirror `api/tests/test_reporting.py` structure exactly.

| Layer | What to Test | Approach |
|-------|-------------|----------|
| POST /followup-checkups | 201 created, patient_id derived correctly | pytest with test DB; assert `followup_checkup.patient_id == diagnostic.patient_id` |
| POST /followup-checkups | 422 on invalid period | body with `period_end < period_start` |
| POST /followup-checkups | 422 on cross-program report | report belonging to a different program |
| POST /followup-checkups | 403 on non-medical role | patient/technician token |
| POST /followup-checkups | 404 on unknown program | non-existent `rehab_program_id` |
| GET /programs/{id}/followup-checkups | 200 list with report_count | two checkups for same program |
| GET /programs/{id}/followup-checkups | 403 technician | technician token |
| GET /followup-checkups/{id} | 200 full detail with linked reports | checkup with two reports |
| GET /followup-checkups/{id} | 404 not found | non-existent id |
| PATCH /followup-checkups/{id} | 204 updates summary | verify row after patch |
| PATCH /followup-checkups/{id} | 403 non-medical | patient token |
| DELETE /followup-checkups/{id} | 204, cascade removes link rows | verify `followup_checkup_report` is empty after delete |
| DELETE /followup-checkups/{id} | 403 non-medical | patient token |
| Unit | `period_end_not_before_start` validator | Pydantic model instantiation |
| Unit | `report_ids_not_empty` validator | Pydantic model instantiation |

---

## Open Questions

- [ ] Confirm that `clinical.followup_checkup` and `clinical.followup_checkup_report` exist in the live migration target DB before writing the corrective migration (required before `sdd-apply`).

## Resolved During Design

- **RehabProgram column name**: `api/app/clinical/models.py` exposes `RehabProgram.id` (Python attribute) mapped to DB column `rehab_program_id`. Router code must use `program.id` to get the UUID, and pass it as the FK value. `program.diagnostic_id` is the direct FK into `Diagnostic`.
- **Diagnostic.patient_id**: `Diagnostic` in `api/app/clinical/models.py` has `patient_id` as a direct column — the two-hop join is `RehabProgram.diagnostic_id → Diagnostic.id → Diagnostic.patient_id`.
