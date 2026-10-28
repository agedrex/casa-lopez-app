"use client";

import { ConfirmForm } from "@/components/confirm-form";
import { FormFeedback, SecondaryButton } from "@/components/form";
import { sameDecimalText } from "@/lib/format";
import { CONSUMPTION_FIELDS, originLabel } from "@/lib/modelos";
import type { ModeloDetalle } from "@/lib/types";
import { useActionForm } from "@/lib/use-action-form";
import { setValidado, updateConsumos } from "../actions";
import { ConsumptionFields, type ForroOption } from "../consumption-fields";

export function ValidadoForm({
  codigo,
  validado,
}: {
  codigo: string;
  validado: boolean;
}) {
  const { state, pending, onSubmit } = useActionForm(
    setValidado.bind(null, codigo, !validado),
  );
  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <p className="text-sm text-muted">
        {validado
          ? "Una persona confirmó estos consumos. Quitar la marca los vuelve a poner en revisión."
          : "Marque el modelo como validado cuando una persona confirme que sus consumos son razonables. La aplicación nunca lo hace sola."}
      </p>
      <FormFeedback state={state} />
      <SecondaryButton pending={pending}>
        {pending
          ? "Guardando…"
          : validado
            ? "Quitar la validación"
            : "Marcar como validado"}
      </SecondaryButton>
    </form>
  );
}

export function ConsumosForm({
  modelo,
  forros,
}: {
  modelo: ModeloDetalle;
  forros: ForroOption[];
}) {
  return (
    <ConfirmForm
      action={updateConsumos.bind(null, modelo.codigo)}
      reviewLabel="Revisar los cambios"
      confirmLabel="Confirmar y guardar"
      pendingLabel="Guardando…"
      summary={(data) => {
        const rows = CONSUMPTION_FIELDS.map((field) => ({
          label: `${field.label} (${field.unit})`,
          before: modelo[field.name] ?? "—",
          after: String(data.get(field.name) ?? "").trim() || "—",
          same: sameDecimalText(
            modelo[field.name],
            String(data.get(field.name) ?? ""),
          ),
        }));
        const forroAntes = modelo.forro ?? "Sin forro";
        const forroAhora = String(data.get("forro") ?? "") || "Sin forro";
        const origenAhora = String(data.get("origen_de_los_consumos") ?? "");
        return (
          <>
            <p className="font-bold text-ink-soft">
              Valores anteriores y nuevos de {modelo.nombre_del_modelo}
            </p>
            <table className="mt-2 w-full text-left text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-caps-sm text-muted">
                  <th className="py-1 pr-4 font-normal">Dato</th>
                  <th className="py-1 pr-4 font-normal">Antes</th>
                  <th className="py-1 font-normal">Ahora</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.label}
                    className={row.same ? "text-muted" : "font-bold"}
                  >
                    <td className="py-0.5 pr-4">{row.label}</td>
                    <td className="py-0.5 pr-4 tabular-nums">{row.before}</td>
                    <td className="py-0.5 tabular-nums">
                      {row.after}
                      {row.same ? "" : " (cambia)"}
                    </td>
                  </tr>
                ))}
                <tr
                  className={
                    forroAntes === forroAhora ? "text-muted" : "font-bold"
                  }
                >
                  <td className="py-0.5 pr-4">Forro</td>
                  <td className="py-0.5 pr-4">{forroAntes}</td>
                  <td className="py-0.5">{forroAhora}</td>
                </tr>
                <tr
                  className={
                    modelo.origen_de_los_consumos === origenAhora
                      ? "text-muted"
                      : "font-bold"
                  }
                >
                  <td className="py-0.5 pr-4">Origen</td>
                  <td className="py-0.5 pr-4">
                    {originLabel(modelo.origen_de_los_consumos)}
                  </td>
                  <td className="py-0.5">{originLabel(origenAhora)}</td>
                </tr>
              </tbody>
            </table>
            <p className="mt-2 text-muted">
              Al guardar, el modelo vuelve a quedar sin validar y los{" "}
              {modelo.productos} productos que lo usan se costean con estos
              valores desde ahora. Las cotizaciones ya guardadas no cambian. Los
              valores anteriores no se guardan.
            </p>
          </>
        );
      }}
    >
      <ConsumptionFields prefix="editar" forros={forros} current={modelo} />
    </ConfirmForm>
  );
}
