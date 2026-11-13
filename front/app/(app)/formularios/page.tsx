import type { Metadata } from "next";
import Link from "next/link";
import { inputClass } from "@/components/form";
import {
  Badge,
  CardItem,
  CardList,
  ErrorNotice,
  Notice,
  PageHeader,
  ResponsiveTable,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDate } from "@/lib/format";
import {
  estadoLabel,
  estadosVisibles,
  estadoTone,
  parseEstado,
} from "@/lib/formulario";
import { canWrite, isTallerOnly } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { FormularioEstado, FormularioResumen, Taller } from "@/lib/types";
import { NuevoFormularioForm } from "./nuevo-form";

export const metadata: Metadata = { title: "Formularios de consumos" };

type Search = Promise<{
  q?: string | string[];
  estado?: string | string[];
}>;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

export default async function FormulariosPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const { user } = await requireSession();
  const params = await searchParams;
  const q = first(params.q);
  const estado = parseEstado(first(params.estado));
  const writer = canWrite(user.role);
  const tallerOnly = isTallerOnly(user.role);

  const filter = new URLSearchParams();
  if (q) filter.set("q", q);
  if (estado) filter.set("estado", estado);

  const [result, talleres] = await Promise.all([
    apiGet<FormularioResumen[]>(`/formularios?${filter}`),
    writer ? apiGet<Taller[]>("/talleres") : null,
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Producción"
        title={tallerOnly ? "Planillas de consumos" : "Formularios de consumos"}
        description={
          tallerOnly
            ? "Planillas para completar: cargá lo que lleva cada modelo (consumos y herrajes) y tocá Completar. Podés practicar con la de ejemplo."
            : undefined
        }
      />
      {writer ? (
        <details className="mb-8 rounded-card border border-line bg-surface p-4 sm:p-6">
          <summary className="cursor-pointer text-sm uppercase tracking-caps-sm">
            Nuevo formulario
          </summary>
          <div className="mt-5">
            <NuevoFormularioForm
              talleres={
                talleres?.ok
                  ? talleres.data
                      .filter((taller) => taller.activo)
                      .map(({ codigo, nombre }) => ({ codigo, nombre }))
                  : []
              }
            />
          </div>
        </details>
      ) : null}
      <SearchForm q={q} estado={estado} estados={estadosVisibles(user.role)} />
      {result.ok ? (
        tallerOnly && !estado && !q ? (
          <ListaTaller formularios={result.data} />
        ) : (
          <Lista formularios={result.data} filtered={filter.size > 0} />
        )
      ) : (
        <ErrorNotice message={result.message} />
      )}
    </>
  );
}

// A plain GET form: it works without JavaScript and keeps the filters in the URL.
function SearchForm({
  q,
  estado,
  estados,
}: {
  q: string;
  estado: string;
  estados: readonly FormularioEstado[];
}) {
  return (
    <search className="mb-8">
      <form
        method="get"
        action="/formularios"
        className="flex flex-wrap items-end gap-4"
      >
        <div className="w-full sm:min-w-60 sm:flex-1 sm:w-auto">
          <label
            htmlFor="formularios-q"
            className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Buscar por código, artículo, producto o taller
          </label>
          <input
            id="formularios-q"
            name="q"
            type="search"
            defaultValue={q}
            autoComplete="off"
            placeholder="FCO-0001, cartera, PRD-0001…"
            className={inputClass}
          />
        </div>
        <div className="w-full sm:w-auto sm:min-w-48">
          <label
            htmlFor="formularios-estado"
            className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Estado
          </label>
          <select
            id="formularios-estado"
            name="estado"
            defaultValue={estado}
            className={inputClass}
          >
            <option value="">Todos los estados</option>
            {estados.map((valor) => (
              <option key={valor} value={valor}>
                {estadoLabel(valor)}
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
        {q || estado ? (
          <Link
            href="/formularios"
            className="flex min-h-11 items-center px-2 text-sm text-muted underline decoration-gold underline-offset-4 sm:min-h-0 sm:py-2.5"
          >
            Limpiar
          </Link>
        ) : null}
      </form>
    </search>
  );
}

const linkClass = "underline decoration-gold underline-offset-4";

/** Taller: the sheets waiting for it first (ENVIADO), then the ones it already completed. */
function ListaTaller({ formularios }: { formularios: FormularioResumen[] }) {
  const porCompletar = formularios.filter(
    (formulario) => formulario.estado === "ENVIADO",
  );
  const resto = formularios.filter(
    (formulario) => formulario.estado !== "ENVIADO",
  );
  return (
    <div className="space-y-10">
      <section aria-labelledby="para-completar">
        <h2 id="para-completar" className="mb-4 text-xl">
          Planillas para completar
        </h2>
        {porCompletar.length === 0 ? (
          <Notice
            tone="info"
            title="No hay planillas para completar por ahora."
          >
            Cuando el administrador te envíe una, aparece acá.
          </Notice>
        ) : (
          <Lista formularios={porCompletar} filtered={false} />
        )}
      </section>
      {resto.length > 0 ? (
        <section aria-labelledby="ya-completadas">
          <h2 id="ya-completadas" className="mb-4 text-xl">
            Ya completadas
          </h2>
          <Lista formularios={resto} filtered={false} />
        </section>
      ) : null}
    </div>
  );
}

function Lista({
  formularios,
  filtered,
}: {
  formularios: FormularioResumen[];
  filtered: boolean;
}) {
  if (formularios.length === 0) {
    return (
      <Notice
        tone="info"
        title={
          filtered
            ? "Ningún formulario coincide con la búsqueda."
            : "Todavía no hay formularios."
        }
      />
    );
  }
  return (
    <>
      <p className="mb-3 text-sm text-muted" aria-live="polite">
        {formularios.length}{" "}
        {formularios.length === 1 ? "formulario" : "formularios"}
      </p>
      <ResponsiveTable
        cards={
          <CardList>
            {formularios.map((formulario) => (
              <CardItem key={formulario.codigo}>
                <Link
                  href={`/formularios/${encodeURIComponent(formulario.codigo)}`}
                  className="block"
                >
                  <div className="flex items-start justify-between gap-3">
                    <p className="min-w-0 break-words font-bold">
                      {formulario.articulo}
                    </p>
                    <span
                      className={`shrink-0 text-xs text-muted ${linkClass}`}
                    >
                      {formulario.codigo}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    {[
                      formulario.modelo ? `Modelo ${formulario.modelo}` : null,
                      formulario.producto,
                      formulario.taller,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "Sin modelo, producto ni taller"}
                    {" · "}
                    {formatDate(formulario.created_at)}
                  </p>
                </Link>
                <div className="mt-2">
                  <Badge tone={estadoTone(formulario.estado)}>
                    {estadoLabel(formulario.estado)}
                  </Badge>
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
                  <th scope="col" className={thClass}>
                    Código
                  </th>
                  <th scope="col" className={thClass}>
                    Artículo
                  </th>
                  <th scope="col" className={thClass}>
                    Modelo
                  </th>
                  <th scope="col" className={thClass}>
                    Estado
                  </th>
                  <th scope="col" className={thClass}>
                    Producto
                  </th>
                  <th scope="col" className={thClass}>
                    Taller
                  </th>
                  <th scope="col" className={thClass}>
                    Creado
                  </th>
                </tr>
              </thead>
              <tbody>
                {formularios.map((formulario) => (
                  <tr key={formulario.codigo} className="hover:bg-paper-mid/50">
                    <td className={tdClass}>
                      <Link
                        href={`/formularios/${encodeURIComponent(formulario.codigo)}`}
                        className={linkClass}
                      >
                        {formulario.codigo}
                      </Link>
                    </td>
                    <td className={tdClass}>
                      <div className="max-w-sm break-words">
                        {formulario.articulo}
                      </div>
                    </td>
                    <td className={tdClass}>{formulario.modelo ?? "—"}</td>
                    <td className={tdClass}>
                      <Badge tone={estadoTone(formulario.estado)}>
                        {estadoLabel(formulario.estado)}
                      </Badge>
                    </td>
                    <td className={tdClass}>{formulario.producto ?? "—"}</td>
                    <td className={tdClass}>{formulario.taller ?? "—"}</td>
                    <td className={tdClass}>
                      {formatDate(formulario.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        }
      />
    </>
  );
}
