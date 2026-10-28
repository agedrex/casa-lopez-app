import type { Metadata } from "next";
import Link from "next/link";
import { Avisos } from "@/components/avisos";
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
import { formatArs, formatUsd, lifecycleLabel } from "@/lib/format";
import type { ProductoResumen } from "@/lib/types";

export const metadata: Metadata = { title: "Productos" };

const PAGE_SIZE = 50;

export default async function ProductosPage({
  searchParams,
}: {
  searchParams: Promise<{ pagina?: string | string[] }>;
}) {
  const { pagina } = await searchParams;
  const raw = Array.isArray(pagina) ? pagina[0] : pagina;
  const parsed = Number.parseInt(raw ?? "1", 10);
  const page = Number.isFinite(parsed) && parsed >= 1 ? parsed : 1;

  const result = await apiGet<ProductoResumen[]>(
    `/productos?limit=${PAGE_SIZE}&offset=${(page - 1) * PAGE_SIZE}`,
  );

  return (
    <>
      <PageHeader
        eyebrow="Catálogo"
        title="Productos"
        description="Costo de hoy de cada producto, calculado con el dólar y los precios vigentes."
      />
      {result.ok ? (
        <ProductTable productos={result.data} page={page} />
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </>
  );
}

function ProductTable({
  productos,
  page,
}: {
  productos: ProductoResumen[];
  page: number;
}) {
  if (productos.length === 0) {
    return (
      <Notice
        tone="info"
        title={
          page === 1
            ? "Todavía no hay productos cargados."
            : "No hay más productos en esta página."
        }
      />
    );
  }
  return (
    <>
      <TableWrap>
        <table className={tableClass}>
          <thead>
            <tr>
              <th className={thClass}>Código</th>
              <th className={thClass}>Nombre</th>
              <th className={thClass}>Categoría</th>
              <th className={thClass}>Estado</th>
              <th className={`${thClass} ${numClass}`}>Costo hoy (ARS)</th>
              <th className={`${thClass} ${numClass}`}>Costo hoy (USD)</th>
              <th className={thClass}>Avisos</th>
            </tr>
          </thead>
          <tbody>
            {productos.map((producto) => (
              <tr key={producto.codigo} className="hover:bg-paper-mid/50">
                <td className={tdClass}>
                  <Link
                    href={`/productos/${encodeURIComponent(producto.codigo)}`}
                    className="underline decoration-gold underline-offset-4"
                  >
                    {producto.codigo}
                  </Link>
                </td>
                <td className={tdClass}>
                  {producto.nombre}{" "}
                  {producto.es_kit ? <Badge>Kit</Badge> : null}
                </td>
                <td className={tdClass}>{producto.categoria ?? "—"}</td>
                <td className={tdClass}>
                  {lifecycleLabel(producto.estado_del_ciclo)}
                </td>
                {producto.costo_hoy_ars === null ? (
                  <td className={`${tdClass} text-muted`} colSpan={2}>
                    Falta cargar dólar o precios
                  </td>
                ) : (
                  <>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(producto.costo_hoy_ars)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatUsd(producto.costo_hoy_usd)}
                    </td>
                  </>
                )}
                <td className={tdClass}>
                  <Avisos avisos={producto.avisos} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>

      <nav
        aria-label="Paginación"
        className="mt-6 flex items-center justify-between text-sm"
      >
        {page > 1 ? (
          <Link
            href={page === 2 ? "/productos" : `/productos?pagina=${page - 1}`}
            className="underline decoration-gold underline-offset-4"
          >
            ← Anterior
          </Link>
        ) : (
          <span />
        )}
        <span className="text-muted">Página {page}</span>
        {productos.length === PAGE_SIZE ? (
          <Link
            href={`/productos?pagina=${page + 1}`}
            className="underline decoration-gold underline-offset-4"
          >
            Siguiente →
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </>
  );
}
