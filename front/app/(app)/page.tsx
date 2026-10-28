import type { Metadata } from "next";
import Link from "next/link";
import { Card, ErrorNotice, PageHeader, SectionTitle } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatArs, formatDate, formatPeriod, formatRate } from "@/lib/format";
import type { Calidad, CasaVsTaller, CostosFijos, Dolar } from "@/lib/types";
import type { GrillaData } from "./grilla/grilla-client";

export const metadata: Metadata = { title: "Panel del negocio" };

type Row = GrillaData["filas"][number];
type Bar = { label: string; value: string; href?: string };
const stages = [
  "CUERO",
  "FORRO",
  "FLEX",
  "GOMA_EVA",
  "HERRAJES",
  "HILO_CEMENTO",
  "CORTE",
  "CONFECCION",
];

function amount(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function Empty({
  text,
  href,
  link,
}: {
  text: string;
  href: string;
  link: string;
}) {
  return (
    <p className="text-sm text-muted">
      {text}{" "}
      <Link
        className="underline decoration-gold underline-offset-4"
        href={href}
      >
        {link}
      </Link>
    </p>
  );
}

function Metric({
  title,
  children,
  href,
}: {
  title: string;
  children: React.ReactNode;
  href: string;
}) {
  return (
    <Card>
      <h2 className="text-sm text-muted">{title}</h2>
      <div className="mt-3">{children}</div>
      <Link
        className="mt-4 inline-block text-sm underline decoration-gold underline-offset-4"
        href={href}
      >
        Ver detalle
      </Link>
    </Card>
  );
}

// Widths are visual scaling only; every money label is the exact API value.
function MoneyBars({ bars }: { bars: Bar[] }) {
  const maximum = Math.max(...bars.map((bar) => amount(bar.value)), 0);
  return (
    <ul className="space-y-4">
      {bars.map((bar) => (
        <li key={bar.label}>
          <div className="mb-1 flex items-start justify-between gap-3 text-sm">
            {bar.href ? (
              <Link
                className="min-w-0 truncate underline decoration-gold underline-offset-4"
                href={bar.href}
              >
                {bar.label}
              </Link>
            ) : (
              <span className="min-w-0 truncate">{bar.label}</span>
            )}
            <span className="shrink-0 tabular-nums">
              {formatArs(bar.value)}
            </span>
          </div>
          <svg
            className="h-3 w-full"
            viewBox="0 0 100 12"
            preserveAspectRatio="none"
            role="img"
            aria-label={bar.label + ": " + formatArs(bar.value)}
          >
            <rect
              width="100"
              height="12"
              rx="6"
              fill="currentColor"
              className="text-paper-mid"
            />
            <rect
              width={
                maximum > 0
                  ? Math.max(0, (amount(bar.value) / maximum) * 100)
                  : 0
              }
              height="12"
              rx="6"
              fill="currentColor"
              className="text-bordeaux"
            />
          </svg>
        </li>
      ))}
    </ul>
  );
}

function Charts({ data }: { data: GrillaData }) {
  const ordered = data.filas
    .filter((row) => amount(row.catalogo[7]) > 0)
    .sort((a, b) => amount(b.catalogo[7]) - amount(a.catalogo[7]));
  const top = ordered[0];
  const categories = new Map<string, Row>();
  for (const row of ordered) {
    const category = row.catalogo[2];
    if (category && !categories.has(category)) categories.set(category, row);
  }
  const productLink = (row: Row) =>
    "/productos/" + encodeURIComponent(row.codigo);
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <SectionTitle>¿En qué se va el costo?</SectionTitle>
        {top ? (
          <>
            <p className="mb-5 text-sm text-muted">
              Etapas de{" "}
              <Link
                className="underline decoration-gold underline-offset-4"
                href={productLink(top)}
              >
                {top.catalogo[1]}
              </Link>
              , el producto de mayor costo hoy.
            </p>
            <MoneyBars
              bars={stages.map((stage) => ({
                label: stage.replaceAll("_", " "),
                value:
                  top.costos_variables[
                    data.encabezados_costos_variables.indexOf(stage)
                  ] ?? "0",
              }))}
            />
          </>
        ) : (
          <Empty
            text="Faltan productos con costos de hoy."
            href="/productos"
            link="Cargar productos y precios"
          />
        )}
      </Card>
      <Card>
        <SectionTitle>¿Qué categoría cuesta más?</SectionTitle>
        {categories.size ? (
          <>
            <p className="mb-5 text-sm text-muted">
              Producto más caro de cada categoría; no es un total de la
              categoría.
            </p>
            <MoneyBars
              bars={[...categories].map(([category, row]) => ({
                label: category + " · " + row.catalogo[1],
                value: row.catalogo[7],
                href: productLink(row),
              }))}
            />
          </>
        ) : (
          <Empty
            text="Faltan productos con categoría y costo de hoy."
            href="/productos"
            link="Completar productos"
          />
        )}
      </Card>
      <Card>
        <SectionTitle>Productos más caros</SectionTitle>
        {ordered.length ? (
          <MoneyBars
            bars={ordered.slice(0, 5).map((row) => ({
              label: row.catalogo[1],
              value: row.catalogo[7],
              href: productLink(row),
            }))}
          />
        ) : (
          <Empty
            text="Faltan productos con costos de hoy."
            href="/grilla"
            link="Ver la grilla"
          />
        )}
      </Card>
    </div>
  );
}

function Production({ data }: { data: CasaVsTaller }) {
  const months = data.meses.filter((month) => month.porcentaje_taller !== null);
  return (
    <Card>
      <SectionTitle>¿Cuánto hacemos en casa y en taller?</SectionTitle>
      {months.length ? (
        <>
          <p className="mb-5 text-sm text-muted">
            Unidades por mes en los últimos 12 meses. Claro: casa · oscuro:
            taller.
          </p>
          <ul className="space-y-4">
            {months.map((month) => (
              <li key={month.periodo}>
                <div className="mb-1 flex flex-wrap justify-between gap-x-3 text-sm">
                  <span>{formatPeriod(month.periodo)}</span>
                  <span>
                    {month.unidades_casa} en casa · {month.unidades_taller} en
                    taller
                  </span>
                </div>
                <svg
                  className="h-3 w-full"
                  viewBox="0 0 100 12"
                  preserveAspectRatio="none"
                  role="img"
                  aria-label={
                    formatPeriod(month.periodo) +
                    ": " +
                    month.unidades_casa +
                    " unidades en casa y " +
                    month.unidades_taller +
                    " en taller"
                  }
                >
                  <rect
                    width="100"
                    height="12"
                    rx="6"
                    fill="currentColor"
                    className="text-sage"
                  />
                  <rect
                    width={Math.min(
                      100,
                      Math.max(0, amount(month.porcentaje_taller ?? "0")),
                    )}
                    height="12"
                    rx="6"
                    fill="currentColor"
                    className="text-ink"
                  />
                </svg>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <Empty
          text="Faltan lotes con fecha y unidades."
          href="/fabricacion"
          link="Cargar lotes"
        />
      )}
      <Link
        className="mt-5 inline-block text-sm underline decoration-gold underline-offset-4"
        href="/fabricacion"
      >
        Ver fabricación
      </Link>
    </Card>
  );
}

export default async function PanelPage() {
  const [grilla, production, fixed, quality, dollar] = await Promise.all([
    apiGet<GrillaData>("/grilla"),
    apiGet<CasaVsTaller>("/fabricacion/casa-vs-taller"),
    apiGet<CostosFijos>("/costos-fijos"),
    apiGet<Calidad>("/calidad"),
    apiGet<Dolar[]>("/dolar"),
  ]);
  const rows = grilla.ok ? grilla.data.filas : [];
  const withCost = rows.filter((row) => row.catalogo[7] !== "").length;
  const recost = rows.filter((row) => row.catalogo[13] === "SI").length;

  return (
    <>
      <PageHeader
        eyebrow="Resumen"
        title="Panel del negocio"
        description="Costos, fabricación y alertas de un vistazo."
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric title="Productos" href="/grilla">
          {grilla.ok ? (
            rows.length ? (
              <>
                <p className="font-display text-3xl">{rows.length}</p>
                <p className="mt-2 text-sm text-muted">
                  {withCost} con costo hoy · {rows.length - withCost} sin costo
                  · {recost} para recotizar
                </p>
              </>
            ) : (
              <Empty
                text="Faltan productos."
                href="/productos"
                link="Cargar productos"
              />
            )
          ) : (
            <ErrorNotice message={grilla.message} />
          )}
        </Metric>
        <Metric title="Dólar vigente" href="/dolar">
          {dollar.ok ? (
            dollar.data[0] ? (
              <>
                <p className="font-display text-3xl">
                  {formatRate(dollar.data[0].ars_por_usd)}
                </p>
                <p className="mt-2 text-sm text-muted">
                  Pesos por dólar · {formatDate(dollar.data[0].fecha)} ·{" "}
                  {dollar.data[0].fuente}
                </p>
              </>
            ) : (
              <Empty
                text="Falta cargar un dólar."
                href="/dolar"
                link="Cargar dólar"
              />
            )
          ) : (
            <ErrorNotice message={dollar.message} />
          )}
        </Metric>
        <Metric title="Costos fijos del mes" href="/costos-fijos">
          {fixed.ok ? (
            fixed.data.gastos.length ? (
              <>
                <p className="text-xs text-muted">
                  {formatPeriod(fixed.data.periodo)}
                </p>
                <p className="mt-2 text-sm">
                  Fábrica{" "}
                  <strong className="block text-lg">
                    {formatArs(fixed.data.total_fabrica)}
                  </strong>
                </p>
                <p className="mt-2 text-sm">
                  Tienda{" "}
                  <strong className="block text-lg">
                    {formatArs(fixed.data.total_tienda)}
                  </strong>
                </p>
                {fixed.data.pendientes > 0 && (
                  <p className="mt-2 text-xs text-muted">
                    {fixed.data.pendientes} montos pendientes
                  </p>
                )}
              </>
            ) : (
              <Empty
                text="Faltan costos fijos de este mes."
                href="/costos-fijos"
                link="Cargar gastos"
              />
            )
          ) : (
            <ErrorNotice message={fixed.message} />
          )}
        </Metric>
        <Metric title="Alertas" href="/calidad">
          {quality.ok ? (
            quality.data.resumen.total ? (
              <>
                <p className="font-display text-3xl">
                  {quality.data.resumen.total}
                </p>
                <p className="mt-2 text-sm text-muted">
                  {quality.data.resumen.alta} altas ·{" "}
                  {quality.data.resumen.media} medias ·{" "}
                  {quality.data.resumen.baja} bajas
                </p>
              </>
            ) : (
              <Empty
                text="Todavía no hay alertas."
                href="/calidad"
                link="Revisar calidad"
              />
            )
          ) : (
            <ErrorNotice message={quality.message} />
          )}
        </Metric>
      </div>
      <div className="mt-6 space-y-5">
        {grilla.ok ? (
          <Charts data={grilla.data} />
        ) : (
          <Card>
            <SectionTitle>Costos por producto</SectionTitle>
            <ErrorNotice message={grilla.message} />
          </Card>
        )}
        {production.ok ? (
          <Production data={production.data} />
        ) : (
          <Card>
            <SectionTitle>Casa y taller</SectionTitle>
            <ErrorNotice message={production.message} />
          </Card>
        )}
      </div>
    </>
  );
}
