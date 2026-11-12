import { Field, inputClass } from "@/components/form";
import { CONSUMPTION_FIELDS, ORIGINS } from "@/lib/modelos";
import type { ModeloDetalle } from "@/lib/types";

export type ForroOption = { codigo: string; label: string };

/**
 * The consumption inputs shared by "Nuevo modelo" and "Editar consumos". Uncontrolled: the
 * server action reads them; an empty field is missing data and a 0 means "no lleva".
 */
export function ConsumptionFields({
  prefix,
  forros,
  current,
}: {
  prefix: string;
  forros: ForroOption[];
  current?: ModeloDetalle;
}) {
  return (
    <>
      <p className="text-sm text-muted">
        Vacío es dato faltante; 0 significa que el modelo no lleva ese insumo.
        Use coma o punto para los decimales.
      </p>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {CONSUMPTION_FIELDS.map((field) => (
          <Field
            key={field.name}
            id={`${prefix}-${field.name}`}
            label={`${field.label} (${field.unit})`}
          >
            <input
              id={`${prefix}-${field.name}`}
              name={field.name}
              required={field.required}
              inputMode="decimal"
              autoComplete="off"
              defaultValue={current?.[field.name] ?? ""}
              className={inputClass}
            />
          </Field>
        ))}
        <Field
          id={`${prefix}-forro`}
          label="Forro (material)"
          hint="Solo forros que se pueden cotizar."
        >
          <select
            id={`${prefix}-forro`}
            name="forro"
            defaultValue={current?.forro ?? ""}
            aria-describedby={`${prefix}-forro-hint`}
            className={inputClass}
          >
            <option value="">Sin forro</option>
            {forros.map((forro) => (
              <option key={forro.codigo} value={forro.codigo}>
                {forro.label}
              </option>
            ))}
          </select>
        </Field>
        <Field id={`${prefix}-origen`} label="Origen de los consumos">
          <select
            id={`${prefix}-origen`}
            name="origen_de_los_consumos"
            required
            defaultValue={current?.origen_de_los_consumos ?? ""}
            className={inputClass}
          >
            <option value="" disabled>
              Elegir…
            </option>
            {ORIGINS.map((origin) => (
              <option key={origin.value} value={origin.value}>
                {origin.label}
              </option>
            ))}
          </select>
        </Field>
      </div>
    </>
  );
}
