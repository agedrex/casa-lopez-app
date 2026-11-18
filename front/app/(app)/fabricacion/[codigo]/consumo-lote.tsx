import Link from "next/link";
import {
  ErrorNotice,
  Notice,
  numClass,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatArs, formatDate } from "@/lib/format";
import { resumenDeConsumo } from "@/lib/lote-consumo";
import { collapseSpaces } from "@/lib/productos";
import type { ConsumoLote } from "@/lib/types";

/**
 * What the lot consumes: per product (each supply, per unit and for the lot quantity), then the total per supply
 * of the whole lot. Quantities only. `costoTotal` is passed for the admin alone (the taller never gets money):
 * it is the lot's cost, fixed at the lot's date, shown at the end.
 */
export async function ConsumoDelLote({
  codigo,
  vacio,
  costoTotal,
  fecha,
}: {
  codigo: string;
  vacio: boolean;
  costoTotal?: string | null;
  fecha?: string | null;
}) {
  if (vacio) return null;
  const result = await apiGet<ConsumoLote>(
    `/ordenes/${encodeURIComponent(codigo)}/consumo`,
  );
  if (!result.ok) {
    return (
      <section aria-label="Consumo del lote">
        <SectionTitle>Consumo del lote</SectionTitle>
        <ErrorNotice
          title="No pudimos calcular el consumo del lote."
          message={result.message}
        />
      </section>
    );
  }
  const resumen = resumenDeConsumo(result.data);
  return (
    <section aria-label="Consumo del lote" className="space-y-6">
      <div>
        <SectionTitle>Consumo del lote</SectionTitle>
        <p className="text-sm text-muted">{resumen.titular}</p>
      </div>
      <ul className="space-y-4">
        {resumen.productos.map((producto) => (
          <li
            key={producto.key}
            className="rounded-card border border-line bg-surface p-4 shadow-card"
          >
            <div className="flex items-baseline justify-between gap-4">
              <Link
                href={`/productos/${encodeURIComponent(producto.producto)}`}
                className="min-w-0 break-words font-bold underline decoration-gold underline-offset-4"
              >
                {collapseSpaces(producto.titulo)}
              </Link>
              <span className="shrink-0 text-sm text-muted">
                {producto.cantidad} a hacer
              </span>
            </div>
            {producto.sinConsumo ? (
              <p className="mt-2 text-sm text-muted">
                Este producto no tiene insumos cargados.
              </p>
            ) : (
              <dl className="mt-3 grid grid-cols-[1fr_auto_auto] gap-x-4 gap-y-1 text-sm">
                <dt className="text-xs uppercase tracking-caps-sm text-muted">
                  Insumo
                </dt>
                <dd className="text-right text-xs uppercase tracking-caps-sm text-muted">
                  Por unidad
                </dd>
                <dd className="text-right text-xs uppercase tracking-caps-sm text-muted">
                  En el lote
                </dd>
                {producto.insumos.map((insumo) => (
                  <div key={insumo.key} className="contents">
                    <dt className="min-w-0 break-words">{insumo.nombre}</dt>
                    <dd className="text-right tabular-nums text-muted">
                      {insumo.porUnidad}
                    </dd>
                    <dd className="text-right font-bold tabular-nums">
                      {insumo.total}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </li>
        ))}
      </ul>
      {resumen.sinConsumo.length > 0 ? (
        <Notice title="Sin insumos cargados (no se cuentan en el total)">
          {resumen.sinConsumo.join(", ")}
        </Notice>
      ) : null}
      {resumen.totales.length > 0 ? (
        <div>
          <h3 className="mb-2 font-display text-lg">
            Total de insumos del lote
          </h3>
          <TableWrap>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Insumo</th>
                  <th className={`${thClass} ${numClass}`}>Total</th>
                  <th className={`${thClass} ${numClass}`}>Productos</th>
                </tr>
              </thead>
              <tbody>
                {resumen.totales.map((total) => (
                  <tr key={total.key}>
                    <td className={tdClass}>{total.nombre}</td>
                    <td className={`${tdClass} ${numClass} font-bold`}>
                      {total.total}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {total.productos}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        </div>
      ) : null}
      {costoTotal !== undefined ? (
        <div className="rounded-card border border-line bg-surface p-5 shadow-card">
          <p className="text-xs uppercase tracking-caps-sm text-muted">
            Costo total del lote
          </p>
          <p className="mt-2 font-display text-2xl tabular-nums">
            {formatArs(costoTotal)}
          </p>
          <p className="mt-1 text-xs text-muted">
            {fecha
              ? `Con los precios y el dólar del ${formatDate(fecha)}, la fecha del lote: no cambia después.`
              : "El lote no tiene fecha: se calcula con los precios de hoy."}
          </p>
        </div>
      ) : null}
    </section>
  );
}
