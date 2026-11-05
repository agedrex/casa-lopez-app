import type { Metadata } from "next";
import Link from "next/link";
import { Card, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDate, formatRate } from "@/lib/format";
import type { PanelCostos } from "@/lib/types";
import { BloqueConError, PanelCvu, PorRevisar } from "./panel-cvu";

export const metadata: Metadata = { title: "Panel del negocio" };

const linkClass = "underline decoration-gold underline-offset-4";

export default async function PanelPage() {
  const panel = await apiGet<PanelCostos>("/panel/costos");

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
