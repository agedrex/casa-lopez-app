// View model of the leather summary of a lot. Every square meter figure is calculated by the API
// (GET /ordenes/{codigo}/cuero); nothing here adds or subtracts. Square meters, never money.

import { grupoTitulo, isPositive } from "./cueros";
import { formatQuantity } from "./format";
import type { LoteCuero, LoteCueroGrupo } from "./types";

export type EstadoDeCuero = "FALTA" | "ALCANZA" | "YA_CORTADO";

export type TarjetaDeCuero = {
  key: string;
  titulo: string;
  estado: EstadoDeCuero;
  /** Headline of the card: `Falta 0,5 m²`, `Alcanza · sobran 2 m²`, `Ya está cortado`. */
  mensaje: string;
  /** `Necesita`, `Hay`, (when something was cut) `Ya cortado` and (when other lots hold some) `Reservado por …` and `Libre`, each with its m². */
  cifras: { label: string; value: string }[];
  /** Codes of the products of the lot that use this leather. */
  productos: string[];
  /** Shortage explanation written by the API (stock, reserved by other lots); null when it fits. */
  aviso: string | null;
};

export type ResumenDeCuero = {
  tarjetas: TarjetaDeCuero[];
  /** How many leathers are short. */
  faltan: number;
  /** One line for the top of the section. */
  titular: string;
  sinConsumo: LoteCuero["sin_consumo"];
};

function m2(value: string): string {
  return `${formatQuantity(value)} m²`;
}

/** Short beats enough beats nothing left to cut. */
export function estadoDeCuero(grupo: LoteCueroGrupo): EstadoDeCuero {
  if (!isPositive(grupo.por_cortar)) return "YA_CORTADO";
  return grupo.alcanza ? "ALCANZA" : "FALTA";
}

const ORDEN: Record<EstadoDeCuero, number> = {
  FALTA: 0,
  ALCANZA: 1,
  YA_CORTADO: 2,
};

function mensajeDe(grupo: LoteCueroGrupo, estado: EstadoDeCuero): string {
  if (estado === "FALTA") return `Falta ${m2(grupo.faltante)}`;
  if (estado === "YA_CORTADO") return "Ya está cortado";
  return isPositive(grupo.sobrante)
    ? `Alcanza · sobran ${m2(grupo.sobrante)}`
    : "Alcanza justo";
}

function titularDe(faltan: number, total: number): string {
  if (total === 0) return "Todavía no hay consumo de cuero para este lote.";
  if (faltan === 0) return "Hay cuero para todo el lote.";
  return faltan === 1
    ? "Falta cuero de 1 tipo."
    : `Falta cuero de ${faltan} tipos.`;
}

/** Cards for the phone: leathers that are short first, then the ones that fit, then the ones already cut. */
export function resumenDeCuero(datos: LoteCuero): ResumenDeCuero {
  const tarjetas = datos.cueros
    .map((grupo, index): [TarjetaDeCuero, number] => {
      const estado = estadoDeCuero(grupo);
      const cifras = [
        { label: "Necesita", value: m2(grupo.necesario) },
        ...(isPositive(grupo.ya_cortado)
          ? [{ label: "Ya cortado", value: m2(grupo.ya_cortado) }]
          : []),
        { label: "Hay", value: m2(grupo.disponible) },
        ...(isPositive(grupo.reservado_por_otros)
          ? [
              {
                label: `Reservado por ${grupo.reservado_por.join(", ")}`,
                value: m2(grupo.reservado_por_otros),
              },
              { label: "Libre para este lote", value: m2(grupo.libre) },
            ]
          : []),
      ];
      return [
        {
          key: `${grupo.material}|${grupo.color ?? ""}`,
          titulo: grupoTitulo(grupo.material_nombre, grupo.color),
          estado,
          mensaje: mensajeDe(grupo, estado),
          cifras,
          productos: grupo.productos,
          aviso: estado === "FALTA" ? grupo.mensaje : null,
        },
        index,
      ];
    })
    .sort(([a, i], [b, j]) => ORDEN[a.estado] - ORDEN[b.estado] || i - j)
    .map(([tarjeta]) => tarjeta);
  const faltan = tarjetas.filter((t) => t.estado === "FALTA").length;
  return {
    tarjetas,
    faltan,
    titular: titularDe(faltan, tarjetas.length),
    sinConsumo: datos.sin_consumo,
  };
}
