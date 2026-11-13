// Pure helpers of the materials page: what each material shows and how the materials are grouped.
// Nothing is calculated here: the price of a row is chosen among the ones the API sent.
import { STAGE_ORDER } from "./format";
import type { Material, Precio } from "./types";

export type FilaDeMaterial = {
  material: Material;
  /** The price for all colors in force today (else the newest one); null when there is none. */
  precio: Precio | null;
  /** How many prices by color are in force: they keep their own history and are not edited in the grid. */
  preciosPorColor: number;
};

export type GrupoDeMateriales = { etapa: string; filas: FilaDeMaterial[] };

function precioDeLaFila(historial: Precio[]): Precio | null {
  const generales = historial.filter((precio) => precio.color === null);
  const vigente = generales.find((precio) => precio.vigente);
  if (vigente) return vigente;
  // The API lists the newest first, so on a tie of dates the first one wins.
  return generales.reduce<Precio | null>(
    (mejor, precio) =>
      mejor === null || precio.vigente_desde > mejor.vigente_desde
        ? precio
        : mejor,
    null,
  );
}

/** Materials by stage, in the order of the quote (an unknown stage goes last), by name inside each stage. */
export function agruparMateriales(
  materiales: Material[],
  precios: Precio[],
): GrupoDeMateriales[] {
  const porMaterial = new Map<string, Precio[]>();
  for (const precio of precios) {
    const lista = porMaterial.get(precio.material) ?? [];
    lista.push(precio);
    porMaterial.set(precio.material, lista);
  }
  const posicion = (etapa: string) => {
    const index = STAGE_ORDER.indexOf(etapa);
    return index === -1 ? STAGE_ORDER.length : index;
  };
  const etapas = [
    ...new Set(materiales.map((material) => material.etapa)),
  ].sort((a, b) => posicion(a) - posicion(b) || a.localeCompare(b, "es-AR"));
  return etapas.map((etapa) => ({
    etapa,
    filas: materiales
      .filter((material) => material.etapa === etapa)
      .sort((a, b) => a.nombre.localeCompare(b.nombre, "es-AR"))
      .map((material) => {
        const historial = porMaterial.get(material.codigo) ?? [];
        return {
          material,
          precio: precioDeLaFila(historial),
          preciosPorColor: historial.filter(
            (precio) => precio.color !== null && precio.vigente,
          ).length,
        };
      }),
  }));
}
