import type { Metadata } from "next";
import Link from "next/link";
import { inputClass } from "@/components/form";
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
import { formatArs, formatQuantity } from "@/lib/format";
import { originLabel, SIZES, sizeLabel } from "@/lib/modelos";
import { requireRole } from "@/lib/session";
import type { Catalogos, ModeloLista } from "@/lib/types";
import { BackToAdmin } from "../back-link";

export const metadata: Metadata = { title: "Modelos" };

// The API caps a page at 1000 models; the sheet has about 325.
const PAGE_LIMIT = 1000;

type Search = Promise<{
  q?: string | string[];
  categoria?: string | string[];
  validado?: string | string[];
  tamano?: string | string[];
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

  const filter = new URLSearchParams({ limit: String(PAGE_LIMIT) });
  if (q) filter.set("q", q);
  if (categoria) filter.set("categoria", categoria);
  if (validado) filter.set("validado", validado);
  if (tamano) filter.set("tamano", tamano);

  const [modelos, catalogos] = await Promise.all([
    apiGet<ModeloLista[]>(`/modelos?${filter}`),
    apiGet<Catalogos>("/catalogos"),
  ]);
  const filtered = Boolean(q || categoria || validado || tamano);

  return (
    <>
      <BackToAdmin />
      <PageHeader
        eyebrow="Administración"
        title="Modelos"
        description="Los consumos de cada modelo. Un modelo se valida cuando una persona confirma que sus números son razonables; editar los consumos le quita esa marca."
        actions={
          <Link
            href="/admin/modelos/nuevo"
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
            </p>
            <TableWrap>
              <table className={tableClass}>
                <thead>
                  <tr>
                    <th className={thClass}>Modelo</th>
                    <th className={thClass}>Categoría</th>
                    <th className={thClass}>Tamaño</th>
                    <th className={`${thClass} ${numClass}`}>Cuero m²</th>
                    <th className={`${thClass} ${numClass}`}>Forro m²</th>
                    <th className={`${thClass} ${numClass}`}>Confección</th>
                    <th className={thClass}>Origen</th>
                    <th className={thClass}>Validado</th>
                  </tr>
                </thead>
                <tbody>
                  {modelos.data.map((modelo) => (
                    <tr key={modelo.codigo} className="hover:bg-paper-mid/50">
                      <td className={tdClass}>
                        <Link
                          href={`/admin/modelos/${encodeURIComponent(modelo.codigo)}`}
                          className="underline decoration-gold underline-offset-4"
                        >
                          {modelo.nombre_del_modelo}
                        </Link>
                        <span className="block text-xs text-muted">
                          {modelo.codigo}
                        </span>
                      </td>
                      <td className={tdClass}>{modelo.categoria ?? "—"}</td>
                      <td className={tdClass}>{sizeLabel(modelo.tamano)}</td>
                      <td className={`${tdClass} ${numClass}`}>
                        {formatQuantity(modelo.cuero_m2_por_unidad)}
                      </td>
                      <td className={`${tdClass} ${numClass}`}>
                        {formatQuantity(modelo.forro_m2_por_unidad)}
                      </td>
                      <td className={`${tdClass} ${numClass}`}>
                        {formatArs(modelo.confeccion_estimada_ars)}
                      </td>
                      <td className={tdClass}>
                        {originLabel(modelo.origen_de_los_consumos)}
                      </td>
                      <td className={tdClass}>
                        <Badge tone={modelo.validado ? "good" : "neutral"}>
                          {modelo.validado ? "Validado" : "Sin validar"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
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
  categorias,
}: {
  q: string;
  categoria: string;
  validado: string;
  tamano: string;
  categorias: string[];
}) {
  const label = "mb-1.5 block text-xs uppercase tracking-caps-sm text-muted";
  return (
    <search className="mb-8">
      <form
        method="get"
        action="/admin/modelos"
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
        <button
          type="submit"
          className="inline-flex min-h-11 items-center justify-center sm:min-h-0 rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white"
        >
          Filtrar
        </button>
        <Link
          href="/admin/modelos"
          className="py-2.5 text-sm text-muted underline"
        >
          Limpiar
        </Link>
      </form>
    </search>
  );
}
