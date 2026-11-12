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
import type { Catalogos, ProductoReventa } from "@/lib/types";
import { formatMargenPct } from "./margen";
import { ReventaGrid } from "./reventa-grid";

export const metadata: Metadata = { title: "Reventa" };

export default async function ReventaPage() {
  const { user } = await requireSession();
  const writer = canWrite(user.role);
  const [result, catalogos] = await Promise.all([
    apiGet<ProductoReventa[]>("/reventa"),
    writer ? apiGet<Catalogos>("/catalogos") : null,
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Productos y costos"
        title="Mercadería"
        description="Acá se cargan los productos que la casa compra hechos, a qué precio se compran y a cuánto se van a vender. Editar un costo o un precio agrega una actualización al historial: nada se pisa. Las compras con unidades se registran en la ficha del producto."
      />
      {result.ok && catalogos && !catalogos.ok ? (
        <ErrorNotice message={catalogos.message} />
      ) : result.ok && catalogos?.ok ? (
        <>
          <ReventaGrid
            productos={result.data}
            categorias={catalogos.data.categorias}
          />
          {result.data.some((producto) => !producto.activo) ? (
            <p className="mt-6 text-sm text-muted">
              Archivados (se activan desde su ficha):{" "}
              {result.data
                .filter((producto) => !producto.activo)
                .map((producto, index) => (
                  <span key={producto.codigo}>
                    {index > 0 ? ", " : ""}
                    <Link
                      href={`/reventa/${encodeURIComponent(producto.codigo)}`}
                      className="underline decoration-gold underline-offset-4"
                    >
                      {producto.nombre}
                    </Link>
                  </span>
                ))}
            </p>
          ) : null}
        </>
      ) : result.ok ? (
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
