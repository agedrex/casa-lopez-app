import type { Metadata } from "next";
import Link from "next/link";
import { ReadOnlyNote } from "@/components/form";
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
import {
  formatDate,
  formatMoney,
  formatPercent,
  STAGE_ORDER,
  stageLabel,
  todayIso,
} from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Catalogos, Material, Precio } from "@/lib/types";
import { type MaterialOption, PrecioForm } from "./precio-form";

export const metadata: Metadata = { title: "Materiales y precios" };

export default async function MaterialesPage({
  searchParams,
}: {
  searchParams: Promise<{ material?: string | string[] }>;
}) {
  const { user } = await requireSession();
  const { material } = await searchParams;
  const preselected = Array.isArray(material) ? material[0] : material;

  const [materiales, precios, catalogos] = await Promise.all([
    apiGet<Material[]>("/materiales"),
    apiGet<Precio[]>("/precios"),
    apiGet<Catalogos>("/catalogos"),
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Costos"
        title="Materiales y precios"
        description="Cada precio queda con su fecha, moneda y unidad. Un precio nuevo no reemplaza al anterior: se suma a la historia."
      />
      {!materiales.ok ? (
        <ErrorNotice message={materiales.message} />
      ) : !precios.ok ? (
        <ErrorNotice message={precios.message} />
      ) : (
        <div className="space-y-10">
          <section>
            <SectionTitle>Cargar precio nuevo</SectionTitle>
            {canWrite(user.role) ? (
              <Card>
                <PrecioForm
                  key={preselected ?? ""}
                  materials={optionsOf(materiales.data)}
                  colores={catalogos.ok ? catalogos.data.colores : []}
                  today={todayIso()}
                  defaultMaterial={
                    materiales.data.some(
                      (m) => m.codigo === preselected && m.cotizable,
                    )
                      ? (preselected ?? "")
                      : ""
                  }
                />
              </Card>
            ) : (
              <ReadOnlyNote />
            )}
          </section>
          <Catalog
            materiales={materiales.data}
            precios={precios.data}
            writer={canWrite(user.role)}
          />
        </div>
      )}
    </>
  );
}

function optionsOf(materiales: Material[]): MaterialOption[] {
  return materiales
    .filter((m) => m.cotizable)
    .map((m) => ({
      codigo: m.codigo,
      label: `${m.codigo} · ${m.nombre} (${m.unidad_de_consumo})`,
      unidad: m.unidad_de_consumo,
      group: stageLabel(m.etapa),
    }));
}

function Catalog({
  materiales,
  precios,
  writer,
}: {
  materiales: Material[];
  precios: Precio[];
  writer: boolean;
}) {
  const pricesOf = new Map<string, Precio[]>();
  for (const precio of precios) {
    pricesOf.set(precio.material, [
      ...(pricesOf.get(precio.material) ?? []),
      precio,
    ]);
  }
  const stages = [
    ...STAGE_ORDER.filter((stage) => materiales.some((m) => m.etapa === stage)),
    ...[...new Set(materiales.map((m) => m.etapa))].filter(
      (stage) => !STAGE_ORDER.includes(stage),
    ),
  ];

  return (
    <>
      {stages.map((stage) => (
        <section key={stage}>
          <SectionTitle>{stageLabel(stage)}</SectionTitle>
          <div className="space-y-6">
            {materiales
              .filter((m) => m.etapa === stage)
              .map((m) => (
                <MaterialCard
                  key={m.codigo}
                  material={m}
                  precios={pricesOf.get(m.codigo) ?? []}
                  writer={writer}
                />
              ))}
          </div>
        </section>
      ))}
    </>
  );
}

function MaterialCard({
  material,
  precios,
  writer,
}: {
  material: Material;
  precios: Precio[];
  writer: boolean;
}) {
  const hasColor = precios.some((p) => p.color);
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-lg">{material.nombre}</h3>
          <p className="mt-1 text-sm text-muted">
            {material.codigo} · se consume en {material.unidad_de_consumo}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {material.cotizable ? (
            <Badge tone="good">Cotizable</Badge>
          ) : (
            <Badge tone="alert">No cotizable</Badge>
          )}
          {material.cotizable && writer ? (
            <Link
              href={`/materiales?material=${encodeURIComponent(material.codigo)}#cargar`}
              className="text-sm underline decoration-gold underline-offset-4"
            >
              Cargar precio nuevo
            </Link>
          ) : null}
        </div>
      </div>

      {!material.cotizable ? (
        <div className="mt-4">
          <Notice title="Bloqueado: falta definir unidad">
            El precio de este material no está en la misma unidad que su
            consumo, así que no se puede cotizar ni cargar un precio nuevo hasta
            que Casa López defina la unidad.
          </Notice>
        </div>
      ) : null}

      <div className="mt-4">
        {precios.length === 0 ? (
          <p className="text-sm text-muted">Todavía no tiene precios.</p>
        ) : (
          <TableWrap>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Desde</th>
                  <th className={`${thClass} ${numClass}`}>Precio</th>
                  <th className={thClass}>Moneda</th>
                  <th className={thClass}>Unidad</th>
                  {hasColor ? <th className={thClass}>Color</th> : null}
                  <th className={thClass}>Proveedor</th>
                  <th className={thClass}>Nota</th>
                  <th className={thClass}>Estado</th>
                </tr>
              </thead>
              <tbody>
                {precios.map((p) => (
                  <tr
                    key={p.codigo}
                    className={p.vigente ? "bg-paper-mid/70" : ""}
                  >
                    <td className={tdClass}>{formatDate(p.vigente_desde)}</td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatMoney(p.precio, p.moneda)}
                    </td>
                    <td className={tdClass}>{p.moneda}</td>
                    <td className={tdClass}>{p.unidad_del_precio}</td>
                    {hasColor ? (
                      <td className={tdClass}>{p.color ?? "—"}</td>
                    ) : null}
                    <td className={tdClass}>{p.proveedor ?? "—"}</td>
                    <td className={tdClass}>{p.nota_fuente ?? "—"}</td>
                    <td className={tdClass}>
                      <span className="flex flex-wrap gap-1.5">
                        {p.vigente ? <Badge tone="good">Vigente</Badge> : null}
                        {p.salto_grande ? (
                          <Badge
                            tone="warn"
                            title="Varía mucho respecto del precio anterior de este material."
                          >
                            {formatPercent(p.variacion_pct)} vs. anterior
                          </Badge>
                        ) : null}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </div>
    </Card>
  );
}
