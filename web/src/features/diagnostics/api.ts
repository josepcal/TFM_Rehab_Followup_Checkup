import type { DiagnosticsApi } from "../../api/diagnostics";
import type { PatientsApi } from "../../api/patients";

export type DiagnosticFeatureApi = DiagnosticsApi & PatientsApi;
