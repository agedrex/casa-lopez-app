"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { inputClass } from "@/components/form";
import { CardItem, CardList, Notice, tdClass, thClass } from "@/components/ui";
import { formatArs, formatUsd } from "@/lib/format";

type Row = { codigo: string; catalogo: string[]; costos_variables: string[] };
export type GrillaData = {
  encabezados_catalogo: string[];
  encabezados_costos_variables: string[];
  filas: Row[];
};
type Source = "catalogo" | "costos_variables";
type Group = "Producto" | "Etapas" | "Totales" | "Cotizaciones";
type Column = {
  id: string;
  label: string;
  source: Source;
  index: number;
  group: Group;
};
const GROUPS: Group[] = ["Producto", "Etapas", "Totales", "Cotizaciones"];
const DECIMAL = /^-?\d+(?:\.\d+)?$/;
const collator = new Intl.Collator("es-AR", {
  numeric: true,
  sensitivity: "base",
});
const buttonClass =
  "inline-flex min-h-11 items-center justify-center rounded-card border border-line bg-surface px-4 py-2 text-sm hover:border-gold focus-visible:outline-2 focus-visible:outline-gold";

function makeColumns(data: GrillaData): Column[] {
  const catalogo = data.encabezados_catalogo.map(
    (label, index): Column => ({
      id: `catalogo:${index}`,
      label,
      source: "catalogo",
      index,
      group:
        index <= 6
          ? "Producto"
          : index <= 8 || index === 14
            ? "Totales"
            : "Cotizaciones",
    }),
  );
  const costos = data.encabezados_costos_variables.map(
    (label, index): Column => ({
      id: `costos_variables:${index}`,
      label: index < 2 ? `${label} (costos)` : label,
      source: "costos_variables",
      index,
      group: index <= 2 ? "Producto" : index <= 10 ? "Etapas" : "Totales",
    }),
  );
  return [
    catalogo[1],
    ...catalogo.filter((_, index) => index !== 1),
    ...costos,
  ];
}

function cellValue(row: Row, column: Column): string {
  return row[column.source][column.index] ?? "";
}

// Sort decimal strings without converting an API amount to a JS number.
function compareDecimal(left: string, right: string): number {
  const leftNegative = left.startsWith("-");
  const rightNegative = right.startsWith("-");
  if (leftNegative !== rightNegative) return leftNegative ? -1 : 1;
  const [leftWhole, leftPart = ""] = left.replace(/^-/, "").split(".");
  const [rightWhole, rightPart = ""] = right.replace(/^-/, "").split(".");
  const a = leftWhole.replace(/^0+/, "") || "0";
  const b = rightWhole.replace(/^0+/, "") || "0";
  const width = Math.max(leftPart.length, rightPart.length);
  const order =
    a.length - b.length ||
    a.localeCompare(b) ||
    leftPart.padEnd(width, "0").localeCompare(rightPart.padEnd(width, "0"));
  return leftNegative ? -order : order;
}

function compare(left: string, right: string): number {
  if (!left || !right) return left ? 1 : right ? -1 : 0;
  return DECIMAL.test(left) && DECIMAL.test(right)
    ? compareDecimal(left, right)
    : collator.compare(left, right);
}

function csvCell(value: string): string {
  const safeValue =
    /^[=+\-@]/.test(value) && !DECIMAL.test(value) ? `'${value}` : value;
  return `"${safeValue.replaceAll('"', '""')}"`;
}

export function GrillaClient({ data }: { data: GrillaData }) {
  const columns = useMemo(() => makeColumns(data), [data]);
  const [visible, setVisible] = useState(
    () => new Set(columns.map((column) => column.id)),
  );
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [sortId, setSortId] = useState("catalogo:1");
  const [descending, setDescending] = useState(false);
  const [mobileGrid, setMobileGrid] = useState(false);
  const [showColumns, setShowColumns] = useState(false);
  const categories = useMemo(
    () =>
      [
        ...new Set(data.filas.map((row) => row.catalogo[2]).filter(Boolean)),
      ].sort(collator.compare),
    [data.filas],
  );
  const grouped = GROUPS.map((group) => ({
    group,
    columns: columns.filter(
      (column) => column.group === group && visible.has(column.id),
    ),
  })).filter((item) => item.columns.length > 0);
  const shownColumns = grouped.flatMap((item) => item.columns);
  const rows = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("es-AR");
    const sortedColumn =
      columns.find((column) => column.id === sortId) ?? columns[0];
    return data.filas
      .filter(
        (row) =>
          (!needle ||
            `${row.codigo} ${row.catalogo[1]}`
              .toLocaleLowerCase("es-AR")
              .includes(needle)) &&
          (!category || row.catalogo[2] === category),
      )
      .sort((a, b) => {
        const order = compare(
          cellValue(a, sortedColumn),
          cellValue(b, sortedColumn),
        );
        return (
          (descending ? -order : order) || collator.compare(a.codigo, b.codigo)
        );
      });
  }, [category, columns, data.filas, descending, query, sortId]);

  function toggleColumn(id: string) {
    setVisible((current) => {
      if (current.size === 1 && current.has(id)) return current;
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function sortBy(id: string) {
    if (sortId === id) setDescending((current) => !current);
    else {
      setSortId(id);
      setDescending(false);
    }
  }

  function downloadCsv() {
    const lines = [
      shownColumns.map((column) => csvCell(column.label)).join(","),
    ];
    for (const row of rows)
      lines.push(
        shownColumns.map((column) => csvCell(cellValue(row, column))).join(","),
      );
    const url = URL.createObjectURL(
      new Blob(["\uFEFF", lines.join("\r\n")], {
        type: "text/csv;charset=utf-8",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "grilla-completa.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="min-w-0">
      <div className="mb-5 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,14rem)]">
        <label className="block text-xs uppercase tracking-caps-sm text-muted">
          Buscar por nombre o código
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Nombre o código"
            className={`${inputClass} mt-1.5`}
          />
        </label>
        <label className="block text-xs uppercase tracking-caps-sm text-muted">
          Categoría
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            className={`${inputClass} mt-1.5`}
          >
            <option value="">Todas</option>
            {categories.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="mb-5 flex flex-wrap gap-2">
        <button
          type="button"
          className={buttonClass}
          aria-expanded={showColumns}
          onClick={() => setShowColumns((current) => !current)}
        >
          Elegir columnas
        </button>
        <button
          type="button"
          className={buttonClass}
          disabled={rows.length === 0}
          onClick={downloadCsv}
        >
          Descargar CSV
        </button>
        <button
          type="button"
          className={`${buttonClass} md:hidden`}
          onClick={() => setMobileGrid((current) => !current)}
        >
          {mobileGrid ? "Ver como tarjetas" : "Ver como grilla"}
        </button>
      </div>
      {showColumns ? (
        <div className="mb-5 rounded-card border border-line bg-surface p-4">
          <p className="mb-3 text-sm text-muted">
            Elegí las columnas que querés ver y descargar.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {GROUPS.map((group) => (
              <fieldset key={group}>
                <legend className="mb-2 font-bold">{group}</legend>
                <div className="space-y-1">
                  {columns
                    .filter((column) => column.group === group)
                    .map((column) => (
                      <label
                        key={column.id}
                        className="flex min-h-11 items-center gap-2 text-sm"
                      >
                        <input
                          type="checkbox"
                          checked={visible.has(column.id)}
                          onChange={() => toggleColumn(column.id)}
                        />
                        {column.label}
                      </label>
                    ))}
                </div>
              </fieldset>
            ))}
          </div>
        </div>
      ) : null}
      <p className="mb-3 text-sm text-muted" aria-live="polite">
        {rows.length} {rows.length === 1 ? "producto" : "productos"}
      </p>
      {data.filas.length === 0 ? (
        <Notice title="Todavía no hay productos cargados." tone="info">
          Para empezar,{" "}
          <Link
            href="/productos/nuevo"
            className="underline decoration-gold underline-offset-4"
          >
            creá un producto
          </Link>
          .
        </Notice>
      ) : rows.length === 0 ? (
        <Notice title="No hay productos con esos filtros." tone="info">
          Probá con otra búsqueda o categoría.
        </Notice>
      ) : (
        <>
          <div className={mobileGrid ? "hidden" : "md:hidden"}>
            <CardList>
              {rows.map((row) => (
                <CardItem key={row.codigo}>
                  <Link
                    href={`/productos/${encodeURIComponent(row.codigo)}`}
                    className="block min-h-11"
                  >
                    <span className="text-xs text-muted">{row.codigo}</span>
                    <p className="mt-1 font-bold">{row.catalogo[1]}</p>
                    <p className="mt-1 text-xs text-muted">{row.catalogo[2]}</p>
                    <p className="mt-3 font-semibold tabular-nums">
                      {formatArs(row.catalogo[7])}
                    </p>
                    <p className="text-sm text-muted tabular-nums">
                      {formatUsd(row.catalogo[8])}
                    </p>
                    {row.catalogo[14] ? (
                      <p className="mt-3 text-sm text-bordeaux">
                        Aviso: {row.catalogo[14]}
                      </p>
                    ) : null}
                  </Link>
                </CardItem>
              ))}
            </CardList>
          </div>
          <div
            className={mobileGrid ? "block min-w-0" : "hidden min-w-0 md:block"}
          >
            <div className="max-h-[70vh] max-w-full overflow-auto overscroll-contain rounded-card border border-line bg-surface">
              <table className="w-max min-w-full border-separate border-spacing-0 text-left text-sm">
                <thead className="sticky top-0 z-10">
                  <tr>
                    {grouped.map(({ group, columns: groupColumns }) => (
                      <th
                        key={group}
                        colSpan={groupColumns.length}
                        className="border-b border-r border-line bg-paper-mid px-4 py-2 text-xs uppercase tracking-caps-sm text-ink-soft"
                      >
                        {group}
                      </th>
                    ))}
                  </tr>
                  <tr>
                    {shownColumns.map((column, index) => (
                      <th
                        key={column.id}
                        scope="col"
                        className={`${thClass} whitespace-nowrap ${index === 0 ? "sticky left-0 z-20 bg-paper-mid" : ""}`}
                      >
                        <button
                          type="button"
                          className="min-h-11 text-left hover:text-ink focus-visible:outline-2 focus-visible:outline-gold"
                          onClick={() => sortBy(column.id)}
                          aria-label={`Ordenar por ${column.label}`}
                        >
                          {column.label}
                          {sortId === column.id
                            ? descending
                              ? " ↓"
                              : " ↑"
                            : ""}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.codigo} className="hover:bg-paper-mid/50">
                      {shownColumns.map((column, index) => (
                        <td
                          key={column.id}
                          title={cellValue(row, column)}
                          className={`${tdClass} max-w-72 whitespace-nowrap ${index === 0 ? "sticky left-0 z-10 bg-surface font-semibold" : ""}`}
                        >
                          <Link
                            href={`/productos/${encodeURIComponent(row.codigo)}`}
                            className="block min-h-11 min-w-full py-1 focus-visible:outline-2 focus-visible:outline-gold"
                          >
                            {cellValue(row, column) || "—"}
                          </Link>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
