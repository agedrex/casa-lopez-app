import Link from "next/link";
import { buttonClass, labelClass } from "@/components/cueros/estilos";
import { inputClass } from "@/components/form";
import { Card, ErrorNotice, Notice } from "@/components/ui";
import {
  formatArs,
  formatPercent,
  formatPeriod,
  formatQuantity,
} from "@/lib/format";
import type { CvuMes, PanelCostos } from "@/lib/types";
import { guardarPrecio } from "./panel-actions";

const linkClass = "underline decoration-gold underline-offset-4";
const CERO = /^-?0+(\.0+)?$/;
// Notices that this panel already explains in its own blocks.
const AVISOS_PROPIOS = new Set(["VOLUMEN_PRODUCIDO"]);

export function BloqueConError({ message }: { message: string }) {
  return (
    <Card>
      <ErrorNotice title="No pudimos cargar el panel." message={message} />
    </Card>
  );
}

export function FormularioPrecio({
  precio,
  invalido,
}: {
  precio: string | null;
  invalido: string | null;
}) {
  return (
    <Card>
      <form action={guardarPrecio} className="flex flex-wrap items-end gap-3">
        <div className="min-w-48 flex-1">
          <label htmlFor="panel-precio" className={labelClass}>
            Precio de venta promedio por unidad
          </label>
          <input
            id="panel-precio"
            name="precio"
            inputMode="decimal"
            autoComplete="off"
            defaultValue={precio ?? invalido ?? ""}
            className={inputClass}
          />
        </div>
        <button type="submit" className={buttonClass}>
          Ver resultado
        </button>
      </form>
      {invalido !== null && (
        <p role="alert" className="mt-3 text-sm text-bordeaux">
          “{invalido}” no sirve como precio. Escribí un número mayor que cero.
        </p>
      )}
    </Card>
  );
}

function Cifra({
  titulo,
  valor,
  detalle,
  signo,
}: {
  titulo: string;
  valor: string;
  detalle?: string;
  signo?: "menos" | "igual";
}) {
  return (
    <div className="rounded-card border border-line p-4">
      <h3 className="text-sm text-muted">
        {signo === "menos" ? "− " : signo === "igual" ? "= " : ""}
        {titulo}
      </h3>
      <p className="mt-2 font-display text-2xl tabular-nums">{valor}</p>
      {detalle && <p className="mt-1 text-xs text-muted">{detalle}</p>}
    </div>
  );
}

function Resultado({
  cvu,
  panel,
  precio,
}: {
  cvu: CvuMes;
  panel: PanelCostos;
  precio: string;
}) {
  const perdida = cvu.utilidad.startsWith("-");
  const justo = CERO.test(cvu.utilidad);
  const anterior = panel.anterior.cvu;
  return (
    <Card>
      <p className="text-sm text-muted">
        Resultado de {formatPeriod(panel.periodo)}
      </p>
      <p
        className={`mt-2 font-display text-4xl tabular-nums sm:text-5xl ${perdida ? "text-bordeaux" : ""}`}
      >
        {formatArs(cvu.utilidad)}
      </p>
      <p className="mt-2 text-base">
        {justo
          ? "Estás justo en el punto de equilibrio: no ganás ni perdés."
          : perdida
            ? "Con este precio, el mes termina en pérdida."
            : "Es lo que queda después de pagar todos los costos."}
      </p>
      {anterior && (
        <p className="mt-1 text-sm text-muted">
          {formatPeriod(panel.periodo_anterior)}: {formatArs(anterior.utilidad)}
        </p>
      )}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Cifra
          titulo="Ventas"
          valor={formatArs(cvu.ingresos)}
          detalle={`${formatQuantity(panel.actual.unidades)} unidades a ${formatArs(precio)}`}
        />
        <Cifra
          signo="menos"
          titulo="Costo de fabricar"
          valor={formatArs(cvu.costo_variable_total)}
          detalle="Materiales y mano de obra"
        />
        <Cifra
          signo="menos"
          titulo="Costos fijos"
          valor={formatArs(cvu.costos_fijos)}
          detalle="Alquiler, sueldos y servicios"
        />
        <Cifra
          signo="igual"
          titulo="Ganancia"
          valor={formatArs(cvu.utilidad)}
        />
      </div>
    </Card>
  );
}

/** The bar is only a picture: the printed numbers are the API's. */
function BarraEquilibrio({
  unidades,
  equilibrio,
}: {
  unidades: string;
  equilibrio: string;
}) {
  const total = Number(unidades);
  const meta = Number(equilibrio);
  const maximo = Math.max(total, meta);
  if (!Number.isFinite(maximo) || maximo <= 0) return null;
  const marca = (meta / maximo) * 100;
  const llenado = (total / maximo) * 100;
  const alcanza = total >= meta;
  return (
    <div
      role="img"
      aria-label={`Producís ${formatQuantity(unidades)} unidades y necesitás ${formatQuantity(equilibrio)}`}
      className="relative mt-4 h-4 rounded-full bg-parchment"
    >
      <div
        className={`h-4 rounded-full ${alcanza ? "bg-gold" : "bg-blush-deep"}`}
        style={{ width: `${llenado}%` }}
      />
      <div
        className="absolute top-[-4px] h-6 w-0.5 bg-ink"
        style={{ left: `${marca}%` }}
      />
    </div>
  );
}

function Equilibrio({ cvu, panel }: { cvu: CvuMes; panel: PanelCostos }) {
  const unidades = panel.actual.unidades;
  const alcanza = !cvu.margen_seguridad_pct.startsWith("-");
  return (
    <Card>
      <h2 className="text-xl">Cuánto tenés que vender para no perder</h2>
      <p className="mt-3 text-base">
        <strong className="font-display text-3xl tabular-nums">
          {formatQuantity(cvu.equilibrio_unidades)}
        </strong>{" "}
        unidades por mes, que son{" "}
        <strong>{formatArs(cvu.equilibrio_ingresos)}</strong> en ventas.
      </p>
      <BarraEquilibrio
        unidades={unidades}
        equilibrio={cvu.equilibrio_unidades}
      />
      <p className="mt-3 text-sm text-muted">
        Este mes: {formatQuantity(unidades)} unidades.{" "}
        {alcanza
          ? `Estás ${formatPercent(cvu.margen_seguridad_pct)} por encima del mínimo.`
          : `Te falta ${formatPercent(cvu.margen_seguridad_pct.slice(1))} para llegar.`}
      </p>
    </Card>
  );
}

function Contribucion({ cvu }: { cvu: CvuMes }) {
  return (
    <Card>
      <h2 className="text-xl">Lo que deja cada venta</h2>
      <p className="mt-3 text-base">
        Cada unidad deja{" "}
        <strong className="font-display text-3xl tabular-nums">
          {formatArs(cvu.margen_contribucion_unidad)}
        </strong>{" "}
        después de pagar su costo de fabricar.
      </p>
      <p className="mt-3 text-sm text-muted">
        De cada 100 pesos que vendés, {formatArs(cvu.margen_contribucion_pct)}{" "}
        sirven para pagar los costos fijos y ganar.
      </p>
    </Card>
  );
}

function CostoPorUnidad({ panel }: { panel: PanelCostos }) {
  const { actual } = panel;
  return (
    <Card>
      <h2 className="text-xl">Cuánto cuesta cada unidad</h2>
      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        <Cifra
          titulo="Fabricarla"
          valor={formatArs(actual.costo_variable_por_unidad)}
          detalle="Materiales y mano de obra"
        />
        <Cifra
          titulo="Parte de los costos fijos"
          valor={formatArs(actual.fijo_por_unidad)}
          detalle={`Repartidos en ${formatQuantity(actual.unidades)} unidades`}
        />
        <Cifra
          titulo="Costo total"
          valor={formatArs(actual.total_por_unidad)}
        />
      </div>
    </Card>
  );
}

function SinResultado({
  panel,
  precio,
}: {
  panel: PanelCostos;
  precio: string | null;
}) {
  const { equilibrio } = panel.actual;
  if (precio === null) {
    return (
      <Notice
        tone="info"
        title="Escribí un precio de venta para ver el resultado."
      >
        Con el precio y lo que producís este mes calculamos ventas, ganancia y
        punto de equilibrio.
      </Notice>
    );
  }
  if (equilibrio.motivo === "PRECIO_NO_CUBRE_COSTO_VARIABLE") {
    return (
      <Notice title="Con este precio no se cubre ni el costo de fabricar.">
        Fabricar una unidad cuesta{" "}
        {formatArs(panel.actual.costo_variable_por_unidad)} y la vendés a{" "}
        {formatArs(precio)}. Probá con un precio más alto.
      </Notice>
    );
  }
  if (equilibrio.motivo === "SIN_FIJOS") {
    return (
      <Notice
        title={`Faltan los costos fijos de ${formatPeriod(panel.periodo)}.`}
      >
        Sin ellos no se puede calcular la ganancia.{" "}
        <Link className={linkClass} href="/costos-fijos">
          Cargar costos fijos
        </Link>
      </Notice>
    );
  }
  return (
    <Notice title="Todavía no hay producción este mes.">
      Hace falta que haya lotes del mes con productos que tengan costo.{" "}
      <Link className={linkClass} href="/fabricacion">
        Ir a fabricación
      </Link>
    </Notice>
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

export function PanelCvu({
  panel,
  precio,
}: {
  panel: PanelCostos;
  precio: string | null;
}) {
  const cvu = panel.actual.cvu;
  return (
    <>
      {cvu && precio !== null ? (
        <>
          <Resultado cvu={cvu} panel={panel} precio={precio} />
          <div className="grid gap-5 lg:grid-cols-2">
            <Equilibrio cvu={cvu} panel={panel} />
            <Contribucion cvu={cvu} />
          </div>
        </>
      ) : (
        <SinResultado panel={panel} precio={precio} />
      )}
      <CostoPorUnidad panel={panel} />
      <p className="text-xs text-muted">
        El volumen es lo producido en el mes, no lo vendido.
      </p>
    </>
  );
}
