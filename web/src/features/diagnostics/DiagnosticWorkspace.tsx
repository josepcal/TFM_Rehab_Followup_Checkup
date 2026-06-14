import { useMemo, useState } from "react";

import type { PatientOut } from "../../api/patients";
import type { DiagnosticFeatureApi } from "./api";
import { DiagnosticHistoryList } from "./components/DiagnosticHistoryList";
import { PatientSelector } from "./components/PatientSelector";
import { useDiagnosticHistory, usePatients } from "./hooks";

type DiagnosticWorkspaceProps = {
  api: DiagnosticFeatureApi;
};

export function DiagnosticWorkspace({ api }: DiagnosticWorkspaceProps) {
  const [selectedPatientId, setSelectedPatientId] = useState<string>();
  const patientsQuery = usePatients(api);
  const historyQuery = useDiagnosticHistory(api, selectedPatientId);
  const patients = patientsQuery.data ?? [];
  const selectedPatient = useMemo(
    () => patients.find((patient) => patient.id === selectedPatientId),
    [patients, selectedPatientId],
  );

  return (
    <section aria-labelledby="diagnostic-workspace-title" className="workspace-grid">
      <header>
        <p className="eyebrow">UC-01 · AC-01</p>
        <h2 id="diagnostic-workspace-title">Patient diagnostic history</h2>
        <p>Select an assigned patient to inspect their diagnostic history.</p>
      </header>

      <PatientSelector
        patients={patients}
        selectedPatientId={selectedPatientId}
        isLoading={patientsQuery.isLoading}
        error={patientsQuery.error}
        onSelectPatient={setSelectedPatientId}
      />

      {selectedPatient ? <PatientSummary patient={selectedPatient} /> : null}

      <DiagnosticHistoryList
        diagnostics={historyQuery.data?.items ?? []}
        isLoading={historyQuery.isLoading}
        error={historyQuery.error}
        hasSelectedPatient={Boolean(selectedPatientId)}
      />
    </section>
  );
}

function PatientSummary({ patient }: { patient: PatientOut }) {
  return (
    <aside aria-label="Selected patient" className="patient-summary">
      <strong>
        {patient.nombre} {patient.apellidos}
      </strong>
      <span>{patient.id}</span>
    </aside>
  );
}
