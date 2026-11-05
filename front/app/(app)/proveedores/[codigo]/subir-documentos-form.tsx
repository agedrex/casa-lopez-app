"use client";

import { type FormEvent, useRef, useState, useTransition } from "react";
import { Field, inputClass, PrimaryButton } from "@/components/form";
import { error, type FormState } from "@/lib/action-state";
import { ACCEPT_ATTRIBUTE, DOCUMENT_TYPES, fileHint } from "@/lib/proveedores";
import { uploadDocumento } from "../actions";

type Result = { name: string; state: FormState };

/**
 * Several files, sent one per server action call so each one gets its own request body
 * (the API reads the text of every file before answering, so this can take a while).
 */
export function SubirDocumentosForm({ codigo }: { codigo: string }) {
  const formRef = useRef<HTMLFormElement>(null);
  const [pending, startTransition] = useTransition();
  const [results, setResults] = useState<Result[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const tipo = String(data.get("tipo") ?? "");
    const files = data
      .getAll("archivo")
      .filter((item): item is File => item instanceof File && item.size > 0);
    if (files.length === 0) {
      setResults([]);
      setMessage("Elija al menos un archivo para subir.");
      return;
    }
    setMessage(null);
    setResults([]);

    startTransition(async () => {
      const done: Result[] = [];
      for (const file of files) {
        let state: FormState;
        const hint = fileHint(file);
        if (hint) {
          state = error(`No se puede subir este archivo: ${hint}.`);
        } else {
          const one = new FormData();
          one.append("archivo", file, file.name);
          one.append("tipo", tipo);
          try {
            state = await uploadDocumento(codigo, one);
          } catch {
            state = error("No se pudo subir el archivo. Pruebe de nuevo.");
          }
        }
        done.push({ name: file.name, state });
        setResults([...done]);
      }
      if (done.every((item) => item.state.status === "ok")) {
        formRef.current?.reset();
      }
    });
  }

  return (
    <form ref={formRef} onSubmit={onSubmit} className="space-y-5">
      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="subir-tipo" label="Qué son estos archivos">
          <select
            id="subir-tipo"
            name="tipo"
            defaultValue="FACTURA"
            className={inputClass}
          >
            {DOCUMENT_TYPES.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </Field>
        <Field
          id="subir-archivo"
          label="Archivos"
          hint="Fotos (JPG, PNG, WebP) o PDF, de hasta 10 MB cada uno. Puede elegir varios."
        >
          <input
            id="subir-archivo"
            name="archivo"
            type="file"
            multiple
            accept={ACCEPT_ATTRIBUTE}
            aria-describedby="subir-archivo-hint"
            className={inputClass}
          />
        </Field>
      </div>
      <p className="text-sm text-muted">
        Al subir, la aplicación lee el texto del archivo para poder buscarlo.
        Eso puede tardar unos segundos por archivo. Lo que lee es solo una
        sugerencia: no cambia ningún precio.
      </p>
      <div aria-live="polite" aria-atomic="false" className="space-y-2">
        {message ? (
          <p
            role="alert"
            className="rounded-card border border-bordeaux/30 bg-bordeaux/5 px-4 py-3 text-sm font-bold text-bordeaux"
          >
            {message}
          </p>
        ) : null}
        {pending ? (
          <p className="text-sm text-muted">Subiendo y leyendo los archivos…</p>
        ) : null}
        {results.length > 0 ? (
          <ul className="space-y-1.5 text-sm">
            {results.map((result) => (
              <li
                key={result.name}
                className={
                  result.state.status === "ok"
                    ? "text-ink-soft"
                    : "text-bordeaux"
                }
              >
                <span className="font-bold">{result.name}:</span>{" "}
                {result.state.message}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <PrimaryButton pending={pending}>
        {pending ? "Subiendo…" : "Subir archivos"}
      </PrimaryButton>
    </form>
  );
}
