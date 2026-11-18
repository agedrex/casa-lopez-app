"use client";

import { ConfirmForm } from "@/components/confirm-form";
import { Card, SectionTitle } from "@/components/ui";
import { lotStateLabel } from "@/lib/format";
import { siguienteEstadoDelTaller } from "@/lib/lote-estados";
import { avanzarEstado } from "./avanzar-actions";

/**
 * What the taller does with a lot: one big button that moves it to the next state. It asks once ("¿Confirmás?")
 * before saving, so a wrong tap is cheap. After LISTA the admin closes it (it needs the delivery date).
 * There is no "Deshacer": see avanzar-actions.ts.
 */
export function AvanzarEstado({
  codigo,
  estado,
}: {
  codigo: string;
  estado: string;
}) {
  const siguiente = siguienteEstadoDelTaller(estado);
  if (estado === "CERRADA") return null;
  return (
    <section aria-label="Avanzar el lote">
      <SectionTitle>Avanzar el lote</SectionTitle>
      <Card>
        {siguiente ? (
          <ConfirmForm
            action={avanzarEstado.bind(null, codigo)}
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
      </Card>
    </section>
  );
}
