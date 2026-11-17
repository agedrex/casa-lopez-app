/** Text for the Retazos block of the Panel (Fábrica). The amounts themselves come calculated by the API. */

/** Notice shown when some written-off remainders have no price: the month total does not include them. */
export function retazosSinPrecioAviso(sinPrecio: number): string | null {
  if (!Number.isInteger(sinPrecio) || sinPrecio <= 0) return null;
  return sinPrecio === 1
    ? "Hay 1 retazo sin precio: el total no lo incluye."
    : `Hay ${sinPrecio} retazos sin precio: el total no los incluye.`;
}

/** `Cuero estándar` + `Negro` -> `Cuero estándar · Negro`; no color -> just the leather. */
export function cueroYColor(material: string, color: string | null): string {
  return color ? `${material} · ${color}` : material;
}
