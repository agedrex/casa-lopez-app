"use client";

import { useActionState, useId, useState } from "react";
import { inputClass, PrimaryButton } from "@/components/form";
import { useDictation } from "@/lib/use-dictation";
import { INTERPRETAR_IDLE, VOZ_MAX_CHARS } from "@/lib/voz";
import { interpretarVoz } from "./actions";
import { ExampleList } from "./examples";
import { PropuestaCard } from "./propuesta-card";

const NOT_CONFIGURED =
  "El módulo de voz no está configurado: falta la clave del modelo. Pídale a un administrador que cargue ANTHROPIC_API_KEY en el servicio del backend.";

/**
 * Text box (always the fallback), push-to-talk dictation where the browser has it, and the proposal that comes back.
 * Nothing is saved from here: the card asks for an explicit confirmation.
 */
export function VozPanel({ configured }: { configured: boolean }) {
  const [text, setText] = useState("");
  const [state, dispatch, pending] = useActionState(
    interpretarVoz,
    INTERPRETAR_IDLE,
  );
  const dictation = useDictation(setText);
  const textId = useId();
  const micHelpId = `${textId}-mic`;
  const countId = `${textId}-count`;

  const trimmed = text.trim();
  const canInterpret = configured && trimmed.length > 0 && !pending;

  return (
    <div className="space-y-8">
      {configured ? null : (
        <div
          role="alert"
          className="rounded-card border border-blush-deep bg-blush/30 px-5 py-4 text-sm"
        >
          <p className="font-bold text-ink-soft">
            Módulo de voz sin configurar
          </p>
          <p className="mt-1 text-muted">{NOT_CONFIGURED}</p>
        </div>
      )}

      <form action={dispatch} className="space-y-4">
        <div>
          <label
            htmlFor={textId}
            className="mb-1.5 block text-xs uppercase tracking-caps-sm text-muted"
          >
            Qué quiere cargar
          </label>
          <textarea
            id={textId}
            name="texto"
            rows={3}
            maxLength={VOZ_MAX_CHARS}
            value={text}
            disabled={!configured}
            onChange={(event) => setText(event.target.value)}
            aria-describedby={`${countId} ${micHelpId}`}
            placeholder="Por ejemplo: El dólar vendedor hoy está a 1480"
            className={inputClass}
          />
          <p id={countId} className="mt-1 text-xs text-muted">
            {text.length} de {VOZ_MAX_CHARS} caracteres. Puede corregir el texto
            antes de interpretarlo.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {configured ? (
            <button
              type="button"
              onClick={() =>
                dictation.listening ? dictation.stop() : dictation.start(text)
              }
              disabled={!dictation.supported}
              aria-pressed={dictation.listening}
              aria-describedby={micHelpId}
              className="rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white disabled:cursor-not-allowed disabled:opacity-60 aria-pressed:bg-bordeaux aria-pressed:text-white"
            >
              {dictation.listening ? "Terminar de hablar" : "Hablar"}
            </button>
          ) : null}
          <PrimaryButton pending={!canInterpret}>
            {pending ? "Interpretando…" : "Interpretar"}
          </PrimaryButton>
        </div>

        <p id={micHelpId} className="text-sm text-muted">
          {!configured
            ? "El dictado se habilita cuando el módulo de voz está configurado."
            : dictation.supported
              ? "Toque «Hablar», diga el pedido y toque «Terminar de hablar». El texto aparece arriba y se puede corregir."
              : "Este navegador no permite dictar por voz (funciona en Chrome, Edge y Safari, con https). Escriba el pedido en el cuadro."}
        </p>
        <output className="block min-h-5 text-sm">
          {pending ? "Interpretando el pedido…" : dictation.status}
        </output>
      </form>

      <div aria-live="polite" aria-atomic="true">
        {state.status === "error" ? (
          <div className="rounded-card border border-bordeaux/30 bg-bordeaux/5 px-4 py-3 text-sm">
            <p className="font-bold text-bordeaux">{state.message}</p>
          </div>
        ) : null}
      </div>
      {state.status === "ok" && state.propuesta ? (
        <PropuestaCard key={state.id} propuesta={state.propuesta} />
      ) : null}

      <section aria-labelledby={`${textId}-ej`}>
        <h2 id={`${textId}-ej`} className="mb-3 text-xl">
          Ejemplos
        </h2>
        <ExampleList onPick={setText} />
      </section>
    </div>
  );
}
