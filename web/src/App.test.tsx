import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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
  };
}

describe("UC-01 medical access shell", () => {
  it("GIVEN a medical user WHEN opening the UI THEN shows the diagnostic workspace", () => {
    renderApp(<App authClient={createMockAuthClient()} diagnosticApi={makeApi()} />);

    expect(screen.getByRole("heading", { name: /doctor diagnostic workspace/i })).toBeInTheDocument();
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
