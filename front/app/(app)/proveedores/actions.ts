"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { error, type FormState, ok } from "@/lib/action-state";
import { apiPost, apiPostForm } from "@/lib/api";
import { parseDecimalInput } from "@/lib/format";
import { DOCUMENT_TYPES, fileHint } from "@/lib/proveedores";
import type { DocumentoProveedor, Proveedor } from "@/lib/types";
import {
  denyUnlessWriter,
  fromFailure,
  optional,
  text,
} from "@/lib/write-guard";

const CONFLICT_PROVEEDOR = "Ya hay un proveedor con ese nombre o con ese CUIT.";

function proveedorBody(formData: FormData) {
  return {
    nombre: text(formData, "nombre"),
    cuit: optional(formData, "cuit"),
    contacto: optional(formData, "contacto"),
    telefono: optional(formData, "telefono"),
    direccion: optional(formData, "direccion"),
    nota: optional(formData, "nota"),
  };
}

export async function createProveedor(
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const body = proveedorBody(formData);
  if (!body.nombre) return error("Indique el nombre del proveedor.");

  const result = await apiPost<Proveedor>("/proveedores", {
    codigo: optional(formData, "codigo"),
    ...body,
  });
  if (!result.ok) {
    return fromFailure(result, {
      409: `${CONFLICT_PROVEEDOR} Revise también el código si lo escribió.`,
    });
  }
  redirect(`/proveedores/${encodeURIComponent(result.data.codigo)}`);
}

export async function updateProveedor(
  codigo: string,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const body = proveedorBody(formData);
  if (!body.nombre) return error("Indique el nombre del proveedor.");

  const result = await apiPost<Proveedor>(
    `/proveedores/${encodeURIComponent(codigo)}`,
    body,
  );
  if (!result.ok) return fromFailure(result, { 409: CONFLICT_PROVEEDOR });
  refresh();
  return ok("Datos guardados.");
}

/** Deactivating hides nothing and deletes nothing: the documents stay with the supplier. */
export async function setProveedorActivo(
  codigo: string,
  activo: boolean,
  _previous: FormState,
  _formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const result = await apiPost<Proveedor>(
    `/proveedores/${encodeURIComponent(codigo)}/activo`,
    { activo },
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok(activo ? "Proveedor activado." : "Proveedor desactivado.");
}

/**
 * One file per call: the client sends several files one after the other, so the 12 MB body
 * limit of a server action is never shared between files. The API stores the file and
 * reads its text (OCR) before answering.
 */
export async function uploadDocumento(
  codigo: string,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const file = formData.get("archivo");
  if (!(file instanceof File) || file.size === 0) {
    return error("Elija un archivo para subir.");
  }
  const hint = fileHint(file);
  if (hint) return error(`No se puede subir este archivo: ${hint}.`);

  const tipo = text(formData, "tipo");
  if (!DOCUMENT_TYPES.some((item) => item.value === tipo)) {
    return error("Elija si es una factura, una imagen u otro documento.");
  }

  const body = new FormData();
  body.append("archivo", file, file.name);
  body.append("tipo", tipo);
  const result = await apiPostForm<DocumentoProveedor>(
    `/proveedores/${encodeURIComponent(codigo)}/documentos`,
    body,
  );
  if (!result.ok) {
    return fromFailure(result, {
      409: "Este archivo ya está cargado para este proveedor.",
      413: "El archivo supera los 10 MB.",
    });
  }
  refresh();
  return ok("Archivo subido.");
}

/** Only a person confirms number, date, total and currency; the OCR just suggests them. */
export async function confirmarDatos(
  id: number,
  _previous: FormState,
  formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const tipo = text(formData, "tipo");
  if (!DOCUMENT_TYPES.some((item) => item.value === tipo)) {
    return error("Elija el tipo de documento.");
  }
  const totalText = text(formData, "total");
  const total = totalText ? parseDecimalInput(totalText) : null;
  if (totalText && total === null) {
    return error("El total debe ser un número, por ejemplo 125000,50.");
  }
  const moneda = optional(formData, "moneda");
  if (total !== null && !moneda) return error("Elija la moneda del total.");

  const result = await apiPost<DocumentoProveedor>(
    `/documentos-proveedor/${id}/datos`,
    {
      tipo,
      numero: optional(formData, "numero"),
      fecha_documento: optional(formData, "fecha_documento"),
      total,
      moneda: total === null ? null : moneda,
    },
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok("Datos confirmados.");
}

export async function retryOcr(
  id: number,
  _previous: FormState,
  _formData: FormData,
): Promise<FormState> {
  const denied = await denyUnlessWriter();
  if (denied) return denied;

  const result = await apiPost<DocumentoProveedor>(
    `/documentos-proveedor/${id}/ocr`,
    {},
    60_000,
  );
  if (!result.ok) return fromFailure(result);
  refresh();
  return ok("Se volvió a leer el documento.");
}
