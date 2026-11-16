import { SectionTabs } from "@/components/section-tabs";
import { ErrorNotice, Notice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import type { FormularioResumen, OrdenResumen } from "@/lib/types";
import { HojasGrid } from "./hojas-grid";
import { LotesGrid } from "./lotes-grid";

export type VistaDelTaller = "lotes" | "modelos";

/** The two tabs are two routes (Lotes at /fabricacion, Modelos at /taller/modelos), so each one is a plain link. */
const TABS = [
  { href: "/fabricacion", title: "Lotes", exact: true },
  { href: "/taller/modelos", title: "Modelos" },
];

/**
 * The screen of the taller, in two tabs: its lots and its models, each in the same grid as the admin's, with no
 * filters or extra panels. No money of any kind. Only the data of the open tab is requested.
 */
export async function LotesYModelos({ vista }: { vista: VistaDelTaller }) {
  return (
    <>
      <PageHeader eyebrow="Producción" title="Lotes y modelos" />
      <SectionTabs label="Lotes y modelos" tabs={TABS} />
      {vista === "lotes" ? <Lotes /> : <Modelos />}
    </>
  );
}

async function Lotes() {
  const ordenes = await apiGet<OrdenResumen[]>("/ordenes");
  if (!ordenes.ok) return <ErrorNotice message={ordenes.message} />;
  if (ordenes.data.length === 0) {
    return <Notice tone="info" title="Todavía no hay lotes cargados." />;
  }
  return <LotesGrid ordenes={ordenes.data} taller />;
}

async function Modelos() {
  const hojas = await apiGet<FormularioResumen[]>("/formularios");
  if (!hojas.ok) return <ErrorNotice message={hojas.message} />;
  if (hojas.data.length === 0) {
    return (
      <Notice tone="info" title="Todavía no hay modelos.">
        Cuando te envíen un modelo aparece acá.
      </Notice>
    );
  }
  return <HojasGrid hojas={hojas.data} />;
}
