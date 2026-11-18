// Pure logic of the paginated, sortable tables (sort and slice). It knows nothing about React or the API.

export const PAGE_SIZE = 25;

export type Direccion = "asc" | "desc";
export type Orden = { clave: string; dir: Direccion };
export type Valor = string | number | null | undefined;

const collator = new Intl.Collator("es", {
  sensitivity: "base",
  numeric: true,
});

function vacio(valor: Valor): valor is null | undefined {
  return valor === null || valor === undefined || valor === "";
}

function comparar(a: NonNullable<Valor>, b: NonNullable<Valor>): number {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return collator.compare(String(a), String(b));
}

/**
 * A sorted copy: stable, and the empty values (NULL = missing data) go last in both directions, so
 * flipping the direction never brings the blanks to the top.
 */
export function ordenar<T>(
  items: readonly T[],
  valor: (item: T) => Valor,
  dir: Direccion,
): T[] {
  const sign = dir === "asc" ? 1 : -1;
  return items
    .map((item, index) => ({ item, index, value: valor(item) }))
    .sort((a, b) => {
      if (vacio(a.value) || vacio(b.value)) {
        if (vacio(a.value) && vacio(b.value)) return a.index - b.index;
        return vacio(a.value) ? 1 : -1;
      }
      return sign * comparar(a.value, b.value) || a.index - b.index;
    })
    .map((entry) => entry.item);
}

/** First click on a header sorts ascending; the same header again flips the direction. */
export function siguienteOrden(actual: Orden | null, clave: string): Orden {
  if (actual?.clave === clave) {
    return { clave, dir: actual.dir === "asc" ? "desc" : "asc" };
  }
  return { clave, dir: "asc" };
}

export function ariaSort(
  orden: Orden | null,
  clave: string,
): "ascending" | "descending" | "none" {
  if (orden?.clave !== clave) return "none";
  return orden.dir === "asc" ? "ascending" : "descending";
}

export type Pagina<T> = {
  items: T[];
  /** The page actually shown (the requested one, corrected to the nearest valid one). */
  pagina: number;
  paginas: number;
  total: number;
  /** 1-based position of the first and last row shown; 0 and 0 when there are none. */
  desde: number;
  hasta: number;
};

export function paginar<T>(
  items: readonly T[],
  pagina: number,
  tamano: number = PAGE_SIZE,
): Pagina<T> {
  const total = items.length;
  const paginas = Math.max(1, Math.ceil(total / tamano));
  const pedida = Number.isFinite(pagina) ? Math.trunc(pagina) : 1;
  const actual = Math.min(Math.max(pedida, 1), paginas);
  const inicio = (actual - 1) * tamano;
  const pedazo = items.slice(inicio, inicio + tamano);
  return {
    items: pedazo,
    pagina: actual,
    paginas,
    total,
    desde: pedazo.length === 0 ? 0 : inicio + 1,
    hasta: inicio + pedazo.length,
  };
}
