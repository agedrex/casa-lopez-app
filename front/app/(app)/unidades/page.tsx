import type { Metadata } from "next";
import Link from "next/link";
import {
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
import { formatPeriod, formatQuantity, todayIso } from "@/lib/format";
import { requireSession } from "@/lib/session";
import type { UnidadesProducidas } from "@/lib/types";

export const metadata: Metadata = { title: "Unidades producidas" };

const PERIODO = /^\d{4}-(0[1-9]|1[0-2])$/;

export default async function UnidadesPage({
  searchParams,
}: {
  searchParams: Promise<{ periodo?: string | string[] }>;
}) {
  await requireSession();
  const raw = (await searchParams).periodo;
  const requested = (Array.isArray(raw) ? raw[0] : raw)?.trim() ?? "";
  // The calendar starts on the current month; "todo" is the explicit way to see every month.
  const verTodo = requested === "todo";
  const periodo = verTodo
    ? ""
    : PERIODO.test(requested)
      ? requested
      : todayIso().slice(0, 7);
  const result = await apiGet<UnidadesProducidas>(
    `/ordenes/unidades-por-producto${periodo ? `?periodo=${periodo}` : ""}`,
  );

  return (
    <>
      <PageHeader
        eyebrow="Costos variables"
        title="Unidades producidas"
        description="Unidades de cada producto que salieron a producción, sumando los lotes ya iniciados. Un lote planificado todavía no cuenta."
      />
      <form className="mb-6 flex flex-wrap items-end gap-3" action="/unidades">
        <label className="text-sm text-ink-soft">
          Mes de envío
          <input
            type="month"
            name="periodo"
            defaultValue={periodo}
            className="mt-1 block rounded-card border border-line bg-surface px-3 py-2 text-sm"
          />
        </label>
        <button
          type="submit"
          className="inline-flex min-h-11 items-center rounded-card bg-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm text-white hover:bg-ink-soft sm:min-h-0"
        >
          Ver
        </button>
        {periodo ? (
          <Link
            href="/unidades?periodo=todo"
            className="py-2.5 text-sm underline"
          >
            Ver todo
          </Link>
        ) : null}
      </form>
      {result.ok ? (
        result.data.productos.length === 0 ? (
          <Notice
            tone="info"
            title={
              periodo
                ? `No hay unidades en producción enviadas en ${formatPeriod(periodo)}.`
                : "Todavía no hay unidades en producción."
            }
          />
        ) : (
          <TableWrap>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Producto</th>
                  <th className={thClass}>Categoría</th>
                  <th className={`${thClass} ${numClass}`}>Lotes</th>
                  <th className={`${thClass} ${numClass}`}>Unidades</th>
                </tr>
              </thead>
              <tbody>
                {result.data.productos.map((fila) => (
                  <tr key={fila.producto} className="hover:bg-paper-mid/50">
                    <td className={tdClass}>
                      <Link
                        href={`/productos/${encodeURIComponent(fila.producto)}`}
                        className="underline decoration-gold underline-offset-4"
                      >
                        {fila.producto_nombre}
                      </Link>
                      <span className="block text-xs text-muted">
                        {fila.producto}
                      </span>
                    </td>
                    <td className={tdClass}>{fila.categoria ?? "—"}</td>
                    <td className={`${tdClass} ${numClass}`}>{fila.lotes}</td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatQuantity(fila.unidades)}
                    </td>
                  </tr>
                ))}
                <tr>
                  <td className={`${tdClass} font-medium`} colSpan={3}>
                    Total
                  </td>
                  <td className={`${tdClass} ${numClass} font-medium`}>
                    {formatQuantity(result.data.total_unidades)}
                  </td>
                </tr>
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
