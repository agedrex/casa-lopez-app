import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { inputClass } from "@/components/form";
import { LotStateBadge, whereText } from "@/components/orders-table";
import {
  CardItem,
  CardList,
  ErrorNotice,
  Notice,
  PageHeader,
} from "@/components/ui";
import { type ApiResult, apiGet } from "@/lib/api";
import {
  formatDate,
  formatQuantity,
  LOT_STATES,
  lotStateLabel,
  whereLabel,
} from "@/lib/format";
import { canWrite, isTallerOnly } from "@/lib/permissions";
import { collapseSpaces } from "@/lib/productos";
import { requireSession } from "@/lib/session";
import type { OrdenDetalle, OrdenResumen, Taller } from "@/lib/types";
import { CasaVsTallerSection } from "./casa-vs-taller";

export const metadata: Metadata = { title: "Lotes" };

/** The taller sees each lot with its products inline; this caps the detail calls (one per lot). */
const TALLER_DETAIL_LIMIT = 30;

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
  const tallerOnly = isTallerOnly(user.role);
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

  // The taller reads lots but not the workshops list nor the house-vs-workshop summary (admin only).
  const [ordenes, talleres] = await Promise.all([
    apiGet<OrdenResumen[]>(`/ordenes?${filter}`),
    tallerOnly ? null : apiGet<Taller[]>("/talleres"),
  ]);
  const filtered = Boolean(estado || donde || taller);
  // For the taller each lot card lists what to make: one detail call per lot, in parallel.
  const detalles = ordenes.ok
    ? await Promise.all(
        ordenes.data
          .slice(0, TALLER_DETAIL_LIMIT)
          .map((orden) =>
            apiGet<OrdenDetalle>(
              `/ordenes/${encodeURIComponent(orden.codigo)}`,
            ),
          ),
      )
    : [];

  return (
    <>
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
      <div className="space-y-12">
        <section aria-labelledby="lotes-titulo">
          <h2 id="lotes-titulo" className="sr-only">
            Lotes
          </h2>
          <Filters
            estado={estado}
            donde={donde}
            taller={taller}
            talleres={talleres?.ok ? talleres.data : []}
            soloEstado={tallerOnly}
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
                <TallerLotes ordenes={ordenes.data} detalles={detalles} />
              </>
            )
          ) : (
            <ErrorNotice message={ordenes.message} />
          )}
        </section>
        {tallerOnly ? null : (
          <Suspense
            fallback={<p className="text-sm text-muted">Cargando resumen…</p>}
          >
            <CasaVsTallerSection />
          </Suspense>
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
  soloEstado = false,
}: {
  estado: string;
  donde: string;
  taller: string;
  talleres: Taller[];
  /** Taller role: only the state filter (it cannot list workshops and works with every lot it is given). */
  soloEstado?: boolean;
}) {
  return (
    <search className="mb-8">
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
        {soloEstado ? null : (
          <>
            <div className="w-full sm:w-auto sm:min-w-44">
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
          </>
        )}
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

/**
 * Taller view of the lots: one card per lot with its code, state, dates and, for each product,
 * the name and how many to make (linked to the product sheet). No money of any kind.
 */
function TallerLotes({
  ordenes,
  detalles,
}: {
  ordenes: OrdenResumen[];
  detalles: ApiResult<OrdenDetalle>[];
}) {
  return (
    <div className="max-w-3xl">
      <CardList>
        {ordenes.map((orden, index) => {
          const detalle = detalles[index];
          return (
            <CardItem key={orden.codigo}>
              <div className="flex items-start justify-between gap-3">
                <Link
                  href={`/fabricacion/${encodeURIComponent(orden.codigo)}`}
                  className="text-lg font-bold underline decoration-gold underline-offset-4"
                >
                  {orden.codigo}
                </Link>
                <LotStateBadge estado={orden.estado} />
              </div>
              <p className="mt-1 text-sm text-muted">{whereText(orden)}</p>
              <p className="mt-1 text-sm text-muted">
                Envío {formatDate(orden.fecha_de_envio)} · Entrega{" "}
                {formatDate(orden.fecha_de_entrega)}
              </p>
              {detalle?.ok && detalle.data.items.length > 0 ? (
                <ul className="mt-3 divide-y divide-line/70 border-t border-line/70">
                  {detalle.data.items.map((item) => (
                    <li key={item.codigo}>
                      <Link
                        href={`/productos/${encodeURIComponent(item.producto)}`}
                        className="flex min-h-12 items-center justify-between gap-3 py-2"
                      >
                        <span className="min-w-0">
                          <span className="line-clamp-2 break-words underline decoration-gold underline-offset-4">
                            {collapseSpaces(item.producto_nombre)}
                          </span>
                          <span className="block text-xs text-muted">
                            {item.producto}
                          </span>
                        </span>
                        <span className="shrink-0 text-right">
                          <span className="font-display text-2xl tabular-nums">
                            {formatQuantity(item.cantidad)}
                          </span>
                          <span className="block text-xs text-muted">
                            a hacer
                          </span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-muted">
                  {orden.productos}{" "}
                  {orden.productos === 1 ? "producto" : "productos"} ·{" "}
                  {formatQuantity(orden.unidades)} u. Abrí el lote para ver qué
                  hay que hacer.
                </p>
              )}
            </CardItem>
          );
        })}
      </CardList>
    </div>
  );
}
