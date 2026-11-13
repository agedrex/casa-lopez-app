import {
  Card,
  Notice,
  numClass,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import {
  formatArs,
  formatMoney,
  formatQuantity,
  formatUsd,
  stageLabel,
} from "@/lib/format";
import { CONSUMPTION_FIELDS } from "@/lib/modelos";
import type { Material, ModeloDetalle } from "@/lib/types";
import { ConsumosForm } from "./[codigo]/modelo-forms";
import type { ForroOption } from "./consumption-fields";

// Pieces of the model sheet shared by /productos/modelos/[codigo] and the "Modelo" block of the
// product sheet, so the consumptions are shown and edited the same way in both places.

function display(
  field: (typeof CONSUMPTION_FIELDS)[number],
  value: string | null,
) {
  if (value === null) return "Falta el dato";
  if (field.unit === "USD") return formatUsd(value);
  if (field.unit === "ARS") return formatArs(value);
  return `${formatQuantity(value)} ${field.unit}`;
}

/** Quotable linings a model may use; empty if the materials cannot be loaded. */
export async function loadForros(): Promise<ForroOption[]> {
  const materiales = await apiGet<Material[]>("/materiales");
  return materiales.ok
    ? materiales.data
        .filter((m) => m.etapa === "FORRO" && m.cotizable)
        .map((m) => ({ codigo: m.codigo, label: `${m.codigo} · ${m.nombre}` }))
    : [];
}

export function ConsumosTable({ modelo }: { modelo: ModeloDetalle }) {
  return (
    <>
      <TableWrap>
        <table className={tableClass}>
          <thead>
            <tr>
              <th className={thClass}>Insumo</th>
              <th className={`${thClass} ${numClass}`}>Por unidad</th>
            </tr>
          </thead>
          <tbody>
            {CONSUMPTION_FIELDS.map((field) => (
              <tr key={field.name}>
                <td className={tdClass}>{field.label}</td>
                <td className={`${tdClass} ${numClass}`}>
                  {display(field, modelo[field.name])}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      <p className="mt-2 text-xs text-muted">
        &quot;Falta el dato&quot; es un consumo sin cargar; 0 significa que el
        modelo no lleva ese insumo.
      </p>
      <InsumosTable insumos={modelo.insumos} />
    </>
  );
}

function unitLabel(unit: string): string {
  return unit === "m2" ? "m²" : unit;
}

/** Supplies the model carries per unit (from its validated consumption sheet); nothing is shown when there are none. */
function InsumosTable({ insumos }: { insumos: ModeloDetalle["insumos"] }) {
  if (insumos.length === 0) return null;
  return (
    <div className="mt-6">
      <h3 className="mb-2 text-sm font-bold text-ink-soft">
        Insumos por unidad
      </h3>
      <TableWrap>
        <table className={tableClass}>
          <thead>
            <tr>
              <th className={thClass}>Material</th>
              <th className={thClass}>Etapa</th>
              <th className={`${thClass} ${numClass}`}>Cantidad</th>
              <th className={`${thClass} ${numClass}`}>Precio unitario</th>
            </tr>
          </thead>
          <tbody>
            {insumos.map((insumo) => (
              <tr key={insumo.codigo}>
                <td className={tdClass}>
                  {insumo.nombre}
                  <span className="ml-2 text-xs text-muted">
                    {insumo.material}
                  </span>
                </td>
                <td className={tdClass}>{stageLabel(insumo.etapa)}</td>
                <td className={`${tdClass} ${numClass}`}>
                  {formatQuantity(insumo.cantidad_por_unidad)}{" "}
                  {unitLabel(insumo.unidad_de_consumo)}
                </td>
                <td className={`${tdClass} ${numClass}`}>
                  {insumo.precio_unitario !== null && insumo.moneda !== null
                    ? formatMoney(insumo.precio_unitario, insumo.moneda)
                    : "sin precio"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
    </div>
  );
}

export function EditarConsumos({
  modelo,
  forros,
}: {
  modelo: ModeloDetalle;
  forros: ForroOption[];
}) {
  return (
    <Card>
      <details>
        <summary className="cursor-pointer text-sm underline decoration-gold underline-offset-4">
          Cambiar los consumos de este modelo
        </summary>
        <div className="mt-5 space-y-5">
          <Notice title="Esto cambia el costo de los productos del modelo">
            Guardar quita la marca de validado y los {modelo.productos}{" "}
            productos que lo usan se costean con los valores nuevos. Antes de
            guardar se muestran los valores anteriores y los nuevos.
          </Notice>
          <ConsumosForm modelo={modelo} forros={forros} />
        </div>
      </details>
    </Card>
  );
}
