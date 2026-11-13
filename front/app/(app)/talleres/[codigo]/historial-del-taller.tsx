import Link from "next/link";
import { LotStateBadge } from "@/components/orders-table";
import {
  Badge,
  Card,
  numClass,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { formatArs, formatDate, formatQuantity } from "@/lib/format";
import { ordenarLotes } from "@/lib/lotes";
import type { HistorialDeTaller } from "@/lib/types";
import { MiniBar, VariationBadge } from "../../proveedores/historial-ui";

const lotLink = (code: string) => `/fabricacion/${encodeURIComponent(code)}`;

/**
 * What was given to the workshop and what it was paid. Everything comes calculated by the API: this
 * only lays it out. A lot's average per unit mixes products, so it is shown but not compared with
 * other lots; the comparison in time is per product, below.
 */
export function HistorialDelTaller({
  historial,
}: {
  historial: HistorialDeTaller;
}) {
  return (
    <>
      <section>
        <SectionTitle>Lo pagado, lote por lote</SectionTitle>
        <p className="mb-4 text-sm text-muted">
          Unidades y total pagado de cada lote, del más nuevo al más viejo. El
          promedio por unidad mezcla productos distintos: para ver si un precio
          subió, mirá cada producto más abajo.
        </p>
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Lote</th>
                <th className={thClass}>Fecha</th>
                <th className={thClass}>Estado</th>
                <th className={`${thClass} ${numClass}`}>Productos</th>
                <th className={`${thClass} ${numClass}`}>Unidades</th>
                <th className={`${thClass} ${numClass}`}>Total pagado</th>
                <th className={thClass}>
                  <span className="sr-only">Comparación del total</span>
                </th>
                <th className={`${thClass} ${numClass}`}>
                  Promedio por unidad
                </th>
              </tr>
            </thead>
            <tbody>
              {ordenarLotes(historial.lotes).map((lote) => (
                <tr key={lote.lote}>
                  <td className={tdClass}>
                    <Link
                      href={lotLink(lote.lote)}
                      className="underline decoration-gold underline-offset-4"
                    >
                      {lote.lote}
                    </Link>
                  </td>
                  <td className={tdClass}>{formatDate(lote.fecha)}</td>
                  <td className={tdClass}>
                    <LotStateBadge estado={lote.estado} />
                  </td>
                  <td className={`${tdClass} ${numClass}`}>{lote.productos}</td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatQuantity(lote.unidades)}
                    {lote.unidades_con_precio_pagado !== lote.unidades ? (
                      <span className="block text-xs text-muted">
                        {formatQuantity(lote.unidades_con_precio_pagado)} con
                        precio pagado
                      </span>
                    ) : null}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {lote.precio_pagado_promedio === null
                      ? "Sin precio pagado"
                      : formatArs(lote.total_pagado)}
                  </td>
                  <td className={tdClass}>
                    <MiniBar
                      pct={lote.barra_pct}
                      label={formatArs(lote.total_pagado)}
                    />
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(lote.precio_pagado_promedio)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </section>

      <section>
        <SectionTitle>
          Productos que se le dieron y cómo cambió el precio
        </SectionTitle>
        <ul className="space-y-3">
          {historial.productos.map((producto) => (
            <li key={producto.producto}>
              <Card>
                <details>
                  <summary className="flex cursor-pointer flex-wrap items-center gap-x-4 gap-y-2">
                    <span className="min-w-48 flex-1">
                      <span className="font-bold">
                        {producto.producto_nombre}
                      </span>
                      <span className="block text-xs text-muted">
                        {producto.producto}
                        {producto.categoria ? ` · ${producto.categoria}` : ""}
                      </span>
                    </span>
                    <span className="tabular-nums">
                      {producto.ultimo_pagado === null
                        ? "Sin precio pagado"
                        : `${formatArs(producto.ultimo_pagado)} por unidad`}
                      <span className="text-xs text-muted">
                        {" "}
                        · último {formatDate(producto.ultima_fecha)}
                      </span>
                    </span>
                    <span className="flex items-center gap-2 text-xs text-muted">
                      Último cambio
                      <VariationBadge value={producto.variacion_ultima_pct} />
                    </span>
                    <Badge>
                      {producto.lotes === 1
                        ? "1 lote"
                        : `${producto.lotes} lotes`}{" "}
                      · {formatQuantity(producto.unidades)} u.
                    </Badge>
                  </summary>
                  <div className="mt-4">
                    {producto.variacion_total_pct !== null ? (
                      <p className="mb-3 text-sm text-muted">
                        Del primer precio pagado (
                        {formatArs(producto.primer_pagado)}) al último cambió{" "}
                        <VariationBadge value={producto.variacion_total_pct} />
                      </p>
                    ) : null}
                    <TableWrap>
                      <table className={tableClass}>
                        <thead>
                          <tr>
                            <th className={thClass}>Fecha</th>
                            <th className={thClass}>Lote</th>
                            <th className={`${thClass} ${numClass}`}>
                              Cantidad
                            </th>
                            <th className={`${thClass} ${numClass}`}>
                              Pidió por unidad
                            </th>
                            <th className={`${thClass} ${numClass}`}>
                              Se pagó por unidad
                            </th>
                            <th className={thClass}>Variación</th>
                            <th className={thClass}>
                              <span className="sr-only">Comparación</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {producto.historial.map((pago) => (
                            <tr key={pago.item}>
                              <td className={tdClass}>
                                {formatDate(pago.fecha)}
                              </td>
                              <td className={tdClass}>
                                <Link
                                  href={lotLink(pago.lote)}
                                  className="underline decoration-gold underline-offset-4"
                                >
                                  {pago.lote}
                                </Link>
                              </td>
                              <td className={`${tdClass} ${numClass}`}>
                                {formatQuantity(pago.cantidad)}
                              </td>
                              <td className={`${tdClass} ${numClass}`}>
                                {formatArs(pago.cotizado)}
                              </td>
                              <td className={`${tdClass} ${numClass}`}>
                                {pago.pagado === null
                                  ? "Todavía sin pagar"
                                  : formatArs(pago.pagado)}
                              </td>
                              <td className={tdClass}>
                                <VariationBadge
                                  value={pago.variacion_pct}
                                  bigJump={pago.salto_grande}
                                />
                              </td>
                              <td className={tdClass}>
                                <MiniBar
                                  pct={pago.barra_pct}
                                  label={formatArs(pago.pagado)}
                                />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </TableWrap>
                  </div>
                </details>
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
