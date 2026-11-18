// Checks of one cell of an editable grid that do not need the server, and when to show them.
// Pure on purpose: the grid only draws what these functions decide.

import { parseDecimalInput } from "./format";

export type CellError = { message: string; immediate: boolean };

/** The part of a grid column that the checks need. */
export type CeldaValidable = {
  kind: "text" | "decimal" | "select";
  required?: boolean;
  validate?: (
    value: string,
    context: { original: string; isNew: boolean },
  ) => string | null;
};

/** The problem of a cell, or null. `immediate` errors (a malformed number) show while typing. */
export function cellError(
  column: CeldaValidable,
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

/**
 * Whether the error of a cell is drawn: right away when it is `immediate`, once the person left
 * the cell (`visited`), or after a save was tried (`attempted`).
 */
export function mostrarErrorDeCelda(
  error: CellError | null | undefined,
  state: { visited: boolean; attempted: boolean },
): boolean {
  if (!error) return false;
  return error.immediate || state.visited || state.attempted;
}
