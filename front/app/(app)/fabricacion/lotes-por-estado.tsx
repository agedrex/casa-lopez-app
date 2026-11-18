import Link from "next/link";
import { LotStateBadge, whereText } from "@/components/orders-table";
import { formatQuantity, lotStateLabel, todayIso } from "@/lib/format";
import {
  agruparLotesPorEstado,
  diasEntre,
  textoDeDias,
} from "@/lib/lote-estados";
import { nombreDeLote } from "@/lib/lotes";
import type { OrdenResumen } from "@/lib/types";

function LoteCard({ orden, hoy }: { orden: OrdenResumen; hoy: string }) {
  const dias = diasEntre(orden.fecha_de_envio, hoy);
  const unidades = Number(orden.unidades);
  return (
    <li>
      <Link
        href={`/fabricacion/${encodeURIComponent(orden.codigo)}`}
        className="flex min-h-28 items-center justify-between gap-4 rounded-card border border-line bg-surface p-4 shadow-card"
      >
        <span className="min-w-0 space-y-1">
          <span className="block break-words text-lg font-bold underline decoration-gold underline-offset-4">
            {nombreDeLote(orden.codigo, orden.fecha_de_envio)}
          </span>
          <span className="block text-sm text-muted">{whereText(orden)}</span>
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <LotStateBadge estado={orden.estado} />
            {dias !== null && orden.estado !== "CERRADA" ? (
              <span className="text-xs text-muted">
                Hace {textoDeDias(dias)}
              </span>
            ) : null}
          </span>
        </span>
        <span className="shrink-0 text-right">
          <span className="font-display text-4xl tabular-nums">
            {formatQuantity(orden.unidades)}
          </span>
          <span className="block text-xs text-muted">
            {unidades === 1 ? "unidad" : "unidades"}
          </span>
        </span>
      </Link>
    </li>
  );
}

function Grupo({
  estado,
  lotes,
  hoy,
}: {
  estado: string;
  lotes: OrdenResumen[];
  hoy: string;
}) {
  return (
    <ul
      className="grid gap-3 md:grid-cols-2"
      aria-label={lotStateLabel(estado)}
    >
      {lotes.map((orden) => (
        <LoteCard key={orden.codigo} orden={orden} hoy={hoy} />
      ))}
    </ul>
  );
}

/**
 * The lots of the taller as big cards, one block per state in the order of the cycle (what is still to start first,
 * then what is being cut or sewn, then what is ready), the closed ones apart and folded. Lot name, state and units;
 * no money of any kind.
 */
export function LotesPorEstado({ ordenes }: { ordenes: OrdenResumen[] }) {
  const hoy = todayIso();
  const grupos = agruparLotesPorEstado(ordenes);
  const abiertos = grupos.filter((g) => g.estado !== "CERRADA");
  const cerrados = grupos.find((g) => g.estado === "CERRADA");
  return (
    <div className="space-y-8">
      {abiertos.length === 0 ? (
        <p className="text-base text-muted">
          No hay lotes para hacer en este momento.
        </p>
      ) : null}
      {abiertos.map((grupo) => (
        <section key={grupo.estado} aria-label={lotStateLabel(grupo.estado)}>
          <h2 className="mb-3 flex items-baseline gap-2 text-xl">
            {lotStateLabel(grupo.estado)}
            <span className="text-sm text-muted">
              {grupo.lotes.length} {grupo.lotes.length === 1 ? "lote" : "lotes"}
            </span>
          </h2>
          <Grupo estado={grupo.estado} lotes={grupo.lotes} hoy={hoy} />
        </section>
      ))}
      {cerrados ? (
        <details>
          <summary className="min-h-11 cursor-pointer py-2 text-base text-muted">
            Lotes cerrados ({cerrados.lotes.length})
          </summary>
          <div className="mt-3">
            <Grupo estado="CERRADA" lotes={cerrados.lotes} hoy={hoy} />
          </div>
        </details>
      ) : null}
    </div>
  );
}
