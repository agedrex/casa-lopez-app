import Link from "next/link";
import { Badge, Card, Notice, SectionTitle } from "@/components/ui";
import { formatArs, formatPeriod, formatQuantity } from "@/lib/format";
import type {
  MesTendencia,
  MotivoIncompleto,
  TendenciaCostos,
} from "@/lib/types";
import { Variacion } from "./panel-costos";

const linkClass = "underline decoration-gold underline-offset-4";

const ETIQUETAS: Record<MotivoIncompleto, string> = {
  SIN_FIJOS: "Faltan costos fijos",
  FIJOS_PENDIENTES: "Hay montos pendientes",
  FIJOS_FICTICIOS: "Montos de ejemplo",
  SIN_UNIDADES: "Sin producción cargada",
  PRODUCTOS_SIN_COSTO: "Productos sin costo",
};

// Why a value can be missing: only the reasons that stop a figure from being calculated.
const RAZONES: Partial<Record<MotivoIncompleto, string>> = {
  SIN_UNIDADES: "no hay producción cargada",
  SIN_FIJOS: "faltan cargar los costos fijos",
  FIJOS_PENDIENTES: "hay costos fijos sin monto",
  PRODUCTOS_SIN_COSTO: "hay productos sin costo calculado",
};

const MOTIVOS_DE_FIJOS: MotivoIncompleto[] = [
  "SIN_FIJOS",
  "FIJOS_PENDIENTES",
  "FIJOS_FICTICIOS",
];

function razonDeFalta(mes: MesTendencia): string {
  const razones = mes.incompleto
    .map((codigo) => RAZONES[codigo])
    .filter((razon): razon is string => razon !== undefined);
  return razones.length
    ? `Sin dato: ${razones.join(" y ")}.`
    : "Todavía no se puede calcular.";
}

/** The bar is only a picture: its width is scaled to the biggest month, every printed amount is the API's string. */
function Barra({ mes, maximo }: { mes: MesTendencia; maximo: number }) {
  const valor =
    mes.total_por_unidad === null ? 0 : Number(mes.total_por_unidad);
  const ancho = maximo > 0 ? Math.max(2, (valor / maximo) * 100) : 0;
  return (
    <svg
      viewBox="0 0 100 6"
      preserveAspectRatio="none"
      role="img"
      aria-label={
        mes.total_por_unidad === null
          ? `${formatPeriod(mes.periodo)}: sin costo por unidad`
          : `${formatPeriod(mes.periodo)}: ${formatArs(mes.total_por_unidad)} por unidad`
      }
      className="h-2.5 w-full"
    >
      <rect
        x="0"
        y="0"
        width="100"
        height="6"
        rx="1"
        className="fill-parchment"
      />
      {mes.total_por_unidad !== null && (
        <rect
          x="0"
          y="0"
          width={ancho}
          height="6"
          rx="1"
          className={mes.incompleto.length ? "fill-blush-deep" : "fill-gold"}
        />
      )}
    </svg>
  );
}

function Dato({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs text-muted">{titulo}</dt>
      <dd className="mt-0.5 text-sm tabular-nums">{children}</dd>
    </div>
  );
}

function Mes({ mes, maximo }: { mes: MesTendencia; maximo: number }) {
  const pideFijos = mes.incompleto.some((codigo) =>
    MOTIVOS_DE_FIJOS.includes(codigo),
  );
  return (
    <li className="rounded-card border border-line p-4">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <h3 className="font-bold">{formatPeriod(mes.periodo)}</h3>
        {mes.incompleto.length > 0 && (
          <span className="flex flex-wrap gap-1.5">
            {mes.incompleto.map((codigo) => (
              <Badge key={codigo} tone="warn">
                {ETIQUETAS[codigo] ?? codigo}
              </Badge>
            ))}
          </span>
        )}
      </div>
      <p className="mt-3 font-display text-2xl tabular-nums">
        {mes.total_por_unidad === null ? (
          <>
            —
            <span className="ml-2 font-sans text-sm text-muted">
              por unidad
            </span>
          </>
        ) : (
          <>
            {formatArs(mes.total_por_unidad)}
            <span className="ml-2 font-sans text-sm text-muted">
              por unidad
            </span>
          </>
        )}
      </p>
      <div className="mt-2">
        <Barra mes={mes} maximo={maximo} />
      </div>
      <p className="mt-2">
        {mes.total_por_unidad === null ? (
          <span className="text-sm text-muted">{razonDeFalta(mes)}</span>
        ) : (
          <Variacion
            value={mes.variacion_pct_total_por_unidad}
            contra="el mes anterior"
          />
        )}
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-3">
        <Dato titulo="Unidades producidas">
          {formatQuantity(mes.unidades)}
          {mes.incompleto.includes("PRODUCTOS_SIN_COSTO") && (
            <span className="block text-xs text-muted">
              {formatQuantity(mes.unidades_sin_costo)} sin costo
            </span>
          )}
        </Dato>
        <Dato titulo="Costos fijos de la Fábrica">
          {mes.fijos_cargados ? formatArs(mes.fijos_fabrica) : "Sin cargar"}
        </Dato>
      </dl>
      {pideFijos && (
        <Link
          className={`mt-3 inline-flex min-h-11 items-center text-sm sm:min-h-0 ${linkClass}`}
          href={`/costos-fijos?periodo=${encodeURIComponent(mes.periodo)}`}
        >
          Revisar costos fijos de {formatPeriod(mes.periodo)}
        </Link>
      )}
    </li>
  );
}

export function ComoVieneElNegocio({
  tendencia,
}: {
  tendencia: TendenciaCostos;
}) {
  // The API sends the oldest month first; the newest one goes on top.
  const meses = [...tendencia.meses].reverse();
  const maximo = Math.max(
    0,
    ...tendencia.meses
      .map((mes) =>
        mes.total_por_unidad === null ? 0 : Number(mes.total_por_unidad),
      )
      .filter((valor) => Number.isFinite(valor)),
  );
  return (
    <Card>
      <SectionTitle>Cómo viene el negocio</SectionTitle>
      <p className="mb-5 text-sm text-muted">
        Cuánto costó producir cada unidad en los últimos meses. Si a un mes le
        falta algún dato, se muestra el motivo en vez de un número inventado.
      </p>
      {meses.length ? (
        <ul className="grid gap-4 lg:grid-cols-2">
          {meses.map((mes) => (
            <Mes key={mes.periodo} mes={mes} maximo={maximo} />
          ))}
        </ul>
      ) : (
        <Notice tone="info" title="Todavía no hay meses para comparar.">
          Cuando haya producción y costos fijos cargados, vas a ver acá cómo fue
          cambiando el costo por unidad.
        </Notice>
      )}
      {tendencia.nota && (
        <p className="mt-4 text-xs text-muted">{tendencia.nota}</p>
      )}
    </Card>
  );
}
