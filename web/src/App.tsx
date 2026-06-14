import { useMemo } from "react";

import { createDiagnosticsApi } from "./api/diagnostics";
import { createHttpClient } from "./api/http";
import { createPatientsApi } from "./api/patients";
import type { AuthClient } from "./auth/authClient";
import type { DiagnosticFeatureApi } from "./features/diagnostics/api";
import { DiagnosticWorkspace } from "./features/diagnostics/DiagnosticWorkspace";

export type AppProps = {
  authClient: AuthClient;
  diagnosticApi?: DiagnosticFeatureApi;
};

export function App({ authClient, diagnosticApi }: AppProps) {
  const session = authClient.getSession();
  const api = useMemo(
    () => diagnosticApi ?? createDiagnosticFeatureApi(authClient),
    [authClient, diagnosticApi],
  );

  if (!session.authenticated) {
    return (
      <main className="app-shell" aria-labelledby="login-title">
        <h1 id="login-title">FTM Diagnostic UI</h1>
        <p>Please sign in to access the medical diagnostic workspace.</p>
      </main>
    );
  }

  if (!session.roles.includes("medical")) {
    return (
      <main className="app-shell" aria-labelledby="denied-title">
        <h1 id="denied-title">Access denied</h1>
        <p>The UC-01 diagnostic workspace is available only to medical users.</p>
      </main>
    );
  }

  return (
    <main className="app-shell" aria-labelledby="workspace-title">
      <p className="eyebrow">UC-01 · Diagnostic Assessment</p>
      <h1 id="workspace-title">Doctor diagnostic workspace</h1>
      <DiagnosticWorkspace api={api} />
    </main>
  );
}

function createDiagnosticFeatureApi(authClient: AuthClient): DiagnosticFeatureApi {
  const http = createHttpClient({ authClient });

  return {
    ...createPatientsApi(http),
    ...createDiagnosticsApi(http),
  };
}
