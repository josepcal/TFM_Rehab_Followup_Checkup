import Keycloak from "keycloak-js";

export type UserRole = "medical" | "patient" | "technician" | "admin";

export type AuthSession = {
  authenticated: boolean;
  subject?: string;
  givenName?: string;
  familyName?: string;
  displayName?: string;
  roles: UserRole[];
  token?: string;
};

export type AuthClient = {
  getSession: () => AuthSession;
  getToken: () => Promise<string | undefined>;
  logout: () => Promise<void>;
};

type BrowserAuthMode = "dev" | "pkce" | "keycloak";

const DEFAULT_DEV_SESSION: AuthSession = {
  authenticated: true,
  subject: "dev-medical-user",
  givenName: "Medical",
  familyName: "User",
  displayName: "Medical User",
  roles: ["medical"],
  token: "dev-token",
};

const KNOWN_ROLES: UserRole[] = ["medical", "patient", "technician", "admin"];

export function createMockAuthClient(session: AuthSession = DEFAULT_DEV_SESSION): AuthClient {
  return {
    getSession: () => session,
    getToken: async () => session.token,
    logout: async () => undefined,
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
      if (keycloak.authenticated !== true || !keycloak.token) {
        await keycloak.login();
        return undefined;
      }

      try {
        await keycloak.updateToken(30);
        return keycloak.token;
      } catch {
        // If refresh fails but the in-memory access token is still present, use it
        // for the current request instead of sending an unauthenticated API call.
        if (keycloak.token) {
          return keycloak.token;
        }
        keycloak.clearToken();
        await keycloak.login();
        return undefined;
      }
    },
    logout: async () => {
      await keycloak.logout({
        redirectUri: `${window.location.origin}/`,
        logoutMethod: "POST",
      });
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
    givenName: import.meta.env.VITE_FTM_DEV_GIVEN_NAME ?? "Medical",
    familyName: import.meta.env.VITE_FTM_DEV_FAMILY_NAME ?? "User",
    displayName: import.meta.env.VITE_FTM_DEV_DISPLAY_NAME ?? "Medical User",
    roles: [toUserRole(role)],
    token: import.meta.env.VITE_FTM_DEV_TOKEN ?? "dev-token",
  };
}

function readKeycloakSession(keycloak: Keycloak): AuthSession {
  const roles = keycloak.tokenParsed?.realm_access?.roles ?? [];
  const token = keycloak.tokenParsed as Record<string, unknown> | undefined;
  const givenName = readStringClaim(token, "given_name");
  const familyName = readStringClaim(token, "family_name");

  return {
    authenticated: keycloak.authenticated === true,
    subject: keycloak.subject ?? keycloak.tokenParsed?.sub,
    givenName,
    familyName,
    displayName: readDisplayName(token, givenName, familyName),
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

function readDisplayName(
  token: Record<string, unknown> | undefined,
  givenName?: string,
  familyName?: string,
) {
  const fullName = [givenName, familyName].filter(Boolean).join(" ").trim();
  return fullName || readStringClaim(token, "name") || readStringClaim(token, "preferred_username");
}

function readStringClaim(token: Record<string, unknown> | undefined, claim: string) {
  const value = token?.[claim];
  return typeof value === "string" && value.trim() ? value : undefined;
}
