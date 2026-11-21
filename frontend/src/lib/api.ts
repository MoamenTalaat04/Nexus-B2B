export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export interface ApiFetchOptions extends RequestInit {
  /** Skip redirecting on 401 when probing session state (e.g. GET /auth/me). */
  suppressUnauthorizedRedirect?: boolean;
}

const API_BASE = "/api/v1";

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") {
    return fallback;
  }
  const record = payload as Record<string, unknown>;
  if (typeof record.detail === "string") {
    return record.detail;
  }
  if (Array.isArray(record.detail) && record.detail.length > 0) {
    const first = record.detail[0] as Record<string, unknown> | undefined;
    if (first && typeof first.msg === "string") {
      return first.msg;
    }
  }
  if (typeof record.message === "string") {
    return record.message;
  }
  if (record.error && typeof record.error === "object") {
    const errObj = record.error as Record<string, unknown>;
    if (typeof errObj.message === "string") {
      return errObj.message;
    }
  }
  return fallback;
}

export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const { suppressUnauthorizedRedirect = false, headers, body, ...rest } = options;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = normalizedPath.startsWith("/api/")
    ? normalizedPath
    : `${API_BASE}${normalizedPath}`;

  const mergedHeaders = new Headers(headers);
  if (body && !(body instanceof FormData) && !mergedHeaders.has("Content-Type")) {
    mergedHeaders.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...rest,
    headers: mergedHeaders,
    body,
    credentials: "include",
  });

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json().catch(() => null) : await response.text().catch(() => null);

  if (!response.ok) {
    if (
      response.status === 401 &&
      !suppressUnauthorizedRedirect &&
      typeof window !== "undefined" &&
      !window.location.pathname.startsWith("/login") &&
      !window.location.pathname.startsWith("/register") &&
      !window.location.pathname.startsWith("/signup")
    ) {
      window.location.href = "/login";
    }
    const message = extractErrorMessage(
      payload,
      response.statusText || `Request failed with status ${response.status}`,
    );
    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string, options?: ApiFetchOptions) =>
    apiFetch<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, data?: unknown, options?: ApiFetchOptions) =>
    apiFetch<T>(path, {
      ...options,
      method: "POST",
      body: data === undefined ? undefined : JSON.stringify(data),
    }),
  patch: <T>(path: string, data?: unknown, options?: ApiFetchOptions) =>
    apiFetch<T>(path, {
      ...options,
      method: "PATCH",
      body: data === undefined ? undefined : JSON.stringify(data),
    }),
  put: <T>(path: string, data?: unknown, options?: ApiFetchOptions) =>
    apiFetch<T>(path, {
      ...options,
      method: "PUT",
      body: data === undefined ? undefined : JSON.stringify(data),
    }),
  delete: <T>(path: string, options?: ApiFetchOptions) =>
    apiFetch<T>(path, { ...options, method: "DELETE" }),
  upload: <T>(path: string, formData: FormData, options?: ApiFetchOptions) =>
    apiFetch<T>(path, { ...options, method: "POST", body: formData }),
};
