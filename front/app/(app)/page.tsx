import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { Card, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDate, formatRate } from "@/lib/format";
import { PRECIO_COOKIE, precioValido } from "@/lib/precio-panel";
import type { PanelCostos } from "@/lib/types";
import {
  BloqueConError,
  FormularioPrecio,
  PanelCvu,
  PorRevisar,
} from "./panel-cvu";

export const metadata: Metadata = { title: "Panel del negocio" };

type Search = Promise<{ precio_invalido?: string | string[] }>;

const linkClass = "underline decoration-gold underline-offset-4";

export default async function PanelPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const params = await searchParams;
  const invalidoRaw = params.precio_invalido;
  const invalido = Array.isArray(invalidoRaw) ? invalidoRaw[0] : invalidoRaw;
  const guardado = (await cookies()).get(PRECIO_COOKIE)?.value ?? "";
  const precio = precioValido(guardado);
  const query = precio === null ? "" : `?precio=${encodeURIComponent(precio)}`;
  const panel = await apiGet<PanelCostos>(`/panel/costos${query}`);

  return (
    <>
      <PageHeader
        title="Panel del negocio"
        description="Cuánto vendés, cuánto gastás y cuánto te queda."
      />
      <div className="space-y-5">
        <FormularioPrecio precio={precio} invalido={invalido ?? null} />
        {panel.ok ? (
          <>
            <PanelCvu panel={panel.data} precio={precio} />
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
