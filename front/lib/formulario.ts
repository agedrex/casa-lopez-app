// Pure rules of the consumption form screens (no server-only, no React): what each role may do in each state,
// how the rows travel between the sheet and the API. Mirrors backend/src/backend/formulario.py; the backend decides.
// No calculations and no money here: a quantity is the text a person typed, normalised by parseDecimalInput.
import { decimalInputText, parseDecimalInput } from "./format";
import { parseRoles } from "./permissions";
import type {
  FormularioEstado,
  FormularioLinea,
  FormularioSeccion,
} from "./types";

export const FORMULARIO_ESTADOS: readonly FormularioEstado[] = [
  "BORRADOR",
  "ENVIADO",
  "COMPLETADO",
  "VALIDADO",
];

const ESTADO_LABELS: Record<FormularioEstado, string> = {
  BORRADOR: "Borrador",
  ENVIADO: "Enviado al taller",
  COMPLETADO: "Completado",
  VALIDADO: "Validado",
};

export function estadoLabel(estado: FormularioEstado): string {
  return ESTADO_LABELS[estado];
}

/** Badge tone: waiting on someone (warn), done (good). */
export function estadoTone(
  estado: FormularioEstado,
): "neutral" | "warn" | "good" {
  if (estado === "VALIDADO") return "good";
  return estado === "BORRADOR" ? "neutral" : "warn";
}

export function parseEstado(value: string): FormularioEstado | "" {
  return FORMULARIO_ESTADOS.find((estado) => estado === value) ?? "";
}

/** The states a role can list: admin gets all, a taller user only ENVIADO and COMPLETADO, gerente none (module closed). */
export function estadosVisibles(
  role: string | null | undefined,
): readonly FormularioEstado[] {
  const roles = parseRoles(role);
  if (roles.includes("admin")) return FORMULARIO_ESTADOS;
  return roles.includes("taller") ? ["ENVIADO", "COMPLETADO"] : [];
}

/** Only admin sees the validated form inside the product sheet; the Formularios module is closed to gerente and taller. */
export function seesValidatedFormulario(
  role: string | null | undefined,
): boolean {
  return parseRoles(role).includes("admin");
}

export type FormularioAcciones = {
  /** The rows (and for admin the article) can be edited. */
  editar: boolean;
  /** Only admin changes the article name. */
  editarArticulo: boolean;
  enviar: boolean;
  completar: boolean;
  devolver: boolean;
  validar: boolean;
  duplicar: boolean;
};

/**
 * What the screen offers to `role` on a form in `estado`. Same table as the backend (`ACCIONES`,
 * `comprobar_edicion`): admin edits until VALIDADO, taller only the rows and only while ENVIADO,
 * gerente nothing; VALIDADO is readonly for everyone and the way to change it is to duplicate.
 */
export function accionesDe(
  role: string | null | undefined,
  estado: FormularioEstado,
): FormularioAcciones {
  const roles = parseRoles(role);
  const admin = roles.includes("admin");
  const taller = roles.includes("taller");
  const abierto = estado !== "VALIDADO";
  return {
    editar: abierto && (admin || (taller && estado === "ENVIADO")),
    editarArticulo: abierto && admin,
    enviar: admin && (estado === "BORRADOR" || estado === "ENVIADO"),
    completar: (admin || taller) && estado === "ENVIADO",
    devolver: admin && estado === "COMPLETADO",
    validar: admin && estado === "COMPLETADO",
    duplicar: admin,
  };
}

// --- Rows ---------------------------------------------------------------------------------------------------------

export const SECCIONES: readonly FormularioSeccion[] = ["CONSUMO", "HERRAJE"];

/** A row while it is being edited: every cell is the text typed (the quantity is not parsed until it is sent). */
export type FilaEditable = {
  key: string;
  nombre: string;
  cantidad: string;
  comentario: string;
};

export type SeccionesEditables = Record<FormularioSeccion, FilaEditable[]>;

/** Rows from the API as editable text; `nextKey` gives each row a stable React key. */
export function filasDe(
  lineas: FormularioLinea[],
  nextKey: () => string,
): SeccionesEditables {
  const seccion = (nombre: FormularioSeccion) =>
    lineas
      .filter((linea) => linea.seccion === nombre)
      .sort((a, b) => a.orden - b.orden)
      .map((linea) => ({
        key: nextKey(),
        nombre: linea.nombre,
        cantidad: decimalInputText(linea.cantidad),
        comentario: linea.comentario ?? "",
      }));
  return { CONSUMO: seccion("CONSUMO"), HERRAJE: seccion("HERRAJE") };
}

/** Wire format of the hidden `lineas` field: the typed text per row, section by section in sheet order. */
export function serializarFilas(secciones: SeccionesEditables): string {
  return JSON.stringify(
    SECCIONES.flatMap((seccion) =>
      secciones[seccion].map(({ nombre, cantidad, comentario }) => ({
        seccion,
        nombre,
        cantidad,
        comentario,
      })),
    ),
  );
}

/** A row nobody filled in: no quantity and no comment (the name alone is the preloaded label). */
export function lineaVacia(linea: {
  cantidad: string | null;
  comentario: string | null;
}): boolean {
  return !(linea.cantidad ?? "").trim() && !(linea.comentario ?? "").trim();
}

export type LineaParaApi = {
  seccion: FormularioSeccion;
  nombre: string;
  cantidad: string | null;
  comentario: string | null;
};

export type LineasParseadas =
  | { ok: true; lineas: LineaParaApi[] }
  | { ok: false; message: string };

// NUMERIC(12,6): up to 6 digits before the point and 6 after.
const CANTIDAD_API = /^\d{1,6}(\.\d{1,6})?$/;

/**
 * Reads the hidden `lineas` field into rows for the API. A row with nothing typed at all (an added row left
 * blank) is dropped; a row with a quantity or comment needs a name. The quantity goes through the shared
 * `parseDecimalInput` (`0,25` and `0.25` are accepted) and stays text.
 */
export function parseLineas(raw: string): LineasParseadas {
  let datos: unknown;
  try {
    datos = JSON.parse(raw);
  } catch {
    return { ok: false, message: "No pudimos leer las filas del formulario." };
  }
  if (!Array.isArray(datos)) {
    return { ok: false, message: "No pudimos leer las filas del formulario." };
  }
  const lineas: LineaParaApi[] = [];
  for (const item of datos) {
    const fila = (item ?? {}) as Record<string, unknown>;
    const seccion = SECCIONES.find((valor) => valor === fila.seccion);
    const cell = (key: string) =>
      typeof fila[key] === "string" ? (fila[key] as string).trim() : null;
    const nombre = cell("nombre");
    const cantidad = cell("cantidad");
    const comentario = cell("comentario");
    if (
      !seccion ||
      nombre === null ||
      cantidad === null ||
      comentario === null
    ) {
      return {
        ok: false,
        message: "No pudimos leer las filas del formulario.",
      };
    }
    if (!nombre && !cantidad && !comentario) continue;
    if (!nombre) {
      return {
        ok: false,
        message: "Escribí el nombre de cada fila que completes.",
      };
    }
    let normalizada: string | null = null;
    if (cantidad) {
      normalizada = parseDecimalInput(cantidad);
      if (normalizada === null) {
        return {
          ok: false,
          message: `La cantidad de ${nombre} tiene que ser un número, por ejemplo 0,25.`,
        };
      }
      if (!CANTIDAD_API.test(normalizada)) {
        return {
          ok: false,
          message: `La cantidad de ${nombre} admite hasta 6 enteros y 6 decimales.`,
        };
      }
    }
    lineas.push({
      seccion,
      nombre,
      cantidad: normalizada,
      comentario: comentario || null,
    });
  }
  return { ok: true, lineas };
}
