import "server-only";
import { error, type FormState } from "./action-state";
import { apiGet, apiPost } from "./api";
import type { ItemCatalogo } from "./types";
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
    return { ok: false, state: error(`Escriba el nombre de ${noun}.`) };
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
