import type { Metadata } from "next";
import Link from "next/link";
import { PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import type { PanelCostos, TendenciaCostos } from "@/lib/types";
import { BloqueConError, PanelCvu } from "./panel-cvu";
import { TendenciaDeCostos } from "./tendencia-costos";

export const metadata: Metadata = { title: "Panel del negocio" };

export default async function PanelPage() {
  const [panel, tendencia] = await Promise.all([
    apiGet<PanelCostos>("/panel/costos"),
    apiGet<TendenciaCostos>("/panel/tendencia"),
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Resumen mensual"
        title="Panel del negocio"
        description="Los números del mes comparados con el anterior."
        actions={
          <Link
            href="/escenarios"
            className="rounded-card border border-line bg-surface px-4 py-2 text-sm text-ink-soft hover:bg-parchment"
          >
            Simular escenarios →
          </Link>
        }
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
