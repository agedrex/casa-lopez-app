import Link from "next/link";
import { Badge, Card, Notice, SectionTitle } from "@/components/ui";
import {
  formatArs,
  formatDate,
  formatPercent,
  formatPeriod,
  formatQuantity,
  formatRate,
} from "@/lib/format";
import type { AvisoPanel, PanelCostos } from "@/lib/types";

const linkClass = "underline decoration-gold underline-offset-4";
const ZERO_PERCENT = /^-?0+(\.0+)?$/;

// Notices that have their own spot on the screen (the break-even block or the "stale" block).
const AVISOS_CON_LUGAR_PROPIO = new Set([
  "FIJOS_NO_CARGADOS",
  "FIJOS_PENDIENTES",
  "FIJOS_FICTICIOS",
  "VOLUMEN_PRODUCIDO",
  "DOLAR_VIEJO",
  "PRECIOS_VIEJOS",
]);

export function Avisos({ avisos }: { avisos: AvisoPanel[] }) {
  const visibles = avisos.filter(
    (aviso) => !AVISOS_CON_LUGAR_PROPIO.has(aviso.codigo),
  );
  if (!visibles.length) return null;
  return (
    <div className="mb-6 space-y-3">
      {visibles.map((aviso) => (
        <Notice key={aviso.codigo} title={aviso.texto} />
      ))}
    </div>
  );
}

// The API sends the percentage already calculated; only the sign is read as text here.
function Variacion({ value }: { value: string | null }) {
  if (value === null) {
    return (
      <span className="text-sm text-muted">Sin mes anterior para comparar</span>
    );
  }
  if (ZERO_PERCENT.test(value)) {
    return <span className="text-sm text-muted">Igual que el mes pasado</span>;
  }
  const bajo = value.startsWith("-");
  return (
    <span className={`text-sm ${bajo ? "text-ink-soft" : "text-bordeaux"}`}>
      {bajo ? "▼ Bajó " : "▲ Subió "}
      {formatPercent(bajo ? value.slice(1) : value)} vs. el mes pasado
    </span>
  );
}

function Cifra({
  titulo,
  valor,
  variacion,
  destacada = false,
}: {
  titulo: string;
  valor: string;
  variacion?: string | null;
  destacada?: boolean;
}) {
  return (
    <div
      className={`rounded-card border p-4 ${destacada ? "border-gold bg-parchment" : "border-line"}`}
    >
      <h3 className="text-sm text-muted">{titulo}</h3>
      <p className="mt-2 font-display text-2xl sm:text-3xl">{valor}</p>
      {variacion !== undefined && (
        <p className="mt-2">
          <Variacion value={variacion} />
        </p>
      )}
    </div>
  );
}

export function CostoDelMes({ panel }: { panel: PanelCostos }) {
  const { actual, variacion_pct: variacion } = panel;
  const aviso = panel.avisos.find(
    (item) => item.codigo === "VOLUMEN_PRODUCIDO",
  );
  return (
    <Card>
      <SectionTitle>Cuánto cuesta producir este mes</SectionTitle>
      <p className="mb-5 text-sm text-muted">
        Por cada unidad producida en {formatPeriod(panel.periodo)}.{" "}
        <strong>Unidades producidas, no vendidas.</strong>
        {aviso ? ` ${aviso.texto}` : ""}
      </p>
      {actual.total_por_unidad === null && (
        <div className="mb-4">
          <Notice title="Todavía no se puede calcular el costo total por unidad.">
            Hace falta que haya lotes fabricados este mes y productos con costo
            calculado.{" "}
            <Link className={linkClass} href="/fabricacion">
              Ir a fabricación
            </Link>
          </Notice>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Cifra
          titulo="Costo de fabricar (materiales y mano de obra)"
          valor={formatArs(actual.costo_variable_por_unidad)}
          variacion={variacion.costo_variable_por_unidad}
        />
        <Cifra
          titulo="Costo fijo de la Fábrica, repartido"
          valor={formatArs(actual.fijo_por_unidad)}
          variacion={variacion.fijos_fabrica}
        />
        <Cifra
          titulo="Costo total por unidad"
          valor={formatArs(actual.total_por_unidad)}
          variacion={variacion.total_por_unidad}
          destacada
        />
        <Cifra
          titulo="Unidades producidas"
          valor={formatQuantity(actual.unidades)}
        />
      </div>
      <p className="mt-4 text-xs text-muted">
        La variación del costo fijo compara el total del mes, no el repartido
        por unidad.
      </p>
      <Link
        className={`mt-4 inline-block text-sm ${linkClass}`}
        href="/fabricacion"
      >
        Ver fabricación
      </Link>
    </Card>
  );
}

export function QueSubio({ panel }: { panel: PanelCostos }) {
  const subieron = panel.precios_que_subieron;
  return (
    <Card>
      <SectionTitle>Qué subió</SectionTitle>
      {subieron.length ? (
        <>
          <p className="mb-4 text-sm text-muted">
            Materiales cuyo último precio es más alto que el anterior.
          </p>
          <ul className="space-y-3">
            {subieron.map((precio) => (
              <li
                key={`${precio.material}-${precio.color ?? ""}-${precio.vigente_desde}`}
                className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm"
              >
                <span className="min-w-0">
                  {precio.material}
                  {precio.color ? ` · ${precio.color}` : ""}
                  <span className="block text-xs text-muted">
                    Desde el {formatDate(precio.vigente_desde)}
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  {precio.salto_grande && (
                    <Badge tone="warn">Salto grande</Badge>
                  )}
                  <strong className="tabular-nums text-bordeaux">
                    +{formatPercent(precio.variacion_pct)}
                  </strong>
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="text-sm text-muted">
          No hay materiales que hayan subido de precio. 👍
        </p>
      )}
      <Link
        className={`mt-5 inline-block text-sm ${linkClass}`}
        href="/materiales"
      >
        Ver materiales y precios
      </Link>
    </Card>
  );
}

function Pendiente({
  texto,
  href,
  link,
}: {
  texto: string;
  href: string;
  link: string;
}) {
  return (
    <li className="text-sm">
      {texto}{" "}
      <Link className={linkClass} href={href}>
        {link}
      </Link>
    </li>
  );
}

export function QueEstaViejo({ panel }: { panel: PanelCostos }) {
  const { actual, dolar, precios_viejos: viejos } = panel;
  const items: React.ReactNode[] = [];
  if (!dolar) {
    items.push(
      <Pendiente
        key="dolar"
        texto="No hay ningún dólar cargado."
        href="/dolar"
        link="Cargar el dólar"
      />,
    );
  } else if (panel.dolar_viejo) {
    items.push(
      <Pendiente
        key="dolar"
        texto={`El dólar es del ${formatDate(dolar.fecha)} (${formatRate(dolar.ars_por_usd)} pesos por dólar).`}
        href="/dolar"
        link="Actualizar el dólar"
      />,
    );
  }
  if (viejos.cantidad > 0) {
    items.push(
      <li key="precios" className="text-sm">
        {viejos.cantidad === 1
          ? "Hay 1 precio de material sin actualizar hace tiempo."
          : `Hay ${viejos.cantidad} precios de materiales sin actualizar hace tiempo.`}{" "}
        <Link className={linkClass} href="/materiales">
          Revisar precios
        </Link>
        <ul className="mt-2 space-y-1 text-xs text-muted">
          {viejos.mas_viejos.map((precio) => (
            <li
              key={`${precio.material}-${precio.color ?? ""}-${precio.vigente_desde}`}
            >
              {precio.material}
              {precio.color ? ` · ${precio.color}` : ""} · desde el{" "}
              {formatDate(precio.vigente_desde)}
            </li>
          ))}
        </ul>
      </li>,
    );
  }
  if (!actual.fijos_cargados) {
    items.push(
      <Pendiente
        key="fijos"
        texto={`Faltan cargar los costos fijos de ${formatPeriod(panel.periodo)}.`}
        href="/costos-fijos"
        link="Cargar costos fijos"
      />,
    );
  }
  if (actual.fijos_pendientes > 0) {
    items.push(
      <Pendiente
        key="pendientes"
        texto={
          actual.fijos_pendientes === 1
            ? "Hay 1 costo fijo de la Fábrica sin monto."
            : `Hay ${actual.fijos_pendientes} costos fijos de la Fábrica sin monto.`
        }
        href="/costos-fijos"
        link="Completar montos"
      />,
    );
  }
  if (actual.fijos_ficticios) {
    items.push(
      <Pendiente
        key="ficticios"
        texto="Algunos costos fijos son de ejemplo, no reales."
        href="/costos-fijos"
        link="Cargar los reales"
      />,
    );
  }
  return (
    <Card>
      <SectionTitle>Qué está viejo</SectionTitle>
      {items.length ? (
        <ul className="space-y-3">{items}</ul>
      ) : (
        <p className="text-sm text-muted">
          Todo está al día: el dólar, los precios y los costos fijos. 👍
        </p>
      )}
    </Card>
  );
}
