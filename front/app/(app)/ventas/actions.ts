"use server";

import { revalidatePath } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { parseDecimalInput } from "@/lib/format";
import {
  denyUnlessAdmin,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const FECHA = /^\d{4}-\d{2}-\d{2}$/;

/** A positive decimal typed by a person, as the plain string the API takes (never converted to a number). */
function positive(raw: string): string | null {
  const parsed = parseDecimalInput(raw);
  return parsed !== null && /[1-9]/.test(parsed) ? parsed : null;
}

const BY_STATUS = {
  404: "No encontramos ese producto. Elegilo de la lista.",
} as const;

/** Appends one real sale. The API freezes the cost of that moment; the price is the net one charged. */
export async function registrarVenta(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;
  const producto = text(formData, "producto").toUpperCase();
  if (!producto) return error("Elegí qué producto se vendió.");
  const unidades = positive(text(formData, "unidades"));
  if (unidades === null) {
    return error("Escribí cuántas unidades se vendieron (más de 0).");
  }
  const precio = positive(text(formData, "precio"));
  if (precio === null) {
    return error("Escribí el precio cobrado por unidad (más de 0).");
  }
  const fecha = optional(formData, "fecha");
  if (fecha !== null && !FECHA.test(fecha)) {
    return error("La fecha no es válida.");
  }
  const result = await apiPost("/ventas", {
    producto,
    unidades,
    precio_unitario_ars: precio,
    fecha,
    canal: optional(formData, "canal"),
    nota: optional(formData, "nota"),
  });
  if (!result.ok) return fromFailure(result, BY_STATUS);
  revalidatePath("/ventas");
  return ok("Venta registrada. El costo de hoy quedó guardado con ella.");
}

/** Appends one transfer to the store. The API freezes the factory cost and the transfer price. */
export async function registrarTransferencia(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;
  const producto = text(formData, "producto").toUpperCase();
  if (!producto) return error("Elegí qué producto pasás a la tienda.");
  const unidades = positive(text(formData, "unidades"));
  if (unidades === null) {
    return error("Escribí cuántas unidades pasan a la tienda (más de 0).");
  }
  const fecha = optional(formData, "fecha");
  if (fecha !== null && !FECHA.test(fecha)) {
    return error("La fecha no es válida.");
  }
  const result = await apiPost("/transferencias", {
    producto,
    unidades,
    fecha,
    nota: optional(formData, "nota"),
  });
  if (!result.ok) return fromFailure(result, BY_STATUS);
  revalidatePath("/ventas");
  return ok(
    "Pase registrado. El costo y el precio de transferencia de hoy quedaron guardados.",
  );
}
