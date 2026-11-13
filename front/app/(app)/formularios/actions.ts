"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost, apiPut } from "@/lib/api";
import { parseLineas } from "@/lib/formulario";
import type { Formulario } from "@/lib/types";
import {
  denyUnlessFormularioWorker,
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

// Who may do what is decided three times: the screen offers the buttons by role and state (accionesDe), the
// action below checks the role again, and the backend answers 403 / 409 for anything else.
const ACCIONES_ADMIN = ["enviar", "devolver", "validar"];
const ACCIONES = ["guardar", "completar", ...ACCIONES_ADMIN];

const HECHO: Record<string, string> = {
  guardar: "Cambios guardados.",
  enviar: "Formulario enviado al taller.",
  completar:
    "Formulario completado: queda para que lo revise el administrador.",
  devolver: "Formulario devuelto al taller con tu comentario.",
  validar: "Formulario validado.",
};

const BY_STATUS = {
  403: "No tiene permiso para esta acción.",
  404: "No encontramos ese formulario.",
};

export async function crearFormulario(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const articulo = text(formData, "articulo");
  if (!articulo) return error("Escribí el nombre o el código del artículo.");

  const result = await apiPost<Formulario>("/formularios", {
    articulo,
    taller: optional(formData, "taller"),
    producto: optional(formData, "producto")?.toUpperCase() ?? null,
    nota: null,
  });
  if (!result.ok) return fromFailure(result, BY_STATUS);
  redirect(`/formularios/${encodeURIComponent(result.data.codigo)}`);
}

/**
 * One server action for every button of the sheet (`accion`): the rows typed so far are saved first when they
 * changed (or when the button is "Guardar"), then the state change runs. So "Completar" never loses what the
 * taller just typed.
 */
export async function trabajarFormulario(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const accion = text(formData, "accion");
  if (!ACCIONES.includes(accion)) return error("Acción desconocida.");
  const denied = ACCIONES_ADMIN.includes(accion)
    ? await denyUnlessWriter()
    : await denyUnlessFormularioWorker();
  if (denied) return denied;

  const base = `/formularios/${encodeURIComponent(codigo)}`;
  const comentario = text(formData, "comentario");
  if (accion === "devolver" && !comentario) {
    return error(
      "Escribí el comentario para devolver el formulario al taller.",
    );
  }

  let guardado = false;
  if (accion === "guardar" || text(formData, "dirty") === "1") {
    const articulo = text(formData, "articulo");
    if (!articulo) return error("Escribí el nombre o el código del artículo.");
    const lineas = parseLineas(text(formData, "lineas"));
    if (!lineas.ok) return error(lineas.message);
    const saved = await apiPut<Formulario>(base, {
      articulo,
      nota: optional(formData, "nota"),
      lineas: lineas.lineas,
    });
    if (!saved.ok) return fromFailure(saved, BY_STATUS);
    guardado = true;
  }
  if (accion === "guardar") {
    refresh();
    return ok(HECHO.guardar);
  }

  const moved = await apiPost<Formulario>(
    `${base}/${accion}`,
    accion === "devolver" ? { comentario } : {},
  );
  if (guardado) refresh();
  if (!moved.ok) {
    const failure = fromFailure(moved, BY_STATUS);
    return guardado
      ? error(
          `Se guardaron los cambios, pero no se pudo continuar: ${failure.message}`,
        )
      : failure;
  }
  refresh();
  const sinMaterial = moved.data.sin_material ?? [];
  if (accion === "validar" && sinMaterial.length > 0) {
    // The sheet leaves edit mode once validated, so a form state would be lost: carry the warning in the URL.
    const params = new URLSearchParams();
    for (const nombre of sinMaterial) params.append("sin_material", nombre);
    redirect(`${base}?${params.toString()}`);
  }
  return ok(HECHO[accion]);
}

export async function duplicarFormulario(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const articulo = text(formData, "articulo");
  if (!articulo) return error("Escribí el artículo del formulario nuevo.");

  const result = await apiPost<Formulario>(
    `/formularios/${encodeURIComponent(codigo)}/duplicar`,
    { articulo },
  );
  if (!result.ok) return fromFailure(result, BY_STATUS);
  redirect(`/formularios/${encodeURIComponent(result.data.codigo)}`);
}
