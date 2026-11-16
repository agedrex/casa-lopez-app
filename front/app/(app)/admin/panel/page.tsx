import type { Metadata } from "next";
import { ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { canWrite } from "@/lib/permissions";
import { requireRole, requireSession } from "@/lib/session";
import type { Calidad, PanelCostos } from "@/lib/types";
import { Alertas, type AlertasSearch, alertasFilters } from "./alertas-panel";
import { DolarPanel } from "./dolar-panel";
import { NegocioVistas } from "./negocio-vistas";
import { BloqueConError, PanelCvu } from "./panel-cvu";
import { VISTAS_DEL_PANEL, VistaTabs, vistaDelPanel } from "./vista-tabs";

export const metadata: Metadata = { title: "Panel" };

type Search = AlertasSearch & {
  vista?: string | string[];
  periodo?: string | string[];
};

const PERIODO = /^\d{4}-(0[1-9]|1[0-2])$/;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

/** Costs first (the app is about costs): the month figures, the dollar and the alerts. */
async function Costos({
  searchParams,
  writer,
}: {
  searchParams: Search;
  writer: boolean;
}) {
  const filters = alertasFilters(searchParams);
  const [panel, calidad] = await Promise.all([
    apiGet<PanelCostos>("/panel/costos"),
    apiGet<Calidad>("/calidad"),
  ]);
  return (
    <>
      {panel.ok ? (
        <PanelCvu panel={panel.data} />
      ) : (
        <BloqueConError message={panel.message} />
      )}
      <div className="mt-6 space-y-6">
        <DolarPanel canWrite={writer} />
        <section
          id="alertas"
          aria-labelledby="alertas-titulo"
          className="scroll-mt-6"
        >
          {calidad.ok ? (
            <Alertas data={calidad.data} {...filters} />
          ) : (
            <ErrorNotice message={calidad.message} />
          )}
        </section>
      </div>
    </>
  );
}

export default async function PanelPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const { user } = await requireSession();
  const params = await searchParams;
  const vista = vistaDelPanel(first(params.vista));
  const requestedPeriodo = first(params.periodo);
  const periodo = PERIODO.test(requestedPeriodo) ? requestedPeriodo : "";
  // The Negocio tabs are admin only: the menu and the proxy already hide them, this is the check next to the data.
  if (vista !== "costos") await requireRole("admin");

  return (
    <>
      <PageHeader
        eyebrow="Resumen mensual"
        title="Panel"
        description={VISTAS_DEL_PANEL[vista].description}
      />
      <VistaTabs vista={vista} periodo={periodo} />
      {vista === "costos" ? (
        <Costos searchParams={params} writer={canWrite(user.role)} />
      ) : (
        <NegocioVistas vista={vista} periodo={periodo} />
      )}
    </>
  );
}
