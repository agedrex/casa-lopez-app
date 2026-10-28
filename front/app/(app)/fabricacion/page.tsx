import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { inputClass } from "@/components/form";
import { OrdersTable } from "@/components/orders-table";
import { ErrorNotice, Notice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { LOT_STATES, lotStateLabel, whereLabel } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { OrdenResumen, Taller } from "@/lib/types";
import { CasaVsTallerSection } from "./casa-vs-taller";

export const metadata: Metadata = { title: "Fabricación" };

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
      <PageHeader
        eyebrow="Producción"
        title="Fabricación"
        description="Lotes en casa o en taller con sus cantidades, fechas y precios. El costo de cada lote lo calcula la aplicación: materiales de hoy más lo que cobra el taller."
        actions={
          canWrite(user.role) ? (
            <Link
              href="/fabricacion/nuevo"
              className="rounded-card bg-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm text-white hover:bg-ink-soft"
            >
              Nuevo lote
            </Link>
          ) : undefined
        }
      />
      <div className="space-y-12">
        <section aria-labelledby="lotes-titulo">
          <h2 id="lotes-titulo" className="sr-only">
            Lotes
          </h2>
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
              <>
                <p className="mb-3 text-sm text-muted" aria-live="polite">
                  {ordenes.data.length}{" "}
                  {ordenes.data.length === 1 ? "lote" : "lotes"}
                </p>
                <OrdersTable ordenes={ordenes.data} />
              </>
            )
          ) : (
            <ErrorNotice message={ordenes.message} />
          )}
        </section>
        <Suspense
          fallback={<p className="text-sm text-muted">Cargando resumen…</p>}
        >
          <CasaVsTallerSection />
        </Suspense>
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
    <search className="mb-8">
      <form
        method="get"
        action="/fabricacion"
        className="flex flex-wrap items-end gap-4"
      >
        <div className="min-w-44">
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
        <div className="min-w-44">
          <label
            htmlFor="filtro-donde"
            className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Dónde
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
        <div className="min-w-52">
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
          className="rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white"
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
