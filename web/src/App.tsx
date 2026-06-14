import type { AuthClient } from "./auth/authClient";

export type AppProps = {
  authClient: AuthClient;
};

export function App({ authClient }: AppProps) {
  const session = authClient.getSession();

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
      <p>
        Frontend foundation is ready. Patient selection, diagnostic history,
        create, detail, and edit screens will be added in the next PR slices.
      </p>
    </main>
  );
}
