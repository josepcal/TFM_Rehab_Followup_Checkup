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
        <AppTopbar userLabel="Guest" />
        <section className="hero-card">
          <p className="eyebrow">Secure clinical workspace</p>
          <h1 id="login-title">FTM Diagnostic UI</h1>
          <p className="muted">Please sign in to access the medical diagnostic workspace.</p>
        </section>
      </main>
    );
  }

  if (!session.roles.includes("medical")) {
    return (
      <main className="app-shell" aria-labelledby="denied-title">
        <AppTopbar userLabel="Signed in" />
        <section className="hero-card">
          <p className="eyebrow">Role protected area</p>
          <h1 id="denied-title">Access denied</h1>
          <p className="muted">The UC-01 diagnostic workspace is available only to medical users.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell" aria-labelledby="workspace-title">
      <AppTopbar userLabel="Medical user" />
      <section className="hero-card">
        <p className="eyebrow">UC-01 · Diagnostic Assessment</p>
        <h1 id="workspace-title">Doctor diagnostic workspace</h1>
        <p className="muted">
          Select an assigned patient, review their diagnostic history and create or attest a new
          clinical assessment.
        </p>
      </section>
      <DiagnosticWorkspace api={api} />
    </main>
  );
}

function AppTopbar({ userLabel }: { userLabel: string }) {
  return (
    <header className="app-topbar" aria-label="FTM application header">
      <div className="brand-lockup">
        <span className="brand-mark" aria-hidden="true">
          F
        </span>
        <div className="brand-text">
          <span className="brand-title">FTM Rehab</span>
          <span className="brand-subtitle">Follow-up Check-up Tool</span>
        </div>
      </div>
      <div className="user-chip" aria-label="Current session">
        <span className="avatar-mark" aria-hidden="true">
          MD
        </span>
        <span>{userLabel}</span>
      </div>
    </header>
  );
}

function createDiagnosticFeatureApi(authClient: AuthClient): DiagnosticFeatureApi {
  const http = createHttpClient({ authClient });

  return {
    ...createPatientsApi(http),
    ...createDiagnosticsApi(http),
  };
}
