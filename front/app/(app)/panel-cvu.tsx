import Link from "next/link";
import { Card, ErrorNotice, Notice } from "@/components/ui";
import {
  formatArs,
  formatPercent,
  formatPeriod,
  formatQuantity,
} from "@/lib/format";
import type { PanelCostos } from "@/lib/types";

const linkClass = "underline decoration-gold underline-offset-4";
const ZERO_PERCENT = /^-?0+(\.0+)?$/;
// Notices that this panel already explains in its own blocks.
const AVISOS_PROPIOS = new Set(["VOLUMEN_PRODUCIDO"]);

export function BloqueConError({ message }: { message: string }) {
  return (
    <Card>
      <ErrorNotice title="No pudimos cargar el panel." message={message} />
    </Card>
  );
}

// The API sends the percentage already calculated; only the sign is read as text here.
function Variacion({ value }: { value: string | null }) {
  if (value === null) {
    return <span className="text-muted">Sin mes anterior para comparar</span>;
  }
  if (ZERO_PERCENT.test(value)) {
    return <span className="text-muted">Igual que el mes pasado</span>;
  }
  const bajo = value.startsWith("-");
  return (
    <span className={bajo ? "text-ink-soft" : "text-bordeaux"}>
      {bajo ? "▼ Bajó " : "▲ Subió "}
      {formatPercent(bajo ? value.slice(1) : value)} vs. el mes pasado
    </span>
  );
}

function Cifra({
  titulo,
  valor,
  detalle,
}: {
  titulo: string;
  valor: string;
  detalle?: string;
}) {
  return (
    <div className="rounded-card border border-line p-4">
      <h3 className="text-sm text-muted">{titulo}</h3>
      <p className="mt-2 text-2xl font-bold tabular-nums">{valor}</p>
      {detalle && <p className="mt-1 text-xs text-muted">{detalle}</p>}
    </div>
  );
}

function Resumen({ panel }: { panel: PanelCostos }) {
  const { actual, variacion_pct: variacion } = panel;
  return (
    <Card>
      <p className="text-sm text-muted">
        Costo total de {formatPeriod(panel.periodo)}
      </p>
      <p className="mt-2 text-4xl font-bold tabular-nums sm:text-5xl">
        {formatArs(actual.costo_total)}
      </p>
      <p className="mt-2 text-base">
        {actual.total_por_unidad === null
          ? "Todavía no se puede calcular cuánto cuesta cada unidad."
          : `Cada unidad cuesta ${formatArs(actual.total_por_unidad)} entre fabricarla y su parte de los costos fijos.`}
      </p>
      <p className="mt-1 text-sm">
        <Variacion value={variacion.total_por_unidad} />
      </p>
      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <Cifra
          titulo="Unidades producidas"
          valor={formatQuantity(actual.unidades)}
          detalle="Lo producido en el mes, no lo vendido"
        />
        <Cifra
          titulo="Costos variables"
          valor={formatArs(actual.costo_variable_total)}
          detalle={`${formatArs(actual.costo_variable_por_unidad)} por unidad: materiales y mano de obra`}
        />
        <Cifra
          titulo="Costos fijos"
          valor={actual.fijos_cargados ? formatArs(actual.fijos_fabrica) : "—"}
          detalle={
            actual.fijo_por_unidad === null
              ? "Alquiler, sueldos y servicios"
              : `${formatArs(actual.fijo_por_unidad)} por unidad`
          }
        />
      </div>
    </Card>
  );
}

/** The bar is only a picture: the printed percentage is the API's. */
function Estructura({ panel }: { panel: PanelCostos }) {
  const pct = panel.actual.fijos_pct_del_total;
  if (pct === null) return null;
  const ancho = Math.min(100, Math.max(0, Number(pct)));
  return (
    <Card>
      <h2 className="text-xl">De qué está hecho el costo</h2>
      <div
        role="img"
        aria-label={`Los costos fijos son el ${formatPercent(pct)} del costo total`}
        className="mt-4 flex h-4 overflow-hidden rounded-full bg-gold"
      >
        <div className="h-4 bg-bordeaux" style={{ width: `${ancho}%` }} />
      </div>
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <span>
          <span className="mr-2 inline-block size-3 rounded-full bg-bordeaux align-middle" />
          Costos fijos: <strong>{formatPercent(pct)}</strong>
        </span>
        <span>
          <span className="mr-2 inline-block size-3 rounded-full bg-gold align-middle" />
          Costos variables
        </span>
      </div>
      <p className="mt-3 text-sm text-muted">
        Cuantas más unidades producís, menos pesan los costos fijos en cada una.
      </p>
    </Card>
  );
}

function ComparacionConElMesPasado({ panel }: { panel: PanelCostos }) {
  const { actual, anterior, variacion_pct: variacion } = panel;
  const filas = [
    {
      titulo: "Costo de fabricar por unidad",
      ahora: actual.costo_variable_por_unidad,
      antes: anterior.costo_variable_por_unidad,
      variacion: variacion.costo_variable_por_unidad,
    },
    {
      titulo: "Costo total por unidad",
      ahora: actual.total_por_unidad,
      antes: anterior.total_por_unidad,
      variacion: variacion.total_por_unidad,
    },
    {
      titulo: "Costos fijos del mes",
      ahora: actual.fijos_cargados ? actual.fijos_fabrica : null,
      antes: anterior.fijos_cargados ? anterior.fijos_fabrica : null,
      variacion: variacion.fijos_fabrica,
    },
  ];
  return (
    <Card>
      <h2 className="text-xl">
        Comparado con {formatPeriod(panel.periodo_anterior)}
      </h2>
      <ul className="mt-4 divide-y divide-line">
        {filas.map((fila) => (
          <li
            key={fila.titulo}
            className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-3"
          >
            <span>
              {fila.titulo}
              <span className="block text-xs text-muted">
                Antes: {formatArs(fila.antes)}
              </span>
            </span>
            <span className="text-right">
              <strong className="tabular-nums">{formatArs(fila.ahora)}</strong>
              <span className="block text-sm">
                <Variacion value={fila.variacion} />
              </span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

const PENDIENTES: Record<string, { link: string; href: string }> = {
  FIJOS_NO_CARGADOS: { link: "Cargar costos fijos", href: "/costos-fijos" },
  FIJOS_PENDIENTES: { link: "Completar montos", href: "/costos-fijos" },
  FIJOS_FICTICIOS: { link: "Revisar costos fijos", href: "/costos-fijos" },
  DOLAR_VIEJO: { link: "Actualizar el dólar", href: "/dolar" },
  PRECIOS_VIEJOS: { link: "Revisar precios", href: "/materiales" },
  PRODUCTOS_SIN_COSTO: { link: "Ver productos", href: "/productos" },
  SIN_UNIDADES: { link: "Ir a fabricación", href: "/fabricacion" },
};

export function PorRevisar({ panel }: { panel: PanelCostos }) {
  const avisos = panel.avisos.filter(
    (aviso) => !AVISOS_PROPIOS.has(aviso.codigo),
  );
  if (!avisos.length) return null;
  return (
    <Card>
      <h2 className="mb-3 text-xl">Para revisar</h2>
      <ul className="space-y-2 text-sm">
        {avisos.map((aviso) => {
          const destino = PENDIENTES[aviso.codigo];
          return (
            <li key={aviso.codigo}>
              {aviso.texto}{" "}
              {destino && (
                <Link className={linkClass} href={destino.href}>
                  {destino.link}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

export function PanelCvu({ panel }: { panel: PanelCostos }) {
  if (panel.actual.costo_total === null) {
    return (
      <Notice
        title={`Todavía no se puede calcular el costo de ${formatPeriod(panel.periodo)}.`}
      >
        Hace falta que haya lotes del mes con productos que tengan costo y los
        costos fijos cargados.{" "}
        <Link className={linkClass} href="/fabricacion">
          Ir a fabricación
        </Link>
      </Notice>
    );
  }
  return (
    <>
      <Resumen panel={panel} />
      <div className="grid gap-5 lg:grid-cols-2">
        <Estructura panel={panel} />
        <ComparacionConElMesPasado panel={panel} />
      </div>
    </>
  );
}
