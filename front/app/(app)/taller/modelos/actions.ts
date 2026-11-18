"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import { armarLineas, type FilaHoja } from "@/lib/formularios";
import { canFillFormularios } from "@/lib/permissions";
import { getSession } from "@/lib/session";
import type { FormularioDetalle } from "@/lib/types";
import { denyUnlessAdmin, fromFailure } from "@/lib/write-guard";

/**
 * Admin and taller work on the sheet of a model (only the admin creates models). The page already hides the screens from the other roles, but anyone can
 * post to a server action, so the role is checked again here; the backend checks it a third time (403). The article and the note
 * are read fresh and sent back as they are: this screen edits rows only.
 */
async function denyUnlessFiller(): Promise<FormState | null> {
  const session = await getSession();
  if (!session) redirect("/login");
  if (!canFillFormularios(session.user.role)) {
    return error("No tenés permiso para esta acción.");
  }
  return null;
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

/** Admin only: saves what is on screen and sends the sheet (a draft) to the workshop: "Enviar al taller". */
export async function enviarHojaAlTaller(
  codigo: string,
  filas: FilaHoja[],
): Promise<FormState> {
  const check = await denyUnlessAdmin();
  if (check.denied) return check.denied;
  const guardado = await guardarFilas(codigo, filas);
  if (!guardado.ok) return guardado.state;

  const enviada = await apiPost<FormularioDetalle>(
    `/formularios/${encodeURIComponent(codigo)}/enviar`,
    {},
  );
  if (!enviada.ok) {
    return fromFailure(enviada, {
      409: "La hoja ya no se puede enviar. Actualizá la página.",
    });
  }
  refresh();
  return ok("Hoja enviada al taller.");
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
  // The page lists the same rows for good (it reads them again from the validated sheet); this is the message of the moment.
  const noAplicadas = validada.data.no_aplicadas ?? [];
  return {
    ...ok("Hoja validada."),
    avisos: noAplicadas.map(
      (fila) => `No se aplicó al modelo «${fila.nombre}»: ${fila.motivo}`,
    ),
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
