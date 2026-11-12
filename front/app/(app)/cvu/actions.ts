"use server";

import { redirect } from "next/navigation";
import { error, type FormState } from "@/lib/action-state";
import { apiPost } from "@/lib/api";
import { parseDecimalInput } from "@/lib/format";
import { getSession } from "@/lib/session";
import type { Escenario } from "@/lib/types";
import { fromFailure, text } from "@/lib/write-guard";

export type EscenarioState = FormState & { data?: Escenario };

const PERIODO = /^\d{4}-\d{2}$/;

function positive(value: string | null): value is string {
  return value !== null && /[1-9]/.test(value);
}

/**
 * Runs the sales scenario. It saves nothing, but the API only lets an admin call it
 * (ESCRITURA); here we only check the session and the API's 403 comes back as the error.
 */
export async function runEscenario(
  _previous: EscenarioState,
  formData: FormData,
): Promise<EscenarioState> {
  const session = await getSession();
  if (!session) redirect("/login");

  const codigos = formData.getAll("codigo");
  const unidades = formData.getAll("unidades");
  const precios = formData.getAll("precio");
  const items: { codigo: string; unidades: string; precio: string | null }[] =
    [];
  for (let index = 0; index < codigos.length; index += 1) {
    const codigo = String(codigos[index] ?? "").trim();
    const units = String(unidades[index] ?? "").trim();
    const price = String(precios[index] ?? "").trim();
    // A fully empty row is just an unused row.
    if (!codigo && !units && !price) continue;
    const row = items.length + 1;
    if (!codigo) return error(`Fila ${row}: elegí el producto.`);
    const parsedUnits = parseDecimalInput(units);
    if (!positive(parsedUnits)) {
      return error(`Fila ${row}: ingresá las unidades, mayor que cero.`);
    }
    let parsedPrice: string | null = null;
    if (price) {
      parsedPrice = parseDecimalInput(price);
      if (!positive(parsedPrice)) {
        return error(
          `Fila ${row}: el precio tiene que ser un número mayor que cero, por ejemplo 45000.`,
        );
      }
    }
    items.push({ codigo, unidades: parsedUnits, precio: parsedPrice });
  }
  if (items.length === 0) return error("Agregá al menos un producto.");

  const periodo = text(formData, "periodo");
  if (periodo && !PERIODO.test(periodo)) return error("Elegí el mes.");

  const result = await apiPost<Escenario>("/cvu/escenario", {
    periodo: periodo || null,
    items,
  });
  if (!result.ok) return fromFailure(result);
  return { status: "ok", data: result.data };
}
