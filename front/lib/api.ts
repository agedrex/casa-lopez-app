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

/**
 * Server-side GET to the costing API. The browser never talks to the backend:
 * the visitor's `cookie` header is forwarded so the backend can verify the same
 * Better Auth session. A 401 sends the visitor to /login.
 */
export async function apiGet<T>(path: string): Promise<ApiResult<T>> {
  const base = apiBaseUrl();
  if (!base) return failure(0, "La dirección de la API no está configurada.");

  const incoming = await headers();
  const forwarded: Record<string, string> = { accept: "application/json" };
  const cookie = incoming.get("cookie");
  if (cookie) forwarded.cookie = cookie;

  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      headers: forwarded,
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    return failure(0, "No se pudo conectar con la API de costos.");
  }

  if (response.status === 401) redirect("/login");

  if (!response.ok) {
    let detail = "";
    let avisos: string[] = [];
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object") {
        const record = body as { detail?: unknown; avisos?: unknown };
        if (typeof record.detail === "string") detail = record.detail;
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

  try {
    return { ok: true, data: (await response.json()) as T };
  } catch {
    return failure(502, "La API devolvió una respuesta inválida.");
  }
}
