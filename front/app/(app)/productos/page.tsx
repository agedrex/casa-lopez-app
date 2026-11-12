import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
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
import { canOpenProductSheet, canWrite } from "@/lib/permissions";
import {
  collapseSpaces,
  costoFaltante,
  LIFECYCLE_STATES,
  type LifecycleState,
  parseLifecycleState,
} from "@/lib/productos";
import { requireSession } from "@/lib/session";
import type { Catalogos, Conteo, ProductoResumen } from "@/lib/types";

export const metadata: Metadata = { title: "Productos" };

const PAGE_SIZE = 50;

type Search = Promise<{
  pagina?: string | string[];
  q?: string | string[];
  categoria?: string | string[];
  revisar?: string | string[];
  sin_cuero?: string | string[];
  sin_color?: string | string[];
  estado?: string | string[];
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
  const revisar = first(params.revisar) === "true";
  const sinCuero = first(params.sin_cuero) === "true";
  const sinColor = first(params.sin_color) === "true";
  const estado = parseLifecycleState(first(params.estado));
  // Taller reads the list but not the product sheet, and `/catalogos` is closed to it:
  // without the catalog there is no category selector for that role.
  const openSheet = canOpenProductSheet(user.role);

  const filter = new URLSearchParams();
  if (q) filter.set("q", q);
  if (categoria) filter.set("categoria", categoria);
  if (revisar) filter.set("revisar", "true");
  if (sinCuero) filter.set("sin_cuero", "true");
  if (sinColor) filter.set("sin_color", "true");
  if (estado) filter.set("estado", estado);
  const paged = new URLSearchParams(filter);
  paged.set("limit", String(PAGE_SIZE));
  paged.set("offset", String((page - 1) * PAGE_SIZE));

  const [result, count, catalogos] = await Promise.all([
    apiGet<ProductoResumen[]>(`/productos?${paged}`),
    apiGet<Conteo>(`/productos/conteo?${filter}`),
    openSheet ? apiGet<Catalogos>("/catalogos") : null,
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
        revisar={revisar}
        sinCuero={sinCuero}
        sinColor={sinColor}
        estado={estado}
        categorias={catalogos?.ok ? catalogos.data.categorias : null}
      />
      {result.ok ? (
        <ProductTable
          productos={result.data}
          page={page}
          total={count.ok ? count.data.total : null}
          filter={filter}
          filtered={filter.size > 0}
          openSheet={openSheet}
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
  revisar,
  sinCuero,
  sinColor,
  estado,
  categorias,
}: {
  q: string;
  categoria: string;
  revisar: boolean;
  sinCuero: boolean;
  sinColor: boolean;
  estado: LifecycleState | "";
  /** `null`: the role has no catalog, so the category selector is not shown. */
  categorias: string[] | null;
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
            placeholder="PRD-0001, MOD-0001, portafolio, negro…"
            className={inputClass}
          />
        </div>
        {categorias === null ? null : (
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
        )}
        <div className="w-full sm:w-auto sm:min-w-48">
          <label
            htmlFor="buscar-estado"
            className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Estado
          </label>
          <select
            id="buscar-estado"
            name="estado"
            defaultValue={estado}
            className={inputClass}
          >
            <option value="">Todos los estados</option>
            {LIFECYCLE_STATES.map((state) => (
              <option key={state} value={state}>
                {lifecycleLabel(state)}
              </option>
            ))}
          </select>
        </div>
        <label className="flex min-h-11 items-center gap-2 text-sm sm:min-h-0 sm:py-2.5">
          <input
            type="checkbox"
            name="sin_cuero"
            value="true"
            defaultChecked={sinCuero}
            className="size-4"
          />
          Sin cuero
        </label>
        <label className="flex min-h-11 items-center gap-2 text-sm sm:min-h-0 sm:py-2.5">
          <input
            type="checkbox"
            name="sin_color"
            value="true"
            defaultChecked={sinColor}
            className="size-4"
          />
          Sin color
        </label>
        <label className="flex min-h-11 items-center gap-2 text-sm sm:min-h-0 sm:py-2.5">
          <input
            type="checkbox"
            name="revisar"
            value="true"
            defaultChecked={revisar}
            className="size-4"
          />
          Solo los marcados para revisar
        </label>
        <button
          type="submit"
          className="min-h-11 flex-1 rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white sm:min-h-0 sm:flex-none"
        >
          Buscar
        </button>
        {q || categoria || revisar || sinCuero || sinColor || estado ? (
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

/** The name as typed in the Excel can be very long and full of spaces: two lines, the whole text in the tooltip. */
function NombreProducto({ nombre }: { nombre: string }) {
  const limpio = collapseSpaces(nombre);
  return (
    <span title={limpio} className="line-clamp-2 break-words">
      {limpio}
    </span>
  );
}

/** Taller reads the list but cannot open the sheet: for that role the code and name are plain text. */
function SheetLink({
  codigo,
  openSheet,
  className,
  children,
}: {
  codigo: string;
  openSheet: boolean;
  className: string;
  children: ReactNode;
}) {
  if (!openSheet) return <div className={className}>{children}</div>;
  return (
    <Link
      href={`/productos/${encodeURIComponent(codigo)}`}
      className={className}
    >
      {children}
    </Link>
  );
}

/** "Revisar" badge plus the reasons as visible text (the tooltip is not the only place). */
function MarcaRevisar({ motivos }: { motivos: string[] }) {
  return (
    <span className="flex flex-col items-start gap-1">
      <Badge tone="warn">Revisar</Badge>
      {motivos.length > 0 ? (
        <span className="text-xs text-muted">{motivos.join(" · ")}</span>
      ) : null}
    </span>
  );
}

/** Without a cost, the first warning is already shown where the cost would be: the rest goes in the warnings. */
function restoDeAvisos(producto: ProductoResumen): string[] {
  return producto.costo_hoy_ars === null
    ? producto.avisos.slice(1)
    : producto.avisos;
}

function ProductTable({
  productos,
  page,
  total,
  filter,
  filtered,
  openSheet,
}: {
  productos: ProductoResumen[];
  page: number;
  total: number | null;
  filter: URLSearchParams;
  filtered: boolean;
  openSheet: boolean;
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
                <SheetLink
                  codigo={producto.codigo}
                  openSheet={openSheet}
                  className="block"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="min-w-0 font-bold">
                      <NombreProducto nombre={producto.nombre} />
                    </p>
                    <span
                      className={`shrink-0 text-xs text-muted ${openSheet ? "underline decoration-gold underline-offset-4" : ""}`}
                    >
                      {producto.codigo}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    {producto.modelo ? `Modelo ${producto.modelo} · ` : ""}
                    {producto.categoria ?? "—"} ·{" "}
                    {lifecycleLabel(producto.estado_del_ciclo)}
                  </p>
                  {producto.costo_hoy_ars === null ? (
                    <p className="mt-3 text-sm text-muted">
                      {costoFaltante(producto.avisos)}
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
                </SheetLink>
                {/* Badges and warnings stay outside the link: they are not part of its name. */}
                {producto.es_kit || producto.revisar ? (
                  <div className="mt-2 flex flex-wrap items-start gap-2">
                    {producto.es_kit ? <Badge>Kit</Badge> : null}
                    {producto.revisar ? (
                      <MarcaRevisar motivos={producto.motivos_revisar} />
                    ) : null}
                  </div>
                ) : null}
                {restoDeAvisos(producto).length > 0 ? (
                  <div className="mt-2">
                    <Avisos avisos={restoDeAvisos(producto)} wrap />
                  </div>
                ) : null}
              </CardItem>
            ))}
          </CardList>
        }
        table={
          <TableWrap>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th scope="col" className={thClass}>
                    Código
                  </th>
                  <th scope="col" className={thClass}>
                    Modelo
                  </th>
                  <th scope="col" className={thClass}>
                    Nombre
                  </th>
                  <th scope="col" className={thClass}>
                    Categoría
                  </th>
                  <th scope="col" className={thClass}>
                    Estado
                  </th>
                  <th scope="col" className={`${thClass} ${numClass}`}>
                    Costo hoy (ARS)
                  </th>
                  <th scope="col" className={`${thClass} ${numClass}`}>
                    Costo hoy (USD)
                  </th>
                  <th scope="col" className={thClass}>
                    Avisos
                  </th>
                </tr>
              </thead>
              <tbody>
                {productos.map((producto) => (
                  <tr key={producto.codigo} className="hover:bg-paper-mid/50">
                    <td className={tdClass}>
                      {openSheet ? (
                        <Link
                          href={`/productos/${encodeURIComponent(producto.codigo)}`}
                          className="underline decoration-gold underline-offset-4"
                        >
                          {producto.codigo}
                        </Link>
                      ) : (
                        producto.codigo
                      )}
                    </td>
                    <td className={tdClass}>
                      {producto.modelo ? (
                        <Link
                          href={`/productos?q=${encodeURIComponent(producto.modelo)}`}
                          title="Ver los productos de este modelo"
                          className="underline decoration-gold underline-offset-4"
                        >
                          {producto.modelo}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className={tdClass}>
                      <div className="max-w-sm">
                        <NombreProducto nombre={producto.nombre} />
                      </div>
                      {producto.es_kit || producto.revisar ? (
                        <div className="mt-1 flex flex-wrap items-start gap-2">
                          {producto.es_kit ? <Badge>Kit</Badge> : null}
                          {producto.revisar ? (
                            <MarcaRevisar motivos={producto.motivos_revisar} />
                          ) : null}
                        </div>
                      ) : null}
                    </td>
                    <td className={tdClass}>{producto.categoria ?? "—"}</td>
                    <td className={tdClass}>
                      {lifecycleLabel(producto.estado_del_ciclo)}
                    </td>
                    {producto.costo_hoy_ars === null ? (
                      <td className={`${tdClass} text-muted`} colSpan={2}>
                        {costoFaltante(producto.avisos)}
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
                      <Avisos avisos={restoDeAvisos(producto)} wrap />
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
