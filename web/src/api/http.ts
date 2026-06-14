import type { AuthClient } from "../auth/authClient";

export type HttpClientOptions = {
  baseUrl?: string;
  authClient: AuthClient;
  fetchImpl?: typeof fetch;
};

export type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly payload?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function createHttpClient({
  baseUrl = "/api",
  authClient,
  fetchImpl = fetch,
}: HttpClientOptions) {
  async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const token = await authClient.getToken();
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");

    if (options.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }

    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetchImpl(`${baseUrl}${path}`, {
      ...options,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });

    const payload = await readPayload(response);

    if (!response.ok) {
      throw new ApiError(getErrorMessage(payload, response.status), response.status, payload);
    }

    return payload as T;
  }

  return { request };
}

async function readPayload(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return undefined;
  }

  const text = await response.text();
  if (!text) {
    return undefined;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function getErrorMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
  }

  return `API request failed with status ${status}`;
}
