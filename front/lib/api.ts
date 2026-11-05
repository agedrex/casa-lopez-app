import "server-only";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

export type ApiFailure = {
  ok: false;
  status: number;
  message: string;
  avisos: string[];
};

export type ApiResult<T> = { ok: true; data: T } | ApiFailure;

const TIMEOUT_MS = 10_000;
// Uploads run the OCR before answering; file downloads move up to 10 MB.
const FILE_TIMEOUT_MS = 60_000;

function apiBaseUrl(): string | null {
  const configured = process.env.API_URL?.trim();
  if (configured) return configured.replace(/\/+$/, "");
  // Local development convenience only; deployed environments must set API_URL.
  return process.env.NODE_ENV === "production" ? null : "http://127.0.0.1:8000";
}

function failure(
  status: number,
  message: string,
  avisos: string[] = [],
): ApiFailure {
  return { ok: false, status, message, avisos };
}

type Method = "GET" | "POST";

function describeInvalidBody(detail: unknown[]): string {
  // FastAPI sends a list of {loc, msg} when the body does not validate.
  const fields = detail
    .map((item) => {
      const loc = (item as { loc?: unknown })?.loc;
      return Array.isArray(loc) ? String(loc[loc.length - 1]) : null;
    })
    .filter((field): field is string => field !== null);
  return fields.length > 0
    ? `Revise los datos ingresados (${[...new Set(fields)].join(", ")}).`
    : "Revise los datos ingresados.";
}

async function readFailure(response: Response): Promise<ApiFailure> {
  let detail = "";
  let avisos: string[] = [];
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object") {
      const record = body as { detail?: unknown; avisos?: unknown };
      if (typeof record.detail === "string") detail = record.detail;
      else if (Array.isArray(record.detail))
        detail = describeInvalidBody(record.detail);
      if (Array.isArray(record.avisos)) {
        avisos = record.avisos.filter(
          (item): item is string => typeof item === "string",
        );
      }
    }
  } catch {
    // Non-JSON error body: fall back to the generic message below.
  }
  const fallback =
    response.status === 404
      ? "No se encontró lo que buscaba."
      : "La API respondió con un error.";
  return failure(response.status, detail || fallback, avisos);
}

/**
 * Server-side call to the costing API. The browser never talks to the backend:
 * the visitor's `cookie` header is forwarded so the backend can verify the same
 * Better Auth session. A 401 sends the visitor to /login.
 */
async function apiRequest<T>(
  method: Method,
  path: string,
  body?: unknown,
  timeoutMs: number = TIMEOUT_MS,
): Promise<ApiResult<T>> {
  const base = apiBaseUrl();
  if (!base) return failure(0, "La dirección de la API no está configurada.");

  const incoming = await headers();
  const forwarded: Record<string, string> = { accept: "application/json" };
  const cookie = incoming.get("cookie");
  if (cookie) forwarded.cookie = cookie;
  // FormData sets its own multipart boundary header: never set content-type for it.
  const isForm = body instanceof FormData;
  if (body !== undefined && !isForm) {
    forwarded["content-type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      method,
      headers: forwarded,
      body:
        body === undefined ? undefined : isForm ? body : JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch {
    return failure(0, "No se pudo conectar con la API de costos.");
  }

  if (response.status === 401) redirect("/login");
  if (!response.ok) return readFailure(response);

  try {
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return failure(502, "La API devolvió una respuesta inválida.");
  }
}

export function apiGet<T>(path: string): Promise<ApiResult<T>> {
  return apiRequest<T>("GET", path);
}

/**
 * Writes go through server actions only; amounts travel as decimal strings.
 * `timeoutMs` is for the few calls that legitimately take longer than a read.
 */
export function apiPost<T>(
  path: string,
  body: unknown,
  timeoutMs?: number,
): Promise<ApiResult<T>> {
  return apiRequest<T>("POST", path, body, timeoutMs);
}

/**
 * Multipart upload (a file plus its fields). Same session forwarding as `apiPost`; the
 * default timeout is longer because the API reads the text of the file before answering.
 */
export function apiPostForm<T>(
  path: string,
  body: FormData,
  timeoutMs: number = FILE_TIMEOUT_MS,
): Promise<ApiResult<T>> {
  return apiRequest<T>("POST", path, body, timeoutMs);
}

/**
 * Raw (not JSON) GET for files: the caller streams the response to the browser. Returns the
 * API `Response` untouched when it is OK, so headers such as Content-Type survive.
 */
export async function apiGetFile(
  path: string,
): Promise<{ ok: true; response: Response } | ApiFailure> {
  const base = apiBaseUrl();
  if (!base) return failure(0, "La dirección de la API no está configurada.");

  const incoming = await headers();
  const forwarded: Record<string, string> = {};
  const cookie = incoming.get("cookie");
  if (cookie) forwarded.cookie = cookie;

  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      method: "GET",
      headers: forwarded,
      cache: "no-store",
      signal: AbortSignal.timeout(FILE_TIMEOUT_MS),
    });
  } catch {
    return failure(0, "No se pudo conectar con la API de costos.");
  }
  if (response.status === 401) redirect("/login");
  if (!response.ok) return readFailure(response);
  return { ok: true, response };
}
