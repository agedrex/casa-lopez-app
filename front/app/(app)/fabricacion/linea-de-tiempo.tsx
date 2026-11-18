import { Notice, SectionTitle } from "@/components/ui";
import {
  formatDate,
  formatDateTime,
  lotStateLabel,
  todayIso,
} from "@/lib/format";
import {
  lineaDeTiempo,
  textoDeDias,
  textoDeResponsable,
} from "@/lib/lote-estados";
import type { EstadoDeOrden } from "@/lib/types";

/**
 * The follow-up of a lot from the day it was created to the day it ended: every state with its date, how many days
 * it lasted, who changed it and when it was saved. Shared by the admin and the taller; no money.
 */
export function LineaDeTiempo({ estados }: { estados: EstadoDeOrden[] }) {
  const linea = lineaDeTiempo(estados, todayIso());
  const primero = linea.pasos[0];
  const cierre = linea.pasos.find((p) => p.estado === "CERRADA");
  return (
    <section aria-label="Seguimiento del lote">
      <SectionTitle>Estados del lote</SectionTitle>
      {primero === undefined ? (
        <Notice tone="info" title="Este lote no tiene historial de estados." />
      ) : (
        <>
          <p className="mb-4 text-sm text-muted">
            Creado {formatDate(primero.fecha)} ·{" "}
            {cierre
              ? `Terminado ${formatDate(cierre.fecha)}`
              : "Todavía en curso"}
            {linea.diasTotales !== null
              ? ` · ${textoDeDias(linea.diasTotales)} ${linea.terminado ? "en total" : "hasta hoy"}`
              : ""}
          </p>
          <ol className="space-y-0 border-l border-line pl-6">
            {linea.pasos.map((paso, index) => (
              <li
                key={`${paso.estado}-${paso.fecha}-${index}`}
                className="relative pb-6 last:pb-0"
                aria-current={paso.actual ? "step" : undefined}
              >
                <span
                  aria-hidden="true"
                  className="absolute -left-[1.85rem] top-1.5 size-2.5 rounded-full bg-gold"
                />
                <p className="font-bold">{lotStateLabel(paso.estado)}</p>
                <p className="text-sm text-muted">
                  {formatDate(paso.fecha)}
                  {paso.diasDesdeElInicio !== null && index > 0
                    ? ` · día ${paso.diasDesdeElInicio} del lote`
                    : ""}
                  {paso.diasEnElEstado !== null
                    ? ` · ${paso.actual ? "lleva" : "duró"} ${textoDeDias(paso.diasEnElEstado)}`
                    : ""}
                </p>
                {textoDeResponsable(paso, formatDateTime) ? (
                  <p className="text-sm text-muted">
                    {textoDeResponsable(paso, formatDateTime)}
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
