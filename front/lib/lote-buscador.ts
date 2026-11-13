// Pure helpers of the product finder of the new-lot form. The search itself runs in the API
// (`GET /productos?q=`); here only the text is prepared and the picked rows are managed.
// No money is read or calculated: the results keep code, name, model and category only.
import { collapseSpaces } from "./productos";
import type { ProductoResumen } from "./types";

/** Shorter searches match half the catalog and say nothing. */
export const MIN_QUERY = 2;
/** Results shown at once; the API is asked for one more to know whether the list was cut. */
export const RESULT_LIMIT = 20;
// The API refuses a `q` longer than this (422).
const MAX_QUERY = 100;

export type ResultadoDeBusqueda = {
  codigo: string;
  nombre: string;
  modelo: string | null;
  categoria: string | null;
};

/** One product picked for the lot, with the quantity still as typed text. */
export type FilaDeLote = {
  id: number;
  producto: string;
  nombre: string;
  cantidad: string;
};

/** The text to search, or null while it is too short to be worth a call. */
export function consultaDeBusqueda(raw: string): string | null {
  const texto = collapseSpaces(raw).slice(0, MAX_QUERY).trim();
  return texto.length >= MIN_QUERY ? texto : null;
}

export function rutaDeBusqueda(consulta: string): string {
  return `/productos?limit=${RESULT_LIMIT + 1}&q=${encodeURIComponent(consulta)}`;
}

export function resultadosDeBusqueda(filas: ProductoResumen[]): {
  resultados: ResultadoDeBusqueda[];
  hayMas: boolean;
} {
  return {
    resultados: filas.slice(0, RESULT_LIMIT).map((fila) => ({
      codigo: fila.codigo,
      nombre: collapseSpaces(fila.nombre),
      modelo: fila.modelo,
      categoria: fila.categoria,
    })),
    hayMas: filas.length > RESULT_LIMIT,
  };
}

/** Adds the product as a new row; a product already in the lot stays as it is (change its quantity instead). */
export function agregarProducto(
  filas: FilaDeLote[],
  resultado: ResultadoDeBusqueda,
  id: number,
): FilaDeLote[] {
  if (filas.some((fila) => fila.producto === resultado.codigo)) return filas;
  return [
    ...filas,
    { id, producto: resultado.codigo, nombre: resultado.nombre, cantidad: "" },
  ];
}

export function quitarProducto(filas: FilaDeLote[], id: number): FilaDeLote[] {
  return filas.filter((fila) => fila.id !== id);
}

/** Value of the "who makes it" choice that means the house itself. */
export const FABRICA = "FABRICA";

/** The API takes the place and the workshop apart: the factory is INTERNA with no workshop. */
export function responsableDelLote(responsable: string): {
  donde: "INTERNA" | "EXTERNA";
  taller: string;
} {
  return responsable === FABRICA
    ? { donde: "INTERNA", taller: "" }
    : { donde: "EXTERNA", taller: responsable };
}
