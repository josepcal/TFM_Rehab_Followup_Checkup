/// <reference types="vite/client" />
/// <reference types="vitest" />

interface ImportMetaEnv {
  readonly VITE_FTM_AUTH_MODE?: "dev" | "pkce" | "keycloak";
  readonly VITE_FTM_DEV_AUTHENTICATED?: string;
  readonly VITE_FTM_DEV_ROLE?: string;
  readonly VITE_FTM_DEV_SUBJECT?: string;
  readonly VITE_FTM_DEV_TOKEN?: string;
  readonly VITE_FTM_KEYCLOAK_URL?: string;
  readonly VITE_FTM_KEYCLOAK_REALM?: string;
  readonly VITE_FTM_KEYCLOAK_CLIENT_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
