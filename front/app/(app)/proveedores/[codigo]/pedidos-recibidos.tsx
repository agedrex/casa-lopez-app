import {
  Card,
  numClass,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import {
  formatDate,
  formatMoney,
  formatQuantity,
  formatRate,
} from "@/lib/format";
import type { PedidoProveedor } from "@/lib/types";

/** Orders already registered, newest first. Read only: an order is never edited or deleted. */
export function PedidosRecibidos({ pedidos }: { pedidos: PedidoProveedor[] }) {
  return (
    <ul className="space-y-4">
      {pedidos.map((pedido) => (
        <li key={pedido.codigo}>
          <Card>
            <div className="mb-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <span className="font-bold">{pedido.codigo}</span>
              <span className="text-sm">
                Recibido el {formatDate(pedido.fecha_de_recepcion)}
              </span>
              {pedido.remito ? (
                <span className="text-sm text-muted">
                  Remito: {pedido.remito}
                </span>
              ) : null}
            </div>
            {pedido.nota ? (
              <p className="mb-3 text-sm text-muted">{pedido.nota}</p>
            ) : null}
            <TableWrap>
              <table className={tableClass}>
                <thead>
                  <tr>
                    <th className={thClass}>Material</th>
                    <th className={thClass}>Llegó</th>
                    <th className={`${thClass} ${numClass}`}>Contenido</th>
                    <th className={`${thClass} ${numClass}`}>Precio</th>
                    <th className={`${thClass} ${numClass}`}>
                      Precio unitario
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {pedido.lineas.map((linea) => (
                    <tr key={linea.orden}>
                      <td className={tdClass}>
                        {linea.material_nombre}
                        <span className="block text-xs text-muted">
                          {linea.material}
                        </span>
                      </td>
                      <td className={tdClass}>
                        {formatQuantity(linea.cantidad_presentaciones)} ×{" "}
                        {linea.presentacion}
                      </td>
                      <td className={`${tdClass} ${numClass}`}>
                        {formatQuantity(linea.contenido_por_presentacion)}{" "}
                        {linea.unidad_de_consumo}
                      </td>
                      <td className={`${tdClass} ${numClass}`}>
                        {formatMoney(
                          linea.precio_por_presentacion,
                          linea.moneda,
                        )}
                        {linea.iva_incluido ? (
                          <span className="block text-xs text-muted">
                            con IVA
                          </span>
                        ) : null}
                      </td>
                      <td className={`${tdClass} ${numClass}`}>
                        {linea.moneda} {formatRate(linea.precio_unitario)}
                        <span className="block text-xs text-muted">
                          por {linea.unidad_de_consumo}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          </Card>
        </li>
      ))}
    </ul>
  );
}
