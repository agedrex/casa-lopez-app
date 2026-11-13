import type { Metadata } from "next";
import Link from "next/link";
import { inputClass } from "@/components/form";
import { ErrorNotice, Notice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { hasMissingConsumptions, SIZES } from "@/lib/modelos";
import { requireRole } from "@/lib/session";
import type { Catalogos, Material, ModeloLista } from "@/lib/types";
import { ProductosNav } from "../productos-nav";
import { ModelosGrid } from "./modelos-grid";

export const metadata: Metadata = { title: "Modelos" };

// The API caps a page at 1000 models; the sheet has about 325.
const PAGE_LIMIT = 1000;

type Search = Promise<{
  q?: string | string[];
  categoria?: string | string[];
  validado?: string | string[];
  tamano?: string | string[];
  incompletos?: string | string[];
}>;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

export default async function ModelosPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  await requireRole("admin");
  const params = await searchParams;
  const q = first(params.q);
  const categoria = first(params.categoria);
  // Unknown values are dropped here: the API answers 422 to a size it does not know.
  const validado = ["true", "false"].includes(first(params.validado))
    ? first(params.validado)
    : "";
  const tamano = SIZES.some((size) => size.value === first(params.tamano))
    ? first(params.tamano)
    : "";

  const incompletos = first(params.incompletos) === "1";

  const filter = new URLSearchParams({ limit: String(PAGE_LIMIT) });
  if (q) filter.set("q", q);
  if (categoria) filter.set("categoria", categoria);
  if (validado) filter.set("validado", validado);
  if (tamano) filter.set("tamano", tamano);

  const [found, catalogos, materiales] = await Promise.all([
    apiGet<ModeloLista[]>(`/modelos?${filter}`),
    apiGet<Catalogos>("/catalogos"),
    apiGet<Material[]>("/materiales"),
  ]);
  // "Incompletos" is decided here: the API has no such filter, and a NULL consumption is
  // exactly what the grid highlights.
  const incompleteCount = found.ok
    ? found.data.filter(hasMissingConsumptions).length
    : 0;
  const modelos = found.ok
    ? {
        ...found,
        data: incompletos
          ? found.data.filter(hasMissingConsumptions)
          : found.data,
      }
    : found;
  const forros = materiales.ok
    ? materiales.data
        .filter((m) => m.etapa === "FORRO" && m.cotizable)
        .map((m) => ({ codigo: m.codigo, label: `${m.codigo} · ${m.nombre}` }))
    : [];
  const filtered = Boolean(q || categoria || validado || tamano || incompletos);

  return (
    <>
      <ProductosNav />
      <PageHeader
        eyebrow="Productos"
        title="Modelos"
        actions={
          <Link
            href="/productos/modelos/nuevo"
            className="inline-flex min-h-11 items-center justify-center sm:min-h-0 rounded-card bg-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm text-white hover:bg-ink-soft"
          >
            Nuevo modelo
          </Link>
        }
      />
      <Filters
        q={q}
        categoria={categoria}
        validado={validado}
        tamano={tamano}
        incompletos={incompletos}
        categorias={catalogos.ok ? catalogos.data.categorias : []}
      />
      {modelos.ok ? (
        modelos.data.length === 0 ? (
          <Notice
            tone="info"
            title={
              filtered
                ? "Ningún modelo coincide con los filtros."
                : "Todavía no hay modelos cargados."
            }
          />
        ) : (
          <>
            <p className="mb-3 text-sm text-muted" aria-live="polite">
              {modelos.data.length}{" "}
              {modelos.data.length === 1 ? "modelo" : "modelos"}
              {modelos.data.length >= PAGE_LIMIT
                ? ` (se muestran los primeros ${PAGE_LIMIT}: afine el filtro)`
                : ""}
              {incompleteCount > 0 && !incompletos
                ? ` · ${incompleteCount} con consumos incompletos`
                : ""}
            </p>
            <ModelosGrid modelos={modelos.data} forros={forros} />
          </>
        )
      ) : (
        <ErrorNotice message={modelos.message} />
      )}
    </>
  );
}

// A plain GET form: it works without JavaScript and keeps the filters in the URL.
function Filters({
  q,
  categoria,
  validado,
  tamano,
  incompletos,
  categorias,
}: {
  q: string;
  categoria: string;
  validado: string;
  tamano: string;
  incompletos: boolean;
  categorias: string[];
}) {
  const label = "mb-1.5 block text-xs uppercase tracking-caps-sm text-muted";
  return (
    <search className="mb-8">
      <form
        method="get"
        action="/productos/modelos"
        className="flex flex-wrap items-end gap-4"
      >
        <div className="w-full sm:w-auto sm:min-w-56 sm:flex-1">
          <label htmlFor="filtro-q" className={label}>
            Buscar
          </label>
          <input
            id="filtro-q"
            name="q"
            type="search"
            defaultValue={q}
            placeholder="Código o parte del nombre"
            autoComplete="off"
            className={inputClass}
          />
        </div>
        <div className="w-full sm:w-auto sm:min-w-44">
          <label htmlFor="filtro-categoria" className={label}>
            Categoría
          </label>
          <select
            id="filtro-categoria"
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
        <div className="w-full sm:w-auto sm:min-w-36">
          <label htmlFor="filtro-tamano" className={label}>
            Tamaño
          </label>
          <select
            id="filtro-tamano"
            name="tamano"
            defaultValue={tamano}
            className={inputClass}
          >
            <option value="">Todos</option>
            {SIZES.map((size) => (
              <option key={size.value} value={size.value}>
                {size.label}
              </option>
            ))}
          </select>
        </div>
        <div className="w-full sm:w-auto sm:min-w-36">
          <label htmlFor="filtro-validado" className={label}>
            Validación
          </label>
          <select
            id="filtro-validado"
            name="validado"
            defaultValue={validado}
            className={inputClass}
          >
            <option value="">Todos</option>
            <option value="true">Validados</option>
            <option value="false">Sin validar</option>
          </select>
        </div>
        <div className="flex min-h-11 w-full items-center gap-3 sm:w-auto sm:min-h-0 sm:pb-2">
          <input
            id="filtro-incompletos"
            name="incompletos"
            type="checkbox"
            value="1"
            defaultChecked={incompletos}
            className="size-5 accent-ink"
          />
          <label htmlFor="filtro-incompletos" className="text-sm">
            Incompletos
            <span className="block text-xs text-muted">
              Con algún consumo vacío.
            </span>
          </label>
        </div>
        <button
          type="submit"
          className="inline-flex min-h-11 items-center justify-center sm:min-h-0 rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white"
        >
          Filtrar
        </button>
        <Link
          href="/productos/modelos"
          className="py-2.5 text-sm text-muted underline"
        >
          Limpiar
        </Link>
      </form>
    </search>
  );
}
