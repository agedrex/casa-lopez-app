import type { Metadata } from "next";
import Link from "next/link";
import {
  ErrorNotice,
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
import { formatMargenPct } from "../reventa/margen";
import { GrillaClient, type GrillaData } from "./grilla-client";

export const metadata: Metadata = { title: "Grilla completa" };

export default async function GrillaPage() {
  const { user } = await requireSession();
  const result = await apiGet<GrillaData>("/grilla");
  // Mercadería is admin only (same gate as its own section), so the other roles never see its costs here.
  const mercaderia = canWrite(user.role)
    ? await apiGet<ProductoReventa[]>("/reventa")
    : null;
  return (
    <>
      <PageHeader
        eyebrow="Consultas"
        title="Grilla completa"
        description="Todos los productos y sus costos de hoy, etapa por etapa."
      />
      {result.ok ? (
        <GrillaClient data={result.data} />
      ) : (
        <ErrorNotice message={result.message} />
      )}
      {mercaderia ? (
        <section className="mt-10">
          <h2 className="font-serif text-xl">Mercadería</h2>
          <p className="mb-3 text-sm text-muted">
            Productos que se compran hechos y se venden tal cual: el costo es lo
            que se pagó por unidad en la última compra.
          </p>
          {mercaderia.ok ? (
            <TableWrap>
              <table className={tableClass}>
                <thead>
                  <tr>
                    <th className={thClass}>Producto</th>
                    <th className={thClass}>Proveedor</th>
                    <th className={`${thClass} ${numClass}`}>Costo unitario</th>
                    <th className={`${thClass} ${numClass}`}>
                      Precio de venta
                    </th>
                    <th className={`${thClass} ${numClass}`}>Margen</th>
                    <th className={thClass}>Última compra</th>
                    <th className={`${thClass} ${numClass}`}>
                      Unidades compradas
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {mercaderia.data.length === 0 ? (
                    <tr>
                      <td className={tdClass} colSpan={7}>
                        Todavía no hay productos de mercadería cargados.
                      </td>
                    </tr>
                  ) : (
                    mercaderia.data.map((producto) => (
                      <tr key={producto.codigo}>
                        <td className={tdClass}>
                          <Link
                            href={`/reventa/${encodeURIComponent(producto.codigo)}`}
                            className="underline decoration-gold underline-offset-4"
                          >
                            {producto.nombre}
                          </Link>
                          <span className="block text-xs text-muted">
                            {producto.codigo}
                          </span>
                        </td>
                        <td className={tdClass}>{producto.proveedor ?? "—"}</td>
                        <td className={`${tdClass} ${numClass}`}>
                          {formatArs(producto.costo_unitario_ars)}
                        </td>
                        <td className={`${tdClass} ${numClass}`}>
                          {formatArs(producto.precio_venta_unitario_ars)}
                        </td>
                        <td className={`${tdClass} ${numClass}`}>
                          {formatMargenPct(producto.margen_pct)}
                        </td>
                        <td className={tdClass}>
                          {formatDate(producto.ultima_compra)}
                        </td>
                        <td className={`${tdClass} ${numClass}`}>
                          {formatQuantity(producto.unidades_compradas)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </TableWrap>
          ) : (
            <ErrorNotice message={mercaderia.message} />
          )}
        </section>
      ) : null}
    </>
  );
}
