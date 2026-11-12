import {
  Badge,
  Card,
  numClass,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { formatDate, formatMoney } from "@/lib/format";
import type { MaterialDeProveedor } from "@/lib/types";
import { MiniBar, VariationBadge } from "../historial-ui";

/**
 * What a supplier charges, material by material. The summary line has the latest price and how much it
 * changed; opening a material shows every price it had, oldest at the bottom. Nothing is calculated here.
 */
export function MaterialesDelProveedor({
  materiales,
}: {
  materiales: MaterialDeProveedor[];
}) {
  return (
    <ul className="space-y-3">
      {materiales.map((item) => (
        <li key={`${item.material}|${item.color ?? ""}`}>
          <Card>
            <details className="group">
              <summary className="flex cursor-pointer flex-wrap items-center gap-x-4 gap-y-2">
                <span className="min-w-48 flex-1">
                  <span className="font-bold">{item.material_nombre}</span>
                  <span className="block text-xs text-muted">
                    {item.material}
                    {item.color ? ` · ${item.color}` : ""}
                  </span>
                </span>
                <span className="tabular-nums">
                  {formatMoney(item.ultimo_precio, item.moneda)}
                  <span className="text-xs text-muted">
                    {" "}
                    por {item.unidad_del_precio} · desde{" "}
                    {formatDate(item.ultima_fecha)}
                  </span>
                </span>
                <span className="flex items-center gap-2 text-xs text-muted">
                  Último cambio
                  <VariationBadge value={item.variacion_ultima_pct} />
                </span>
                <Badge>
                  {item.cargas === 1 ? "1 precio" : `${item.cargas} precios`}
                </Badge>
              </summary>
              <div className="mt-4">
                {item.variacion_total_pct !== null ? (
                  <p className="mb-3 text-sm text-muted">
                    Desde el primer precio cargado cambió{" "}
                    <VariationBadge value={item.variacion_total_pct} />
                  </p>
                ) : null}
                <TableWrap>
                  <table className={tableClass}>
                    <thead>
                      <tr>
                        <th className={thClass}>Desde</th>
                        <th className={`${thClass} ${numClass}`}>Precio</th>
                        <th className={thClass}>Unidad</th>
                        <th className={thClass}>Variación</th>
                        <th className={thClass}>
                          <span className="sr-only">Comparación</span>
                        </th>
                        <th className={thClass}>Nota</th>
                      </tr>
                    </thead>
                    <tbody>
                      {item.historial.map((precio) => (
                        <tr key={precio.codigo}>
                          <td className={tdClass}>
                            {formatDate(precio.vigente_desde)}
                          </td>
                          <td className={`${tdClass} ${numClass}`}>
                            {formatMoney(precio.precio, precio.moneda)}
                            {precio.iva_incluido ? (
                              <span className="block text-xs text-muted">
                                con IVA
                              </span>
                            ) : null}
                          </td>
                          <td className={tdClass}>
                            {precio.unidad_del_precio}
                          </td>
                          <td className={tdClass}>
                            <VariationBadge
                              value={precio.variacion_pct}
                              bigJump={precio.salto_grande}
                            />
                          </td>
                          <td className={tdClass}>
                            <MiniBar
                              pct={precio.barra_pct}
                              label={formatMoney(precio.precio, precio.moneda)}
                            />
                          </td>
                          <td className={tdClass}>
                            {precio.nota_fuente ?? "—"}
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
  );
}
