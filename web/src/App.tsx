import { useMemo, useState } from "react";

import { createDiagnosticsApi } from "./api/diagnostics";
import { createCatalogApi } from "./api/catalog";
import { createHttpClient } from "./api/http";
import { createPatientsApi } from "./api/patients";
import { createProgramsApi } from "./api/programs";
import type { AuthClient } from "./auth/authClient";
import type { DiagnosticFeatureApi } from "./features/diagnostics/api";
import { DiagnosticWorkspace } from "./features/diagnostics/DiagnosticWorkspace";

export type AppProps = {
  authClient: AuthClient;
  diagnosticApi?: DiagnosticFeatureApi;
};

export function App({ authClient, diagnosticApi }: AppProps) {
  const session = authClient.getSession();
  const [activeWorkspace, setActiveWorkspace] = useState<"diagnostics" | "programs">("diagnostics");
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
        <AppTopbar userLabel={getUserLabel(session, "Signed in")} onLogout={authClient.logout} />
        <section className="hero-card">
          <p className="eyebrow">Role protected area</p>
          <h1 id="denied-title">Access denied</h1>
          <p className="muted">The UC-01 diagnostic workspace is available only to medical users.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell" aria-label="Clinical workspace">
      <AppTopbar userLabel={getUserLabel(session, "Medical user")} onLogout={authClient.logout} />
      <nav className="workspace-tabs" aria-label="Clinical workspace navigation">
        <button
          type="button"
          className={activeWorkspace === "diagnostics" ? "workspace-tab active" : "workspace-tab"}
          aria-pressed={activeWorkspace === "diagnostics"}
          onClick={() => setActiveWorkspace("diagnostics")}
        >
          Diagnostics
        </button>
        <button
          type="button"
          className={activeWorkspace === "programs" ? "workspace-tab active" : "workspace-tab"}
          aria-pressed={activeWorkspace === "programs"}
          onClick={() => setActiveWorkspace("programs")}
        >
          Rehab programs
        </button>
      </nav>
      <DiagnosticWorkspace api={api} mode={activeWorkspace} />
    </main>
  );
}

function AppTopbar({ userLabel, onLogout }: { userLabel: string; onLogout?: () => Promise<void> }) {
  const initials = getInitials(userLabel);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  async function handleLogout() {
    setIsUserMenuOpen(false);
    await onLogout?.();
  }

  return (
    <header className="app-topbar" aria-label="FTM application header">
      <div className="app-topbar-inner">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" focusable="false">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </span>
          <div className="brand-text">
            <span className="brand-title">FTM Rehab</span>
            <span className="brand-subtitle">Follow-up Check-up Tool</span>
          </div>
        </div>
        <div className="user-menu" aria-label="Current session">
          <button
            type="button"
            className="user-chip user-menu-trigger"
            aria-haspopup="menu"
            aria-expanded={isUserMenuOpen}
            onClick={() => setIsUserMenuOpen((open) => !open)}
          >
            <span className="avatar-mark" aria-hidden="true">
              {initials}
            </span>
            <span>{userLabel}</span>
            <span className="menu-caret" aria-hidden="true">
              ▾
            </span>
          </button>
          {isUserMenuOpen ? (
            <div className="user-dropdown" role="menu">
              <p className="user-dropdown-label">{userLabel}</p>
              <button type="button" role="menuitem" className="logout-menu-item" onClick={handleLogout}>
                Log out
              </button>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}

function getUserLabel(session: ReturnType<AuthClient["getSession"]>, fallback: string) {
  const fullName = [session.givenName, session.familyName].filter(Boolean).join(" ").trim();
  const label = fullName || session.displayName || fallback;
  return session.roles.includes("medical") ? addDoctorTitle(label) : label;
}

function getInitials(label: string) {
  return label
    .replace(/^dr\.?\s+/i, "")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase())
    .slice(0, 2)
    .join("");
}

function addDoctorTitle(label: string) {
  return /^dr\.?\s+/i.test(label) ? label : `Dr. ${label}`;
}

function createDiagnosticFeatureApi(authClient: AuthClient): DiagnosticFeatureApi {
  const http = createHttpClient({ authClient });

  return {
    ...createPatientsApi(http),
    ...createDiagnosticsApi(http),
    ...createProgramsApi(http),
    ...createCatalogApi(http),
  };
}
