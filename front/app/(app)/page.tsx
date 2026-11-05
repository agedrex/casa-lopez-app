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
import type { Calidad, PanelCostos, TendenciaCostos } from "@/lib/types";
import {
  Avisos,
  BloqueConError,
  CostoDelMes,
  QueEstaViejo,
  QueSubio,
} from "./panel-costos";
import { Simulador } from "./panel-simulador";
import { ComoVieneElNegocio } from "./panel-tendencia";

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
  // Each block reads its own endpoint and degrades alone: a failure only replaces that block.
  const [panel, tendencia, quality] = await Promise.all([
    apiGet<PanelCostos>(`/panel/costos${query}`),
    apiGet<TendenciaCostos>("/panel/tendencia"),
    apiGet<Calidad>("/calidad"),
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Resumen"
        title="Panel del negocio"
        description="Cómo viene el negocio, cuánto cuesta producir, qué subió y qué hay que actualizar."
      />
      <div className="space-y-5">
        {panel.ok && (
          <p className="text-sm text-muted">
            Mes: <strong>{formatPeriod(panel.data.periodo)}</strong> (se compara
            con {formatPeriod(panel.data.periodo_anterior)})
          </p>
        )}
        {panel.ok ? (
          <Avisos avisos={panel.data.avisos} />
        ) : (
          <ErrorNotice
            title="No pudimos cargar los avisos."
            message={panel.message}
          />
        )}
        {tendencia.ok ? (
          <ComoVieneElNegocio tendencia={tendencia.data} />
        ) : (
          <BloqueConError
            titulo="Cómo viene el negocio"
            message={tendencia.message}
          />
        )}
        {panel.ok ? (
          <CostoDelMes panel={panel.data} />
        ) : (
          <BloqueConError
            titulo="Cuánto cuesta producir este mes"
            message={panel.message}
          />
        )}
        <div className="grid gap-5 lg:grid-cols-2">
          {panel.ok ? (
            <>
              <QueSubio panel={panel.data} />
              <QueEstaViejo panel={panel.data} />
            </>
          ) : (
            <>
              <BloqueConError titulo="Qué subió" message={panel.message} />
              <BloqueConError titulo="Qué está viejo" message={panel.message} />
            </>
          )}
        </div>
        {panel.ok ? (
          <Simulador
            panel={panel.data}
            precio={precio}
            precioInvalido={invalido}
          />
        ) : (
          <BloqueConError
            titulo="Punto de equilibrio"
            message={panel.message}
          />
        )}
        <Card className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 text-sm">
          <p>
            Dólar vigente:{" "}
            {!panel.ok ? (
              "no se pudo leer "
            ) : panel.data.dolar ? (
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
          <p>
            Alertas de calidad:{" "}
            {quality.ok ? (
              <strong>{quality.data.resumen.total}</strong>
            ) : (
              "no se pudieron leer"
            )}{" "}
            <Link className={linkClass} href="/calidad">
              Revisar
            </Link>
          </p>
        </Card>
      </div>
    </>
  );
}
