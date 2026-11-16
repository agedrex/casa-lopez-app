import { decimalInputText, parseDecimalInput } from "./format";
import { hasRole } from "./permissions";
import type { FormularioEstado, FormularioLinea } from "./types";

// Pure rules of the consumption sheet screens. Nothing here calculates money: a quantity is the text a person typed.

export const ESTADO_LABEL: Record<FormularioEstado, string> = {
  BORRADOR: "Borrador",
  ENVIADO: "Para completar",
  COMPLETADO: "En revisión",
  VALIDADO: "Validada",
};

export const ESTADO_TONE: Record<
  FormularioEstado,
  "neutral" | "warn" | "good" | "alert"
> = {
  BORRADOR: "neutral",
  ENVIADO: "warn",
  COMPLETADO: "neutral",
  VALIDADO: "good",
};

export const ESTADOS_FILTRO: readonly FormularioEstado[] = [
  "ENVIADO",
  "COMPLETADO",
  "VALIDADO",
  "BORRADOR",
];

export function estadoLabel(code: string): string {
  return ESTADO_LABEL[code as FormularioEstado] ?? code;
}

export function isEstado(value: string): value is FormularioEstado {
  return value in ESTADO_LABEL;
}

export const SECCIONES = [
  {
    value: "CONSUMO",
    title: "Consumos",
    unit: "m²",
    help: "Cuero, forro y demás materiales: cuántos metros cuadrados lleva cada uno.",
    accent: "border-gold",
  },
  {
    value: "HERRAJE",
    title: "Herrajes",
    unit: "cantidad",
    help: "Broches, cierres y demás herrajes: cuántas unidades lleva cada uno.",
    accent: "border-ink",
  },
] as const;

/**
 * What the screen offers on a sheet:
 * - `editar`: the taller fills the quantities (only while the sheet is waiting for it, ENVIADO);
 * - `revisar`: the admin reads a completed sheet and validates it or sends it back;
 * - `leer`: everything else, read only (a sheet that is VALIDADO is immutable for everybody).
 * Admin wins when a user holds both roles. The backend enforces the same rules (403 / 409).
 */
export type ModoHoja = "editar" | "revisar" | "leer";

export function modoDeHoja(
  role: string | null | undefined,
  estado: FormularioEstado,
): ModoHoja {
  if (hasRole(role, "admin"))
    return estado === "COMPLETADO" ? "revisar" : "leer";
  if (hasRole(role, "taller") && estado === "ENVIADO") return "editar";
  return "leer";
}

/**
 * Whether the user may add a photo from the sheet screen: the admin always; a taller while the sheet is ENVIADO or when it
 * created the sheet (the same rule the API applies to `POST /modelos/<código>/foto`).
 */
export function puedeSubirFoto(
  role: string | null | undefined,
  estado: FormularioEstado,
  creadoPor: string,
  userId: string,
): boolean {
  if (hasRole(role, "admin")) return true;
  return (
    hasRole(role, "taller") && (estado === "ENVIADO" || creadoPor === userId)
  );
}

/** A row as the editor holds it: every cell is text. */
export type FilaHoja = {
  seccion: FormularioLinea["seccion"];
  nombre: string;
  cantidad: string;
  comentario: string;
};

export function filasDeHoja(lineas: FormularioLinea[]): FilaHoja[] {
  return lineas.map((linea) => ({
    seccion: linea.seccion,
    nombre: linea.nombre,
    cantidad: decimalInputText(linea.cantidad),
    comentario: linea.comentario ?? "",
  }));
}

export type LineaParaGuardar = {
  seccion: FormularioLinea["seccion"];
  nombre: string;
  cantidad: string | null;
  comentario: string | null;
};

/**
 * The rows as the API takes them: an empty quantity is "not filled in" (null), `0,25` and `0.25` are the same, and a row
 * needs a name. The first problem found is returned as text for the form; no row is dropped or changed otherwise.
 */
export function armarLineas(
  filas: FilaHoja[],
): { ok: true; lineas: LineaParaGuardar[] } | { ok: false; message: string } {
  const lineas: LineaParaGuardar[] = [];
  for (const fila of filas) {
    const nombre = fila.nombre.replace(/\s+/g, " ").trim();
    if (!nombre)
      return { ok: false, message: "Cada fila tiene que tener un nombre." };
    const raw = fila.cantidad.trim();
    let cantidad: string | null = null;
    if (raw) {
      cantidad = parseDecimalInput(raw);
      if (cantidad === null) {
        return {
          ok: false,
          message: `${nombre}: la cantidad no es un número válido. Ejemplo: 0,25.`,
        };
      }
    }
    lineas.push({
      seccion: fila.seccion,
      nombre,
      cantidad,
      comentario: fila.comentario.trim() || null,
    });
  }
  return { ok: true, lineas };
}
