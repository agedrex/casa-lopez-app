"use server";

import { randomUUID } from "node:crypto";
import { error, type FormState, IDLE } from "@/lib/action-state";
import { apiGet, apiPost } from "@/lib/api";
import type { Material, VozPropuesta } from "@/lib/types";
import { type InterpretarState, VOZ_MAX_CHARS, VOZ_NOTA } from "@/lib/voz";
import { denyUnlessWriter, fromFailure, text } from "@/lib/write-guard";
import { setMonto } from "../costos-fijos/actions";
import { createDolar } from "../dolar/actions";
import { savePrecios } from "../fabricacion/actions";
import { createPrecio } from "../materiales/actions";
import { addExtra } from "../productos/[codigo]/actions";

// The model may take up to 15 s plus one retry on the API side: give the call more room than a normal read.
const INTERPRET_TIMEOUT_MS = 25_000;

/**
 * Sends the sentence to the API, which asks the model to EXTRACT intent and raw mentions and answers a proposal. Nothing is
 * saved here: the card shows the proposal and a person confirms (see `confirmarVoz`).
 */
export async function interpretarVoz(
  _previous: InterpretarState,
  formData: FormData,
): Promise<InterpretarState> {
  const denied = await denyUnlessWriter();
  if (denied) return { status: "error", message: denied.message };

  const texto = text(formData, "texto");
  if (!texto) {
    return {
      status: "error",
      message: "Escriba o dicte lo que quiere cargar.",
    };
  }
  if (texto.length > VOZ_MAX_CHARS) {
    return {
      status: "error",
      message: `El pedido es demasiado largo: el máximo son ${VOZ_MAX_CHARS} caracteres.`,
    };
  }
  const result = await apiPost<VozPropuesta>(
    "/voz/interpretar",
    { texto },
    INTERPRET_TIMEOUT_MS,
  );
  if (!result.ok) return { status: "error", message: result.message };
  return { status: "ok", id: randomUUID(), propuesta: result.data };
}

function pick(formData: FormData, keys: string[]): FormData {
  const picked = new FormData();
  for (const key of keys) {
    const value = formData.get(key);
    if (typeof value === "string") picked.set(key, value);
  }
  return picked;
}

/**
 * What the person confirmed on the card. It runs the SAME server actions as the regular screens, with the person's own
 * session: roles, validation, the "big jump" confirmation and the 409 / 422 messages apply unchanged.
 */
export async function confirmarVoz(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  switch (text(formData, "accion")) {
    case "cargar_precio": {
      const body = pick(formData, [
        "material",
        "color",
        "precio",
        "moneda",
        "vigente_desde",
        "confirmar",
      ]);
      // The unit is always the material's consumption unit (as on the materials screen); the API checks it again.
      const materials = await apiGet<Material[]>("/materiales");
      if (!materials.ok) return fromFailure(materials);
      const chosen = materials.data.find(
        (item) => item.codigo === text(formData, "material"),
      );
      body.set("unidad_del_precio", chosen?.unidad_de_consumo ?? "");
      body.set("nota_fuente", VOZ_NOTA);
      return createPrecio(IDLE, body);
    }
    case "cargar_dolar": {
      const body = pick(formData, ["fecha", "valor", "tipo"]);
      body.set("nota", VOZ_NOTA);
      return createDolar(IDLE, body);
    }
    case "agregar_extra": {
      const producto = text(formData, "producto");
      if (!producto) return error("Indique el producto.");
      const body = pick(formData, ["material", "color", "consumo"]);
      body.set("nota", VOZ_NOTA);
      return addExtra(producto, IDLE, body);
    }
    case "registrar_precio_taller": {
      const lote = text(formData, "lote");
      const item = text(formData, "item");
      const cual = text(formData, "precio_de");
      if (!lote) return error("Indique el lote.");
      if (!item) return error("Indique el renglón del lote.");
      if (cual !== "cotizado" && cual !== "pagado") {
        return error("Indique si es el precio cotizado o el pagado.");
      }
      const body = new FormData();
      body.set(cual, text(formData, "precio"));
      return savePrecios(lote, item, IDLE, body);
    }
    case "cargar_monto_gasto": {
      const gasto = text(formData, "gasto");
      if (!gasto) return error("Indique el costo fijo.");
      return setMonto(gasto, IDLE, pick(formData, ["monto"]));
    }
    default:
      return error("Esa acción no se puede cargar desde la voz.");
  }
}
