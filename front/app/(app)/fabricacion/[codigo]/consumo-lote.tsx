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
import { collapseSpaces } from "@/lib/productos";
import type { ConsumoLote, LoteCuero } from "@/lib/types";
import { tablaDeInsumos } from "./insumos-lote";

/**
 * The supplies of the lot in one table: total per supply and, in the leather rows, whether the stock is enough.
 * The detail per product is folded. Quantities only. `costoTotal` is passed for the admin alone (the taller never
 * gets money): it is the lot's cost, fixed at the lot's date, shown at the end. A closed lot has nothing left to
 * cut, so it skips the leather stock.
 */
export async function ConsumoDelLote({
  codigo,
  estado,
  vacio,
  costoTotal,
  fecha,
}: {
  codigo: string;
  estado: string;
  vacio: boolean;
  costoTotal?: string | null;
  fecha?: string | null;
}) {
  if (vacio) return null;
  const ruta = `/ordenes/${encodeURIComponent(codigo)}`;
  const [consumo, cuero] = await Promise.all([
    apiGet<ConsumoLote>(`${ruta}/consumo`),
    estado === "CERRADA" ? null : apiGet<LoteCuero>(`${ruta}/cuero`),
  ]);
  if (!consumo.ok) {
    return (
      <section aria-label="Insumos del lote">
        <SectionTitle>Insumos del lote</SectionTitle>
        <ErrorNotice
          title="No pudimos calcular los insumos del lote."
          message={consumo.message}
        />
      </section>
    );
  }
  const tabla = tablaDeInsumos(consumo.data, cuero?.ok ? cuero.data : null);
  return (
    <section aria-label="Insumos del lote" className="space-y-4">
      <SectionTitle>Insumos del lote</SectionTitle>
      {tabla.hayCuero ? (
        <p
          className={`text-sm ${tabla.faltan > 0 ? "font-bold text-bordeaux" : "text-muted"}`}
          role={tabla.faltan > 0 ? "alert" : undefined}
        >
          {tabla.titularCuero}
        </p>
      ) : null}
      {cuero && !cuero.ok ? (
        <ErrorNotice
          title="No pudimos calcular el stock de cuero."
          message={cuero.message}
        />
      ) : null}
      {tabla.filas.length === 0 ? (
        <Notice tone="info" title="Todavía no hay insumos para este lote." />
      ) : (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Insumo</th>
                <th className={`${thClass} ${numClass}`}>Total</th>
                {tabla.hayCuero ? <th className={thClass}>Stock</th> : null}
              </tr>
            </thead>
            <tbody>
              {tabla.filas.map((fila) => (
                <tr key={fila.key}>
                  <td className={tdClass}>{fila.nombre}</td>
                  <td className={`${tdClass} ${numClass} font-bold`}>
                    {fila.total}
                  </td>
                  {tabla.hayCuero ? (
                    <td
                      className={`${tdClass} ${fila.falta ? "font-bold text-bordeaux" : "text-muted"}`}
                    >
                      {fila.cuero ?? "—"}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
      {tabla.sinConsumo.length > 0 ? (
        <Notice title="Sin insumos cargados (no se cuentan)">
          {tabla.sinConsumo.join(", ")}
        </Notice>
      ) : null}
      {tabla.sinConsumoDeCuero.length > 0 ? (
        <Notice title="Sin consumo de cuero (no entran en el stock)">
          {tabla.sinConsumoDeCuero.join(", ")}
        </Notice>
      ) : null}
      {tabla.productos.length > 0 ? (
        <details className="rounded-card border border-line bg-surface shadow-card">
          <summary className="min-h-11 cursor-pointer px-4 py-3 text-base">
            Detalle por producto
          </summary>
          <ul className="space-y-4 px-4 pb-4">
            {tabla.productos.map((producto) => (
              <li key={producto.key}>
                <div className="flex items-baseline justify-between gap-4">
                  <Link
                    href={`/productos/${encodeURIComponent(producto.producto)}`}
                    className="min-w-0 break-words font-bold underline decoration-gold underline-offset-4"
                  >
                    {collapseSpaces(producto.titulo)}
                  </Link>
                  <span className="shrink-0 text-sm text-muted">
                    × {producto.cantidad}
                  </span>
                </div>
                {producto.sinConsumo ? (
                  <p className="mt-1 text-sm text-muted">
                    Sin insumos cargados.
                  </p>
                ) : (
                  <dl className="mt-2 grid grid-cols-[1fr_auto_auto] gap-x-4 gap-y-1 text-sm">
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
        </details>
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
              ? `Precios y dólar del ${formatDate(fecha)}. No cambia después.`
              : "Sin fecha de lote: se usan los precios de hoy."}
          </p>
        </div>
      ) : null}
    </section>
  );
}
