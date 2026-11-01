import { Notice } from "@/components/ui";
import {
  daysAgoText,
  formatArs,
  formatDate,
  formatPercent,
  formatQuantity,
} from "@/lib/format";
import type { Referencia, ReferenciaItem, ReferenciaNivel } from "@/lib/types";

const ORIGIN: Record<Exclude<ReferenciaNivel, "SIN_DATOS">, string> = {
  MISMO_PRODUCTO: "Este mismo producto",
  MISMA_CATEGORIA_Y_TAMANO: "Productos comparables: misma categoría y tamaño",
  MISMA_CATEGORIA: "Misma categoría, otro tamaño: referencia lejana",
};

function variationText(item: ReferenciaItem): string | null {
  if (item.precio_anterior === null || item.variacion_pct === null) return null;
  return `Antes pagó ${formatArs(item.precio_anterior)} (${formatPercent(item.variacion_pct)})`;
}

function Item({
  item,
  nivel,
}: {
  item: ReferenciaItem;
  nivel: ReferenciaNivel;
}) {
  const variation = variationText(item);
  return (
    <li className="rounded-card border border-line bg-surface px-4 py-3">
      <p className="font-display text-2xl tabular-nums">
        {formatArs(item.precio)}
        <span className="ml-2 text-base text-muted">por unidad</span>
      </p>
      <p className="mt-1 text-base">
        {formatDate(item.fecha)} · {daysAgoText(item.dias)}
      </p>
      <p className="mt-1 text-sm text-muted">
        {nivel === "MISMO_PRODUCTO"
          ? null
          : `${item.producto} · ${item.nombre} · `}
        {item.taller_nombre ?? item.taller} · lote {item.lote} ·{" "}
        {formatQuantity(item.cantidad)} u.
        {variation ? ` · ${variation}` : ""}
      </p>
    </li>
  );
}

/** "Precio de referencia para negociar": the latest PAID price, from the closest level that has data. */
export function PrecioReferencia({ referencia }: { referencia: Referencia }) {
  return (
    <section
      aria-label="Precio de referencia para negociar"
      className="space-y-3"
    >
      <h3 className="font-display text-lg">
        Precio de referencia para negociar
      </h3>
      {referencia.nivel === "SIN_DATOS" ? (
        <Notice tone="info" title="Sin precios pagados todavía">
          Todavía no hay precios pagados de{" "}
          {referencia.categoria ?? "esta categoría"}. El primero que se cargue
          va a ser la referencia.
        </Notice>
      ) : (
        <>
          <p className="text-base text-muted">{ORIGIN[referencia.nivel]}</p>
          <ul className="space-y-3">
            {referencia.items.map((item) => (
              <Item
                key={`${item.taller}-${item.producto}`}
                item={item}
                nivel={referencia.nivel}
              />
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
