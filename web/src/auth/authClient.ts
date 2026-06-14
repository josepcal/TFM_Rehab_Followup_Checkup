export type UserRole = "medical" | "patient" | "technician" | "admin";

export type AuthSession = {
  authenticated: boolean;
  subject?: string;
  roles: UserRole[];
  token?: string;
};

export type AuthClient = {
  getSession: () => AuthSession;
  getToken: () => Promise<string | undefined>;
};

const DEFAULT_DEV_SESSION: AuthSession = {
  authenticated: true,
  subject: "dev-medical-user",
  roles: ["medical"],
  token: "dev-token",
};

export function createMockAuthClient(session: AuthSession = DEFAULT_DEV_SESSION): AuthClient {
  return {
    getSession: () => session,
    getToken: async () => session.token,
  };
}

export function createBrowserAuthClient(): AuthClient {
  // Production Keycloak wiring stays behind this boundary. Until realm/client
  // config is confirmed, local development uses an explicit mock session.
  return createMockAuthClient(readDevSession());
}

function readDevSession(): AuthSession {
  const role = import.meta.env.VITE_FTM_DEV_ROLE ?? "medical";
  const authenticated = import.meta.env.VITE_FTM_DEV_AUTHENTICATED !== "false";

  return {
    authenticated,
    subject: import.meta.env.VITE_FTM_DEV_SUBJECT ?? "dev-medical-user",
    roles: [toUserRole(role)],
    token: import.meta.env.VITE_FTM_DEV_TOKEN ?? "dev-token",
  };
}

function toUserRole(value: string): UserRole {
  if (["medical", "patient", "technician", "admin"].includes(value)) {
    return value as UserRole;
  }

  return "medical";
}
