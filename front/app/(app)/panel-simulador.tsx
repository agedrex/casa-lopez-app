import Link from "next/link";
import { buttonClass, labelClass } from "@/components/cueros/estilos";
import { inputClass } from "@/components/form";
import { Card, Notice, SectionTitle } from "@/components/ui";
import { formatArs, formatPeriod, formatQuantity } from "@/lib/format";
import type { PanelCostos } from "@/lib/types";

const linkClass = "underline decoration-gold underline-offset-4";
const AVISOS_DE_FIJOS = [
  "FIJOS_NO_CARGADOS",
  "FIJOS_PENDIENTES",
  "FIJOS_FICTICIOS",
];

function Resultado({ panel, precio }: { panel: PanelCostos; precio: string }) {
  const { equilibrio, costo_variable_por_unidad: variable } = panel.actual;
  switch (equilibrio.motivo) {
    case "SIN_PRECIO":
      return (
        <p className="text-sm text-muted">
          Escribí un precio de venta y tocá “Calcular” para ver cuántas unidades
          hay que vender.
        </p>
      );
    case "PRECIO_NO_CUBRE_COSTO_VARIABLE":
      return (
        <Notice title="Con este precio no alcanzás a cubrir ni el costo de fabricar.">
          Probaste {formatArs(precio)} y fabricar una unidad cuesta{" "}
          {formatArs(variable)}. Probá con un precio más alto.
        </Notice>
      );
    case "SIN_COSTO_VARIABLE":
      return (
        <Notice title="Todavía no se puede calcular el costo de fabricar.">
          Hacen falta lotes de este mes con productos que tengan costo.{" "}
          <Link className={linkClass} href="/fabricacion">
            Ir a fabricación
          </Link>
        </Notice>
      );
    case "SIN_FIJOS":
      return (
        <Notice
          title={`Faltan los costos fijos de la Fábrica de ${formatPeriod(panel.periodo)}.`}
        >
          Sin ellos no se puede calcular el punto de equilibrio.{" "}
          <Link className={linkClass} href="/costos-fijos">
            Cargar costos fijos
          </Link>
        </Notice>
      );
    default:
      return (
        <div className="rounded-card border border-gold bg-parchment p-4">
          <p className="text-base">
            Con este precio, cubrís los costos fijos de Fábrica vendiendo{" "}
            <strong className="font-display text-2xl">
              {formatQuantity(equilibrio.unidades)}
            </strong>{" "}
            unidades por mes.
          </p>
          <p className="mt-3 text-sm text-muted">
            Cada unidad vendida a {formatArs(precio)} te deja{" "}
            {formatArs(equilibrio.margen_por_unidad)} después de pagar el costo
            de fabricar.
          </p>
        </div>
      );
  }
}

export function Simulador({
  panel,
  precio,
  precioInvalido,
}: {
  panel: PanelCostos;
  /** Valid price already sent to the API (as typed), or null. */
  precio: string | null;
  /** What the person typed when it is not a valid price. */
  precioInvalido: string | null;
}) {
  const avisosDeFijos = panel.avisos.filter((aviso) =>
    AVISOS_DE_FIJOS.includes(aviso.codigo),
  );
  return (
    <Card>
      <SectionTitle>Punto de equilibrio</SectionTitle>
      <p className="mb-5 text-sm text-muted">
        Probá un precio de venta y mirá cuántas unidades por mes hacen falta
        para cubrir los costos fijos de la Fábrica. Por ahora solo cuenta la
        Fábrica, no la tienda.
      </p>
      {avisosDeFijos.length > 0 && (
        <div className="mb-5 space-y-3">
          {avisosDeFijos.map((aviso) => (
            <Notice key={aviso.codigo} title={aviso.texto}>
              <Link className={linkClass} href="/costos-fijos">
                Revisar costos fijos
              </Link>
            </Notice>
          ))}
        </div>
      )}
      <form method="get" action="/" className="space-y-3">
        <div>
          <label htmlFor="panel-precio" className={labelClass}>
            Precio de venta que querés probar
          </label>
          <input
            id="panel-precio"
            name="precio"
            inputMode="decimal"
            autoComplete="off"
            placeholder="Por ejemplo, 85000"
            defaultValue={precio ?? precioInvalido ?? ""}
            className={inputClass}
          />
        </div>
        <button type="submit" className={buttonClass}>
          Calcular
        </button>
      </form>
      <p className="mt-3 text-xs text-muted">
        Es solo una simulación: el precio no se guarda.
      </p>
      {precioInvalido !== null && (
        <p role="alert" className="mt-3 text-sm text-bordeaux">
          “{precioInvalido}” no sirve como precio. Escribí un número mayor que
          cero, por ejemplo 85000.
        </p>
      )}
      <div className="mt-5">
        <Resultado panel={panel} precio={precio ?? ""} />
      </div>
    </Card>
  );
}
