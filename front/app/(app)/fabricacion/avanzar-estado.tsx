"use client";

import { useEffect, useState, useTransition } from "react";
import { ConfirmForm } from "@/components/confirm-form";
import { FormFeedback } from "@/components/form";
import { Card, SectionTitle } from "@/components/ui";
import { type FormState, IDLE } from "@/lib/action-state";
import { lotStateLabel } from "@/lib/format";
import { msParaDeshacer, siguienteEstadoDelTaller } from "@/lib/lote-estados";
import { avanzarEstado, deshacerEstado } from "./avanzar-actions";

/**
 * What the taller does with a lot: one big button that moves it to the next state. It asks once ("¿Confirmás?")
 * before saving, so a wrong tap is cheap. After LISTA the admin closes it (it needs the delivery date).
 * After a successful advance a "Deshacer" button shows for ~10 s (client timer): it takes the lot back one state
 * through the API, which has the last word (same user, 10 minutes, no leather cut yet).
 */
export function AvanzarEstado({
  codigo,
  estado,
}: {
  codigo: string;
  estado: string;
}) {
  const siguiente = siguienteEstadoDelTaller(estado);
  const [avanzadoEn, setAvanzadoEn] = useState<number | null>(null);
  const [deshecho, setDeshecho] = useState<FormState>(IDLE);
  // Bumped after an undo so the advance form remounts and drops its own "Listo" message (only one message at a time).
  const [vuelta, setVuelta] = useState(0);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    if (avanzadoEn === null) return;
    const timer = setTimeout(
      () => setAvanzadoEn(null),
      msParaDeshacer(avanzadoEn, Date.now()),
    );
    return () => clearTimeout(timer);
  }, [avanzadoEn]);

  async function avanzar(
    previous: FormState,
    formData: FormData,
  ): Promise<FormState> {
    const result = await avanzarEstado(codigo, previous, formData);
    setDeshecho(IDLE);
    if (result.status === "ok") setAvanzadoEn(Date.now());
    return result;
  }

  function deshacer() {
    startTransition(async () => {
      const result = await deshacerEstado(codigo);
      setAvanzadoEn(null);
      setDeshecho(result);
      if (result.status === "ok") setVuelta((n) => n + 1);
    });
  }

  if (estado === "CERRADA") return null;
  return (
    <section aria-label="Avanzar el lote">
      <SectionTitle>Avanzar el lote</SectionTitle>
      <Card>
        {siguiente ? (
          <ConfirmForm
            key={vuelta}
            action={avanzar}
            summary={() => (
              <p className="text-base">
                El lote pasa de <strong>{lotStateLabel(estado)}</strong> a{" "}
                <strong>{lotStateLabel(siguiente)}</strong>. ¿Confirmás?
              </p>
            )}
            reviewLabel={`Pasar a ${lotStateLabel(siguiente)}`}
            confirmLabel={`Sí, pasar a ${lotStateLabel(siguiente)}`}
            pendingLabel="Guardando…"
          >
            <p className="text-base">
              Ahora está <strong>{lotStateLabel(estado)}</strong>. Cuando
              termines esa etapa, pasalo a{" "}
              <strong>{lotStateLabel(siguiente)}</strong>.
            </p>
          </ConfirmForm>
        ) : (
          <p className="text-base">
            El lote está <strong>{lotStateLabel(estado)}</strong>. Lo cierra el
            administrador cuando se entrega.
          </p>
        )}
        {avanzadoEn !== null ? (
          <button
            type="button"
            onClick={deshacer}
            disabled={pending}
            aria-busy={pending}
            className="mt-4 min-h-12 w-full rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white disabled:opacity-60 sm:min-h-0 sm:w-auto"
          >
            {pending ? "Deshaciendo…" : "Deshacer"}
          </button>
        ) : null}
        <FormFeedback state={deshecho} />
      </Card>
    </section>
  );
}
