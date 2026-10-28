import Link from "next/link";
import {
  formatArs,
  formatDate,
  formatQuantity,
  lotStateLabel,
  whereLabel,
} from "@/lib/format";
import type { OrdenResumen } from "@/lib/types";
import { Avisos } from "./avisos";
import {
  Badge,
  CardItem,
  CardList,
  numClass,
  ResponsiveTable,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "./ui";

export function LotStateBadge({ estado }: { estado: string }) {
  return (
    <Badge tone={estado === "CERRADA" ? "good" : "neutral"}>
      {lotStateLabel(estado)}
    </Badge>
  );
}

/** "En taller · Nombre" or "En casa · Persona", as the sheet's "Dónde (para ver)". */
export function whereText(orden: OrdenResumen): string {
  const who =
    orden.donde_se_hace === "EXTERNA"
      ? (orden.taller_nombre ?? "falta el taller")
      : orden.persona_nombre;
  return who
    ? `${whereLabel(orden.donde_se_hace)} · ${who}`
    : whereLabel(orden.donde_se_hace);
}

export function OrdersTable({ ordenes }: { ordenes: OrdenResumen[] }) {
  return (
    <ResponsiveTable
      cards={
        <CardList>
          {ordenes.map((orden) => (
            <CardItem key={orden.codigo}>
              <Link
                href={`/fabricacion/${encodeURIComponent(orden.codigo)}`}
                className="block"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="font-bold underline decoration-gold underline-offset-4">
                    {orden.codigo}
                  </p>
                  <LotStateBadge estado={orden.estado} />
                </div>
                <p className="mt-1 text-sm text-muted">{whereText(orden)}</p>
                <p className="mt-1 text-xs text-muted">
                  {formatDate(orden.fecha_de_envio)} →{" "}
                  {formatDate(orden.fecha_de_entrega)} · {orden.productos}{" "}
                  {orden.productos === 1 ? "producto" : "productos"} ·{" "}
                  {formatQuantity(orden.unidades)} u.
                </p>
                <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm tabular-nums">
                  <div>
                    <dt className="text-xs text-muted">Cotizó el taller</dt>
                    <dd>{formatArs(orden.total_cotizado)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Cobró el taller</dt>
                    <dd>{formatArs(orden.total_cobrado)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Costo del lote</dt>
                    <dd>{formatArs(orden.costo_total)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Costo por unidad</dt>
                    <dd>{formatArs(orden.costo_promedio_por_unidad)}</dd>
                  </div>
                </dl>
              </Link>
              <div className="mt-2 empty:hidden">
                <Avisos avisos={orden.avisos} />
              </div>
            </CardItem>
          ))}
        </CardList>
      }
      table={
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Lote</th>
                <th className={thClass}>Dónde</th>
                <th className={thClass}>Envío</th>
                <th className={thClass}>Entrega</th>
                <th className={thClass}>Estado</th>
                <th className={`${thClass} ${numClass}`}>Productos</th>
                <th className={`${thClass} ${numClass}`}>Unidades</th>
                <th className={`${thClass} ${numClass}`}>Cotizó el taller</th>
                <th className={`${thClass} ${numClass}`}>Cobró el taller</th>
                <th className={`${thClass} ${numClass}`}>Costo del lote</th>
                <th className={`${thClass} ${numClass}`}>Costo por unidad</th>
                <th className={thClass}>Avisos</th>
              </tr>
            </thead>
            <tbody>
              {ordenes.map((orden) => (
                <tr key={orden.codigo} className="hover:bg-paper-mid/50">
                  <td className={tdClass}>
                    <Link
                      href={`/fabricacion/${encodeURIComponent(orden.codigo)}`}
                      className="underline decoration-gold underline-offset-4"
                    >
                      {orden.codigo}
                    </Link>
                  </td>
                  <td className={tdClass}>{whereText(orden)}</td>
                  <td className={tdClass}>
                    {formatDate(orden.fecha_de_envio)}
                  </td>
                  <td className={tdClass}>
                    {formatDate(orden.fecha_de_entrega)}
                  </td>
                  <td className={tdClass}>
                    <LotStateBadge estado={orden.estado} />
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {orden.productos}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatQuantity(orden.unidades)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(orden.total_cotizado)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(orden.total_cobrado)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(orden.costo_total)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(orden.costo_promedio_por_unidad)}
                  </td>
                  <td className={tdClass}>
                    <Avisos avisos={orden.avisos} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      }
    />
  );
}
