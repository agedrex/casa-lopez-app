"use client";

import { useEffect, useState } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import { SIZES } from "@/lib/modelos";
import { useActionForm } from "@/lib/use-action-form";
import {
  FOTO_ACCEPT,
  fotoHint,
} from "../../../productos/modelos/[codigo]/foto-limites";
import { crearModelo } from "../actions";

/**
 * "Nuevo modelo" for the taller: name, category (only the existing ones), size, notes and a photo. The ID of the model is made
 * by the app when it is saved. On success the action redirects to the sheet of the new model, where the consumptions and
 * herrajes are filled in with real data.
 */
export function NuevoModeloForm({ categorias }: { categorias: string[] }) {
  const { state, pending, onSubmit } = useActionForm(crearModelo);
  const [vista, setVista] = useState<string | null>(null);
  const [problema, setProblema] = useState<string | null>(null);

  // The preview is a temporary address of the chosen file: it is released when the file changes or the form goes away.
  useEffect(() => {
    return () => {
      if (vista) URL.revokeObjectURL(vista);
    };
  }, [vista]);

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <Field
        id="nuevo-nombre"
        label="Nombre del modelo"
        hint="Se guarda en MAYÚSCULAS y no puede repetirse: agregá algo que lo distinga. El ID (MOD-0000) lo genera la app al guardar."
      >
        <input
          id="nuevo-nombre"
          name="nombre"
          required
          maxLength={200}
          autoComplete="off"
          aria-describedby="nuevo-nombre-hint"
          className={`${inputClass} min-h-11 uppercase`}
        />
      </Field>
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="nuevo-categoria" label="Categoría">
          <select
            id="nuevo-categoria"
            name="categoria"
            required
            defaultValue=""
            className={`${inputClass} min-h-11`}
          >
            <option value="" disabled>
              Elegir…
            </option>
            {categorias.map((categoria) => (
              <option key={categoria} value={categoria}>
                {categoria}
              </option>
            ))}
          </select>
        </Field>
        <Field id="nuevo-tamano" label="Tamaño (opcional)">
          <select
            id="nuevo-tamano"
            name="tamano"
            defaultValue=""
            className={`${inputClass} min-h-11`}
          >
            <option value="">Sin tamaño</option>
            {SIZES.map((size) => (
              <option key={size.value} value={size.value}>
                {size.label}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field
        id="nuevo-foto"
        label="Foto (opcional)"
        hint="JPG, PNG o WebP, de hasta 5 MB. También la podés subir después, desde la hoja."
      >
        <input
          id="nuevo-foto"
          name="foto"
          type="file"
          accept={FOTO_ACCEPT}
          aria-describedby="nuevo-foto-hint"
          onChange={(event) => {
            const archivo = event.target.files?.[0];
            setProblema(archivo ? fotoHint(archivo) : null);
            setVista(
              archivo && !fotoHint(archivo)
                ? URL.createObjectURL(archivo)
                : null,
            );
          }}
          className={`${inputClass} min-h-11`}
        />
        {problema ? (
          <p role="alert" className="mt-2 text-sm text-bordeaux">
            No se puede subir esta foto: {problema}.
          </p>
        ) : null}
        {vista ? (
          // biome-ignore lint/performance/noImgElement: a local preview (blob address) of the file the person just chose; next/image cannot optimize it.
          <img
            src={vista}
            alt="Vista previa de la foto elegida"
            className="mt-3 max-h-60 rounded-card border border-line object-contain"
          />
        ) : null}
      </Field>
      <Field
        id="nuevo-nota"
        label="Notas del modelo (opcional)"
        hint="Medidas, materiales, detalles."
      >
        <textarea
          id="nuevo-nota"
          name="nota"
          rows={3}
          maxLength={2000}
          aria-describedby="nuevo-nota-hint"
          className={inputClass}
        />
      </Field>
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Creando…" : "Crear modelo y completar la hoja"}
      </PrimaryButton>
    </form>
  );
}
