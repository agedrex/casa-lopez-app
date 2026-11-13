"use client";

import Link from "next/link";
import { LotStateBadge } from "@/components/orders-table";
import {
  numClass,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { formatArs, formatDate, formatQuantity } from "@/lib/format";
import type { UltimoLote } from "@/lib/lotes";
import type { Fila } from "./lote-product-rows";

export type PanelState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; ultimo: UltimoLote | null };

/** Last lot of the chosen workshop next to what is being loaded now. */
export function UltimoLotePanel({
  state,
  filas,
}: {
  state: PanelState;
  filas: Fila[];
}) {
  if (state.status === "idle") return null;
  if (state.status === "loading") {
    return (
      <p className="text-sm text-muted" aria-live="polite">
        Buscando el último lote del taller…
      </p>
    );
  }
  if (state.ultimo === null) {
    return (
      <p className="rounded-card border border-line px-4 py-3 text-sm">
        Primer lote de este taller
      </p>
    );
  }

  const { lote, productos: enElUltimo } = state.ultimo;
  const cargados = filas.filter((fila) => fila.producto.trim() !== "");
  const comparables = cargados.filter(
    (fila) => enElUltimo[fila.producto.trim()] !== undefined,
  );

  return (
    <section
      aria-label="Último lote del taller"
      className="space-y-4 rounded-card border border-line px-4 py-4"
    >
      <h2 className="text-xs uppercase tracking-caps-sm text-muted">
        Último lote de este taller
      </h2>
      <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
        <Datum label="Lote">
          <Link
            href={`/fabricacion/${encodeURIComponent(lote.lote)}`}
            className="underline decoration-gold underline-offset-4"
          >
            {lote.lote}
          </Link>
        </Datum>
        <Datum label="Fecha">{formatDate(lote.fecha)}</Datum>
        <Datum label="Estado">
          <LotStateBadge estado={lote.estado} />
        </Datum>
        <Datum label="Unidades">{formatQuantity(lote.unidades)}</Datum>
        <Datum label="Total pagado">
          {lote.precio_pagado_promedio === null
            ? "Sin precio pagado"
            : formatArs(lote.total_pagado)}
        </Datum>
        <Datum label="Promedio por unidad">
          {formatArs(lote.precio_pagado_promedio)}
        </Datum>
      </dl>
      {comparables.length > 0 ? (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Producto</th>
                <th className={`${thClass} ${numClass}`}>Cantidad ahora</th>
                <th className={`${thClass} ${numClass}`}>
                  Cantidad en el último lote
                </th>
                <th className={`${thClass} ${numClass}`}>
                  Pagado por unidad en el último lote
                </th>
              </tr>
            </thead>
            <tbody>
              {comparables.map((fila) => {
                const codigo = fila.producto.trim();
                const previo = enElUltimo[codigo];
                return (
                  <tr key={fila.id}>
                    <td className={tdClass}>
                      {fila.nombre}
                      <span className="block text-xs text-muted">{codigo}</span>
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {fila.cantidad.trim() || "—"}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatQuantity(previo?.cantidad)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {previo?.pagado == null
                        ? "Sin precio pagado"
                        : formatArs(previo.pagado)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </TableWrap>
      ) : cargados.length > 0 ? (
        <p className="text-sm text-muted">
          Ninguno de los productos cargados estuvo en ese lote.
        </p>
      ) : null}
    </section>
  );
}

function Datum({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-caps-sm text-muted">{label}</dt>
      <dd className="mt-0.5 tabular-nums">{children}</dd>
    </div>
  );
}
