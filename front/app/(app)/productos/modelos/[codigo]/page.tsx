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
import { formatInstantDate } from "@/lib/format";
import { ESTADO_TONE, estadoLabel } from "@/lib/formularios";
import { originLabel, sizeLabel } from "@/lib/modelos";
import { requireRole } from "@/lib/session";
import type { FormularioResumen, ModeloDetalle } from "@/lib/types";
import { ConsumosTable, EditarConsumos, loadForros } from "../modelo-consumos";
import { FotoModelo } from "./foto-modelo";
import { ValidadoForm } from "./modelo-forms";

export const metadata: Metadata = { title: "Modelo" };

function BackLink() {
  return (
    <p className="mb-6 text-sm">
      <Link
        href="/productos/modelos"
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
  const [result, forros, hojas] = await Promise.all([
    apiGet<ModeloDetalle>(`/modelos/${encodeURIComponent(code)}`),
    loadForros(),
    apiGet<FormularioResumen[]>(
      `/formularios?modelo=${encodeURIComponent(code)}`,
    ),
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
        eyebrow="Modelo"
        title={modelo.nombre_del_modelo}
        actions={
          <div className="flex flex-col items-start gap-2 sm:items-end">
            <div className="sm:text-right">
              <p className="text-xs uppercase tracking-caps-sm text-muted">
                ID del modelo
              </p>
              <h2 className="text-2xl tabular-nums">{modelo.codigo}</h2>
            </div>
            <Badge tone={modelo.validado ? "good" : "neutral"}>
              {modelo.validado ? "Validado" : "Sin validar"}
            </Badge>
          </div>
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
          <SectionTitle>Foto</SectionTitle>
          <Card>
            <FotoModelo
              codigo={modelo.codigo}
              nombre={modelo.nombre_del_modelo}
              tieneFoto={modelo.tiene_foto}
              puedeSubir
            />
          </Card>
        </section>
        <section>
          <SectionTitle>Hoja de consumos del taller</SectionTitle>
          <Card>
            {hojas.ok ? (
              hojas.data.length === 0 ? (
                <p className="text-sm text-muted">
                  Este modelo no tiene hoja de consumos (los modelos del Excel
                  viejo traen sus consumos cargados).
                </p>
              ) : (
                <ul className="divide-y divide-line/70 text-sm">
                  {hojas.data.map((hoja) => (
                    <li
                      key={hoja.codigo}
                      className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2"
                    >
                      <Link
                        href={`/taller/modelos/${encodeURIComponent(hoja.codigo)}`}
                        className="tabular-nums underline decoration-gold underline-offset-4"
                      >
                        {hoja.codigo}
                      </Link>
                      <Badge tone={ESTADO_TONE[hoja.estado]}>
                        {estadoLabel(hoja.estado)}
                      </Badge>
                      <span className="text-muted">
                        Creada el {formatInstantDate(hoja.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )
            ) : (
              <ErrorNotice message={hojas.message} />
            )}
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
