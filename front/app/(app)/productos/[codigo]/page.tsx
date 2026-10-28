import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Avisos } from "@/components/avisos";
import {
  Badge,
  Card,
  ErrorNotice,
  Notice,
  numClass,
  PageHeader,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import {
  formatArs,
  formatDate,
  formatQuantity,
  formatRate,
  formatUsd,
  lifecycleLabel,
  quoteTypeLabel,
  stageLabel,
} from "@/lib/format";
import type { Desglose, Ficha } from "@/lib/types";

export const metadata: Metadata = { title: "Ficha de producto" };

const STAGE_ORDER = [
  "CUERO",
  "FORRO",
  "FLEX",
  "GOMA_EVA",
  "HERRAJES",
  "HILO_CEMENTO",
  "CORTE",
  "CONFECCION",
];

function decodeCode(raw: string): string | null {
  try {
    return decodeURIComponent(raw);
  } catch {
    return null;
  }
}

export default async function FichaPage({
  params,
}: {
  params: Promise<{ codigo: string }>;
}) {
  const code = decodeCode((await params).codigo);
  if (code === null) notFound();

  const result = await apiGet<Ficha>(`/productos/${encodeURIComponent(code)}`);

  if (!result.ok) {
    // A missing product is rendered inline: notFound() would be streamed as a late
    // client-side swap here because the page already sits inside a Suspense boundary.
    return (
      <>
        <BackLink />
        {result.status === 404 ? (
          <Notice tone="info" title="No encontramos ese producto">
            Revise el código o vuelva al listado de productos.
          </Notice>
        ) : (
          <ErrorNotice message={result.message} />
        )}
      </>
    );
  }

  const ficha = result.data;
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow={`Producto ${ficha.codigo}`}
        title={ficha.nombre}
        actions={
          <div className="flex flex-wrap gap-2">
            <Badge>{lifecycleLabel(ficha.estado_del_ciclo)}</Badge>
            {ficha.es_kit ? <Badge>Kit</Badge> : null}
            {ficha.categoria ? <Badge>{ficha.categoria}</Badge> : null}
          </div>
        }
      />

      <div className="space-y-10">
        <Details ficha={ficha} />
        <CostToday ficha={ficha} />
        <Recipe ficha={ficha} />
        {ficha.componentes.length > 0 ? <Components ficha={ficha} /> : null}
        <StoredQuotes ficha={ficha} />
      </div>
    </>
  );
}

function BackLink() {
  return (
    <p className="mb-6 text-sm">
      <Link
        href="/productos"
        className="text-muted underline decoration-gold underline-offset-4"
      >
        ← Productos
      </Link>
    </p>
  );
}

function Details({ ficha }: { ficha: Ficha }) {
  const rows: [string, string][] = [
    ["Modelo", ficha.modelo ?? "—"],
    ["Cuero", ficha.cuero ?? "—"],
    ["Color", ficha.color ?? "—"],
    ["Quién lo confecciona", ficha.quien_lo_confecciona ?? "—"],
    ["Fecha de alta", formatDate(ficha.fecha_de_alta)],
    ["Fecha de recotización", formatDate(ficha.fecha_de_recotizacion)],
    ["Fecha de cierre", formatDate(ficha.fecha_de_cierre)],
  ];
  return (
    <Card>
      <dl className="grid gap-x-8 gap-y-5 sm:grid-cols-2 lg:grid-cols-4">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs uppercase tracking-caps-sm text-muted">
              {label}
            </dt>
            <dd className="mt-1 text-sm">{value}</dd>
          </div>
        ))}
      </dl>
      {ficha.nota ? (
        <p className="mt-6 border-t border-line pt-4 text-sm text-muted">
          {ficha.nota}
        </p>
      ) : null}
    </Card>
  );
}

function RecotizarNotice({ recotizar }: { recotizar: boolean | null }) {
  if (recotizar === true) {
    return (
      <Notice title="Conviene recotizar">
        El costo de hoy se aleja de la última cotización guardada.
      </Notice>
    );
  }
  if (recotizar === false) {
    return <Notice tone="info" title="La última cotización sigue al día" />;
  }
  return <Notice tone="info" title="Sin cotización guardada para comparar" />;
}

function stageRows(costo: Desglose) {
  const known = STAGE_ORDER.filter((stage) => stage in costo.etapas);
  const extra = Object.keys(costo.etapas).filter(
    (stage) => !STAGE_ORDER.includes(stage),
  );
  return [...known, ...extra].map(
    (stage) => [stage, costo.etapas[stage]] as const,
  );
}

function CostRow({
  label,
  value,
  strong = false,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <tr>
      <td className={`${tdClass} ${strong ? "font-bold" : ""}`}>{label}</td>
      <td className={`${tdClass} ${numClass} ${strong ? "font-bold" : ""}`}>
        {formatArs(value)}
      </td>
    </tr>
  );
}

function CostToday({ ficha }: { ficha: Ficha }) {
  const costo = ficha.costo_hoy;
  return (
    <section>
      <SectionTitle>Costo hoy</SectionTitle>
      <div className="space-y-4">
        <RecotizarNotice recotizar={ficha.recotizar} />
        {costo === null ? (
          <Card>
            <p className="font-display text-xl">Falta cargar dólar o precios</p>
            <p className="mt-2 text-sm text-muted">
              Sin esos datos no se puede calcular el costo de hoy.
            </p>
            {ficha.avisos.length > 0 ? (
              <ul className="mt-4 list-disc space-y-1 pl-5 text-sm">
                {ficha.avisos.map((aviso) => (
                  <li key={aviso}>{aviso}</li>
                ))}
              </ul>
            ) : null}
          </Card>
        ) : (
          <Card>
            <div className="flex flex-wrap items-end justify-between gap-6">
              <div>
                <p className="text-xs uppercase tracking-caps-sm text-muted">
                  Total
                </p>
                <p className="mt-1 font-display text-4xl">
                  {formatArs(costo.total_ars)}
                </p>
                <p className="mt-1 text-sm text-muted">
                  {formatUsd(costo.total_usd)}
                </p>
              </div>
              <p className="text-sm text-muted">
                Dólar {formatRate(costo.dolar)} · al {formatDate(costo.fecha)}
              </p>
            </div>
            {ficha.avisos.length > 0 ? (
              <div className="mt-4">
                <Avisos avisos={ficha.avisos} limit={3} />
              </div>
            ) : null}
            <div className="mt-6">
              <TableWrap>
                <table className={tableClass}>
                  <thead>
                    <tr>
                      <th className={thClass}>Etapa</th>
                      <th className={`${thClass} ${numClass}`}>Costo (ARS)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stageRows(costo).map(([stage, amount]) => (
                      <CostRow
                        key={stage}
                        label={stageLabel(stage)}
                        value={amount}
                      />
                    ))}
                    <CostRow
                      label="Subtotal de etapas"
                      value={costo.subtotal}
                    />
                    <CostRow
                      label="Componentes del kit"
                      value={costo.componentes_kit}
                    />
                    <CostRow label="IVA de compras" value={costo.iva_compras} />
                    <CostRow label="Arreglos" value={costo.arreglos} />
                    <CostRow label="Total" value={costo.total_ars} strong />
                  </tbody>
                </table>
              </TableWrap>
            </div>
          </Card>
        )}
      </div>
    </section>
  );
}

function Recipe({ ficha }: { ficha: Ficha }) {
  return (
    <section>
      <SectionTitle>Receta</SectionTitle>
      {ficha.receta.length === 0 ? (
        <Notice
          tone="info"
          title="Este producto todavía no tiene líneas de receta."
        />
      ) : (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Etapa</th>
                <th className={thClass}>Material</th>
                <th className={thClass}>Color</th>
                <th className={`${thClass} ${numClass}`}>Consumo</th>
              </tr>
            </thead>
            <tbody>
              {ficha.receta.map((linea, index) => (
                <tr
                  key={`${linea.etapa}-${linea.material}-${linea.color ?? ""}-${index}`}
                >
                  <td className={tdClass}>{stageLabel(linea.etapa)}</td>
                  <td className={tdClass}>{linea.material}</td>
                  <td className={tdClass}>{linea.color ?? "—"}</td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatQuantity(linea.consumo)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
      <p className="mt-3 text-sm text-muted">
        Confección estimada: {formatArs(ficha.confeccion_estimada_ars)}
      </p>
    </section>
  );
}

function Components({ ficha }: { ficha: Ficha }) {
  return (
    <section>
      <SectionTitle>Componentes del kit</SectionTitle>
      <TableWrap>
        <table className={tableClass}>
          <thead>
            <tr>
              <th className={thClass}>Producto</th>
              <th className={`${thClass} ${numClass}`}>Cantidad</th>
            </tr>
          </thead>
          <tbody>
            {ficha.componentes.map((componente) => (
              <tr key={componente.producto}>
                <td className={tdClass}>
                  <Link
                    href={`/productos/${encodeURIComponent(componente.producto)}`}
                    className="underline decoration-gold underline-offset-4"
                  >
                    {componente.producto}
                  </Link>
                </td>
                <td className={`${tdClass} ${numClass}`}>
                  {formatQuantity(componente.cantidad)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
    </section>
  );
}

function StoredQuotes({ ficha }: { ficha: Ficha }) {
  return (
    <section>
      <SectionTitle>Cotizaciones guardadas</SectionTitle>
      {ficha.cotizaciones.length === 0 ? (
        <Notice
          tone="info"
          title="Todavía no se guardó ninguna cotización de este producto."
        />
      ) : (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Fecha</th>
                <th className={thClass}>Tipo</th>
                <th className={`${thClass} ${numClass}`}>Dólar</th>
                <th className={`${thClass} ${numClass}`}>Total (ARS)</th>
                <th className={`${thClass} ${numClass}`}>Total (USD)</th>
                <th className={thClass}>Estado</th>
              </tr>
            </thead>
            <tbody>
              {ficha.cotizaciones.map((cotizacion) => (
                <tr key={`${cotizacion.fecha}-${cotizacion.tipo}`}>
                  <td className={tdClass}>{formatDate(cotizacion.fecha)}</td>
                  <td className={tdClass}>{quoteTypeLabel(cotizacion.tipo)}</td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatRate(cotizacion.dolar)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(cotizacion.total_ars)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatUsd(cotizacion.total_usd)}
                  </td>
                  <td className={tdClass}>{cotizacion.estado ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
    </section>
  );
}
