import "server-only";
import { cookies } from "next/headers";

// The API does not say who made a cut, so "Mis cargas de hoy" lives in this device's cookie:
// the last cuts loaded from here. It holds no prices and is not a record of truth.
const COOKIE = "cargas_corte";
const MAX_CARGAS = 20;
const WEEK_SECONDS = 60 * 60 * 24 * 7;

export type CargaCorte = {
  fecha: string;
  pieza: string;
  m2: string;
  producto: string;
  lote: string;
};

function isCarga(value: unknown): value is CargaCorte {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return ["fecha", "pieza", "m2", "producto", "lote"].every(
    (key) => typeof record[key] === "string",
  );
}

export async function leerCargas(): Promise<CargaCorte[]> {
  const raw = (await cookies()).get(COOKIE)?.value;
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter(isCarga) : [];
  } catch {
    return [];
  }
}

export async function guardarCarga(carga: CargaCorte): Promise<void> {
  const anteriores = await leerCargas();
  (await cookies()).set(
    COOKIE,
    JSON.stringify([carga, ...anteriores].slice(0, MAX_CARGAS)),
    {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/corte",
      maxAge: WEEK_SECONDS,
    },
  );
}
