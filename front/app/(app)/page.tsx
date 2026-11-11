import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import type { PanelCostos, TendenciaCostos } from "@/lib/types";
import { BloqueConError, PanelCvu } from "./panel-cvu";
import { TendenciaDeCostos } from "./tendencia-costos";

export const metadata: Metadata = { title: "Panel" };

export default async function PanelPage() {
  const [panel, tendencia] = await Promise.all([
    apiGet<PanelCostos>("/panel/costos"),
    apiGet<TendenciaCostos>("/panel/tendencia"),
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Resumen mensual"
        title="Panel"
        description="Los números del mes comparados con el anterior."
      />
      {panel.ok ? (
        <div className="space-y-6">
          <PanelCvu panel={panel.data} />
          {tendencia.ok && tendencia.data.meses.length > 0 ? (
            <TendenciaDeCostos tendencia={tendencia.data} />
          ) : null}
        </div>
      ) : (
        <BloqueConError message={panel.message} />
      )}
    </>
  );
}
