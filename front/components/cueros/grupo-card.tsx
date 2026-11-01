import Link from "next/link";
import { CardItem } from "@/components/ui";
import {
  formatArs,
  formatDate,
  formatMoney,
  formatPercent,
  formatQuantity,
} from "@/lib/format";
import type { GrupoCuero, PiezaCuero, UmbralMedido } from "@/lib/types";
import { EstadoBadge } from "./estado-badge";

function M2({ value }: { value: string | null }) {
  return <>{formatQuantity(value)} m²</>;
}

export function Metric({
  label,
  children,
  highlight = false,
}: {
  label: string;
  children: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div
      className={
        highlight
          ? "col-span-2 rounded-card border border-gold bg-parchment px-4 py-3"
          : ""
      }
    >
      <dt className="text-sm text-muted">{label}</dt>
      <dd
        className={
          highlight ? "text-2xl font-bold" : "text-base font-bold tabular-nums"
        }
      >
        {children}
      </dd>
    </div>
  );
}

/** "Umbral de irrecuperable medido: X m² (Y %), sobre N descartes", or a note when there is no data yet. */
export function UmbralLinea({ umbral }: { umbral: UmbralMedido | null }) {
  if (!umbral) {
    return (
      <p className="text-sm text-muted">
        Umbral de irrecuperable medido: todavía no hay datos.
      </p>
    );
  }
  const pct = umbral.promedio_pct_comprado
    ? ` (${formatPercent(umbral.promedio_pct_comprado)})`
    : "";
  const descartes = umbral.casos === 1 ? "descarte" : "descartes";
  return (
    <p className="text-sm text-muted">
      {`Umbral de irrecuperable medido: ${formatQuantity(umbral.promedio_m2)} m²${pct}, sobre ${umbral.casos} ${descartes}.`}
    </p>
  );
}

export function GrupoMetricas({
  grupo,
  showMoney,
}: {
  grupo: GrupoCuero;
  showMoney: boolean;
}) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
      <Metric label="Disponible" highlight>
        <M2 value={grupo.disponible} />
      </Metric>
      <Metric label="Comprado">
        <M2 value={grupo.comprado} />
      </Metric>
      <Metric label="Desperdicio natural 10 %">
        <M2 value={grupo.natural} />
      </Metric>
      <Metric label="Cuero total real">
        <M2 value={grupo.cuero_total_real} />
      </Metric>
      <Metric label="Cortado">
        <M2 value={grupo.cortado} />
      </Metric>
      <Metric label="Irrecuperable">
        <M2 value={grupo.irrecuperable} />
      </Metric>
      <Metric label="Desperdicio neto">
        {formatPercent(grupo.porcentaje_desperdicio_neto)}
      </Metric>
      {showMoney ? (
        <Metric label="Costo del desperdicio">
          {formatArs(grupo.costo_desperdicio_ars)}
        </Metric>
      ) : null}
    </dl>
  );
}

export function PiezaFila({
  pieza,
  showMoney,
}: {
  pieza: PiezaCuero;
  showMoney: boolean;
}) {
  return (
    <Link
      href={`/cueros/${encodeURIComponent(pieza.codigo)}`}
      className="flex min-h-12 flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-card border border-line px-4 py-2 hover:border-gold"
    >
      <span className="flex items-center gap-2">
        <span className="font-bold">{pieza.codigo}</span>
        <EstadoBadge estado={pieza.estado} />
      </span>
      <span className="text-base tabular-nums">
        <M2 value={pieza.disponible} /> disponibles
      </span>
      <span className="w-full text-sm text-muted">
        Compra: {formatDate(pieza.fecha_de_compra)}
        {pieza.proveedor ? ` · ${pieza.proveedor}` : ""}
        {showMoney && pieza.precio_pagado_por_m2 && pieza.moneda
          ? ` · ${formatMoney(pieza.precio_pagado_por_m2, pieza.moneda)} por m²`
          : ""}
      </span>
    </Link>
  );
}

/** One leather and color: totals, the measured threshold and (optionally) its skins. */
export function GrupoCard({
  grupo,
  titulo,
  showMoney,
  conPiezas,
}: {
  grupo: GrupoCuero;
  titulo: string;
  showMoney: boolean;
  conPiezas: boolean;
}) {
  return (
    <CardItem>
      <h3 className="mb-3 font-display text-xl">{titulo}</h3>
      <GrupoMetricas grupo={grupo} showMoney={showMoney} />
      <div className="mt-3">
        <UmbralLinea umbral={grupo.umbral_medido} />
      </div>
      {grupo.avisos.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-muted">
          {grupo.avisos.map((aviso) => (
            <li key={aviso}>{aviso}</li>
          ))}
        </ul>
      ) : null}
      {conPiezas ? (
        <div className="mt-4 space-y-2">
          <h4 className="text-base font-bold">Pieles</h4>
          {grupo.piezas.length === 0 ? (
            <p className="text-sm text-muted">No hay pieles para mostrar.</p>
          ) : (
            grupo.piezas.map((pieza) => (
              <PiezaFila
                key={pieza.codigo}
                pieza={pieza}
                showMoney={showMoney}
              />
            ))
          )}
        </div>
      ) : null}
    </CardItem>
  );
}
