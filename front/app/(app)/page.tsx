import type { Metadata } from "next";
import Link from "next/link";
import { Avisos } from "@/components/avisos";
import { Card, ErrorNotice, PageHeader, SectionTitle } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDate, formatRate } from "@/lib/format";
import type { Dolar, ProductoResumen } from "@/lib/types";

export const metadata: Metadata = { title: "Tablero" };

// The API caps a page at 500 products; the dashboard counts what it receives.
const PAGE_LIMIT = 500;
const ATTENTION_ROWS = 8;

export default async function TableroPage() {
  const [productos, dolar] = await Promise.all([
    apiGet<ProductoResumen[]>(`/productos?limit=${PAGE_LIMIT}`),
    apiGet<Dolar[]>("/dolar"),
  ]);

  return (
    <>
      <PageHeader
        eyebrow="Resumen"
        title="Tablero"
        description="Estado de los costos de un vistazo. Los montos los calcula siempre el sistema."
      />

      {productos.ok ? (
        <Summary productos={productos.data} />
      ) : (
        <ErrorNotice message={productos.message} />
      )}

      <div className="mt-10">
        <Card>
          <SectionTitle>Dólar vigente</SectionTitle>
          {dolar.ok ? (
            <DolarCard dolar={dolar.data[0]} />
          ) : (
            <ErrorNotice
              title="No pudimos cargar el dólar."
              message={dolar.message}
            />
          )}
        </Card>
      </div>
    </>
  );
}

function Summary({ productos }: { productos: ProductoResumen[] }) {
  const withCost = productos.filter((p) => p.costo_hoy_ars !== null).length;
  const withoutCost = productos.length - withCost;
  const withAvisos = productos.filter((p) => p.avisos.length > 0);
  const atLimit = productos.length >= PAGE_LIMIT;

  return (
    <>
      <dl className="grid gap-5 sm:grid-cols-3">
        <Metric
          label={atLimit ? "Productos (primeros 500)" : "Productos"}
          value={String(productos.length)}
        />
        <Metric label="Con costo hoy" value={String(withCost)} />
        <Metric
          label="Sin costo hoy"
          value={String(withoutCost)}
          hint="Falta cargar dólar o precios"
        />
      </dl>

      <div className="mt-10">
        <Card>
          <SectionTitle>Requieren atención</SectionTitle>
          {withAvisos.length === 0 ? (
            <p className="text-sm text-muted">Ningún producto tiene avisos.</p>
          ) : (
            <>
              <ul className="divide-y divide-line">
                {withAvisos.slice(0, ATTENTION_ROWS).map((producto) => (
                  <li
                    key={producto.codigo}
                    className="flex flex-wrap items-center justify-between gap-3 py-3"
                  >
                    <Link
                      href={`/productos/${encodeURIComponent(producto.codigo)}`}
                      className="text-sm hover:underline"
                    >
                      <span className="text-muted">{producto.codigo}</span> ·{" "}
                      {producto.nombre}
                    </Link>
                    <Avisos avisos={producto.avisos} />
                  </li>
                ))}
              </ul>
              {withAvisos.length > ATTENTION_ROWS ? (
                <p className="mt-4 text-sm text-muted">
                  Y {withAvisos.length - ATTENTION_ROWS} más.{" "}
                  <Link
                    href="/productos"
                    className="underline decoration-gold underline-offset-4"
                  >
                    Ver productos
                  </Link>
                </p>
              ) : null}
            </>
          )}
        </Card>
      </div>
    </>
  );
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-card border border-line bg-surface p-6 shadow-card">
      <dt className="text-xs uppercase tracking-caps-sm text-muted">{label}</dt>
      <dd className="mt-3 font-display text-4xl">{value}</dd>
      {hint ? <p className="mt-2 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

function DolarCard({ dolar }: { dolar: Dolar | undefined }) {
  if (!dolar) {
    return (
      <p className="text-sm text-muted">
        Todavía no hay un dólar cargado. Sin él no se puede calcular el costo en
        pesos.
      </p>
    );
  }
  return (
    <p className="text-sm text-muted">
      <span className="font-display text-3xl text-ink">
        {formatRate(dolar.ars_por_usd)}
      </span>{" "}
      pesos por dólar · al {formatDate(dolar.fecha)} · fuente {dolar.fuente}
    </p>
  );
}
