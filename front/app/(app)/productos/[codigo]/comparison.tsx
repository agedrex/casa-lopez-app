import {
  Notice,
  numClass,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import {
  formatArs,
  formatDate,
  formatRate,
  formatUsd,
  quoteTypeLabel,
  stageLabel,
} from "@/lib/format";
import type { Cotizacion, Ficha } from "@/lib/types";

const TYPES = ["INICIAL", "RECOTIZACION", "FINAL"] as const;

// Quote column (backend) behind each stage code.
const STAGE_COLUMN = {
  CUERO: "cuero",
  FORRO: "forro",
  FLEX: "flex",
  GOMA_EVA: "goma_eva",
  HERRAJES: "herrajes",
  HILO_CEMENTO: "hilo_cemento",
  CORTE: "corte",
  CONFECCION: "confeccion",
} as const satisfies Record<string, keyof Cotizacion>;

type Column = {
  key: string;
  title: string;
  date: string | null;
  dollar: string | null;
  stage: (code: keyof typeof STAGE_COLUMN) => string | null;
  other: Record<
    "subtotal" | "componentes" | "iva" | "arreglos" | "totalArs" | "totalUsd",
    string | null
  >;
};

function savedColumn(type: string, c: Cotizacion | undefined): Column {
  return {
    key: type,
    title: quoteTypeLabel(type),
    date: c?.fecha ?? null,
    dollar: c?.dolar ?? null,
    stage: (code) => (c ? c[STAGE_COLUMN[code]] : null),
    other: {
      subtotal: c?.subtotal_etapas ?? null,
      componentes: c?.componentes_kit ?? null,
      iva: c?.iva_compras ?? null,
      arreglos: c?.arreglos ?? null,
      totalArs: c?.total_ars ?? null,
      totalUsd: c?.total_usd ?? null,
    },
  };
}

function todayColumn(ficha: Ficha): Column {
  const cost = ficha.costo_hoy;
  return {
    key: "HOY",
    title: "Hoy (sin guardar)",
    date: cost?.fecha ?? null,
    dollar: cost?.dolar ?? null,
    stage: (code) => cost?.etapas[code] ?? null,
    other: {
      subtotal: cost?.subtotal ?? null,
      componentes: cost?.componentes_kit ?? null,
      iva: cost?.iva_compras ?? null,
      arreglos: cost?.arreglos ?? null,
      totalArs: cost?.total_ars ?? null,
      totalUsd: cost?.total_usd ?? null,
    },
  };
}

/**
 * Side by side view of the stored quotes by type (the newest one of each) and the cost
 * today. Every figure is the string the API sent; nothing is added or subtracted here.
 */
export function Comparison({ ficha }: { ficha: Ficha }) {
  if (ficha.cotizaciones.length === 0) return null;
  // `cotizaciones` comes newest first, so `find` picks the latest of each type.
  const columns = [
    ...TYPES.map((type) =>
      savedColumn(
        type,
        ficha.cotizaciones.find((c) => c.tipo === type),
      ),
    ),
    todayColumn(ficha),
  ];
  const stages = Object.keys(STAGE_COLUMN) as (keyof typeof STAGE_COLUMN)[];

  const rows: {
    label: string;
    strong?: boolean;
    cell: (c: Column) => string;
  }[] = [
    { label: "Fecha", cell: (c) => formatDate(c.date) },
    { label: "Dólar", cell: (c) => formatRate(c.dollar) },
    ...stages.map((code) => ({
      label: stageLabel(code),
      cell: (c: Column) => formatArs(c.stage(code)),
    })),
    { label: "Subtotal de etapas", cell: (c) => formatArs(c.other.subtotal) },
    {
      label: "Componentes del kit",
      cell: (c) => formatArs(c.other.componentes),
    },
    { label: "IVA de compras", cell: (c) => formatArs(c.other.iva) },
    { label: "Arreglos", cell: (c) => formatArs(c.other.arreglos) },
    {
      label: "Total (ARS)",
      strong: true,
      cell: (c) => formatArs(c.other.totalArs),
    },
    {
      label: "Total (USD)",
      strong: true,
      cell: (c) => formatUsd(c.other.totalUsd),
    },
  ];

  return (
    <section>
      <SectionTitle>Comparación de cotizaciones</SectionTitle>
      <TableWrap>
        <table className={tableClass}>
          <caption className="sr-only">
            Cotización inicial, recotización, final y costo de hoy, lado a lado
          </caption>
          <thead>
            <tr>
              <th scope="col" className={thClass}>
                &nbsp;
              </th>
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className={`${thClass} ${numClass}`}
                >
                  {column.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label}>
                <th
                  scope="row"
                  className={`${tdClass} text-left ${row.strong ? "font-bold" : "font-normal"}`}
                >
                  {row.label}
                </th>
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`${tdClass} ${numClass} ${row.strong ? "font-bold" : ""}`}
                  >
                    {row.cell(column)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      <div className="mt-3">
        <Notice tone="info" title="Cómo leer esta tabla">
          Si hay más de una cotización del mismo tipo se muestra la más
          reciente. Un guion significa que todavía no hay una cotización de ese
          tipo.
        </Notice>
      </div>
    </section>
  );
}
