import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DiagnosticOut } from "../../api/diagnostics";
import { ApiError } from "../../api/http";
import type { DiagnosticFeatureApi } from "./api";
import { DiagnosticWorkspace } from "./DiagnosticWorkspace";

const patients = [
  { id: "patient-1", nombre: "Ana", apellidos: "Garcia" },
  { id: "patient-2", nombre: "Luis", apellidos: "Perez" },
];

const diagnostic: DiagnosticOut = {
  id: "diag-1",
  patient_id: "patient-1",
  dolencia: "Shoulder pain",
  descripcion: "Limited range of motion",
  created_at: "2026-06-14T10:00:00Z",
  signature: "attested:diag-1",
  signed_at: "2026-06-14T10:01:00Z",
  content_hash: "abc123",
};

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
    getDiagnostic: async () => diagnostic,
    createDiagnostic: async (body) => ({
      id: "diag-created",
      patient_id: body.patient_id,
      dolencia: body.dolencia,
      descripcion: body.descripcion,
      signature: "attested:diag-created",
      signed_at: "2026-06-14T11:00:00Z",
      content_hash: "created-hash",
    }),
    updateDiagnostic: async (_diagnosticId, body) => ({
      ...diagnostic,
      ...body,
    }),
    ...overrides,
  };
}

describe("UC-01 AC-01 diagnostic history UI", () => {
  it("GIVEN a medical user WHEN selecting a patient THEN displays diagnostic history", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        listDiagnostics: async (params) => ({
          items: [{ ...diagnostic, patient_id: params?.patientId ?? "patient-1" }],
          total: 1,
          limit: 20,
          offset: 0,
        }),
      }),
    );

    await openPatient(user, /ana garcia clinical record/i);

    expect(await screen.findAllByText("Shoulder pain")).toHaveLength(1);
    expect(screen.getByText("Limited range of motion")).toBeInTheDocument();
  });

  it("GIVEN a selected patient with no diagnostics WHEN history loads THEN displays empty state", async () => {
    const user = userEvent.setup();
    renderWorkspace(makeApi());

    await openPatient(user, /luis perez clinical record/i);

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

    await openPatient(user, /ana garcia clinical record/i);

    expect(await screen.findByText(/not authorized/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByLabelText("Diagnostic history")).not.toBeInTheDocument());
  });
});


  it("GIVEN accented patient names WHEN searching without accents or punctuation THEN matches the patient", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        listPatients: async () => [
          { id: "patient-acentos", nombre: "José", apellidos: "García-López" },
          { id: "patient-plain", nombre: "Luis", apellidos: "Perez" },
        ],
      }),
    );

    await user.type(await screen.findByLabelText(/search by name or patient id/i), "jose garcia lopez");

    expect(screen.getByRole("button", { name: /josé garcía-lópez clinical record/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /luis perez clinical record/i })).not.toBeInTheDocument();
  });

describe("UC-01 AC-03 diagnostic create/detail/edit UI", () => {
  it("GIVEN selected patient WHEN creating diagnostic THEN sends patient_id without doctor_id", async () => {
    const user = userEvent.setup();
    const createDiagnostic = vi.fn(makeApi().createDiagnostic);
    renderWorkspace(makeApi({ createDiagnostic }));

    await openPatient(user, /ana garcia clinical record/i);
    await startNewDiagnostic(user);
    await user.type(screen.getByLabelText(/^dolencia$/i), "Knee pain");
    await user.type(screen.getByLabelText(/descripcion/i), "Pain when walking");
    await user.click(screen.getByRole("button", { name: /create diagnostic/i }));

    await waitFor(() => expect(createDiagnostic).toHaveBeenCalled());
    expect(createDiagnostic).toHaveBeenCalledWith({
      patient_id: "patient-1",
      dolencia: "Knee pain",
      descripcion: "Pain when walking",
    });
    expect(JSON.stringify(createDiagnostic.mock.calls[0][0])).not.toContain("doctor_id");
  });

  it("GIVEN empty dolencia WHEN creating diagnostic THEN prevents submission", async () => {
    const user = userEvent.setup();
    const createDiagnostic = vi.fn(makeApi().createDiagnostic);
    renderWorkspace(makeApi({ createDiagnostic }));

    await openPatient(user, /ana garcia clinical record/i);
    await startNewDiagnostic(user);
    expect(screen.getByRole("button", { name: /create diagnostic/i })).toBeDisabled();

    expect(createDiagnostic).not.toHaveBeenCalled();
  });

  it("GIVEN selected diagnostic WHEN opening detail THEN displays attestation metadata", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        listDiagnostics: async () => ({ items: [diagnostic], total: 1, limit: 20, offset: 0 }),
      }),
    );

    await openPatient(user, /ana garcia clinical record/i);
    await user.click(await screen.findByRole("button", { name: /shoulder pain/i }));

    expect((await screen.findAllByLabelText(/diagnostic detail/i)).at(-1)).toHaveTextContent("attested:diag-1");
    expect(screen.getByText("abc123")).toBeInTheDocument();
  });

  it("GIVEN selected diagnostic WHEN editing THEN sends PATCH body and shows updated diagnostic", async () => {
    const user = userEvent.setup();
    const updateDiagnostic = vi.fn(makeApi().updateDiagnostic);
    renderWorkspace(
      makeApi({
        listDiagnostics: async () => ({ items: [diagnostic], total: 1, limit: 20, offset: 0 }),
        updateDiagnostic,
      }),
    );

    await openPatient(user, /ana garcia clinical record/i);
    await user.click(await screen.findByRole("button", { name: /shoulder pain/i }));
    await user.click(await screen.findByRole("button", { name: /edit diagnostic/i }));
    const editForm = await screen.findByRole("form", { name: /edit diagnostic/i });
    const dolenciaInput = withinForm(editForm, /^dolencia$/i);
    await user.clear(dolenciaInput);
    await user.type(dolenciaInput, "Updated shoulder pain");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => expect(updateDiagnostic).toHaveBeenCalled());
    expect(updateDiagnostic).toHaveBeenCalledWith("diag-1", {
      dolencia: "Updated shoulder pain",
      descripcion: "Limited range of motion",
    });
  });

  it("GIVEN missing patient WHEN create returns 404 THEN displays recoverable error", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        createDiagnostic: async () => {
          throw new ApiError("Not found", 404);
        },
      }),
    );

    await openPatient(user, /ana garcia clinical record/i);
    await startNewDiagnostic(user);
    await user.type(screen.getByLabelText(/^dolencia$/i), "Back pain");
    await user.click(screen.getByRole("button", { name: /create diagnostic/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/not found/i);
    expect(screen.getByDisplayValue("Back pain")).toBeInTheDocument();
  });

  it("GIVEN forbidden edit WHEN API returns 403 THEN does not show save success", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        listDiagnostics: async () => ({ items: [diagnostic], total: 1, limit: 20, offset: 0 }),
        updateDiagnostic: async () => {
          throw new ApiError("Forbidden", 403);
        },
      }),
    );

    await openPatient(user, /ana garcia clinical record/i);
    await user.click(await screen.findByRole("button", { name: /shoulder pain/i }));
    await user.click(await screen.findByRole("button", { name: /edit diagnostic/i }));
    await user.click(await screen.findByRole("button", { name: /save changes/i }));

    expect(await screen.findByText(/not authorized/i)).toBeInTheDocument();
  });
});

function withinForm(form: HTMLElement, label: RegExp) {
  return Array.from(form.querySelectorAll("input, textarea")).find((input) => {
    const id = input.getAttribute("id");
    if (!id) {
      return input.previousElementSibling?.textContent?.match(label);
    }
    return form.querySelector(`label[for="${id}"]`)?.textContent?.match(label);
  }) as HTMLInputElement | HTMLTextAreaElement;
}


async function openPatient(user: ReturnType<typeof userEvent.setup>, name: RegExp) {
  await user.click(await screen.findByRole("button", { name }));
}

async function startNewDiagnostic(user: ReturnType<typeof userEvent.setup>) {
  await user.click((await screen.findAllByRole("button", { name: /new diagnostic|create first diagnostic/i }))[0]);
}
