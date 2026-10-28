import type { Metadata } from "next";
import Link from "next/link";
import { Avisos } from "@/components/avisos";
import { inputClass } from "@/components/form";
import {
  Badge,
  CardItem,
  CardList,
  ErrorNotice,
  Notice,
  numClass,
  PageHeader,
  ResponsiveTable,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatArs, formatUsd, lifecycleLabel } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Catalogos, Conteo, ProductoResumen } from "@/lib/types";

export const metadata: Metadata = { title: "Productos" };

const PAGE_SIZE = 50;

type Search = Promise<{
  pagina?: string | string[];
  q?: string | string[];
  categoria?: string | string[];
}>;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

export default async function ProductosPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const { user } = await requireSession();
  const params = await searchParams;
  const parsed = Number.parseInt(first(params.pagina) || "1", 10);
  const page = Number.isFinite(parsed) && parsed >= 1 ? parsed : 1;
  const q = first(params.q);
  const categoria = first(params.categoria);

  const filter = new URLSearchParams();
  if (q) filter.set("q", q);
  if (categoria) filter.set("categoria", categoria);
  const paged = new URLSearchParams(filter);
  paged.set("limit", String(PAGE_SIZE));
  paged.set("offset", String((page - 1) * PAGE_SIZE));

  const [result, count, catalogos] = await Promise.all([
    apiGet<ProductoResumen[]>(`/productos?${paged}`),
    apiGet<Conteo>(`/productos/conteo?${filter}`),
    apiGet<Catalogos>("/catalogos"),
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Catálogo"
        title="Productos"
        description="Costo de hoy de cada producto, calculado con el dólar y los precios vigentes."
        actions={
          canWrite(user.role) ? (
            <Link
              href="/productos/nuevo"
              className="inline-flex min-h-11 items-center justify-center rounded-card bg-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm text-white hover:bg-ink-soft sm:min-h-0"
            >
              Nuevo producto
            </Link>
          ) : undefined
        }
      />
      <SearchForm
        q={q}
        categoria={categoria}
        categorias={catalogos.ok ? catalogos.data.categorias : []}
      />
      {result.ok ? (
        <ProductTable
          productos={result.data}
          page={page}
          total={count.ok ? count.data.total : null}
          filter={filter}
          filtered={Boolean(q || categoria)}
        />
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </>
  );
}

// A plain GET form: it works without JavaScript and keeps the filters in the URL.
function SearchForm({
  q,
  categoria,
  categorias,
}: {
  q: string;
  categoria: string;
  categorias: string[];
}) {
  return (
    <search className="mb-8">
      <form
        method="get"
        action="/productos"
        className="flex flex-wrap items-end gap-4"
      >
        <div className="w-full sm:min-w-60 sm:flex-1 sm:w-auto">
          <label
            htmlFor="buscar-q"
            className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Buscar por código o nombre
          </label>
          <input
            id="buscar-q"
            name="q"
            type="search"
            defaultValue={q}
            autoComplete="off"
            placeholder="PRD-0001, portafolio, negro…"
            className={inputClass}
          />
        </div>
        <div className="w-full sm:w-auto sm:min-w-48">
          <label
            htmlFor="buscar-categoria"
            className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Categoría
          </label>
          <select
            id="buscar-categoria"
            name="categoria"
            defaultValue={categoria}
            className={inputClass}
          >
            <option value="">Todas</option>
            {categorias.map((nombre) => (
              <option key={nombre} value={nombre}>
                {nombre}
              </option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          className="min-h-11 flex-1 rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white sm:min-h-0 sm:flex-none"
        >
          Buscar
        </button>
        {q || categoria ? (
          <Link
            href="/productos"
            className="flex min-h-11 items-center px-2 text-sm text-muted underline decoration-gold underline-offset-4 sm:min-h-0 sm:py-2.5"
          >
            Limpiar
          </Link>
        ) : null}
      </form>
    </search>
  );
}

function pageHref(filter: URLSearchParams, page: number): string {
  const query = new URLSearchParams(filter);
  if (page > 1) query.set("pagina", String(page));
  const text = query.toString();
  return text ? `/productos?${text}` : "/productos";
}

function ProductTable({
  productos,
  page,
  total,
  filter,
  filtered,
}: {
  productos: ProductoResumen[];
  page: number;
  total: number | null;
  filter: URLSearchParams;
  filtered: boolean;
}) {
  if (productos.length === 0) {
    return (
      <Notice
        tone="info"
        title={
          filtered
            ? "Ningún producto coincide con la búsqueda."
            : page === 1
              ? "Todavía no hay productos cargados."
              : "No hay más productos en esta página."
        }
      />
    );
  }
  const hasNext =
    total === null ? productos.length === PAGE_SIZE : page * PAGE_SIZE < total;
  return (
    <>
      {total !== null ? (
        <p className="mb-3 text-sm text-muted" aria-live="polite">
          {total} {total === 1 ? "producto" : "productos"}
        </p>
      ) : null}
      <ResponsiveTable
        cards={
          <CardList>
            {productos.map((producto) => (
              <CardItem key={producto.codigo}>
                <Link
                  href={`/productos/${encodeURIComponent(producto.codigo)}`}
                  className="block"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="font-bold">
                      {producto.nombre}{" "}
                      {producto.es_kit ? <Badge>Kit</Badge> : null}
                    </p>
                    <span className="shrink-0 text-xs text-muted underline decoration-gold underline-offset-4">
                      {producto.codigo}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    {producto.categoria ?? "—"} ·{" "}
                    {lifecycleLabel(producto.estado_del_ciclo)}
                  </p>
                  {producto.costo_hoy_ars === null ? (
                    <p className="mt-3 text-sm text-muted">
                      Falta cargar dólar o precios
                    </p>
                  ) : (
                    <p className="mt-3 flex items-baseline justify-between gap-3 tabular-nums">
                      <span className="text-lg">
                        {formatArs(producto.costo_hoy_ars)}
                      </span>
                      <span className="text-sm text-muted">
                        {formatUsd(producto.costo_hoy_usd)}
                      </span>
                    </p>
                  )}
                </Link>
                <div className="mt-2 empty:hidden">
                  <Avisos avisos={producto.avisos} />
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
        }
      />

      <nav
        aria-label="Paginación"
        className="mt-6 flex items-center justify-between text-sm [&_a]:inline-flex [&_a]:min-h-11 [&_a]:items-center"
      >
        {page > 1 ? (
          <Link
            href={pageHref(filter, page - 1)}
            className="underline decoration-gold underline-offset-4"
          >
            ← Anterior
          </Link>
        ) : (
          <span />
        )}
        <span className="text-muted">Página {page}</span>
        {hasNext ? (
          <Link
            href={pageHref(filter, page + 1)}
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
