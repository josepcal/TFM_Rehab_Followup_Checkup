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

  async function upload(url: string, blob: Blob, contentType: string): Promise<void> {
    const token = await authClient.getToken();
    const headers = new Headers();
    headers.set("Content-Type", contentType);

    if (token && url.startsWith("/api/")) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetchImpl(resolveUploadUrl(url), {
      method: "PUT",
      headers,
      body: blob,
    });

    if (!response.ok) {
      const payload = await readPayload(response);
      throw new ApiError(getErrorMessage(payload, response.status), response.status, payload);
    }
  }

  function resolveUploadUrl(url: string) {
    if (/^https?:\/\//i.test(url)) {
      return url;
    }
    return url;
  }

  return { request, upload };
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
    // FastAPI validation errors return detail as an array of {loc, msg, type}
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as Record<string, unknown>;
      if (typeof first.msg === "string") {
        return first.msg;
      }
    }
  }

  return `API request failed with status ${status}`;
}
