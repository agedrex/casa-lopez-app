import type { Metadata } from "next";
import Link from "next/link";
import {
  Badge,
  ErrorNotice,
  Notice,
  numClass,
  PageHeader,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatArs, formatDate, formatQuantity } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { ProductoReventa } from "@/lib/types";
import { formatMargenPct } from "./margen";

export const metadata: Metadata = { title: "Reventa" };

export default async function ReventaPage() {
  const { user } = await requireSession();
  const result = await apiGet<ProductoReventa[]>("/reventa");

  return (
    <>
      <PageHeader
        eyebrow="Productos y costos"
        title="Mercadería"
        description="Productos que se compran hechos y se venden tal cual. El costo es lo que pagaste por unidad en la última compra. Cada compra nueva queda en el historial."
        actions={
          canWrite(user.role) ? (
            <Link
              href="/reventa/nuevo"
              className="inline-flex min-h-11 items-center justify-center sm:min-h-0 rounded-card bg-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm text-white hover:bg-ink-soft"
            >
              Nuevo producto de mercadería
            </Link>
          ) : undefined
        }
      />
      {result.ok ? (
        result.data.length === 0 ? (
          <Notice
            tone="info"
            title="Todavía no hay productos de mercadería cargados."
          />
        ) : (
          <TableWrap>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Producto</th>
                  <th className={thClass}>Proveedor</th>
                  <th className={`${thClass} ${numClass}`}>Costo unitario</th>
                  <th className={`${thClass} ${numClass}`}>Precio de venta</th>
                  <th className={`${thClass} ${numClass}`}>Margen</th>
                  <th className={thClass}>Última compra</th>
                  <th className={`${thClass} ${numClass}`}>
                    Unidades compradas
                  </th>
                </tr>
              </thead>
              <tbody>
                {result.data.map((producto) => (
                  <tr key={producto.codigo} className="hover:bg-paper-mid/50">
                    <td className={tdClass}>
                      <Link
                        href={`/reventa/${encodeURIComponent(producto.codigo)}`}
                        className="underline decoration-gold underline-offset-4"
                      >
                        {producto.nombre}
                      </Link>
                      <span className="block text-xs text-muted">
                        {producto.codigo}
                        {producto.categoria ? ` · ${producto.categoria}` : ""}
                      </span>
                      {producto.activo ? null : (
                        <Badge tone="warn">Archivado</Badge>
                      )}
                    </td>
                    <td className={tdClass}>{producto.proveedor ?? "—"}</td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(producto.costo_unitario_ars)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(producto.precio_venta_unitario_ars)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(producto.margen_unitario_ars)}
                      <span className="block text-xs text-muted">
                        {formatMargenPct(producto.margen_pct)}
                      </span>
                    </td>
                    <td className={tdClass}>
                      {formatDate(producto.ultima_compra)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatQuantity(producto.unidades_compradas)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </>
  );
}
