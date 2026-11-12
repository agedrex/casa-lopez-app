import type { Metadata } from "next";
import { ErrorNotice, PageHeader, SectionTitle } from "@/components/ui";
import { apiGet } from "@/lib/api";
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
      <div className="mt-12 space-y-12">
        <DolarPanel role={user.role} />
        <section
          id="alertas"
          aria-labelledby="alertas-titulo"
          className="scroll-mt-6"
        >
          <SectionTitle>
            <span id="alertas-titulo">Alertas</span>
          </SectionTitle>
          <p className="mb-5 text-sm text-muted">
            Datos que faltan, se contradicen o son de prueba, con el lugar donde
            corregirlos. La gravedad es una propuesta: alta = no se puede
            cotizar o cerrar; media = se puede, pero hay algo raro; baja =
            informativo.
          </p>
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
