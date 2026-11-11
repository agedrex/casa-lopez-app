import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import type { PanelCostos, ProductoResumen } from "@/lib/types";
import { EscenarioDeVentas } from "./cvu/escenario";
import { BloqueConError, PanelCvu } from "./panel-cvu";

export const metadata: Metadata = { title: "Panel del negocio" };

export default async function PanelPage() {
  // SUPUESTO: 500 is the API's page maximum; it only feeds the product suggestions of the scenario.
  const [panel, productos] = await Promise.all([
    apiGet<PanelCostos>("/panel/costos"),
    apiGet<ProductoResumen[]>("/productos?limit=500"),
  ]);

  return (
    <>
      <PageHeader
        title="Panel del negocio"
        description="Los números del mes y un simulador de ventas."
      />
      <div className="space-y-5">
        {panel.ok ? (
          <>
            <PanelCvu panel={panel.data} />
            <EscenarioDeVentas
              productos={productos.ok ? productos.data : []}
              periodo={panel.data.periodo}
            />
          </>
        ) : (
          <BloqueConError message={panel.message} />
        )}
      </div>
    </>
  );
}
