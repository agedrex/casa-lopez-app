"use client";

import { FormFeedback, PrimaryButton } from "@/components/form";
import { Card, SectionTitle } from "@/components/ui";
import { lotStateLabel } from "@/lib/format";
import { siguienteEstadoDelTaller } from "@/lib/lote-estados";
import { useActionForm } from "@/lib/use-action-form";
import { avanzarEstado } from "./avanzar-actions";

/**
 * What the taller does with a lot: one big button that moves it to the next state. The state it is in and the one it
 * will pass to are in the text, so a wrong tap is hard. After LISTA the admin closes it (it needs the delivery date).
 */
export function AvanzarEstado({
  codigo,
  estado,
}: {
  codigo: string;
  estado: string;
}) {
  const siguiente = siguienteEstadoDelTaller(estado);
  const { state, pending, formKey, onSubmit } = useActionForm(
    avanzarEstado.bind(null, codigo),
  );
  if (estado === "CERRADA") return null;
  return (
    <section aria-label="Avanzar el lote">
      <SectionTitle>Avanzar el lote</SectionTitle>
      <Card>
        {siguiente ? (
          <form key={formKey} onSubmit={onSubmit} className="space-y-4">
            <p className="text-base">
              Ahora está <strong>{lotStateLabel(estado)}</strong>. Cuando
              termines esa etapa, pasalo a{" "}
              <strong>{lotStateLabel(siguiente)}</strong>.
            </p>
            <FormFeedback state={state} />
            <PrimaryButton pending={pending}>
              {pending ? "Guardando…" : `Pasar a ${lotStateLabel(siguiente)}`}
            </PrimaryButton>
          </form>
        ) : (
          <p className="text-base">
            El lote está <strong>{lotStateLabel(estado)}</strong>. Lo cierra el
            administrador cuando se entrega.
          </p>
        )}
      </Card>
    </section>
  );
}
