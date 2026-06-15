import Keycloak from "keycloak-js";

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

type BrowserAuthMode = "dev" | "pkce" | "keycloak";

const DEFAULT_DEV_SESSION: AuthSession = {
  authenticated: true,
  subject: "dev-medical-user",
  roles: ["medical"],
  token: "dev-token",
};

const KNOWN_ROLES: UserRole[] = ["medical", "patient", "technician", "admin"];

export function createMockAuthClient(session: AuthSession = DEFAULT_DEV_SESSION): AuthClient {
  return {
    getSession: () => session,
    getToken: async () => session.token,
  };
}

export async function createBrowserAuthClient(): Promise<AuthClient> {
  const mode = readBrowserAuthMode();

  if (mode === "pkce" || mode === "keycloak") {
    return createKeycloakAuthClient();
  }

  return createMockAuthClient(readDevSession());
}

async function createKeycloakAuthClient(): Promise<AuthClient> {
  const keycloak = new Keycloak({
    url: import.meta.env.VITE_FTM_KEYCLOAK_URL ?? "http://localhost:8085",
    realm: import.meta.env.VITE_FTM_KEYCLOAK_REALM ?? "ftm",
    clientId: import.meta.env.VITE_FTM_KEYCLOAK_CLIENT_ID ?? "ftm-web",
  });

  keycloak.onTokenExpired = () => {
    void keycloak.updateToken(30).catch(() => {
      keycloak.clearToken();
      void keycloak.login();
    });
  };

  const authenticated = await keycloak.init({
    onLoad: "login-required",
    pkceMethod: "S256",
    checkLoginIframe: false,
  });

  if (!authenticated) {
    await keycloak.login();
  }

  return {
    getSession: () => readKeycloakSession(keycloak),
    getToken: async () => {
      try {
        await keycloak.updateToken(30);
        return keycloak.token;
      } catch {
        keycloak.clearToken();
        await keycloak.login();
        return undefined;
      }
    },
  };
}

function readBrowserAuthMode(): BrowserAuthMode {
  const mode = import.meta.env.VITE_FTM_AUTH_MODE ?? "dev";

  if (mode === "pkce" || mode === "keycloak") {
    return mode;
  }

  return "dev";
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

function readKeycloakSession(keycloak: Keycloak): AuthSession {
  const roles = keycloak.tokenParsed?.realm_access?.roles ?? [];

  return {
    authenticated: keycloak.authenticated === true,
    subject: keycloak.subject ?? keycloak.tokenParsed?.sub,
    roles: roles.filter(isUserRole),
    token: keycloak.token,
  };
}

function toUserRole(value: string): UserRole {
  if (isUserRole(value)) {
    return value;
  }

  return "medical";
}

function isUserRole(value: string): value is UserRole {
  return KNOWN_ROLES.includes(value as UserRole);
}
