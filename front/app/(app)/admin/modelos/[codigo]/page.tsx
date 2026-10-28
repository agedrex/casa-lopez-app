import type { Metadata } from "next";
import Link from "next/link";
import {
  Badge,
  Card,
  ErrorNotice,
  Notice,
  numClass,
  PageHeader,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatArs, formatQuantity, formatUsd } from "@/lib/format";
import { CONSUMPTION_FIELDS, originLabel, sizeLabel } from "@/lib/modelos";
import { requireRole } from "@/lib/session";
import type { Material, ModeloDetalle } from "@/lib/types";
import { ConsumosForm, ValidadoForm } from "./modelo-forms";

export const metadata: Metadata = { title: "Modelo" };

function BackLink() {
  return (
    <p className="mb-6 text-sm">
      <Link
        href="/admin/modelos"
        className="text-muted underline decoration-gold underline-offset-4"
      >
        ← Modelos
      </Link>
    </p>
  );
}

function decodeCode(raw: string): string | null {
  try {
    return decodeURIComponent(raw);
  } catch {
    return null;
  }
}

function display(
  field: (typeof CONSUMPTION_FIELDS)[number],
  value: string | null,
) {
  if (value === null) return "Falta el dato";
  if (field.unit === "USD") return formatUsd(value);
  if (field.unit === "ARS") return formatArs(value);
  return `${formatQuantity(value)} ${field.unit}`;
}

export default async function ModeloPage({
  params,
}: {
  params: Promise<{ codigo: string }>;
}) {
  await requireRole("admin");
  const code = decodeCode((await params).codigo);
  if (code === null) {
    return (
      <>
        <BackLink />
        <Notice tone="info" title="No encontramos ese modelo" />
      </>
    );
  }
  const [result, materiales] = await Promise.all([
    apiGet<ModeloDetalle>(`/modelos/${encodeURIComponent(code)}`),
    apiGet<Material[]>("/materiales"),
  ]);
  if (!result.ok) {
    return (
      <>
        <BackLink />
        {result.status === 404 ? (
          <Notice tone="info" title="No encontramos ese modelo">
            Revise el código o vuelva al listado de modelos.
          </Notice>
        ) : (
          <ErrorNotice message={result.message} />
        )}
      </>
    );
  }

  const modelo = result.data;
  const forros = materiales.ok
    ? materiales.data
        .filter((m) => m.etapa === "FORRO" && m.cotizable)
        .map((m) => ({ codigo: m.codigo, label: `${m.codigo} · ${m.nombre}` }))
    : [];

  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow={`Modelo ${modelo.codigo}`}
        title={modelo.nombre_del_modelo}
        actions={
          <Badge tone={modelo.validado ? "good" : "neutral"}>
            {modelo.validado ? "Validado" : "Sin validar"}
          </Badge>
        }
      />
      <div className="space-y-10">
        <section aria-label="Datos del modelo">
          <Card>
            <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <Datum label="Categoría" value={modelo.categoria} />
              <Datum label="Tamaño" value={sizeLabel(modelo.tamano)} />
              <Datum
                label="Origen de los consumos"
                value={originLabel(modelo.origen_de_los_consumos)}
              />
              <Datum
                label="Productos que lo usan"
                value={String(modelo.productos)}
              />
              <Datum label="Forro" value={modelo.forro} />
              <Datum
                label="En el Excel viejo"
                value={
                  modelo.modelo_excel_viejo
                    ? `Modelo ${modelo.modelo_excel_viejo}${
                        modelo.fila_excel_viejo
                          ? `, fila ${modelo.fila_excel_viejo}`
                          : ""
                      }`
                    : null
                }
              />
              <div className="sm:col-span-2">
                <Datum label="Nota" value={modelo.nota} />
              </div>
            </dl>
          </Card>
        </section>
        <section>
          <SectionTitle>Consumos por unidad</SectionTitle>
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
            &quot;Falta el dato&quot; es un consumo sin cargar; 0 significa que
            el modelo no lleva ese insumo.
          </p>
        </section>
        <section>
          <SectionTitle>Validación</SectionTitle>
          <Card>
            <ValidadoForm codigo={modelo.codigo} validado={modelo.validado} />
          </Card>
        </section>
        <section>
          <SectionTitle>Editar consumos</SectionTitle>
          <Card>
            <details>
              <summary className="cursor-pointer text-sm underline decoration-gold underline-offset-4">
                Cambiar los consumos de este modelo
              </summary>
              <div className="mt-5 space-y-5">
                <Notice title="Esto cambia el costo de los productos del modelo">
                  Guardar quita la marca de validado y los {modelo.productos}{" "}
                  productos que lo usan se costean con los valores nuevos. Antes
                  de guardar se muestran los valores anteriores y los nuevos.
                </Notice>
                <ConsumosForm modelo={modelo} forros={forros} />
              </div>
            </details>
          </Card>
        </section>
      </div>
    </>
  );
}

function Datum({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-caps-sm text-muted">{label}</dt>
      <dd className="mt-0.5">{value ?? "—"}</dd>
    </div>
  );
}
