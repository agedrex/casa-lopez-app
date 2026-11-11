import { Badge, Card, ErrorNotice } from "@/components/ui";
import {
  formatArs,
  formatDate,
  formatPercent,
  formatPeriod,
  formatQuantity,
  formatRate,
} from "@/lib/format";
import type { PanelCostos } from "@/lib/types";

export function BloqueConError({ message }: { message: string }) {
  return (
    <Card>
      <ErrorNotice title="No pudimos cargar el panel." message={message} />
    </Card>
  );
}

/** Variation vs. the previous month, computed by the API; the front only shows it. */
function Variacion({ pct }: { pct: string | null | undefined }) {
  if (pct === null || pct === undefined) return null;
  const sube = !pct.startsWith("-") && Number(pct) !== 0;
  const baja = pct.startsWith("-");
  const tono = sube ? "text-bordeaux" : baja ? "text-sage" : "text-muted";
  return (
    <span className={`text-xs font-semibold tabular-nums ${tono}`}>
      {sube ? "▲ +" : baja ? "▼ " : ""}
      {formatPercent(pct)}
      <span className="ml-1 font-normal text-muted">vs. mes anterior</span>
    </span>
  );
}

function Cifra({
  titulo,
  valor,
  detalle,
  variacion,
  destacada = false,
}: {
  titulo: string;
  valor: string;
  detalle: string;
  variacion?: string | null;
  destacada?: boolean;
}) {
  return (
    <div
      className={`flex flex-col rounded-card border p-5 shadow-card ${
        destacada ? "border-gold bg-paper-mid" : "border-line bg-surface"
      }`}
    >
      <h3 className="text-xs font-semibold uppercase tracking-caps-sm text-muted">
        {titulo}
      </h3>
      <p className="mt-3 text-3xl font-bold tabular-nums text-ink">{valor}</p>
      <div className="mt-2 min-h-4">
        <Variacion pct={variacion} />
      </div>
      <p className="mt-auto pt-3 text-xs text-muted">{detalle}</p>
    </div>
  );
}

function Fila({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line/70 py-2.5 text-sm last:border-0">
      <dt className="text-muted">{etiqueta}</dt>
      <dd className="font-semibold tabular-nums">{valor}</dd>
    </div>
  );
}

export function PanelCvu({ panel }: { panel: PanelCostos }) {
  const { actual, variacion_pct: variacion } = panel;
  const fijos = actual.fijos_cargados;
  const subidas = panel.precios_que_subieron;

  return (
    <div className="space-y-6">
      <section aria-labelledby="resumen-titulo">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="resumen-titulo" className="text-xl">
            {formatPeriod(panel.periodo)}
          </h2>
          {panel.dolar ? (
            <Badge tone={panel.dolar_viejo ? "warn" : "neutral"}>
              Dólar {formatRate(panel.dolar.ars_por_usd)} ·{" "}
              {formatDate(panel.dolar.fecha)}
            </Badge>
          ) : null}
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Cifra
            destacada
            titulo="Costo total por unidad"
            valor={formatArs(actual.total_por_unidad)}
            variacion={variacion.total_por_unidad}
            detalle="Variable más fijo, por unidad producida"
          />
          <Cifra
            titulo="Costos fijos del mes"
            valor={fijos ? formatArs(actual.fijos_fabrica) : "—"}
            variacion={variacion.fijos_fabrica}
            detalle="Total de la fábrica, sueldos incluidos"
          />
          <Cifra
            titulo="Costos variables del mes"
            valor={formatArs(actual.costo_variable_total)}
            variacion={variacion.costo_variable_por_unidad}
            detalle="Lo que costó fabricar lo producido"
          />
          <Cifra
            titulo="Unidades producidas"
            valor={formatQuantity(actual.unidades)}
            detalle="Lo producido en el mes, no lo vendido"
          />
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-2 text-lg">Estructura del costo</h2>
          <dl>
            <Fila
              etiqueta="Costo variable por unidad"
              valor={formatArs(actual.costo_variable_por_unidad)}
            />
            <Fila
              etiqueta="Costo fijo por unidad"
              valor={fijos ? formatArs(actual.fijo_por_unidad) : "—"}
            />
            <Fila
              etiqueta="Mano de obra (sueldos de fábrica)"
              valor={fijos ? formatArs(actual.sueldos_fabrica) : "—"}
            />
            <Fila
              etiqueta="Peso de los fijos en el total"
              valor={formatPercent(actual.fijos_pct_del_total)}
            />
          </dl>
        </Card>

        <Card>
          <h2 className="mb-2 text-lg">Precios de materiales</h2>
          {subidas.length === 0 ? (
            <p className="text-sm text-muted">
              Ningún precio subió respecto del período anterior.
            </p>
          ) : (
            <ul>
              {subidas.slice(0, 5).map((precio) => (
                <li
                  key={`${precio.material}-${precio.color ?? ""}`}
                  className="flex items-baseline justify-between gap-4 border-b border-line/70 py-2.5 text-sm last:border-0"
                >
                  <span>
                    {precio.material}
                    {precio.color ? ` · ${precio.color}` : ""}
                  </span>
                  <Badge tone={precio.salto_grande ? "alert" : "warn"}>
                    +{formatPercent(precio.variacion_pct)}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
          {panel.precios_viejos.cantidad > 0 ? (
            <p className="mt-3 text-xs text-muted">
              {panel.precios_viejos.cantidad} precios sin actualizar
              {panel.precios_viejos.mas_viejos[0]
                ? ` (el más viejo, ${panel.precios_viejos.mas_viejos[0].material}, desde ${formatDate(panel.precios_viejos.mas_viejos[0].vigente_desde)})`
                : ""}
              .
            </p>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
