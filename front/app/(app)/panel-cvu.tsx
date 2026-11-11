import { Card, ErrorNotice } from "@/components/ui";
import { formatArs, formatPeriod, formatQuantity } from "@/lib/format";
import type { PanelCostos } from "@/lib/types";

export function BloqueConError({ message }: { message: string }) {
  return (
    <Card>
      <ErrorNotice title="No pudimos cargar el panel." message={message} />
    </Card>
  );
}

function Cifra({
  titulo,
  valor,
  detalle,
}: {
  titulo: string;
  valor: string;
  detalle: string;
}) {
  return (
    <div className="rounded-card border border-line p-4">
      <h3 className="text-sm text-muted">{titulo}</h3>
      <p className="mt-2 text-2xl font-bold tabular-nums">{valor}</p>
      <p className="mt-1 text-xs text-muted">{detalle}</p>
    </div>
  );
}

export function PanelCvu({ panel }: { panel: PanelCostos }) {
  const { actual } = panel;
  const fijos = actual.fijos_cargados;
  return (
    <Card>
      <h2 className="text-xl">Resumen de {formatPeriod(panel.periodo)}</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Cifra
          titulo="Costos fijos del mes"
          valor={fijos ? formatArs(actual.fijos_fabrica) : "—"}
          detalle="Total de la fábrica, sueldos incluidos"
        />
        <Cifra
          titulo="Costos variables del mes"
          valor={formatArs(actual.costo_variable_total)}
          detalle="Lo que costó fabricar lo producido"
        />
        <Cifra
          titulo="Unidades producidas"
          valor={formatQuantity(actual.unidades)}
          detalle="Lo producido en el mes, no lo vendido"
        />
        <Cifra
          titulo="Mano de obra"
          valor={fijos ? formatArs(actual.sueldos_fabrica) : "—"}
          detalle="Total en sueldos de la fábrica"
        />
      </div>
    </Card>
  );
}
