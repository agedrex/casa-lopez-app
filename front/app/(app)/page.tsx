import type { Metadata } from "next";
import Link from "next/link";
import { Card, ErrorNotice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import {
  formatDate,
  formatPeriod,
  formatRate,
  parseDecimalInput,
} from "@/lib/format";
import type { Calidad, PanelCostos } from "@/lib/types";
import { Avisos, CostoDelMes, QueEstaViejo, QueSubio } from "./panel-costos";
import { Simulador } from "./panel-simulador";

export const metadata: Metadata = { title: "Panel del negocio" };

type Search = Promise<{ precio?: string | string[] }>;

const linkClass = "underline decoration-gold underline-offset-4";
// The API accepts up to 14 digits with 4 decimals and a price above zero.
const PRECIO_VALIDO = /^\d{1,10}(\.\d{1,4})?$/;
const SOLO_CEROS = /^0+(\.0+)?$/;

function leerPrecio(raw: string): {
  precio: string | null;
  invalido: string | null;
} {
  const text = raw.trim();
  if (!text) return { precio: null, invalido: null };
  const parsed = parseDecimalInput(text);
  if (
    parsed === null ||
    !PRECIO_VALIDO.test(parsed) ||
    SOLO_CEROS.test(parsed)
  ) {
    return { precio: null, invalido: text };
  }
  return { precio: parsed, invalido: null };
}

export default async function PanelPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const params = await searchParams;
  const raw = Array.isArray(params.precio) ? params.precio[0] : params.precio;
  const { precio, invalido } = leerPrecio(raw ?? "");
  const query = precio === null ? "" : `?precio=${encodeURIComponent(precio)}`;
  const [panel, quality] = await Promise.all([
    apiGet<PanelCostos>(`/panel/costos${query}`),
    apiGet<Calidad>("/calidad"),
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Resumen"
        title="Panel del negocio"
        description="Cuánto cuesta producir, qué subió y qué hay que actualizar."
      />
      {panel.ok ? (
        <div className="space-y-5">
          <p className="text-sm text-muted">
            Mes: <strong>{formatPeriod(panel.data.periodo)}</strong> (se compara
            con {formatPeriod(panel.data.periodo_anterior)})
          </p>
          <Avisos avisos={panel.data.avisos} />
          <CostoDelMes panel={panel.data} />
          <div className="grid gap-5 lg:grid-cols-2">
            <QueSubio panel={panel.data} />
            <QueEstaViejo panel={panel.data} />
          </div>
          <Simulador
            panel={panel.data}
            precio={precio}
            precioInvalido={invalido}
          />
          <Card className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 text-sm">
            <p>
              Dólar vigente:{" "}
              {panel.data.dolar ? (
                <>
                  <strong>{formatRate(panel.data.dolar.ars_por_usd)}</strong>{" "}
                  pesos · {formatDate(panel.data.dolar.fecha)} ·{" "}
                  {panel.data.dolar.fuente}{" "}
                </>
              ) : (
                "no hay ninguno cargado "
              )}
              <Link className={linkClass} href="/dolar">
                Ver dólar
              </Link>
            </p>
            {quality.ok && (
              <p>
                Alertas de calidad:{" "}
                <strong>{quality.data.resumen.total}</strong>{" "}
                <Link className={linkClass} href="/calidad">
                  Revisar
                </Link>
              </p>
            )}
          </Card>
        </div>
      ) : (
        <ErrorNotice message={panel.message} />
      )}
    </>
  );
}
