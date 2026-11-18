import "server-only";
import { error, type FormState } from "./action-state";
import { apiGet, apiPost } from "./api";
import type { ItemCatalogo, Material, MaterialesLote, Taller } from "./types";
import { denyUnlessAdmin, fromFailure, optional, text } from "./write-guard";

export type CatalogChoice =
  | { ok: true; nombre: string | null }
  | { ok: false; state: FormState };

/**
 * Resolves a catalog `<select>` that also offers "create a new one" (colors and categories).
 *
 * - The select holds an existing name (or nothing): that value is returned as is.
 * - The select holds `sentinel`: the typed name (`newField`) is created first (POST `path`, admin
 *   only; the API generates the code) and the name it answers with is returned. If that name already
 *   exists (409) the existing item is used instead of failing the whole form.
 */
export async function resolveCatalogChoice(options: {
  formData: FormData;
  field: string;
  newField: string;
  sentinel: string;
  path: "/colores" | "/categorias";
  noun: string;
}): Promise<CatalogChoice> {
  const { formData, field, newField, sentinel, path, noun } = options;
  if (text(formData, field) !== sentinel) {
    return { ok: true, nombre: optional(formData, field) };
  }

  const check = await denyUnlessAdmin();
  if (check.denied) return { ok: false, state: check.denied };

  const nombre = text(formData, newField);
  if (!nombre) {
    return { ok: false, state: error(`Escribí el nombre de ${noun}.`) };
  }

  const created = await apiPost<ItemCatalogo>(path, { nombre, nota: null });
  if (created.ok) return { ok: true, nombre: created.data.nombre };
  if (created.status !== 409) {
    return { ok: false, state: fromFailure(created) };
  }

  // Already there: use the existing one (same name ignoring case and extra spaces).
  const wanted = nombre.replace(/\s+/g, " ").toLowerCase();
  const existing = await apiGet<ItemCatalogo[]>(path);
  const match = existing.ok
    ? existing.data.find(
        (item) =>
          item.nombre.replace(/\s+/g, " ").trim().toLowerCase() === wanted,
      )
    : undefined;
  if (match) return { ok: true, nombre: match.nombre };
  return { ok: false, state: fromFailure(created) };
}

const igual = (a: string, b: string) =>
  a.replace(/\s+/g, " ").trim().toLowerCase() ===
  b.replace(/\s+/g, " ").trim().toLowerCase();

export type CodigoChoice =
  | { ok: true; codigo: string | null }
  | { ok: false; state: FormState };

/**
 * A leather select that also offers "+ Crear cuero nuevo…": the material (stage CUERO, m², no price) is created first
 * and its code returned. A name that already exists (409) reuses the existing leather. Prices enter only by orders.
 */
export async function resolveCueroChoice(options: {
  formData: FormData;
  field: string;
  newField: string;
  sentinel: string;
}): Promise<CodigoChoice> {
  const { formData, field, newField, sentinel } = options;
  if (text(formData, field) !== sentinel) {
    return { ok: true, codigo: optional(formData, field) };
  }
  const check = await denyUnlessAdmin();
  if (check.denied) return { ok: false, state: check.denied };
  const nombre = text(formData, newField);
  if (!nombre) {
    return { ok: false, state: error("Escribí el nombre del cuero nuevo.") };
  }
  const created = await apiPost<MaterialesLote>("/materiales/lote", {
    cambios: [],
    nuevos: [
      {
        nombre,
        etapa: "CUERO",
        unidad_de_consumo: "m2",
        precio: null,
        moneda: null,
        proveedor: null,
      },
    ],
  });
  if (created.ok && created.data.materiales_nuevos[0]) {
    return { ok: true, codigo: created.data.materiales_nuevos[0] };
  }
  if (!created.ok && created.status === 409) {
    const existing = await apiGet<Material[]>("/materiales");
    const match = existing.ok
      ? existing.data.find(
          (m) => m.etapa === "CUERO" && igual(m.nombre, nombre),
        )
      : undefined;
    if (match) return { ok: true, codigo: match.codigo };
  }
  return {
    ok: false,
    state: created.ok
      ? error("No se pudo crear el cuero; intente de nuevo.")
      : fromFailure(created),
  };
}

/** The same for a workshop ("+ Crear taller nuevo…"): only the name is asked; the rest is completed later in Talleres. */
export async function resolveTallerChoice(options: {
  formData: FormData;
  field: string;
  newField: string;
  sentinel: string;
}): Promise<CodigoChoice> {
  const { formData, field, newField, sentinel } = options;
  if (text(formData, field) !== sentinel) {
    return { ok: true, codigo: optional(formData, field) };
  }
  const check = await denyUnlessAdmin();
  if (check.denied) return { ok: false, state: check.denied };
  const nombre = text(formData, newField);
  if (!nombre) {
    return { ok: false, state: error("Escribí el nombre del taller nuevo.") };
  }
  const created = await apiPost<{ codigo: string }>("/talleres", {
    nombre,
    cuit: null,
    telefono: null,
    direccion: null,
    contacto: null,
    nota: null,
  });
  if (created.ok) return { ok: true, codigo: created.data.codigo };
  if (created.status === 409) {
    const existing = await apiGet<Taller[]>("/talleres");
    const match = existing.ok
      ? existing.data.find((t) => igual(t.nombre, nombre))
      : undefined;
    if (match) return { ok: true, codigo: match.codigo };
  }
  return { ok: false, state: fromFailure(created) };
}
