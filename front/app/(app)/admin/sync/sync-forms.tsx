"use client";

import { ConfirmForm } from "@/components/confirm-form";
import { simularSync, sincronizarSync } from "./actions";

export function SimularForm({ enCurso }: { enCurso: boolean }) {
  if (enCurso) {
    return (
      <Bloqueado
        id="simular"
        etiqueta="Simular (no escribe en Google)"
        motivo="Hay una sincronización en curso."
      />
    );
  }
  return (
    <ConfirmForm
      action={simularSync}
      reviewLabel="Simular (no escribe en Google)"
      confirmLabel="Confirmar simulación"
      pendingLabel="Simulando…"
      summary={() => (
        <p>
          Se van a armar todas las pestañas con los datos de hoy y contar sus
          filas. <strong>No se escribe nada en Google.</strong>
        </p>
      )}
    >
      <p className="text-sm text-muted">
        Sirve para comprobar que la vista se arma bien antes de escribir en el
        Sheet.
      </p>
    </ConfirmForm>
  );
}

export function SincronizarForm({
  configurado,
  faltantes,
  enCurso,
}: {
  configurado: boolean;
  faltantes: string[];
  enCurso: boolean;
}) {
  if (!configurado) {
    return (
      <Bloqueado
        id="sincronizar"
        etiqueta="Sincronizar ahora"
        motivo={`Falta configurar ${faltantes.join(" y ")} en el servicio del backend.`}
      />
    );
  }
  if (enCurso) {
    return (
      <Bloqueado
        id="sincronizar"
        etiqueta="Sincronizar ahora"
        motivo="Hay una sincronización en curso."
      />
    );
  }
  return (
    <ConfirmForm
      action={sincronizarSync}
      reviewLabel="Sincronizar ahora"
      confirmLabel="Confirmar y escribir en Google"
      pendingLabel="Sincronizando…"
      summary={() => (
        <p>
          Se va a <strong>reemplazar el contenido</strong> de las pestañas de la
          app en el Google Sheet. Lo que alguien haya escrito en esas pestañas
          se pierde. Las demás pestañas del Sheet no se tocan.
        </p>
      )}
    >
      <p className="text-sm text-muted">
        Escribe en Google. Las cuentas y los costos se calculan en la app; el
        Sheet solo los muestra.
      </p>
    </ConfirmForm>
  );
}

/** A disabled button that says why, so the reason is read together with the button. */
function Bloqueado({
  id,
  etiqueta,
  motivo,
}: {
  id: string;
  etiqueta: string;
  motivo: string;
}) {
  return (
    <div className="space-y-2">
      <button
        type="button"
        disabled
        aria-describedby={`${id}-bloqueado`}
        className="cursor-not-allowed rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm opacity-60"
      >
        {etiqueta}
      </button>
      <p id={`${id}-bloqueado`} className="text-sm text-muted">
        {motivo}
      </p>
    </div>
  );
}
