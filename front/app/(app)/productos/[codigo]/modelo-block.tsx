import Link from "next/link";
import { Badge, Card, ErrorNotice, SectionTitle } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { originLabel, sizeLabel } from "@/lib/modelos";
import type { ModeloDetalle } from "@/lib/types";
import { ValidadoForm } from "../modelos/[codigo]/modelo-forms";
import {
  ConsumosTable,
  EditarConsumos,
  loadForros,
} from "../modelos/modelo-consumos";

const linkClass = "underline decoration-gold underline-offset-4";

/**
 * The model of the product with its consumptions per unit. Admin only: `/modelos` is closed to
 * the other roles, who already read the consumptions through the recipe of this sheet. The
 * forms are the ones of Administración > Modelos; a change reaches every product of the model.
 */
export async function ModeloBlock({ codigo }: { codigo: string }) {
  const [result, forros] = await Promise.all([
    apiGet<ModeloDetalle>(`/modelos/${encodeURIComponent(codigo)}`),
    loadForros(),
  ]);
  if (!result.ok) {
    return (
      <section id="modelo">
        <SectionTitle>Modelo</SectionTitle>
        <ErrorNotice
          title="No pudimos cargar el modelo."
          message={result.message}
        />
      </section>
    );
  }
  const modelo = result.data;
  const rows: [string, string][] = [
    ["Modelo", modelo.nombre_del_modelo],
    ["Categoría", modelo.categoria ?? "—"],
    ["Tamaño", sizeLabel(modelo.tamano)],
    ["Origen de los consumos", originLabel(modelo.origen_de_los_consumos)],
  ];
  return (
    <section id="modelo" className="space-y-6">
      <SectionTitle>Modelo</SectionTitle>
      <Card>
        <dl className="grid gap-x-8 gap-y-5 text-sm sm:grid-cols-2 lg:grid-cols-4">
          {rows.map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs uppercase tracking-caps-sm text-muted">
                {label}
              </dt>
              <dd className="mt-1">{value}</dd>
            </div>
          ))}
          <div>
            <dt className="text-xs uppercase tracking-caps-sm text-muted">
              Validación
            </dt>
            <dd className="mt-1">
              <Badge tone={modelo.validado ? "good" : "neutral"}>
                {modelo.validado ? "Validado" : "Sin validar"}
              </Badge>
            </dd>
          </div>
        </dl>
        <p className="mt-5 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted">
          <Link
            href={`/productos?q=${encodeURIComponent(modelo.codigo)}`}
            className={linkClass}
          >
            {modelo.productos === 1
              ? "1 producto usa este modelo"
              : `${modelo.productos} productos usan este modelo`}
          </Link>
          <Link
            href={`/productos/modelos/${encodeURIComponent(modelo.codigo)}`}
            className={linkClass}
          >
            Abrir en Administración
          </Link>
        </p>
      </Card>
      <div>
        <h3 className="mb-3 font-display text-lg">Consumos por unidad</h3>
        <ConsumosTable modelo={modelo} />
      </div>
      <Card>
        <ValidadoForm codigo={modelo.codigo} validado={modelo.validado} />
      </Card>
      <EditarConsumos modelo={modelo} forros={forros} />
    </section>
  );
}
