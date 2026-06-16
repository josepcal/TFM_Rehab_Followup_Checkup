import { useMemo, useState } from "react";

import type { DiagnosticFeatureApi } from "./api";
import { DiagnosticDetailCard } from "./components/DiagnosticDetailCard";
import { DiagnosticForm } from "./components/DiagnosticForm";
import { PatientDiagnosticRecord } from "./components/PatientDiagnosticRecord";
import { PatientRegistryTable } from "./components/PatientRegistryTable";
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

type PatientScreen = "record" | "create" | "detail" | "edit";

export function DiagnosticWorkspace({ api }: DiagnosticWorkspaceProps) {
  const [selectedPatientId, setSelectedPatientId] = useState<string>();
  const [selectedDiagnosticId, setSelectedDiagnosticId] = useState<string>();
  const [patientScreen, setPatientScreen] = useState<PatientScreen>("record");
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
    setPatientScreen("record");
  }

  function handleBackToPatients() {
    setSelectedPatientId(undefined);
    setSelectedDiagnosticId(undefined);
    setPatientScreen("record");
  }

  function handleSelectDiagnostic(diagnosticId: string) {
    setSelectedDiagnosticId(diagnosticId);
    setPatientScreen("detail");
  }

  function handleBackToRecord() {
    setPatientScreen("record");
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

      {!selectedPatientId ? (
        <PatientRegistryTable
          patients={patients}
          selectedPatientId={selectedPatientId}
          selectedPatientDiagnosticCount={diagnostics.length}
          isLoading={patientsQuery.isLoading}
          error={patientsQuery.error}
          onOpenPatient={handleSelectPatient}
        />
      ) : null}

      {selectedPatientId && patientScreen === "record" ? (
        <PatientDiagnosticRecord
          patient={selectedPatient}
          diagnostics={diagnostics}
          selectedDiagnosticId={selectedDiagnosticId}
          onSelectDiagnostic={handleSelectDiagnostic}
          onBackToPatients={handleBackToPatients}
          onStartNewDiagnostic={() => setPatientScreen("create")}
          isLoading={historyQuery.isLoading}
          error={historyQuery.error}
          hasSelectedPatient={Boolean(selectedPatientId)}
        />
      ) : null}

      {selectedPatientId && patientScreen === "create" ? (
        <section className="diagnostic-screen" aria-label="Create diagnostic screen">
          <button type="button" className="back-link-button" onClick={handleBackToRecord}>
            ← {selectedPatient ? `${selectedPatient.nombre} ${selectedPatient.apellidos}` : "Patient"}
          </button>
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
                {
                  onSuccess: (diagnostic) => {
                    setSelectedDiagnosticId(diagnostic.id);
                    setPatientScreen("detail");
                  },
                },
              );
            }}
          />
        </section>
      ) : null}

      {selectedPatientId && patientScreen === "detail" ? (
        <section className="diagnostic-screen" aria-label="Diagnostic detail screen">
          <button type="button" className="back-link-button" onClick={handleBackToRecord}>
            ← {selectedPatient ? `${selectedPatient.nombre} ${selectedPatient.apellidos}` : "Patient"}
          </button>
          <div className="diagnostic-screen-actions">
            <button
              type="button"
              className="secondary-button"
              disabled={!detailDiagnostic}
              onClick={() => setPatientScreen("edit")}
            >
              Edit diagnostic
            </button>
          </div>
          <DiagnosticDetailCard
            diagnostic={detailDiagnostic}
            isLoading={detailQuery.isLoading}
            error={detailQuery.error}
          />
        </section>
      ) : null}

      {selectedPatientId && patientScreen === "edit" && detailDiagnostic ? (
        <section className="diagnostic-screen" aria-label="Edit diagnostic screen">
          <button type="button" className="back-link-button" onClick={() => setPatientScreen("detail")}>
            ← Diagnostic detail
          </button>
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
              updateDiagnostic.mutate(
                {
                  diagnosticId: detailDiagnostic.id,
                  body: {
                    dolencia: values.dolencia,
                    descripcion: values.descripcion || null,
                  },
                },
                { onSuccess: () => setPatientScreen("detail") },
              );
            }}
          />
        </section>
      ) : null}
    </section>
  );
}
