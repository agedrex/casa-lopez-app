"use client";

import { useEffect, useState } from "react";
import {
  Field,
  FormFeedback,
  inputClass,
  SecondaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { subirFoto } from "./foto-actions";
import { FOTO_ACCEPT } from "./foto-limites";

/**
 * The photo of the model and, for admin, the control to add a new one. Adding keeps the older photos in the database; the
 * newest is the one shown. The photo route is cached for a minute by the browser, so a successful upload changes the
 * `?v=` of the image to show the new one right away.
 */
export function FotoModelo({
  codigo,
  nombre,
  tieneFoto,
  puedeSubir,
}: {
  codigo: string;
  nombre: string;
  tieneFoto: boolean;
  puedeSubir: boolean;
}) {
  const [version, setVersion] = useState(0);
  const { state, pending, formKey, onSubmit } = useActionForm(
    subirFoto.bind(null, codigo),
  );
  useEffect(() => {
    if (state.status === "ok") setVersion(Date.now());
  }, [state]);

  const hayFoto = tieneFoto || version !== 0;
  const src = `/api/modelos/${encodeURIComponent(codigo)}/foto${version ? `?v=${version}` : ""}`;

  return (
    <div className="grid gap-6 sm:grid-cols-[minmax(0,20rem)_1fr]">
      <div className="flex min-h-48 items-center justify-center overflow-hidden rounded-card border border-line bg-paper-mid">
        {hayFoto ? (
          // biome-ignore lint/performance/noImgElement: the file comes from an authenticated same-origin route, not from a static asset that next/image could optimize.
          <img
            src={src}
            alt={`Foto del modelo ${nombre} (${codigo})`}
            className="max-h-80 w-full object-contain"
          />
        ) : (
          <p className="px-4 py-10 text-center text-sm text-muted">
            Este modelo todavía no tiene foto.
          </p>
        )}
      </div>
      {puedeSubir ? (
        <form key={formKey} onSubmit={onSubmit} className="space-y-3">
          <Field
            id="modelo-foto"
            label={hayFoto ? "Reemplazar la foto" : "Subir una foto"}
            hint="JPG, PNG o WebP, de hasta 5 MB."
          >
            <input
              id="modelo-foto"
              name="archivo"
              type="file"
              accept={FOTO_ACCEPT}
              aria-describedby="modelo-foto-hint"
              className={inputClass}
            />
          </Field>
          <FormFeedback state={state} />
          <SecondaryButton pending={pending}>
            {pending ? "Subiendo…" : hayFoto ? "Reemplazar foto" : "Subir foto"}
          </SecondaryButton>
        </form>
      ) : null}
    </div>
  );
}
