import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ApiError } from "../../api/http";
import type { DiagnosticFeatureApi } from "./api";
import { DiagnosticWorkspace } from "./DiagnosticWorkspace";

const patients = [
  { id: "patient-1", nombre: "Ana", apellidos: "Garcia" },
  { id: "patient-2", nombre: "Luis", apellidos: "Perez" },
];

function renderWorkspace(api: DiagnosticFeatureApi) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <DiagnosticWorkspace api={api} />
    </QueryClientProvider>,
  );
}

function makeApi(overrides: Partial<DiagnosticFeatureApi> = {}): DiagnosticFeatureApi {
  return {
    listPatients: async () => patients,
    listDiagnostics: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    getDiagnostic: async () => {
      throw new Error("Not implemented in AC-01 tests");
    },
    createDiagnostic: async () => {
      throw new Error("Not implemented in AC-01 tests");
    },
    updateDiagnostic: async () => {
      throw new Error("Not implemented in AC-01 tests");
    },
    ...overrides,
  };
}

describe("UC-01 AC-01 diagnostic history UI", () => {
  it("GIVEN a medical user WHEN selecting a patient THEN displays diagnostic history", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        listDiagnostics: async (params) => ({
          items: [
            {
              id: "diag-1",
              patient_id: params?.patientId ?? "patient-1",
              dolencia: "Shoulder pain",
              descripcion: "Limited range of motion",
              created_at: "2026-06-14T10:00:00Z",
            },
          ],
          total: 1,
          limit: 20,
          offset: 0,
        }),
      }),
    );

    await user.selectOptions(await screen.findByLabelText(/select patient/i), "patient-1");

    expect(await screen.findByText("Shoulder pain")).toBeInTheDocument();
    expect(screen.getByText("Limited range of motion")).toBeInTheDocument();
  });

  it("GIVEN a selected patient with no diagnostics WHEN history loads THEN displays empty state", async () => {
    const user = userEvent.setup();
    renderWorkspace(makeApi());

    await user.selectOptions(await screen.findByLabelText(/select patient/i), "patient-2");

    expect(await screen.findByText(/no diagnostics exist/i)).toBeInTheDocument();
  });

  it("GIVEN forbidden history WHEN API returns 403 THEN clears stale records and shows auth error", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        listDiagnostics: async () => {
          throw new ApiError("Forbidden", 403);
        },
      }),
    );

    await user.selectOptions(await screen.findByLabelText(/select patient/i), "patient-1");

    expect(await screen.findByRole("alert")).toHaveTextContent(/not authorized/i);
    await waitFor(() => expect(screen.queryByLabelText("Diagnostic history")).not.toBeInTheDocument());
  });
});
