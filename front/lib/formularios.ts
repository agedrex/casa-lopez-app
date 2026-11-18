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

/**
 * `unit` is the default unit of a row of the section; each row carries its own (`FormularioLinea.unidad`, from the API): hours,
 * labour in pesos and packing rows are not m².
 */
export const SECCIONES = [
  {
    value: "CONSUMO",
    title: "Consumos",
    unit: "m²",
    help: "Cuero, forro y demás materiales en m²; las horas, la mano de obra y el empaque dicen su propia unidad. Cargá el consumo real de cada uno.",
    accent: "border-gold",
  },
  {
    value: "HERRAJE",
    title: "Herrajes",
    unit: "unidades",
    help: "Broches, cierres y demás herrajes: cuántas unidades lleva cada uno.",
    accent: "border-ink",
  },
] as const;

/**
 * What the screen offers on a sheet:
 * - `editar`: the whole sheet is editable (add, remove and rename rows, quantities, comments): the admin while it is a draft or
 *   sent, the taller only while the sheet is waiting for it (ENVIADO);
 * - `revisar`: the admin reviews a completed sheet: it is editable too, and the page adds Validar / Devolver;
 * - `leer`: everything else, read only (a sheet that is VALIDADO is immutable for everybody).
 * Admin wins when a user holds both roles. The backend enforces the same rules (403 / 409).
 */
export type ModoHoja = "editar" | "revisar" | "leer";

export function modoDeHoja(
  role: string | null | undefined,
  estado: FormularioEstado,
): ModoHoja {
  if (hasRole(role, "admin")) {
    if (estado === "VALIDADO") return "leer";
    return estado === "COMPLETADO" ? "revisar" : "editar";
  }
  if (hasRole(role, "taller") && estado === "ENVIADO") return "editar";
  return "leer";
}

/** The buttons of the editable sheet: save always; the admin sends a draft to the workshop, the taller completes. */
export type AccionHoja = "guardar" | "enviar" | "completar";

export function accionesDeHoja(
  role: string | null | undefined,
  estado: FormularioEstado,
): AccionHoja[] {
  if (modoDeHoja(role, estado) === "leer") return [];
  if (hasRole(role, "admin")) {
    return estado === "BORRADOR" ? ["guardar", "enviar"] : ["guardar"];
  }
  return ["guardar", "completar"];
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

/** A row as the editor holds it: every cell is text. `id` only identifies the row on screen (it is never sent). */
export type FilaHoja = {
  id: string;
  seccion: FormularioLinea["seccion"];
  nombre: string;
  cantidad: string;
  comentario: string;
  unidad: string;
};

// The row the sheet used to preload: "ya no aplica, hay que poner el consumo real de todo". Sheets created before it was
// removed still have it: it is hidden while empty (saving the sheet drops it) and shown if somebody typed something in it.
const FILA_RETIRADA = "DESPERDICIO 30%";

function normalizarNombre(nombre: string): string {
  return nombre.replace(/\s+/g, " ").trim().toUpperCase();
}

export function unidadPorDefecto(seccion: FormularioLinea["seccion"]): string {
  return SECCIONES.find((s) => s.value === seccion)?.unit ?? "";
}

export function filasDeHoja(lineas: FormularioLinea[]): FilaHoja[] {
  return lineas
    .filter(
      (linea) =>
        !(
          normalizarNombre(linea.nombre) === FILA_RETIRADA &&
          !decimalInputText(linea.cantidad) &&
          !linea.comentario
        ),
    )
    .map((linea, indice) => ({
      id: `${linea.seccion}-${indice}`,
      seccion: linea.seccion,
      nombre: linea.nombre,
      cantidad: decimalInputText(linea.cantidad),
      comentario: linea.comentario ?? "",
      unidad: linea.unidad ?? unidadPorDefecto(linea.seccion),
    }));
}

/** A new empty row at the end of its section. `id` has to be unique on screen. */
export function agregarFila(
  filas: FilaHoja[],
  seccion: FormularioLinea["seccion"],
  id: string,
): FilaHoja[] {
  const nueva: FilaHoja = {
    id,
    seccion,
    nombre: "",
    cantidad: "",
    comentario: "",
    unidad: unidadPorDefecto(seccion),
  };
  let ultima = -1;
  filas.forEach((fila, indice) => {
    if (fila.seccion === seccion) ultima = indice;
  });
  if (ultima === -1) return [...filas, nueva];
  return [...filas.slice(0, ultima + 1), nueva, ...filas.slice(ultima + 1)];
}

export function quitarFila(filas: FilaHoja[], id: string): FilaHoja[] {
  return filas.filter((fila) => fila.id !== id);
}

/** Renaming a row resets its unit to the default of its section: the API decides the unit of a name when it saves. */
export function renombrarFila(
  filas: FilaHoja[],
  id: string,
  nombre: string,
): FilaHoja[] {
  return filas.map((fila) =>
    fila.id === id
      ? { ...fila, nombre, unidad: unidadPorDefecto(fila.seccion) }
      : fila,
  );
}

export type LineaParaGuardar = {
  seccion: FormularioLinea["seccion"];
  nombre: string;
  cantidad: string | null;
  comentario: string | null;
};

/**
 * The rows as the API takes them: an empty quantity is "not filled in" (null), `0,25` and `0.25` are the same, and a row
 * needs a name. A row with no name, quantity or comment (an added one never used) is skipped. The first problem found is
 * returned as text for the form; no other row is dropped or changed.
 */
export function armarLineas(
  filas: FilaHoja[],
): { ok: true; lineas: LineaParaGuardar[] } | { ok: false; message: string } {
  const lineas: LineaParaGuardar[] = [];
  for (const fila of filas) {
    const nombre = fila.nombre.replace(/\s+/g, " ").trim();
    if (!nombre && !fila.cantidad.trim() && !fila.comentario.trim()) continue;
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
