// Shared by the voice screen (client and server): copy, field names and the browser's speech-recognition types.
// Plain data and pure helpers: no "use server" (that file may only export functions) and no money maths.

import type { VozAccion, VozPropuesta } from "./types";

export const VOZ_MAX_CHARS = 500;

/** What the confirmation card sends as the source note of what it loads. The API stores it as written. */
export const VOZ_NOTA = "Carga por voz (confirmada por una persona)";

export type InterpretarState = {
  status: "idle" | "ok" | "error";
  message?: string;
  /** Changes with every answer, so the card of a new proposal starts from scratch. */
  id?: string;
  propuesta?: VozPropuesta;
};

export const INTERPRETAR_IDLE: InterpretarState = { status: "idle" };

// Examples are UI copy only: they show how to phrase a request, nothing is loaded from them.
export const VOZ_EXAMPLES: string[] = [
  "Cargá el cuero estándar a 26 dólares el metro cuadrado desde hoy",
  "El dólar vendedor hoy está a 1480",
  "Agregale al producto PRD-0001 flex, consumo 0,25",
  "Pagamos 14.000 por unidad en el lote LOT-0003",
  "El monto de la luz de la fábrica de este mes es 180.000 pesos",
];

export const VOZ_ACTION_LABELS: Record<VozAccion, string> = {
  cargar_precio: "Cargar un precio de material",
  cargar_dolar: "Cargar el dólar",
  agregar_extra: "Agregar un extra a un producto",
  registrar_precio_taller: "Registrar el precio de un taller",
  cargar_monto_gasto: "Cargar el monto de un costo fijo",
  desconocida: "No entendí el pedido",
};

// Names the API uses in `faltantes`, worded for people.
export const VOZ_FIELD_LABELS: Record<string, string> = {
  material: "Material",
  color: "Color",
  precio: "Precio",
  moneda: "Moneda",
  vigente_desde: "Fecha desde la que rige",
  ars_por_usd: "Pesos por dólar",
  tipo: "Tipo de dólar",
  fecha: "Fecha",
  producto: "Producto",
  consumo_neto_por_unidad: "Consumo por unidad",
  lote: "Lote",
  item: "Renglón del lote",
  taller: "Taller",
  precio_de: "Qué precio es",
  gasto: "Costo fijo",
  periodo: "Período",
  monto_ars_del_mes: "Monto en pesos",
  datos: "Datos",
};

export function fieldLabel(name: string): string {
  return VOZ_FIELD_LABELS[name] ?? name;
}

// --- Web Speech API ---------------------------------------------------------------------------------------------
// Not in TypeScript's DOM lib. Chrome and Edge ship it as `webkitSpeechRecognition` (unprefixed from Chrome 139), Safari
// 14.1+ only with the `webkit` prefix, Firefox has no support yet (MDN browser-compat-data, checked 2026-10-28). It also
// needs a secure context (https or localhost).

type SpeechAlternative = { transcript: string };
type SpeechResult = ArrayLike<SpeechAlternative> & { isFinal: boolean };

export type SpeechResultEvent = {
  results: ArrayLike<SpeechResult>;
};

export type SpeechErrorEvent = { error: string };

export type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
};

export type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type SpeechWindow = {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
  isSecureContext?: boolean;
};

/** The browser's recognizer (prefixed or not), or null where there is none or the page is not a secure context. */
export function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const speech = window as unknown as SpeechWindow;
  if (speech.isSecureContext === false) return null;
  return speech.SpeechRecognition ?? speech.webkitSpeechRecognition ?? null;
}

/** Joins what was already typed with what was just said, without a double space. */
export function joinSpoken(base: string, spoken: string): string {
  return `${base.trim()} ${spoken.trim()}`.trim().slice(0, VOZ_MAX_CHARS);
}

const SPEECH_ERRORS: Record<string, string> = {
  "not-allowed":
    "El navegador no tiene permiso para usar el micrófono. Habilítelo en la barra de direcciones o escriba el pedido.",
  "service-not-allowed":
    "El navegador no permite el reconocimiento de voz en este sitio. Escriba el pedido.",
  "no-speech": "No se escuchó nada. Pruebe de nuevo o escriba el pedido.",
  "audio-capture": "No se encontró un micrófono. Escriba el pedido.",
  network:
    "El reconocimiento de voz del navegador necesita conexión a internet. Escriba el pedido.",
  "language-not-supported":
    "Este navegador no reconoce el español de Argentina. Escriba el pedido.",
};

/** Spanish text for a recognizer error code; null for the ones that are not a problem (the person stopped it). */
export function speechErrorMessage(code: string): string | null {
  if (code === "aborted") return null;
  return (
    SPEECH_ERRORS[code] ??
    "El reconocimiento de voz falló. Pruebe de nuevo o escriba el pedido."
  );
}
