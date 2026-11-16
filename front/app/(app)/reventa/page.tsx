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
import { formatArs } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Catalogos, ProductoReventa } from "@/lib/types";
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
      <PageHeader eyebrow="Productos y costos" title="Mercadería" />
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
                  <th className={thClass}>ID</th>
                  <th className={thClass}>Producto</th>
                  <th className={thClass}>Categoría</th>
                  <th className={`${thClass} ${numClass}`}>Costo unitario</th>
                  <th className={thClass}>Proveedor</th>
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
                        {producto.codigo}
                      </Link>
                    </td>
                    <td className={tdClass}>
                      {producto.nombre}
                      {producto.activo ? null : (
                        <Badge tone="warn">Archivado</Badge>
                      )}
                    </td>
                    <td className={tdClass}>{producto.categoria ?? "—"}</td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(producto.costo_unitario_ars)}
                    </td>
                    <td className={tdClass}>{producto.proveedor ?? "—"}</td>
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
