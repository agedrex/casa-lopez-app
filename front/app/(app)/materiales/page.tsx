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
import { formatDate, formatMoney, stageLabel, todayIso } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Catalogos, Material, Precio } from "@/lib/types";
import { type MaterialOption, PrecioForm } from "./precio-form";

export const metadata: Metadata = { title: "Materiales y precios" };

export default async function MaterialesPage({
  searchParams,
}: {
  searchParams: Promise<{
    material?: string | string[];
    orden?: string | string[];
    dir?: string | string[];
  }>;
}) {
  const { user } = await requireSession();
  const { material, orden, dir } = await searchParams;
  const preselected = Array.isArray(material) ? material[0] : material;
  const sort = ["etapa", "material", "fecha"].includes(String(orden))
    ? String(orden)
    : "material";
  const direction = dir === "desc" ? "desc" : "asc";

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
          <section id="cargar">
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
          <section className="space-y-5">
            <AllMaterials
              materiales={materiales.data}
              precios={precios.data}
              sort={sort}
              direction={direction}
            />
          </section>
        </div>
      )}
    </>
  );
}

function AllMaterials({
  materiales,
  precios,
  sort,
  direction,
}: {
  materiales: Material[];
  precios: Precio[];
  sort: string;
  direction: "asc" | "desc";
}) {
  const entries = materiales.flatMap((material) => {
    const history = precios.filter(
      (price) => price.material === material.codigo,
    );
    return (history.length ? history : [null]).map((price) => ({
      material,
      price,
    }));
  });
  entries.sort((a, b) => {
    const value = (entry: (typeof entries)[number]) =>
      sort === "etapa"
        ? stageLabel(entry.material.etapa)
        : sort === "fecha"
          ? (entry.price?.vigente_desde ?? "")
          : entry.material.nombre;
    const result = value(a).localeCompare(value(b), "es-AR");
    return direction === "desc" ? -result : result;
  });
  const sortLink = (key: string) =>
    `/materiales?orden=${key}&dir=${sort === key && direction === "asc" ? "desc" : "asc"}`;
  const heading = (key: string, label: string) => (
    <Link
      href={sortLink(key)}
      className="underline decoration-gold underline-offset-4"
    >
      {label}
      {sort === key ? (direction === "asc" ? " ↑" : " ↓") : ""}
    </Link>
  );
  return (
    <>
      <SectionTitle>Todos los materiales y precios</SectionTitle>
      {entries.length ? (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>{heading("etapa", "Etapa")}</th>
                <th className={thClass}>{heading("material", "Material")}</th>
                <th className={thClass}>{heading("fecha", "Desde")}</th>
                <th className={`${thClass} ${numClass}`}>Precio</th>
                <th className={thClass}>Moneda / unidad</th>
                <th className={thClass}>Color</th>
                <th className={thClass}>Proveedor</th>
                <th className={thClass}>Estado</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(({ material, price }) => (
                <tr key={price?.codigo ?? material.codigo}>
                  <td className={tdClass}>{stageLabel(material.etapa)}</td>
                  <td className={tdClass}>
                    {material.nombre}
                    <span className="block text-xs text-muted">
                      {material.codigo}
                    </span>
                  </td>
                  <td className={tdClass}>
                    {price ? formatDate(price.vigente_desde) : "—"}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {price ? formatMoney(price.precio, price.moneda) : "—"}
                  </td>
                  <td className={tdClass}>
                    {price
                      ? `${price.moneda} / ${price.unidad_del_precio}`
                      : "—"}
                  </td>
                  <td className={tdClass}>{price?.color ?? "—"}</td>
                  <td className={tdClass}>{price?.proveedor ?? "—"}</td>
                  <td className={tdClass}>
                    {!material.cotizable ? (
                      <Badge tone="alert">No cotizable</Badge>
                    ) : !price ? (
                      <Badge tone="warn">Sin precio</Badge>
                    ) : price.vigente ? (
                      <Badge tone="good">Vigente</Badge>
                    ) : (
                      "Anterior"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-paper-mid">
                <th className={tdClass} scope="row">
                  Materiales
                </th>
                <td className={tdClass} colSpan={7}>
                  {materiales.length} · {precios.length} precios
                </td>
              </tr>
            </tfoot>
          </table>
        </TableWrap>
      ) : (
        <Notice tone="info" title="Todavía no hay materiales." />
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
