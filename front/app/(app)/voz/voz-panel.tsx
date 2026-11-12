"use client";

import { useActionState, useId, useState } from "react";
import { inputClass, PrimaryButton } from "@/components/form";
import { Card } from "@/components/ui";
import { useRecorder } from "@/lib/use-recorder";
import { INTERPRETAR_IDLE, VOZ_MAX_CHARS } from "@/lib/voz";
import { interpretarVoz } from "./actions";
import { ExampleList } from "./examples";
import { PropuestaCard } from "./propuesta-card";

const NOT_CONFIGURED =
  "El módulo de voz no está configurado: falta la clave del modelo. Pídale a un administrador que cargue AI_GATEWAY_API_KEY en el servicio del backend.";

/**
 * Text box, local audio recorder, and the proposal that comes back.
 * Nothing is saved from here: the card asks for an explicit confirmation.
 */
export function VozPanel({
  configured,
  initialText = "",
}: {
  configured: boolean;
  /** Text dictated from the header microphone; the person reviews it before interpreting. */
  initialText?: string;
}) {
  const [text, setText] = useState(initialText);
  const [state, dispatch, pending] = useActionState(
    interpretarVoz,
    INTERPRETAR_IDLE,
  );
  const recorder = useRecorder();
  const textId = useId();
  const countId = `${textId}-count`;
  const clock = `${String(Math.floor(recorder.seconds / 60)).padStart(2, "0")}:${String(recorder.seconds % 60).padStart(2, "0")}`;

  const recording =
    recorder.state === "recording" || recorder.state === "paused";

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

      <Card className="text-center">
        {/* One toggle button; the red dot and label make it obvious the mic is live. */}
        <button
          type="button"
          onClick={() =>
            recorder.state === "recording" || recorder.state === "paused"
              ? recorder.stop()
              : void recorder.start()
          }
          disabled={!configured || recorder.state === "requesting"}
          aria-pressed={recording}
          className={`min-h-14 w-full rounded-card px-5 py-3 text-base disabled:opacity-40 sm:w-auto sm:min-w-56 ${
            recording ? "bg-bordeaux text-white" : "bg-ink text-white"
          }`}
        >
          {recording
            ? "Detener grabación"
            : recorder.state === "requesting"
              ? "Pidiendo permiso…"
              : "Grabar"}
        </button>
        <p
          className="mt-3 flex items-center justify-center gap-2 text-sm text-muted"
          aria-live="polite"
        >
          {recording ? (
            <>
              <span
                aria-hidden="true"
                className="inline-block size-2.5 rounded-full bg-bordeaux"
              />
              <span>Grabando voz</span>
              <span role="timer" className="tabular-nums">
                {clock}
              </span>
            </>
          ) : (
            "Micrófono apagado"
          )}
        </p>
        {recorder.error ? (
          <p role="alert" className="mt-4 text-sm text-bordeaux">
            {recorder.error}
          </p>
        ) : null}
        {recorder.audioUrl ? (
          <div className="mt-5">
            <p className="mb-2 text-sm text-muted">
              Grabación local, solo en esta pestaña.
            </p>
            {/* This local recording has no transcript until transcription is connected. */}
            {/* biome-ignore lint/a11y/useMediaCaption: Captions cannot be generated without sending audio or adding speech recognition. */}
            <audio
              controls
              src={recorder.audioUrl}
              className="mx-auto w-full max-w-sm"
              aria-label="Escuchar grabación local"
            />
          </div>
        ) : null}
        <p className="mt-4 text-sm text-muted">
          El audio no sale de tu teléfono. Todavía no se transcribe: escribí el
          pedido abajo para interpretarlo.
        </p>
      </Card>

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
            aria-describedby={countId}
            placeholder="Por ejemplo: El dólar vendedor hoy está a 1480"
            className={inputClass}
          />
          <p id={countId} className="mt-1 text-xs text-muted">
            {text.length} de {VOZ_MAX_CHARS} caracteres. Puede corregir el texto
            antes de interpretarlo.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <PrimaryButton pending={!canInterpret}>
            {pending ? "Interpretando…" : "Interpretar"}
          </PrimaryButton>
        </div>

        <output className="block min-h-5 text-sm">
          {pending
            ? "Interpretando el pedido…"
            : "Revisá el texto antes de interpretar."}
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
