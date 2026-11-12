import { Badge, Card, ErrorNotice } from "@/components/ui";
import {
  formatArs,
  formatDate,
  formatPercent,
  formatPeriod,
  formatQuantity,
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
        <h2 id="resumen-titulo" className="mb-3 text-xl">
          {formatPeriod(panel.periodo)}
        </h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <Cifra
            titulo="Costos fijos del mes"
            valor={fijos ? formatArs(actual.fijos_fabrica) : "—"}
            variacion={variacion.fijos_fabrica}
          />
          <Cifra
            titulo="Costos variables del mes"
            valor={formatArs(actual.costo_variable_total)}
            variacion={variacion.costo_variable_por_unidad}
          />
          <Cifra
            titulo="Unidades producidas"
            valor={formatQuantity(actual.unidades)}
          />
        </div>
      </section>

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
  );
}
