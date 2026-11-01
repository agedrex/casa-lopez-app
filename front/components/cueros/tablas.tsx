import Link from "next/link";
import {
  CardItem,
  CardList,
  numClass,
  ResponsiveTable,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { grupoTitulo } from "@/lib/cueros";
import {
  formatArs,
  formatDate,
  formatMoney,
  formatPercent,
  formatQuantity,
} from "@/lib/format";
import type { GrupoCuero, PiezaCuero } from "@/lib/types";
import { EstadoBadge } from "./estado-badge";
import { GrupoCard, PiezaFila } from "./grupo-card";

type Nombres = Record<string, string>;

const m2 = (value: string | null) => `${formatQuantity(value)} m²`;

/** "Todo junto": one row per leather and color (cards on the phone). */
export function GruposTabla({
  grupos,
  nombres,
  showMoney,
}: {
  grupos: GrupoCuero[];
  nombres: Nombres;
  showMoney: boolean;
}) {
  return (
    <ResponsiveTable
      cards={
        <CardList>
          {grupos.map((grupo) => (
            <GrupoCard
              key={`${grupo.material}|${grupo.color ?? ""}`}
              grupo={grupo}
              titulo={grupoTitulo(
                nombres[grupo.material] ?? grupo.material,
                grupo.color,
              )}
              showMoney={showMoney}
              conPiezas={false}
            />
          ))}
        </CardList>
      }
      table={
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Cuero</th>
                <th className={thClass}>Color</th>
                <th className={`${thClass} ${numClass}`}>Comprado</th>
                <th className={`${thClass} ${numClass}`}>Desp. natural 10 %</th>
                <th className={`${thClass} ${numClass}`}>Total real</th>
                <th className={`${thClass} ${numClass}`}>Cortado</th>
                <th className={`${thClass} ${numClass}`}>Irrecuperable</th>
                <th className={`${thClass} ${numClass}`}>Disponible</th>
                <th className={`${thClass} ${numClass}`}>Desp. neto</th>
                {showMoney ? (
                  <th className={`${thClass} ${numClass}`}>Costo desp.</th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {grupos.map((grupo) => (
                <tr key={`${grupo.material}|${grupo.color ?? ""}`}>
                  <td className={tdClass}>
                    {nombres[grupo.material] ?? grupo.material}
                  </td>
                  <td className={tdClass}>{grupo.color ?? "Sin color"}</td>
                  <td className={`${tdClass} ${numClass}`}>
                    {m2(grupo.comprado)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {m2(grupo.natural)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {m2(grupo.cuero_total_real)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {m2(grupo.cortado)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {m2(grupo.irrecuperable)}
                  </td>
                  <td
                    className={`${tdClass} ${numClass} bg-parchment font-bold`}
                  >
                    {m2(grupo.disponible)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatPercent(grupo.porcentaje_desperdicio_neto)}
                  </td>
                  {showMoney ? (
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(grupo.costo_desperdicio_ars)}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      }
    />
  );
}

/** "Todo junto": every skin with its state and what is left (cards on the phone). */
export function PiezasTabla({
  piezas,
  nombres,
  showMoney,
}: {
  piezas: PiezaCuero[];
  nombres: Nombres;
  showMoney: boolean;
}) {
  return (
    <ResponsiveTable
      cards={
        <CardList>
          {piezas.map((pieza) => (
            <CardItem key={pieza.codigo}>
              <p className="mb-2 text-sm text-muted">
                {grupoTitulo(
                  nombres[pieza.material] ?? pieza.material,
                  pieza.color,
                )}
              </p>
              <PiezaFila pieza={pieza} showMoney={showMoney} />
            </CardItem>
          ))}
        </CardList>
      }
      table={
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Piel</th>
                <th className={thClass}>Cuero</th>
                <th className={thClass}>Color</th>
                <th className={thClass}>Estado</th>
                <th className={thClass}>Compra</th>
                <th className={thClass}>Proveedor</th>
                <th className={`${thClass} ${numClass}`}>Inicial</th>
                <th className={`${thClass} ${numClass}`}>Disponible</th>
                {showMoney ? (
                  <th className={`${thClass} ${numClass}`}>Precio por m²</th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {piezas.map((pieza) => (
                <tr key={pieza.codigo}>
                  <td className={tdClass}>
                    <Link
                      href={`/cueros/${encodeURIComponent(pieza.codigo)}`}
                      className="font-bold underline decoration-gold underline-offset-4"
                    >
                      {pieza.codigo}
                    </Link>
                  </td>
                  <td className={tdClass}>
                    {nombres[pieza.material] ?? pieza.material}
                  </td>
                  <td className={tdClass}>{pieza.color ?? "Sin color"}</td>
                  <td className={tdClass}>
                    <EstadoBadge estado={pieza.estado} />
                  </td>
                  <td className={tdClass}>
                    {formatDate(pieza.fecha_de_compra)}
                  </td>
                  <td className={tdClass}>{pieza.proveedor ?? "—"}</td>
                  <td className={`${tdClass} ${numClass}`}>
                    {m2(pieza.m2_iniciales)}
                  </td>
                  <td className={`${tdClass} ${numClass} font-bold`}>
                    {m2(pieza.disponible)}
                  </td>
                  {showMoney ? (
                    <td className={`${tdClass} ${numClass}`}>
                      {pieza.precio_pagado_por_m2 && pieza.moneda
                        ? formatMoney(pieza.precio_pagado_por_m2, pieza.moneda)
                        : "—"}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      }
    />
  );
}
