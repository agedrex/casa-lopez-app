import type { Metadata } from "next";
import { ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Calidad, PanelCostos } from "@/lib/types";
import { Alertas, type AlertasSearch, alertasFilters } from "./alertas-panel";
import { DolarPanel } from "./dolar-panel";
import { BloqueConError, PanelCvu } from "./panel-cvu";

export const metadata: Metadata = { title: "Panel" };

export default async function PanelPage({
  searchParams,
}: {
  searchParams: Promise<AlertasSearch>;
}) {
  const { user } = await requireSession();
  const filters = alertasFilters(await searchParams);
  const [panel, calidad] = await Promise.all([
    apiGet<PanelCostos>("/panel/costos"),
    apiGet<Calidad>("/calidad"),
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Resumen mensual"
        title="Panel"
        description="Los números del mes comparados con el anterior."
      />
      {panel.ok ? (
        <PanelCvu panel={panel.data} />
      ) : (
        <BloqueConError message={panel.message} />
      )}
      <div className="mt-6 space-y-6">
        <DolarPanel canWrite={canWrite(user.role)} />
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
