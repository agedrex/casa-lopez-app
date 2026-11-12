"use client";

import {
  type ClipboardEvent,
  type FocusEvent,
  type KeyboardEvent,
  memo,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useTransition,
} from "react";
import { error, type FormState, IDLE } from "@/lib/action-state";
import { parseDecimalInput, sameDecimalText } from "@/lib/format";
import { FormFeedback } from "./form";
import { Notice } from "./ui";

export type GridOption = { value: string; label: string };

export type GridColumn = {
  key: string;
  header: string;
  kind: "text" | "decimal" | "select";
  options?: GridOption[];
  /** Text of the empty option of a select. */
  emptyLabel?: string;
  /** A modified (or new) row cannot be saved with this cell empty. */
  required?: boolean;
  /** Editable only in the rows that are being added; in saved rows it is plain text. */
  newOnly?: boolean;
  /** Tailwind width class of the column, e.g. `min-w-28`. */
  width?: string;
  placeholder?: string;
  /** Extra check on a non-empty or required cell. Return the message to show, or null. */
  validate?: (
    value: string,
    context: { original: string; isNew: boolean },
  ) => string | null;
};

export type GridRow = {
  id: string;
  /** Plain name of the row, used in labels and messages. */
  name: string;
  /** First (sticky) column. */
  label: ReactNode;
  /** Values as the API has them, already written as a person would type them. */
  cells: Record<string, string>;
  /** Highlights the whole row (for example, data is missing). */
  warn?: boolean;
  /** Read-only cells after the editable ones, one per `extraHeaders` entry. */
  extras?: ReactNode[];
};

export type GridChange = {
  id: string;
  /** Every editable cell of the row, as it is now. */
  cells: Record<string, string>;
  /** Keys of the cells that differ from what the API has. */
  changed: string[];
};

export type GridSave = {
  changes: GridChange[];
  added: Record<string, string>[];
  /** Ids of the saved rows marked for deletion (only with `allowDelete`). */
  deleted: string[];
};

type Values = Record<string, string>;
type Edits = Record<string, Values>;
type Draft = { id: string; cells: Values };
type CellError = { message: string; immediate: boolean };
type RowErrors = Record<string, CellError>;

const NO_ERRORS: RowErrors = {};
const NO_DEFAULTS: Values = {};
const NO_HEADERS: string[] = [];
const MAX_PASTED_ROWS = 500;

function sameCell(column: GridColumn, a: string, b: string): boolean {
  return column.kind === "decimal"
    ? sameDecimalText(a, b)
    : a.trim() === b.trim();
}

function cellError(
  column: GridColumn,
  value: string,
  original: string,
  isNew: boolean,
): CellError | null {
  const text = value.trim();
  if (text === "") {
    if (column.required)
      return { message: "Falta completar.", immediate: false };
  } else if (column.kind === "decimal" && parseDecimalInput(text) === null) {
    return {
      message: "No es un número válido. Ejemplo: 0,25.",
      immediate: true,
    };
  }
  const custom = column.validate?.(text, { original, isNew });
  return custom ? { message: custom, immediate: false } : null;
}

const inputBase =
  "min-h-11 w-full rounded-card border px-2 py-2 text-base outline-none focus:border-gold focus:bg-surface sm:min-h-0 sm:py-1.5 sm:text-sm";

function inputState(modified: boolean, hasError: boolean): string {
  if (hasError) return "border-bordeaux bg-bordeaux/5";
  if (modified) return "border-gold bg-gold/15";
  return "border-transparent bg-transparent hover:border-line";
}

type RowViewProps = {
  row: GridRow;
  rowIndex: number;
  draft: boolean;
  columns: GridColumn[];
  original: Values;
  edit: Values | undefined;
  dirty: boolean;
  errors: RowErrors;
  showAllErrors: boolean;
  onChange: (id: string, key: string, value: string, draft: boolean) => void;
  onRemove?: (id: string) => void;
  /** Present only with `allowDelete`: marks or unmarks a saved row for deletion. */
  onToggleDelete?: (id: string) => void;
  deleting?: boolean;
  /** Present only in auto-save mode: ticks a saved row to delete it later. */
  onToggleSelect?: (id: string) => void;
  selected?: boolean;
  extraHeaders: string[];
};

// Memoized: typing in one cell re-renders only its row, not the 300+ others.
const RowView = memo(function RowView({
  row,
  rowIndex,
  draft,
  columns,
  original,
  edit,
  dirty,
  errors,
  showAllErrors,
  onChange,
  onRemove,
  onToggleDelete,
  deleting = false,
  onToggleSelect,
  selected = false,
  extraHeaders,
}: RowViewProps) {
  const rowTone = deleting
    ? "bg-blush/40 line-through opacity-60"
    : selected
      ? "bg-gold/15"
      : row.warn
        ? "bg-blush/25"
        : "";
  return (
    <tr className={rowTone}>
      <th
        scope="row"
        className={`sticky left-0 z-10 border-b border-line/70 bg-surface px-3 py-2 text-left align-top font-normal sm:px-4 ${dirty ? "border-l-4 border-l-gold" : row.warn ? "border-l-4 border-l-blush-deep" : "border-l-4 border-l-transparent"}`}
      >
        {!draft && onToggleSelect ? (
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onToggleSelect(row.id)}
              aria-label={`Seleccionar ${row.name} para borrar`}
              className="size-4 accent-ink"
            />
            {row.label}
          </label>
        ) : (
          row.label
        )}
        {draft && onRemove ? (
          <button
            type="button"
            onClick={() => onRemove(row.id)}
            aria-label={`Quitar ${row.name}`}
            className="mt-1 block text-sm text-muted underline decoration-gold underline-offset-4 sm:text-xs"
          >
            Quitar
          </button>
        ) : null}
        {!draft && onToggleDelete ? (
          <button
            type="button"
            onClick={() => onToggleDelete(row.id)}
            aria-label={`${deleting ? "Deshacer el borrado de" : "Borrar"} ${row.name}`}
            className="mt-1 block text-sm text-muted underline decoration-gold underline-offset-4 sm:text-xs"
          >
            {deleting ? "Deshacer" : "Borrar"}
          </button>
        ) : null}
      </th>
      {columns.map((column, columnIndex) => {
        const base = original[column.key] ?? "";
        const value = edit?.[column.key] ?? base;
        const cellClass = `border-b border-line/70 px-1.5 py-1.5 align-top ${column.width ?? ""}`;
        if ((column.newOnly && !draft) || (deleting && !draft)) {
          const shown =
            column.kind === "select"
              ? (column.options?.find((option) => option.value === value)
                  ?.label ?? value)
              : value;
          return (
            <td
              key={column.key}
              className={`${cellClass} px-3 py-2 text-sm text-muted`}
            >
              {shown || "—"}
            </td>
          );
        }
        const modified = draft
          ? !sameCell(column, value, base)
          : edit !== undefined &&
            column.key in edit &&
            !sameCell(column, value, base);
        const found = errors[column.key];
        const shownError = found && (showAllErrors || found.immediate);
        const label = `${column.header} de ${row.name}${modified ? " (modificado)" : ""}`;
        const common = {
          "data-grid-r": rowIndex,
          "data-grid-c": columnIndex,
          "aria-label": label,
          "aria-invalid": shownError ? true : undefined,
          "aria-describedby": shownError
            ? `err-${row.id}-${column.key}`
            : undefined,
        } as const;
        return (
          <td key={column.key} className={cellClass}>
            {column.kind === "select" ? (
              <select
                {...common}
                value={value}
                onChange={(event) =>
                  onChange(row.id, column.key, event.target.value, draft)
                }
                className={`${inputBase} ${inputState(modified, Boolean(shownError))}`}
              >
                <option value="">{column.emptyLabel ?? "Elegir…"}</option>
                {value !== "" &&
                !column.options?.some((option) => option.value === value) ? (
                  <option value={value}>{value}</option>
                ) : null}
                {column.options?.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                {...common}
                type="text"
                value={value}
                inputMode={column.kind === "decimal" ? "decimal" : "text"}
                autoComplete="off"
                spellCheck={false}
                placeholder={column.placeholder}
                onChange={(event) =>
                  onChange(row.id, column.key, event.target.value, draft)
                }
                className={`${inputBase} ${column.kind === "decimal" ? "text-right tabular-nums" : ""} ${inputState(modified, Boolean(shownError))}`}
              />
            )}
            {shownError ? (
              <span
                id={`err-${row.id}-${column.key}`}
                className="mt-1 block text-sm text-bordeaux sm:text-xs"
              >
                {found.message}
              </span>
            ) : null}
          </td>
        );
      })}
      {row.extras?.map((extra, index) => (
        <td
          key={extraHeaders[index] ?? row.id}
          className="border-b border-line/70 px-3 py-2 align-top text-sm"
        >
          {extra}
        </td>
      ))}
    </tr>
  );
});

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/**
 * A spreadsheet-like grid: the cells are inputs, a modified cell is highlighted, and one
 * button sends only what changed. Tab, Enter and the arrow keys move between cells, and a
 * block copied from Excel can be pasted over several rows and columns at once.
 *
 * The grid knows nothing about the API: the parent says how to save (`onSave`) and what the
 * result was; this component keeps the typed text, the change count and the checks that do
 * not need the server (a number that is not a number, a required cell left empty).
 */
export function EditableGrid({
  label,
  rowHeader,
  columns,
  extraHeaders = NO_HEADERS,
  rows,
  noun,
  allowNew = false,
  startWithDraft = true,
  addLabel = "Agregar fila",
  allowDelete = false,
  newRowDefaults,
  newRowLabel = "Fila nueva",
  warning,
  note,
  footer,
  autoSave = false,
  compact = false,
  onSave,
}: {
  /** Accessible name of the table. */
  label: string;
  rowHeader: string;
  columns: GridColumn[];
  extraHeaders?: string[];
  rows: GridRow[];
  /** What a row is, for the counters: `{ one: "modelo", many: "modelos" }`. */
  noun: { one: string; many: string };
  allowNew?: boolean;
  /**
   * With `allowNew`, whether an empty draft row is always waiting at the end. Turn it off to show
   * only the saved rows and let the add button create each new row.
   */
  startWithDraft?: boolean;
  /** Text of the add button (needs `allowNew`). */
  addLabel?: string;
  /** Lets a saved row be marked for deletion; the parent decides what deleting means. */
  allowDelete?: boolean;
  newRowDefaults?: Record<string, string>;
  newRowLabel?: string;
  /** A notice shown while there are changes (for example, what saving will undo). */
  warning?: (save: GridSave) => string | null;
  note?: ReactNode;
  footer?: ReactNode;
  /**
   * No save button: a changed row is saved when the cursor leaves the cell (and nothing is left
   * to fix), and saved rows are ticked and deleted with one button. Needs `allowDelete`.
   */
  autoSave?: boolean;
  /** Sin resumen vacío ni instrucciones: solo la grilla y lo que haya pendiente. */
  compact?: boolean;
  onSave: (save: GridSave) => Promise<FormState>;
}) {
  const defaults = newRowDefaults ?? NO_DEFAULTS;
  const sequence = useRef(1);
  const tableRef = useRef<HTMLTableElement>(null);
  const pendingFocus = useRef<{ row: number; column: number } | null>(null);
  const makeDraft = useCallback(
    (): Draft => ({
      id: `nuevo-${sequence.current++}`,
      cells: { ...defaults },
    }),
    [defaults],
  );
  const [edits, setEdits] = useState<Edits>({});
  const [drafts, setDrafts] = useState<Draft[]>(() =>
    allowNew && startWithDraft
      ? [{ id: "nuevo-0", cells: { ...defaults } }]
      : [],
  );
  const [deleted, setDeleted] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [attempted, setAttempted] = useState(false);
  const [result, setResult] = useState<FormState>(IDLE);
  const [pasteInfo, setPasteInfo] = useState("");
  const [saving, startSaving] = useTransition();

  const rowsById = useMemo(
    () => new Map(rows.map((row) => [row.id, row])),
    [rows],
  );

  const analysis = useMemo(() => {
    const changes: GridChange[] = [];
    const added: Values[] = [];
    const errors: Record<string, RowErrors> = {};
    const errorList: string[] = [];
    const dirtyIds = new Set<string>();
    const touchedDrafts = new Set<string>();
    let changedCells = 0;
    let errorCount = 0;

    const check = (
      id: string,
      name: string,
      cells: Values,
      originals: Values,
      isNew: boolean,
    ) => {
      for (const column of columns) {
        if (column.newOnly && !isNew) continue;
        const found = cellError(
          column,
          cells[column.key] ?? "",
          originals[column.key] ?? "",
          isNew,
        );
        if (!found) continue;
        errors[id] = { ...(errors[id] ?? {}), [column.key]: found };
        errorCount += 1;
        errorList.push(
          `${name}, ${column.header.toLowerCase()}: ${found.message}`,
        );
      }
    };

    for (const id of Object.keys(edits)) {
      const row = rowsById.get(id);
      if (!row || deleted.includes(id)) continue;
      const edit = edits[id];
      const changed = columns
        .filter(
          (column) =>
            !column.newOnly &&
            column.key in edit &&
            !sameCell(column, edit[column.key], row.cells[column.key] ?? ""),
        )
        .map((column) => column.key);
      if (changed.length === 0) continue;
      const current: Values = {};
      for (const column of columns) {
        if (column.newOnly) continue;
        current[column.key] = edit[column.key] ?? row.cells[column.key] ?? "";
      }
      changes.push({ id, cells: current, changed });
      dirtyIds.add(id);
      changedCells += changed.length;
      check(id, row.name, current, row.cells, false);
    }

    drafts.forEach((draft, index) => {
      const touched = columns.some(
        (column) =>
          !sameCell(
            column,
            draft.cells[column.key] ?? "",
            defaults[column.key] ?? "",
          ),
      );
      if (!touched) return;
      touchedDrafts.add(draft.id);
      dirtyIds.add(draft.id);
      added.push(draft.cells);
      check(
        draft.id,
        `${newRowLabel} ${index + 1}`,
        draft.cells,
        defaults,
        true,
      );
    });

    return {
      changes,
      added,
      errors,
      errorList,
      errorCount,
      dirtyIds,
      touchedDrafts,
      changedCells,
    };
  }, [edits, drafts, deleted, rowsById, columns, defaults, newRowLabel]);

  const dirty =
    analysis.changes.length + analysis.added.length + deleted.length > 0;

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  // After "add row" the new first cell takes the focus once it exists.
  useEffect(() => {
    const target = pendingFocus.current;
    if (!target) return;
    pendingFocus.current = null;
    tableRef.current
      ?.querySelector<HTMLElement>(
        `[data-grid-r="${target.row}"][data-grid-c="${target.column}"]`,
      )
      ?.focus();
  });

  const handleChange = useCallback(
    (id: string, key: string, value: string, draft: boolean) => {
      setResult((previous) => (previous.status === "idle" ? previous : IDLE));
      setPasteInfo("");
      if (draft) {
        setDrafts((previous) =>
          previous.map((item) =>
            item.id === id
              ? { ...item, cells: { ...item.cells, [key]: value } }
              : item,
          ),
        );
      } else {
        setEdits((previous) => ({
          ...previous,
          [id]: { ...previous[id], [key]: value },
        }));
      }
    },
    [],
  );

  const toggleDelete = useCallback((id: string) => {
    setResult((previous) => (previous.status === "idle" ? previous : IDLE));
    setDeleted((previous) =>
      previous.includes(id)
        ? previous.filter((item) => item !== id)
        : [...previous, id],
    );
  }, []);

  const toggleSelect = useCallback((id: string) => {
    setResult((previous) => (previous.status === "idle" ? previous : IDLE));
    setSelected((previous) =>
      previous.includes(id)
        ? previous.filter((item) => item !== id)
        : [...previous, id],
    );
  }, []);

  const removeDraft = useCallback((id: string) => {
    setDrafts((previous) => previous.filter((item) => item.id !== id));
  }, []);

  function addDraft(focusColumn = 0) {
    pendingFocus.current = {
      row: rows.length + drafts.length,
      column: focusColumn,
    };
    setDrafts((previous) => [...previous, makeDraft()]);
  }

  function discard() {
    setEdits({});
    setDeleted([]);
    setDrafts(allowNew && startWithDraft ? [makeDraft()] : []);
    setAttempted(false);
    setResult(IDLE);
    setPasteInfo("");
  }

  function save() {
    setAttempted(true);
    setPasteInfo("");
    if (analysis.errorCount > 0) {
      setResult(
        error(
          `Hay ${plural(analysis.errorCount, "celda", "celdas")} para revisar. No se guardó nada.`,
          analysis.errorList.slice(0, 6),
        ),
      );
      requestAnimationFrame(() =>
        tableRef.current
          ?.querySelector<HTMLElement>('[aria-invalid="true"]')
          ?.focus(),
      );
      return;
    }
    startSaving(async () => {
      try {
        const outcome = await onSave({
          changes: analysis.changes,
          added: analysis.added,
          deleted,
        });
        setResult(outcome);
        if (outcome.status === "ok") {
          setEdits({});
          setDeleted([]);
          setDrafts(allowNew && startWithDraft ? [makeDraft()] : []);
          setAttempted(false);
        }
      } catch {
        setResult(error("No se pudo guardar. Intente de nuevo."));
      }
    });
  }

  const selectedRows = selected.filter((id) => rowsById.has(id));

  function deleteSelected() {
    const names = selectedRows.map((id) => rowsById.get(id)?.name ?? id);
    const shown = names.slice(0, 5).join(", ");
    const more = names.length > 5 ? ` y ${names.length - 5} más` : "";
    if (!window.confirm(`¿Borrar ${shown}${more}?`)) return;
    startSaving(async () => {
      try {
        const outcome = await onSave({
          changes: [],
          added: [],
          deleted: selectedRows,
        });
        setResult(outcome);
        if (outcome.status === "ok") setSelected([]);
      } catch {
        setResult(error("No se pudo borrar. Intente de nuevo."));
      }
    });
  }

  // Auto-save: leaving a cell saves what changed, but only when nothing is left to fix.
  function onBlurSave() {
    if (!autoSave || saving || !dirty || analysis.errorCount > 0) return;
    save();
  }

  const total = rows.length + drafts.length;

  function findCell(
    row: number,
    column: number,
    dRow: number,
    dColumn: number,
  ) {
    let r = row + dRow;
    let c = column + dColumn;
    while (r >= 0 && r < total && c >= 0 && c < columns.length) {
      const found = tableRef.current?.querySelector<HTMLElement>(
        `[data-grid-r="${r}"][data-grid-c="${c}"]`,
      );
      if (found) return found;
      r += dRow;
      c += dColumn;
    }
    return null;
  }

  function moveFocus(
    row: number,
    column: number,
    dRow: number,
    dColumn: number,
  ): boolean {
    const target = findCell(row, column, dRow, dColumn);
    if (!target) return false;
    target.focus();
    return true;
  }

  function onKeyDown(event: KeyboardEvent<HTMLTableSectionElement>) {
    const el = event.target as HTMLElement;
    if (el.dataset.gridR === undefined) return;
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const row = Number(el.dataset.gridR);
    const column = Number(el.dataset.gridC);
    const isSelect = el instanceof HTMLSelectElement;
    if (event.key === "Enter") {
      event.preventDefault();
      const moved = moveFocus(row, column, event.shiftKey ? -1 : 1, 0);
      const last = drafts[drafts.length - 1];
      if (
        !moved &&
        !event.shiftKey &&
        allowNew &&
        last &&
        row === total - 1 &&
        analysis.touchedDrafts.has(last.id)
      ) {
        addDraft(column);
      }
    } else if (event.key === "ArrowDown" && !isSelect) {
      if (moveFocus(row, column, 1, 0)) event.preventDefault();
    } else if (event.key === "ArrowUp" && !isSelect) {
      if (moveFocus(row, column, -1, 0)) event.preventDefault();
    } else if (el instanceof HTMLInputElement) {
      const collapsed = el.selectionStart === el.selectionEnd;
      if (event.key === "ArrowLeft" && collapsed && el.selectionStart === 0) {
        if (moveFocus(row, column, 0, -1)) event.preventDefault();
      } else if (
        event.key === "ArrowRight" &&
        collapsed &&
        el.selectionStart === el.value.length
      ) {
        if (moveFocus(row, column, 0, 1)) event.preventDefault();
      }
    }
  }

  function onFocus(event: FocusEvent<HTMLTableSectionElement>) {
    const el = event.target;
    if (el instanceof HTMLInputElement && el.dataset.gridR !== undefined) {
      el.select();
    }
  }

  function onPaste(event: ClipboardEvent<HTMLTableSectionElement>) {
    const el = event.target as HTMLElement;
    if (el.dataset.gridR === undefined) return;
    const text = event.clipboardData
      .getData("text/plain")
      .replace(/\r/g, "")
      .replace(/\n+$/, "");
    // A single value pastes the normal way.
    if (!/[\t\n]/.test(text)) return;
    event.preventDefault();

    const firstRow = Number(el.dataset.gridR);
    const firstColumn = Number(el.dataset.gridC);
    const lines = text
      .split("\n")
      .slice(0, MAX_PASTED_ROWS)
      .map((line) => line.split("\t"));
    const missing = allowNew ? Math.max(0, firstRow + lines.length - total) : 0;
    const created = Array.from({ length: missing }, makeDraft);
    const allDrafts = [...drafts, ...created];

    const editPatch: Edits = {};
    const draftPatch = new Map<string, Values>();
    let pasted = 0;
    let skipped = 0;

    lines.forEach((cells, lineIndex) => {
      const index = firstRow + lineIndex;
      const isDraft = index >= rows.length;
      const target = isDraft ? allDrafts[index - rows.length] : rows[index];
      if (!target) {
        skipped += cells.length;
        return;
      }
      cells.forEach((raw, cellIndex) => {
        const column = columns[firstColumn + cellIndex];
        if (!column || (column.newOnly && !isDraft)) {
          skipped += 1;
          return;
        }
        let value = raw.trim();
        if (column.kind === "select" && value !== "") {
          const wanted = value.toLowerCase();
          const match = column.options?.find(
            (option) =>
              option.value.toLowerCase() === wanted ||
              option.label.toLowerCase() === wanted,
          );
          if (!match) {
            skipped += 1;
            return;
          }
          value = match.value;
        }
        pasted += 1;
        if (isDraft) {
          draftPatch.set(target.id, {
            ...draftPatch.get(target.id),
            [column.key]: value,
          });
        } else {
          editPatch[target.id] = {
            ...editPatch[target.id],
            [column.key]: value,
          };
        }
      });
    });

    if (Object.keys(editPatch).length > 0) {
      setEdits((previous) => {
        const next = { ...previous };
        for (const [id, patch] of Object.entries(editPatch)) {
          next[id] = { ...previous[id], ...patch };
        }
        return next;
      });
    }
    if (draftPatch.size > 0 || created.length > 0) {
      setDrafts(
        allDrafts.map((draft) =>
          draftPatch.has(draft.id)
            ? {
                ...draft,
                cells: { ...draft.cells, ...draftPatch.get(draft.id) },
              }
            : draft,
        ),
      );
    }
    setResult(IDLE);
    setPasteInfo(
      `Se pegaron ${plural(pasted, "celda", "celdas")}.${
        skipped > 0
          ? ` ${plural(skipped, "valor no se pudo pegar", "valores no se pudieron pegar")} (columna bloqueada, valor que no coincide o fuera de la grilla).`
          : ""
      } Revise los cambios y guarde.`,
    );
  }

  const parts = [
    analysis.changes.length > 0
      ? `${plural(analysis.changes.length, `${noun.one} modificado`, `${noun.many} modificados`)} (${plural(analysis.changedCells, "celda", "celdas")})`
      : null,
    analysis.added.length > 0
      ? plural(analysis.added.length, "fila nueva", "filas nuevas")
      : null,
    deleted.length > 0
      ? plural(deleted.length, "fila para borrar", "filas para borrar")
      : null,
  ].filter(Boolean);
  const summary =
    parts.length > 0
      ? parts.join(" · ")
      : compact
        ? null
        : "Sin cambios todavía.";
  const warningText = dirty
    ? warning?.({
        changes: analysis.changes,
        added: analysis.added,
        deleted,
      })
    : null;
  const helpId = "grid-help";

  return (
    <div className="space-y-4">
      <div
        className={`flex flex-wrap items-center gap-3 rounded-card border border-line bg-surface px-4 py-3 ${compact && !summary && !saving && selectedRows.length === 0 ? "hidden" : ""}`}
      >
        {summary ? (
          <p aria-live="polite" className="text-sm font-bold">
            {summary}
          </p>
        ) : null}
        {autoSave ? (
          <div className="flex w-full flex-wrap items-center gap-3 sm:ml-auto sm:w-auto">
            {saving ? (
              <span className="text-sm text-muted">Guardando…</span>
            ) : null}
            {selectedRows.length > 0 ? (
              <>
                <button
                  type="button"
                  onClick={() => setSelected([])}
                  disabled={saving}
                  className="min-h-12 flex-1 rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white disabled:opacity-40 sm:min-h-0 sm:flex-none"
                >
                  Quitar selección
                </button>
                <button
                  type="button"
                  onClick={deleteSelected}
                  disabled={saving}
                  className="min-h-12 flex-1 rounded-card bg-bordeaux px-5 py-2.5 text-sm uppercase tracking-caps-sm text-white hover:opacity-90 disabled:opacity-40 sm:min-h-0 sm:flex-none"
                >
                  Borrar {plural(selectedRows.length, "fila", "filas")}
                </button>
              </>
            ) : null}
          </div>
        ) : (
          <div className="flex w-full flex-wrap gap-3 sm:ml-auto sm:w-auto">
            <button
              type="button"
              onClick={discard}
              disabled={!dirty || saving}
              className="min-h-12 flex-1 rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white disabled:opacity-40 sm:min-h-0 sm:flex-none"
            >
              Descartar
            </button>
            <button
              type="button"
              onClick={save}
              disabled={!dirty || saving}
              className="min-h-12 flex-1 rounded-card bg-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm text-white hover:bg-ink-soft disabled:opacity-40 sm:min-h-0 sm:flex-none"
            >
              {saving ? "Guardando…" : "Guardar cambios"}
            </button>
          </div>
        )}
      </div>
      {warningText ? <Notice title={warningText} /> : null}
      <FormFeedback state={result} />
      <p aria-live="polite" className="text-sm text-muted empty:hidden">
        {pasteInfo}
      </p>
      {note}
      {compact ? null : (
        <p id={helpId} className="text-sm text-muted sm:text-xs">
          Escriba en la celda. Tab pasa a la celda de al lado, Enter a la de
          abajo (Mayús + Enter, a la de arriba) y las flechas se mueven por la
          grilla. También puede copiar varias celdas de Excel y pegarlas acá.{" "}
          {autoSave
            ? "Cada cambio se guarda solo al salir de la celda; una fila nueva se guarda cuando tiene todo completo. Para borrar, tilde las filas y use «Borrar»."
            : "Los cambios se resaltan y recién se guardan con «Guardar cambios»."}
        </p>
      )}
      <div className="max-h-[75vh] overflow-auto overscroll-x-contain rounded-card border border-line bg-surface">
        <table
          ref={tableRef}
          aria-label={label}
          aria-describedby={compact ? undefined : helpId}
          className="w-full min-w-max border-collapse text-left text-sm"
        >
          <thead>
            <tr>
              <th className="sticky left-0 top-0 z-30 border-b border-line bg-paper-mid px-3 py-3 text-sm font-normal uppercase tracking-caps-sm text-muted sm:px-4 sm:text-xs">
                {rowHeader}
              </th>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={`sticky top-0 z-20 border-b border-line bg-paper-mid px-3 py-3 text-sm font-normal uppercase tracking-caps-sm text-muted sm:text-xs ${column.kind === "decimal" ? "text-right" : ""} ${column.width ?? ""}`}
                >
                  {column.header}
                </th>
              ))}
              {extraHeaders.map((header) => (
                <th
                  key={header}
                  className="sticky top-0 z-20 border-b border-line bg-paper-mid px-3 py-3 text-sm font-normal uppercase tracking-caps-sm text-muted sm:text-xs"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody
            onKeyDown={onKeyDown}
            onPaste={onPaste}
            onFocus={onFocus}
            onBlur={onBlurSave}
          >
            {rows.map((row, index) => (
              <RowView
                key={row.id}
                row={row}
                rowIndex={index}
                draft={false}
                columns={columns}
                original={row.cells}
                edit={edits[row.id]}
                dirty={analysis.dirtyIds.has(row.id)}
                errors={analysis.errors[row.id] ?? NO_ERRORS}
                showAllErrors={attempted}
                onChange={handleChange}
                onToggleDelete={
                  allowDelete && !autoSave ? toggleDelete : undefined
                }
                deleting={deleted.includes(row.id)}
                onToggleSelect={
                  allowDelete && autoSave ? toggleSelect : undefined
                }
                selected={selected.includes(row.id)}
                extraHeaders={extraHeaders}
              />
            ))}
            {drafts.map((draft, index) => (
              <RowView
                key={draft.id}
                row={{
                  id: draft.id,
                  name: `${newRowLabel} ${index + 1}`,
                  label: (
                    <span className="text-sm text-muted">
                      {newRowLabel} {index + 1}
                    </span>
                  ),
                  cells: defaults,
                }}
                rowIndex={rows.length + index}
                draft
                columns={columns}
                original={defaults}
                edit={draft.cells}
                dirty={analysis.dirtyIds.has(draft.id)}
                errors={analysis.errors[draft.id] ?? NO_ERRORS}
                showAllErrors={attempted}
                onChange={handleChange}
                onRemove={removeDraft}
                extraHeaders={extraHeaders}
              />
            ))}
          </tbody>
        </table>
      </div>
      {allowNew ? (
        <button
          type="button"
          onClick={() => addDraft()}
          className="min-h-12 w-full rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white sm:min-h-0 sm:w-auto"
        >
          {addLabel}
        </button>
      ) : null}
      {footer}
    </div>
  );
}
