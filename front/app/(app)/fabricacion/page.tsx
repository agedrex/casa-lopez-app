import type { Metadata } from "next";
import Link from "next/link";
import { Atajos } from "@/components/atajos";
import { inputClass } from "@/components/form";
import { ErrorNotice, Notice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { LOT_STATES, lotStateLabel, whereLabel } from "@/lib/format";
import { canWrite, isTallerOnly } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { OrdenResumen, Taller } from "@/lib/types";
import { LotesGrid } from "./lotes-grid";
import { LotesYModelos } from "./lotes-y-modelos";

export const metadata: Metadata = { title: "Lotes" };

type Search = Promise<{
  estado?: string | string[];
  donde?: string | string[];
  taller?: string | string[];
}>;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

export default async function FabricacionPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const { user } = await requireSession();
  // The taller has one screen with two tabs, Lotes (this route) and Modelos, in the same grids.
  if (isTallerOnly(user.role)) return <LotesYModelos vista="lotes" />;
  const params = await searchParams;
  // Unknown values are dropped here: the API answers 422 to a state or place it does not know.
  const estado = LOT_STATES.includes(first(params.estado))
    ? first(params.estado)
    : "";
  const donde = ["EXTERNA", "INTERNA"].includes(first(params.donde))
    ? first(params.donde)
    : "";
  const taller = first(params.taller);

  const filter = new URLSearchParams();
  if (estado) filter.set("estado", estado);
  if (donde) filter.set("donde", donde);
  if (taller) filter.set("taller", taller);

  const [ordenes, talleres] = await Promise.all([
    apiGet<OrdenResumen[]>(`/ordenes?${filter}`),
    apiGet<Taller[]>("/talleres"),
  ]);
  const filtered = Boolean(estado || donde || taller);

  return (
    <>
      <Atajos nuevo={canWrite(user.role) ? "/fabricacion/nuevo" : undefined} />
      <PageHeader
        eyebrow="Producción"
        title="Lotes"
        actions={
          canWrite(user.role) ? (
            <Link
              href="/fabricacion/nuevo"
              className="inline-flex min-h-11 items-center justify-center sm:min-h-0 rounded-card bg-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm text-white hover:bg-ink-soft"
            >
              Nuevo lote
            </Link>
          ) : undefined
        }
      />
      <div className="space-y-6">
        <Filters
          estado={estado}
          donde={donde}
          taller={taller}
          talleres={talleres.ok ? talleres.data : []}
        />
        {ordenes.ok ? (
          ordenes.data.length === 0 ? (
            <Notice
              tone="info"
              title={
                filtered
                  ? "Ningún lote coincide con los filtros."
                  : "Todavía no hay lotes cargados."
              }
            />
          ) : (
            <LotesGrid ordenes={ordenes.data} />
          )
        ) : (
          <ErrorNotice message={ordenes.message} />
        )}
      </div>
    </>
  );
}

// A plain GET form: it works without JavaScript and keeps the filters in the URL.
function Filters({
  estado,
  donde,
  taller,
  talleres,
}: {
  estado: string;
  donde: string;
  taller: string;
  talleres: Taller[];
}) {
  return (
    <search>
      <form
        method="get"
        action="/fabricacion"
        className="flex flex-wrap items-end gap-4"
      >
        <div className="w-full sm:w-auto sm:min-w-44">
          <label
            htmlFor="filtro-estado"
            className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Estado
          </label>
          <select
            id="filtro-estado"
            name="estado"
            defaultValue={estado}
            className={inputClass}
          >
            <option value="">Todos</option>
            {LOT_STATES.map((code) => (
              <option key={code} value={code}>
                {lotStateLabel(code)}
              </option>
            ))}
          </select>
        </div>
        <div className="w-full sm:w-auto sm:min-w-44">
          <label
            htmlFor="filtro-donde"
            className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Fabricación
          </label>
          <select
            id="filtro-donde"
            name="donde"
            defaultValue={donde}
            className={inputClass}
          >
            <option value="">En casa y en taller</option>
            {["INTERNA", "EXTERNA"].map((code) => (
              <option key={code} value={code}>
                {whereLabel(code)}
              </option>
            ))}
          </select>
        </div>
        <div className="w-full sm:w-auto sm:min-w-52">
          <label
            htmlFor="filtro-taller"
            className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Taller
          </label>
          <select
            id="filtro-taller"
            name="taller"
            defaultValue={taller}
            className={inputClass}
          >
            <option value="">Todos</option>
            {talleres.map((t) => (
              <option key={t.codigo} value={t.codigo}>
                {t.nombre}
              </option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          className="inline-flex min-h-11 items-center justify-center sm:min-h-0 rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white"
        >
          Filtrar
        </button>
        {estado || donde || taller ? (
          <Link
            href="/fabricacion"
            className="py-2.5 text-sm text-muted underline decoration-gold underline-offset-4"
          >
            Limpiar
          </Link>
        ) : null}
      </form>
    </search>
  );
}
