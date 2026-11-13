import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { PanelCostos, ProductoResumen } from "@/lib/types";
import { BloqueConError } from "../admin/panel/panel-cvu";
import { EscenarioDeVentas } from "../cvu/escenario";

export const metadata: Metadata = { title: "Escenarios" };

export default async function EscenariosPage() {
  const { user } = await requireSession();
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
            puedeCorregir={canWrite(user.role)}
          />
        ) : (
          <BloqueConError message={panel.message} />
        )}
      </div>
    </>
  );
}
