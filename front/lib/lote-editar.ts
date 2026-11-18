// Pure helpers of the "edit a lot's lines" UI (admin only). No session, no API, no arithmetic on amounts.
import { error, type FormState } from "./action-state";
import { parseDecimalInput } from "./format";

/** `10.000000` -> `10`, `6.500000` -> `6.5`: the quantity as the person typed it, for the input's initial value. */
export function plainQuantity(value: string): string {
  return value.includes(".") ? value.replace(/\.?0+$/, "") : value;
}

/** Reads the new quantity of a line; it must be a number greater than zero (to take a line out there is "Quitar"). */
export function readCantidad(formData: FormData): string | FormState {
  const raw = String(formData.get("cantidad") ?? "").trim();
  const cantidad = parseDecimalInput(raw);
  if (cantidad === null || !/[1-9]/.test(cantidad)) {
    return error(
      "Ingrese una cantidad mayor que cero. Para sacar el producto del lote usá «Quitar».",
    );
  }
  return cantidad;
}
