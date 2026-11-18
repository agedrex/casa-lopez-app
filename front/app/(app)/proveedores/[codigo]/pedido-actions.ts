"use server";

import { refresh } from "next/cache";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiGet, apiPost } from "@/lib/api";
import {
  type LineaDePedidoBody,
  leerLineaSimpleDePedido,
  leerPielesDePedido,
  type PielesDePedidoBody,
} from "@/lib/pedidos";
import { type MaterialOption, materialOptions } from "@/lib/proveedores";
import type { Material, MaterialesLote, PedidoProveedor } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

/**
 * Reads `lineas.0.material`, `lineas.1.material`... until one is missing; the first row that is wrong is
 * reported. Leather rows (the ones with a sizes field) go under `pieles`, the rest under `lineas`.
 */
function readLines(
  formData: FormData,
): { lineas: LineaDePedidoBody[]; pieles: PielesDePedidoBody[] } | string {
  const lineas: LineaDePedidoBody[] = [];
  const pieles: PielesDePedidoBody[] = [];
  for (let i = 0; formData.has(`lineas.${i}.material`); i++) {
    const field = (name: string) => text(formData, `lineas.${i}.${name}`);
    const iva = formData.get(`lineas.${i}.iva`) === "on";
    // Only a leather row renders the `tamanos` field.
    if (formData.has(`lineas.${i}.tamanos`)) {
      const result = leerPielesDePedido(
        {
          material: field("material"),
          tamanos: field("tamanos"),
          precioPorM2: field("precio_por_m2"),
          color: field("color"),
          moneda: field("moneda"),
          iva,
        },
        i + 1,
      );
      if (!result.ok) return result.message;
      pieles.push(result.pieles);
    } else {
      const result = leerLineaSimpleDePedido(
        {
          material: field("material"),
          cantidad: field("cantidad"),
          precio: field("precio"),
          moneda: field("moneda"),
          iva,
        },
        i + 1,
      );
      if (!result.ok) return result.message;
      lineas.push(result.linea);
    }
  }
  return { lineas, pieles };
}

/**
 * Registers an order that arrived from the supplier. The API creates the unit price of each line and
 * saves everything or nothing; a refused line (for example a price already loaded for that date) is
 * named in its message. Orders are only added: there is no edit and no delete.
 */
export async function createPedidoDeProveedor(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const fecha = text(formData, "fecha_de_recepcion");
  if (!fecha) return error("Indique la fecha de recepción.");
  const read = readLines(formData);
  if (typeof read === "string") return error(read);
  const { lineas, pieles } = read;
  if (lineas.length === 0 && pieles.length === 0) {
    return error("Agregue al menos un material.");
  }

  const result = await apiPost<PedidoProveedor>(
    `/proveedores/${encodeURIComponent(codigo)}/pedidos`,
    {
      fecha_de_recepcion: fecha,
      remito: optional(formData, "remito"),
      nota: optional(formData, "nota"),
      lineas,
      pieles,
    },
  );
  if (!result.ok) {
    return fromFailure(result, { 404: "No existe ese proveedor." });
  }
  refresh();
  return ok(`Pedido ${result.data.codigo} registrado.`);
}

export type MaterialRapidoResult =
  | { ok: true; option: MaterialOption }
  | { ok: false; message: string };

const ETAPAS_RAPIDAS = [
  "CUERO",
  "FORRO",
  "FLEX",
  "GOMA_EVA",
  "HERRAJES",
  "HILO_CEMENTO",
];
const UNIDAD_POR_ETAPA: Record<string, string> = {
  CUERO: "m2",
  FORRO: "m2",
  FLEX: "m2",
  GOMA_EVA: "m2",
  HERRAJES: "unidad",
  HILO_CEMENTO: "unidad",
};

/**
 * Creates a material (no price) from the order form, so a supplier's new leather can be loaded without leaving it.
 * Prices still enter only through the order. If the name already exists the existing material is returned.
 */
export async function crearMaterialRapido(
  nombreCrudo: string,
  etapa: string,
): Promise<MaterialRapidoResult> {
  const denied = await denyUnlessWriter();
  if (denied)
    return { ok: false, message: "No tiene permiso para esta acción." };
  const nombre = nombreCrudo.replace(/\s+/g, " ").trim();
  if (!nombre) return { ok: false, message: "Escriba el nombre del material." };
  if (!ETAPAS_RAPIDAS.includes(etapa)) {
    return { ok: false, message: "Elija qué tipo de material es." };
  }
  const created = await apiPost<MaterialesLote>("/materiales/lote", {
    cambios: [],
    nuevos: [
      {
        nombre,
        etapa,
        unidad_de_consumo: UNIDAD_POR_ETAPA[etapa],
        precio: null,
        moneda: null,
        proveedor: null,
      },
    ],
  });
  const lista = await apiGet<Material[]>("/materiales");
  const todos = lista.ok ? materialOptions(lista.data) : [];
  if (created.ok) {
    const option = todos.find(
      (m) => m.codigo === created.data.materiales_nuevos[0],
    );
    if (option) return { ok: true, option };
  } else if (created.status === 409) {
    const wanted = nombre.toLowerCase();
    const option = todos.find(
      (m) => m.label.replace(/\s+/g, " ").trim().toLowerCase() === wanted,
    );
    if (option) return { ok: true, option };
  }
  return {
    ok: false,
    message: created.ok
      ? "Se creó el material pero no se pudo leer; recargue la página."
      : created.message,
  };
}
