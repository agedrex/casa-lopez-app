import {
  Notice,
  numClass,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { cueroYColor, retazosSinPrecioAviso } from "@/lib/costos-negocio";
import {
  formatArs,
  formatDate,
  formatPeriod,
  formatQuantity,
} from "@/lib/format";
import type { RetazosDelMes } from "@/lib/types";

/** Leather remainders written off this month: charged to the factory, read-only (calculated by the API, never written to the costs grid). */
export function RetazosDelMesTabla({ datos }: { datos: RetazosDelMes }) {
  const aviso = retazosSinPrecioAviso(datos.sin_precio);
  return (
    <section aria-label="Retazos de cuero del mes" className="space-y-3">
      <SectionTitle>
        Retazos de cuero de {formatPeriod(datos.periodo)}
      </SectionTitle>
      <p className="max-w-3xl text-sm text-muted">
        Cuando un resto de cuero ya no sirve y se da de baja en Cueros, los m²
        perdidos a lo que pagaste por m² de esa pieza se suman a los costos de
        la fábrica. Se calcula solo: no se carga acá.
      </p>
      {aviso ? (
        <Notice tone="info" title="Retazos sin precio">
          {aviso}
        </Notice>
      ) : null}
      {datos.retazos.length > 0 ? (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Fecha</th>
                <th className={thClass}>Pieza</th>
                <th className={thClass}>Cuero y color</th>
                <th className={`${thClass} ${numClass}`}>m²</th>
                <th className={`${thClass} ${numClass}`}>Precio por m²</th>
                <th className={`${thClass} ${numClass}`}>Total</th>
              </tr>
            </thead>
            <tbody>
              {datos.retazos.map((retazo, index) => (
                <tr key={`${retazo.pieza}|${retazo.fecha}|${index}`}>
                  <td className={tdClass}>{formatDate(retazo.fecha)}</td>
                  <td className={tdClass}>{retazo.pieza}</td>
                  <td className={tdClass}>
                    {cueroYColor(retazo.material, retazo.color)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatQuantity(retazo.m2)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {retazo.precio_por_m2_ars === null
                      ? "sin precio"
                      : formatArs(retazo.precio_por_m2_ars)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {retazo.total_ars === null
                      ? "sin precio"
                      : formatArs(retazo.total_ars)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-paper-mid font-bold">
                <th className={tdClass} scope="row" colSpan={5}>
                  Retazos del mes
                </th>
                <td className={`${tdClass} ${numClass}`}>
                  {formatArs(datos.total_retazos)}
                </td>
              </tr>
            </tfoot>
          </table>
        </TableWrap>
      ) : (
        <p className="text-sm text-muted">
          No hay retazos dados de baja en este mes.
        </p>
      )}
    </section>
  );
}
