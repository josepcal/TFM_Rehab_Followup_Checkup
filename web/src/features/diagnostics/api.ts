import type { ConsentApi } from "../../api/consent";
import type { DiagnosticsApi } from "../../api/diagnostics";
import type { CatalogApi } from "../../api/catalog";
import type { DoctorsApi } from "../../api/doctors";
import type { FollowupCheckupsApi } from "../../api/followupCheckups";
import type { NormsApi } from "../../api/norms";
import type { PatientPortalApi } from "../../api/patientPortal";
import type { PatientsApi } from "../../api/patients";
import type { ProgramsApi } from "../../api/programs";
import type { AnalysisApi, RecordingsApi } from "../../api/recordings";
import type { ReportsApi } from "../../api/reports";

export type DiagnosticFeatureApi = DiagnosticsApi & PatientsApi & ProgramsApi & CatalogApi & DoctorsApi & PatientPortalApi & RecordingsApi & AnalysisApi & ReportsApi & FollowupCheckupsApi & NormsApi & ConsentApi;
