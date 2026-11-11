import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import type { PanelCostos, ProductoResumen } from "@/lib/types";
import { EscenarioDeVentas } from "../cvu/escenario";
import { BloqueConError } from "../panel-cvu";

export const metadata: Metadata = { title: "Escenarios" };

export default async function EscenariosPage() {
  // SUPUESTO: 500 is the API's page maximum; it only feeds the product suggestions of the scenario.
  const [panel, productos] = await Promise.all([
    apiGet<PanelCostos>("/panel/costos"),
    apiGet<ProductoResumen[]>("/productos?limit=500"),
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Simulador"
        title="Escenarios"
        description="Probá un escenario de ventas y mirá cómo cambian el margen y el punto de equilibrio."
      />
      <div className="space-y-5">
        {panel.ok ? (
          <EscenarioDeVentas
            productos={productos.ok ? productos.data : []}
            periodo={panel.data.periodo}
          />
        ) : (
          <BloqueConError message={panel.message} />
        )}
      </div>
    </>
  );
}
