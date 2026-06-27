import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { DiagnosticFeatureApi } from "./features/diagnostics/api";
import { createMockAuthClient } from "./auth/authClient";

function renderApp(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function makeApi(): DiagnosticFeatureApi {
  return {
    listPatients: async () => [],
    listDiagnostics: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    getDiagnostic: async () => {
      throw new Error("Not implemented in shell tests");
    },
    createDiagnostic: async () => {
      throw new Error("Not implemented in shell tests");
    },
    updateDiagnostic: async () => {
      throw new Error("Not implemented in shell tests");
    },
    listPrograms: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    getProgram: async () => {
      throw new Error("Not implemented in shell tests");
    },
    createProgram: async () => {
      throw new Error("Not implemented in shell tests");
    },
    updateProgram: async () => {
      throw new Error("Not implemented in shell tests");
    },
    listProgramExercises: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    assignProgramExercise: async () => {
      throw new Error("Not implemented in shell tests");
    },
    listExercises: async () => [],
    listDoctors: async () => [],
    getMyPatient: async () => ({ id: "patient-1", nombre: "Ana", apellidos: "Garcia" }),
    listMyDiagnostics: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    listMyPrograms: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    getMyProgram: async (programId) => ({ id: programId, diagnostic_id: "diag-1", estado: "active", name: "Mobility plan" }),
    listMyProgramExercises: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    createRecordingUploadUrl: async () => ({ key: "recording.wav", url: "/api/recordings/_local-upload/recording.wav" }),
    uploadRecordingBlob: async () => undefined,
    registerRecording: async () => ({ recording_id: "recording-1" }),
    listExerciseRecordings: async () => [],
    deleteRecording: async () => undefined,
    getRecordingDownloadUrl: async () => "/api/recordings/_local-download/recording.wav",
    runAnalysis: async () => ({ job_id: "job-1", status: "pending" }),
    getRecordingMetrics: async () => ({ function_name: "dysarthria_analysis_v1", metrics: null }),
    listProgramReports: async () => [],
    createReport: async () => ({ exercise_report_id: "rep-1" }),
    getReportDetail: async () => { throw new Error("not implemented"); },
    updateReport: async () => undefined,
    deleteReport: async () => { throw new Error("Delete is not yet supported by the API."); },
    createCheckup: async () => ({ followup_checkup_id: "chk-1" }),
    listProgramCheckups: async () => [],
    getCheckupDetail: async () => { throw new Error("not implemented"); },
    updateCheckup: async () => undefined,
    deleteCheckup: async () => undefined,
  };
}

describe("UC-01 medical access shell", () => {
  it("GIVEN a medical user WHEN opening the UI THEN shows the diagnostic workspace", async () => {
    renderApp(
      <App
        authClient={createMockAuthClient({
          authenticated: true,
          givenName: "Elena",
          familyName: "Marsh",
          roles: ["medical"],
        })}
        diagnosticApi={makeApi()}
      />,
    );

    expect(screen.queryByRole("heading", { name: /doctor diagnostic workspace/i })).not.toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 3, name: /^patients$/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/current session/i)).toHaveTextContent("Dr. Elena Marsh");
  });

  it("GIVEN a medical user WHEN using top-level navigation THEN opens rehab programs", async () => {
    const user = userEvent.setup();
    renderApp(
      <App
        authClient={createMockAuthClient({
          authenticated: true,
          givenName: "Elena",
          familyName: "Marsh",
          roles: ["medical"],
        })}
        diagnosticApi={makeApi()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /rehab programs/i }));

    expect(screen.getByRole("heading", { level: 2, name: /^rehab programs$/i })).toBeInTheDocument();
  });



  it("GIVEN an authenticated user WHEN using the topbar menu THEN can trigger logout", async () => {
    const user = userEvent.setup();
    const logout = vi.fn(async () => undefined);

    renderApp(
      <App
        authClient={{
          ...createMockAuthClient({
            authenticated: true,
            givenName: "Elena",
            familyName: "Marsh",
            roles: ["medical"],
          }),
          logout,
        }}
        diagnosticApi={makeApi()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /dr\. elena marsh/i }));
    await user.click(screen.getByRole("menuitem", { name: /log out/i }));

    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("GIVEN a non-medical user WHEN opening the UI THEN shows access denied", () => {
    renderApp(
      <App
        authClient={createMockAuthClient({
          authenticated: true,
          roles: ["technician"],
        })}
        diagnosticApi={makeApi()}
      />,
    );

    expect(screen.getByRole("heading", { name: /access denied/i })).toBeInTheDocument();
  });

  it("GIVEN a patient user WHEN opening the UI THEN shows the patient portal", async () => {
    const user = userEvent.setup();
    renderApp(
      <App
        authClient={createMockAuthClient({
          authenticated: true,
          givenName: "Ana",
          familyName: "Garcia",
          roles: ["patient"],
        })}
        diagnosticApi={{
          ...makeApi(),
          listMyDiagnostics: async () => ({
            items: [
              {
                id: "diag-1",
                patient_id: "patient-1",
                dolencia: "Shoulder pain",
                descripcion: "Limited mobility",
                signed_at: "2026-06-14T10:00:00Z",
              },
            ],
            total: 1,
            limit: 20,
            offset: 0,
          }),
          listMyPrograms: async () => ({
            items: [{ id: "program-1", diagnostic_id: "diag-1", estado: "active", name: "Mobility plan" }],
            total: 1,
            limit: 20,
            offset: 0,
          }),
          getMyProgram: async () => ({
            id: "program-1",
            diagnostic_id: "diag-1",
            estado: "active",
            name: "Mobility plan",
            start_date: "2026-06-16T00:00:00Z",
          }),
          listMyProgramExercises: async () => ({
            items: [
              {
                id: "assignment-1",
                program_id: "program-1",
                exercise_id: "exercise-1",
                pauta: "2 series daily",
                estado: "active",
              },
            ],
            total: 1,
            limit: 20,
            offset: 0,
          }),
        }}
      />,
    );

    expect(await screen.findByRole("heading", { name: /ana garcia/i })).toBeInTheDocument();
    expect(screen.getAllByText("Shoulder pain").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("link", { name: /mobility plan/i }));

    expect(await screen.findByRole("heading", { name: /mobility plan/i })).toBeInTheDocument();
    expect(screen.getByText(/view exercises and record progress/i)).toBeInTheDocument();
    expect(screen.getAllByText("2 series daily").length).toBeGreaterThan(0);
  });
});
