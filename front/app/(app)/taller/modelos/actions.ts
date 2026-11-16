"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiGet, apiPost, apiPostForm, apiPut } from "@/lib/api";
import { armarLineas, type FilaHoja } from "@/lib/formularios";
import { SIZES } from "@/lib/modelos";
import { canFillFormularios } from "@/lib/permissions";
import { collapseSpaces } from "@/lib/productos";
import { getSession } from "@/lib/session";
import type { AltaModelo, FormularioDetalle } from "@/lib/types";
import {
  denyUnlessAdmin,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";
import { fotoHint } from "../../productos/modelos/[codigo]/foto-limites";

/**
 * Admin and taller work on the sheet of a model. The page already hides the screens from the other roles, but anyone can
 * post to a server action, so the role is checked again here; the backend checks it a third time (403).
 */
async function denyUnlessFiller(): Promise<FormState | null> {
  const session = await getSession();
  if (!session) redirect("/login");
  if (!canFillFormularios(session.user.role)) {
    return error("No tenés permiso para esta acción.");
  }
  return null;
}

const sheetHref = (codigo: string, query = "") =>
  `/taller/modelos/${encodeURIComponent(codigo)}${query}`;

/**
 * Creates the model (name, category, size, notes) and then uploads its photo. The model is created FIRST and the photo goes
 * in a second request: when the photo fails the model already exists, so we land on its sheet with a notice instead of
 * losing what the person typed. The category must already exist (only the admin creates categories).
 */
export async function crearModelo(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessFiller();
  if (denied) return denied;

  const nombre = collapseSpaces(text(formData, "nombre"));
  const categoria = text(formData, "categoria");
  const tamano = text(formData, "tamano");
  if (!nombre) return error("Escribí el nombre del modelo.");
  if (!categoria) return error("Elegí la categoría.");
  if (tamano && !SIZES.some((item) => item.value === tamano)) {
    return error("El tamaño no es válido.");
  }

  // The photo is checked before anything is created: a refused file must not leave a half-made model.
  const archivo = formData.get("foto");
  const foto = archivo instanceof File && archivo.size > 0 ? archivo : null;
  if (foto) {
    const hint = fotoHint(foto);
    if (hint) return error(`No se puede subir esta foto: ${hint}.`);
  }

  const creado = await apiPost<AltaModelo>("/productos/nuevo", {
    nombre,
    categoria,
    tamano: tamano || null,
    nota: optional(formData, "nota"),
  });
  if (!creado.ok) {
    return fromFailure(creado, {
      409: "Ya hay un modelo con ese nombre: agregá algo que lo distinga.",
    });
  }

  let fotoFallo = false;
  if (foto) {
    const body = new FormData();
    body.append("archivo", foto, foto.name);
    const subida = await apiPostForm(
      `/modelos/${encodeURIComponent(creado.data.modelo)}/foto`,
      body,
    );
    fotoFallo = !subida.ok;
  }
  redirect(sheetHref(creado.data.formulario, fotoFallo ? "?foto=error" : ""));
}

type Guardado =
  | { ok: true; hoja: FormularioDetalle }
  | { ok: false; state: FormState };

/** Saves the rows of the sheet. The article and the note are read fresh: the taller may not change them, it only sends them back. */
async function guardarFilas(
  codigo: string,
  filas: FilaHoja[],
): Promise<Guardado> {
  if (!Array.isArray(filas)) {
    return { ok: false, state: error("No hay filas para guardar.") };
  }
  const armadas = armarLineas(filas);
  if (!armadas.ok) return { ok: false, state: error(armadas.message) };

  const actual = await apiGet<FormularioDetalle>(
    `/formularios/${encodeURIComponent(codigo)}`,
  );
  if (!actual.ok) return { ok: false, state: fromFailure(actual) };

  const guardada = await apiPut<FormularioDetalle>(
    `/formularios/${encodeURIComponent(codigo)}`,
    {
      articulo: actual.data.articulo,
      nota: actual.data.nota,
      lineas: armadas.lineas,
    },
  );
  if (!guardada.ok) {
    return {
      ok: false,
      state: fromFailure(guardada, {
        409: "La hoja ya no se puede modificar. Actualizá la página.",
      }),
    };
  }
  return { ok: true, hoja: guardada.data };
}

export async function guardarHoja(
  codigo: string,
  filas: FilaHoja[],
): Promise<FormState> {
  const denied = await denyUnlessFiller();
  if (denied) return denied;
  const guardado = await guardarFilas(codigo, filas);
  if (!guardado.ok) return guardado.state;
  refresh();
  return ok("Hoja guardada.");
}

/** Saves what is on screen and then completes the sheet (it goes to the admin; the taller cannot edit it again). */
export async function completarHoja(
  codigo: string,
  filas: FilaHoja[],
): Promise<FormState> {
  const denied = await denyUnlessFiller();
  if (denied) return denied;
  const guardado = await guardarFilas(codigo, filas);
  if (!guardado.ok) return guardado.state;

  const completada = await apiPost<FormularioDetalle>(
    `/formularios/${encodeURIComponent(codigo)}/completar`,
    {},
  );
  if (!completada.ok) {
    return fromFailure(completada, {
      409: "La hoja ya no se puede completar. Actualizá la página.",
    });
  }
  refresh();
  return ok("Hoja completada: quedó en revisión del administrador.");
}

/** Admin only: the measures and supplies of the sheet become the recipe of the model. */
export async function validarHoja(codigo: string): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;
  const validada = await apiPost<FormularioDetalle>(
    `/formularios/${encodeURIComponent(codigo)}/validar`,
    {},
  );
  if (!validada.ok) return fromFailure(validada);
  refresh();
  const sinMaterial = validada.data.sin_material ?? [];
  return {
    ...ok("Hoja validada: las medidas pasaron al modelo."),
    avisos:
      sinMaterial.length > 0
        ? [
            `No se guardaron como insumos porque no coinciden con ningún material: ${sinMaterial.join(", ")}.`,
          ]
        : [],
  };
}

/** Admin only: sends the sheet back to the taller with a comment it reads on top of the sheet. */
export async function devolverHoja(
  codigo: string,
  comentario: string,
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;
  const texto = typeof comentario === "string" ? comentario.trim() : "";
  if (!texto) {
    return error("Escribí el comentario de revisión para devolver la hoja.");
  }
  const devuelta = await apiPost<FormularioDetalle>(
    `/formularios/${encodeURIComponent(codigo)}/devolver`,
    { comentario: texto },
  );
  if (!devuelta.ok) return fromFailure(devuelta);
  refresh();
  return ok("Hoja devuelta al taller con tu comentario.");
}
