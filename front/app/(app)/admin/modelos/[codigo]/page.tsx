import type { Metadata } from "next";
import Link from "next/link";
import {
  Badge,
  Card,
  ErrorNotice,
  Notice,
  PageHeader,
  SectionTitle,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { originLabel, sizeLabel } from "@/lib/modelos";
import { requireRole } from "@/lib/session";
import type { ModeloDetalle } from "@/lib/types";
import { ConsumosTable, EditarConsumos, loadForros } from "../modelo-consumos";
import { ValidadoForm } from "./modelo-forms";

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
  const [result, forros] = await Promise.all([
    apiGet<ModeloDetalle>(`/modelos/${encodeURIComponent(code)}`),
    loadForros(),
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
              <div>
                <dt className="text-xs uppercase tracking-caps-sm text-muted">
                  Productos que lo usan
                </dt>
                <dd className="mt-0.5">
                  {modelo.productos > 0 ? (
                    <Link
                      href={`/productos?q=${encodeURIComponent(modelo.codigo)}`}
                      className="underline decoration-gold underline-offset-4"
                    >
                      Ver los {modelo.productos}{" "}
                      {modelo.productos === 1 ? "producto" : "productos"}
                    </Link>
                  ) : (
                    "Ninguno"
                  )}
                </dd>
              </div>
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
          <ConsumosTable modelo={modelo} />
        </section>
        <section>
          <SectionTitle>Validación</SectionTitle>
          <Card>
            <ValidadoForm codigo={modelo.codigo} validado={modelo.validado} />
          </Card>
        </section>
        <section>
          <SectionTitle>Editar consumos</SectionTitle>
          <EditarConsumos modelo={modelo} forros={forros} />
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
