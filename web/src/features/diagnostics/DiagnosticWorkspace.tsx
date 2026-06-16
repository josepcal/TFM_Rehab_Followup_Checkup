import { useMemo, useState } from "react";

import type { PatientOut } from "../../api/patients";
import type { DiagnosticFeatureApi } from "./api";
import { DiagnosticDetailCard } from "./components/DiagnosticDetailCard";
import { DiagnosticForm } from "./components/DiagnosticForm";
import { DiagnosticHistoryList } from "./components/DiagnosticHistoryList";
import { PatientSelector } from "./components/PatientSelector";
import {
  useCreateDiagnostic,
  useDiagnosticDetail,
  useDiagnosticHistory,
  usePatients,
  useUpdateDiagnostic,
} from "./hooks";

type DiagnosticWorkspaceProps = {
  api: DiagnosticFeatureApi;
};

export function DiagnosticWorkspace({ api }: DiagnosticWorkspaceProps) {
  const [selectedPatientId, setSelectedPatientId] = useState<string>();
  const [selectedDiagnosticId, setSelectedDiagnosticId] = useState<string>();
  const patientsQuery = usePatients(api);
  const historyQuery = useDiagnosticHistory(api, selectedPatientId);
  const detailQuery = useDiagnosticDetail(api, selectedDiagnosticId);
  const createDiagnostic = useCreateDiagnostic(api);
  const updateDiagnostic = useUpdateDiagnostic(api);
  const patients = patientsQuery.data ?? [];
  const diagnostics = historyQuery.data?.items ?? [];
  const selectedPatient = useMemo(
    () => patients.find((patient) => patient.id === selectedPatientId),
    [patients, selectedPatientId],
  );
  const detailDiagnostic = detailQuery.data;

  function handleSelectPatient(patientId: string) {
    setSelectedPatientId(patientId);
    setSelectedDiagnosticId(undefined);
  }

  return (
    <section aria-labelledby="diagnostic-workspace-title" className="workspace-grid">
      <header className="workspace-intro">
        <div>
          <p className="eyebrow">UC-01 · AC-01 / AC-03</p>
          <h2 id="diagnostic-workspace-title">Patient diagnostic history</h2>
          <p>Select an assigned patient to inspect their diagnostic history.</p>
        </div>
        <div className="stat-strip" aria-label="Workspace summary">
          <div className="stat-card">
            <span className="stat-value">{patients.length}</span>
            <span className="stat-label">Assigned patients</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{diagnostics.length}</span>
            <span className="stat-label">Diagnostics loaded</span>
          </div>
        </div>
      </header>

      <div className="workspace-columns">
        <div className="panel-stack">
          <section className="workspace-panel" aria-label="Patient selection">
            <PatientSelector
              patients={patients}
              selectedPatientId={selectedPatientId}
              isLoading={patientsQuery.isLoading}
              error={patientsQuery.error}
              onSelectPatient={handleSelectPatient}
            />
          </section>

          {selectedPatient ? <PatientSummary patient={selectedPatient} /> : null}

          <DiagnosticHistoryList
            diagnostics={diagnostics}
            selectedDiagnosticId={selectedDiagnosticId}
            onSelectDiagnostic={setSelectedDiagnosticId}
            isLoading={historyQuery.isLoading}
            error={historyQuery.error}
            hasSelectedPatient={Boolean(selectedPatientId)}
          />
        </div>

        <div className="panel-stack">
          {selectedPatientId ? (
            <DiagnosticForm
              title="Create diagnostic"
              submitLabel="Create diagnostic"
              isSubmitting={createDiagnostic.isPending}
              error={createDiagnostic.error}
              onSubmit={(values) => {
                createDiagnostic.mutate(
                  {
                    patient_id: selectedPatientId,
                    dolencia: values.dolencia,
                    descripcion: values.descripcion || null,
                  },
                  { onSuccess: (diagnostic) => setSelectedDiagnosticId(diagnostic.id) },
                );
              }}
            />
          ) : null}

          <DiagnosticDetailCard
            diagnostic={detailDiagnostic}
            isLoading={detailQuery.isLoading}
            error={detailQuery.error}
          />

          {detailDiagnostic ? (
            <DiagnosticForm
              key={detailDiagnostic.id}
              title="Edit diagnostic"
              submitLabel="Save changes"
              initialValues={{
                dolencia: detailDiagnostic.dolencia,
                descripcion: detailDiagnostic.descripcion ?? "",
              }}
              isSubmitting={updateDiagnostic.isPending}
              error={updateDiagnostic.error}
              onSubmit={(values) => {
                updateDiagnostic.mutate({
                  diagnosticId: detailDiagnostic.id,
                  body: {
                    dolencia: values.dolencia,
                    descripcion: values.descripcion || null,
                  },
                });
              }}
            />
          ) : null}
        </div>
      </div>
    </section>
  );
}

function PatientSummary({ patient }: { patient: PatientOut }) {
  return (
    <aside aria-label="Selected patient" className="patient-summary">
      <span className="eyebrow">Selected patient</span>
      <strong>
        {patient.nombre} {patient.apellidos}
      </strong>
      <span>{patient.id}</span>
    </aside>
  );
}
