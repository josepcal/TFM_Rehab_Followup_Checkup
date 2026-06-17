import { useMemo, useState } from "react";

import type { DiagnosticFeatureApi } from "./api";
import { DiagnosticDetailCard } from "./components/DiagnosticDetailCard";
import { DiagnosticForm } from "./components/DiagnosticForm";
import { PatientDiagnosticRecord } from "./components/PatientDiagnosticRecord";
import { PatientRegistryTable } from "./components/PatientRegistryTable";
import { RehabProgramForm } from "./components/RehabProgramForm";
import { RehabProgramPanel } from "./components/RehabProgramPanel";
import {
  useCreateProgram,
  useCreateDiagnostic,
  useDiagnosticDetail,
  useDiagnosticHistory,
  usePatients,
  useUpdateDiagnostic,
} from "./hooks";

type DiagnosticWorkspaceProps = {
  api: DiagnosticFeatureApi;
  mode?: "diagnostics" | "programs";
};

type PatientScreen = "record" | "create" | "detail" | "edit" | "program-create";

export function DiagnosticWorkspace({ api, mode = "diagnostics" }: DiagnosticWorkspaceProps) {
  const [selectedPatientId, setSelectedPatientId] = useState<string>();
  const [selectedDiagnosticId, setSelectedDiagnosticId] = useState<string>();
  const [selectedProgramId, setSelectedProgramId] = useState<string>();
  const [patientScreen, setPatientScreen] = useState<PatientScreen>("record");
  const patientsQuery = usePatients(api);
  const historyQuery = useDiagnosticHistory(api, selectedPatientId);
  const detailQuery = useDiagnosticDetail(api, selectedDiagnosticId);
  const createDiagnostic = useCreateDiagnostic(api);
  const updateDiagnostic = useUpdateDiagnostic(api);
  const createProgram = useCreateProgram(api);
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
    setSelectedProgramId(undefined);
    setPatientScreen("record");
  }

  function handleBackToPatients() {
    setSelectedPatientId(undefined);
    setSelectedDiagnosticId(undefined);
    setSelectedProgramId(undefined);
    setPatientScreen("record");
  }

  function handleSelectDiagnostic(diagnosticId: string) {
    setSelectedDiagnosticId(diagnosticId);
    setSelectedProgramId(undefined);
    setPatientScreen("detail");
  }

  function handleBackToRecord() {
    setPatientScreen("record");
  }

  return (
    <section
      aria-label={mode === "diagnostics" ? "Patient registry workspace" : undefined}
      aria-labelledby={mode === "programs" ? "diagnostic-workspace-title" : undefined}
      className="workspace-grid"
    >
      {mode === "programs" ? (
        <header className="workspace-intro">
          <div>
            <p className="eyebrow">UC-02 · AC-04 / AC-06</p>
            <h2 id="diagnostic-workspace-title">Rehab programs</h2>
            <p>Search rehabilitation programs visible to the authenticated doctor.</p>
          </div>
        </header>
      ) : null}

      {mode === "programs" ? (
        <RehabProgramPanel
          api={api}
          selectedProgramId={selectedProgramId}
          title="Rehab programs"
          description="Doctor-wide rehabilitation programs. Open one to inspect its setup metadata."
          onSelectProgram={setSelectedProgramId}
        />
      ) : null}

      {mode === "diagnostics" && !selectedPatientId ? (
        <PatientRegistryTable
          patients={patients}
          selectedPatientId={selectedPatientId}
          selectedPatientDiagnosticCount={diagnostics.length}
          totalPatients={patients.length}
          totalDiagnostics={diagnostics.length}
          isLoading={patientsQuery.isLoading}
          error={patientsQuery.error}
          onOpenPatient={handleSelectPatient}
        />
      ) : null}

      {mode === "diagnostics" && selectedPatientId && patientScreen === "record" ? (
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

      {mode === "diagnostics" && selectedPatientId && patientScreen === "create" ? (
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

      {mode === "diagnostics" && selectedPatientId && patientScreen === "detail" ? (
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
          {detailDiagnostic ? (
            <RehabProgramPanel
              api={api}
              diagnosticId={detailDiagnostic.id}
              patientId={selectedPatientId}
              selectedProgramId={selectedProgramId}
              title="Rehab programs"
              description="Programs linked to this diagnostic."
              onSelectProgram={setSelectedProgramId}
              onCreateProgram={() => setPatientScreen("program-create")}
            />
          ) : null}
        </section>
      ) : null}

      {mode === "diagnostics" && selectedPatientId && patientScreen === "edit" && detailDiagnostic ? (
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

      {mode === "diagnostics" && selectedPatientId && patientScreen === "program-create" && detailDiagnostic ? (
        <section className="diagnostic-screen" aria-label="Create rehab program screen">
          <button type="button" className="back-link-button" onClick={() => setPatientScreen("detail")}>
            ← Diagnostic detail
          </button>
          <RehabProgramForm
            isSubmitting={createProgram.isPending}
            error={createProgram.error}
            onSubmit={(values) => {
              createProgram.mutate(
                {
                  diagnostic_id: detailDiagnostic.id,
                  estado: values.estado,
                  name: values.name,
                  start_date: values.start_date,
                  end_date: values.end_date,
                },
                {
                  onSuccess: (program) => {
                    setSelectedProgramId(program.id);
                    setPatientScreen("detail");
                  },
                },
              );
            }}
          />
        </section>
      ) : null}
    </section>
  );
}
