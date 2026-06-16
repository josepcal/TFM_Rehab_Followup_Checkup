import type { DiagnosticsApi } from "../../api/diagnostics";
import type { CatalogApi } from "../../api/catalog";
import type { PatientsApi } from "../../api/patients";
import type { ProgramsApi } from "../../api/programs";

export type DiagnosticFeatureApi = DiagnosticsApi & PatientsApi & ProgramsApi & CatalogApi;
