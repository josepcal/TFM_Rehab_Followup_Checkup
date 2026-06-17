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
          roles: ["patient"],
        })}
        diagnosticApi={makeApi()}
      />,
    );

    expect(screen.getByRole("heading", { name: /access denied/i })).toBeInTheDocument();
  });
});
