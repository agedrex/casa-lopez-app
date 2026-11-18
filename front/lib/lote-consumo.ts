// View model of the consumption of a lot. Every quantity is calculated by the API
// (GET /ordenes/{codigo}/consumo); nothing here multiplies or adds. Quantities only, never money:
// the taller role reads this.

const SINGULAR: Record<string, string> = {
  m2: "m²",
  cm: "cm",
  m: "m",
  juego: "juego",
  unidad: "unidad",
};
const PLURAL: Record<string, string> = { juego: "juegos", unidad: "unidades" };

/** Unit as shown next to a quantity: `m2` → `m²`; countable units go plural unless the quantity is exactly 1. */
export function unidadTexto(unidad: string, cantidad?: string): string {
  const plural = PLURAL[unidad];
  if (plural && cantidad !== undefined && Number(cantidad) !== 1) return plural;
  return SINGULAR[unidad] ?? unidad;
}

/** `Estándar · Negro`, or just the name when the supply has no color. */
export function insumoTexto(insumo: {
  material_nombre: string;
  color: string | null;
}): string {
  return insumo.color
    ? `${insumo.material_nombre} · ${insumo.color}`
    : insumo.material_nombre;
}
