import type { Metadata } from "next";
import Link from "next/link";
import { Card, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDate, formatRate } from "@/lib/format";
import type { PanelCostos, ProductoResumen } from "@/lib/types";
import { EscenarioDeVentas } from "./cvu/escenario";
import { BloqueConError, PanelCvu, PorRevisar } from "./panel-cvu";

export const metadata: Metadata = { title: "Panel del negocio" };

const linkClass = "underline decoration-gold underline-offset-4";

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
        description="Cuánto producís, cuánto cuesta y de qué está hecho el costo."
      />
      <div className="space-y-5">
        {panel.ok ? (
          <>
            <PanelCvu panel={panel.data} />
            <PorRevisar panel={panel.data} />
            <EscenarioDeVentas
              productos={productos.ok ? productos.data : []}
              periodo={panel.data.periodo}
            />
            {panel.data.dolar && (
              <Card className="text-sm">
                Dólar:{" "}
                <strong>{formatRate(panel.data.dolar.ars_por_usd)}</strong>{" "}
                pesos · {formatDate(panel.data.dolar.fecha)}{" "}
                <Link className={linkClass} href="/dolar">
                  Ver dólar
                </Link>
              </Card>
            )}
          </>
        ) : (
          <BloqueConError message={panel.message} />
        )}
      </div>
    </>
  );
}
