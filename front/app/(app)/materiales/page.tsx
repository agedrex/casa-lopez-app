import type { Metadata } from "next";
import { Fragment } from "react";
import {
  Badge,
  ErrorNotice,
  Notice,
  numClass,
  PageHeader,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDate, formatMoney, STAGE_ORDER, stageLabel } from "@/lib/format";
import { agruparMateriales, type GrupoDeMateriales } from "@/lib/materiales";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { EtapaCatalogo, Material, Precio } from "@/lib/types";
import { MaterialesGrid } from "./materiales-grid";

export const metadata: Metadata = { title: "Materiales y precios" };

export default async function MaterialesPage() {
  const { user } = await requireSession();
  const writer = canWrite(user.role);

  const [materiales, precios, etapas] = await Promise.all([
    apiGet<Material[]>("/materiales"),
    apiGet<Precio[]>("/precios"),
    writer ? apiGet<EtapaCatalogo[]>("/catalogo/etapas") : null,
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Costos"
        title="Materiales y precios"
        description="Los materiales que se compran, por etapa. Cambiar un precio agrega uno nuevo con la fecha de hoy: el anterior queda en la historia. Un material nuevo se agrega al final de la grilla."
      />
      {!materiales.ok ? (
        <ErrorNotice message={materiales.message} />
      ) : !precios.ok ? (
        <ErrorNotice message={precios.message} />
      ) : materiales.data.length === 0 && !writer ? (
        <Notice tone="info" title="Todavía no hay materiales." />
      ) : writer ? (
        <MaterialesGrid
          grupos={agruparMateriales(materiales.data, precios.data)}
          etapas={materialStages(etapas?.ok ? etapas.data : null)}
        />
      ) : (
        <ReadOnlyMateriales
          grupos={agruparMateriales(materiales.data, precios.data)}
        />
      )}
    </>
  );
}

/** Stages that hold materials (the others are tasks); the quote order if the catalog cannot be read. */
function materialStages(catalogo: EtapaCatalogo[] | null): string[] {
  if (!catalogo) return STAGE_ORDER.slice(0, 6);
  return [...catalogo]
    .filter((etapa) => etapa.tipo === "MATERIAL")
    .sort((a, b) => a.orden - b.orden)
    .map((etapa) => etapa.codigo);
}

/** The same grouping as the grid for roles that read but do not write (taller). */
function ReadOnlyMateriales({ grupos }: { grupos: GrupoDeMateriales[] }) {
  return (
    <TableWrap>
      <table className={tableClass}>
        <thead>
          <tr>
            <th className={thClass}>Material</th>
            <th className={thClass}>Unidad de consumo</th>
            <th className={`${thClass} ${numClass}`}>Precio</th>
            <th className={thClass}>Proveedor</th>
            <th className={thClass}>Desde</th>
            <th className={thClass}>Estado</th>
          </tr>
        </thead>
        <tbody>
          {grupos.map((grupo) => (
            <Fragment key={grupo.etapa}>
              <tr className="bg-paper-mid">
                <th
                  scope="colgroup"
                  colSpan={6}
                  className={`${tdClass} text-left font-bold uppercase`}
                >
                  {stageLabel(grupo.etapa)}
                </th>
              </tr>
              {grupo.filas.map(({ material, precio }) => (
                <tr key={material.codigo}>
                  <td className={tdClass}>
                    {material.nombre}
                    <span className="block text-xs text-muted">
                      {material.codigo}
                    </span>
                  </td>
                  <td className={tdClass}>{material.unidad_de_consumo}</td>
                  <td className={`${tdClass} ${numClass}`}>
                    {precio ? formatMoney(precio.precio, precio.moneda) : "—"}
                  </td>
                  <td className={tdClass}>{precio?.proveedor ?? "—"}</td>
                  <td className={tdClass}>
                    {precio ? formatDate(precio.vigente_desde) : "—"}
                  </td>
                  <td className={tdClass}>
                    {!material.cotizable ? (
                      <Badge tone="alert">No cotizable</Badge>
                    ) : !precio ? (
                      <Badge tone="warn">Sin precio</Badge>
                    ) : precio.vigente ? (
                      <Badge tone="good">Vigente</Badge>
                    ) : (
                      "Anterior"
                    )}
                  </td>
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}
