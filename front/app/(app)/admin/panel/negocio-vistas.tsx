import Link from "next/link";
import {
  Card,
  ErrorNotice,
  Notice,
  numClass,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatArs, formatPeriod } from "@/lib/format";
import type {
  CostosFijos,
  MercaderiaDelMes,
  Persona,
  ProductoResumen,
  ProductoReventa,
} from "@/lib/types";
import { EscenarioDeVentas, type ProductOption } from "../../cvu/escenario";
import { type AreaDelNegocio, CostosAreaGrid } from "./costos-area-grid";

const PERIODO = /^\d{4}-(0[1-9]|1[0-2])$/;

const linkClass = "underline decoration-gold underline-offset-4";

function productOptions(
  productos: ProductoResumen[],
  mercaderia: ProductoReventa[],
): ProductOption[] {
  return [
    ...productos.map(({ codigo, nombre }) => ({ codigo, nombre })),
    ...mercaderia
      .filter((item) => item.activo)
      .map(({ codigo, nombre }) => ({ codigo, nombre })),
  ];
}

function Total({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <Card className="space-y-2">
      <p className="text-sm text-muted">{label}</p>
      <p className="text-3xl font-bold tabular-nums">{formatArs(value)}</p>
      {detail ? <p className="text-sm text-muted">{detail}</p> : null}
    </Card>
  );
}

/** What the store bought as Mercadería this month: charged to the store, read-only (it is loaded in Mercadería). */
function MercaderiaDelMesTabla({ datos }: { datos: MercaderiaDelMes }) {
  return (
    <section aria-label="Mercadería del mes" className="space-y-3">
      <SectionTitle>
        Mercadería comprada en {formatPeriod(datos.periodo)}
      </SectionTitle>
      <p className="max-w-3xl text-sm text-muted">
        La mercadería se compra directamente para la tienda, así que cada compra
        del mes se suma a sus costos.{" "}
        <Link className={linkClass} href="/reventa">
          Cargar compras en Mercadería
        </Link>
      </p>
      {datos.compras.length > 0 ? (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Fecha</th>
                <th className={thClass}>Producto</th>
                <th className={`${thClass} ${numClass}`}>Unidades</th>
                <th className={`${thClass} ${numClass}`}>Costo por unidad</th>
                <th className={`${thClass} ${numClass}`}>Total</th>
              </tr>
            </thead>
            <tbody>
              {datos.compras.map((compra, index) => (
                <tr key={`${compra.producto}|${compra.fecha}|${index}`}>
                  <td className={tdClass}>{compra.fecha}</td>
                  <td className={tdClass}>
                    {compra.producto_nombre}
                    <span className="block text-xs text-muted">
                      {compra.producto}
                    </span>
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {compra.unidades}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(compra.costo_unitario_ars)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(compra.total_ars)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-paper-mid font-bold">
                <th className={tdClass} scope="row" colSpan={4}>
                  Mercadería del mes
                </th>
                <td className={`${tdClass} ${numClass}`}>
                  {formatArs(datos.total_mercaderia)}
                </td>
              </tr>
            </tfoot>
          </table>
        </TableWrap>
      ) : (
        <p className="text-sm text-muted">
          No hay compras de Mercadería cargadas en este mes.
        </p>
      )}
    </section>
  );
}

/**
 * One area of the business (the factory or the store): the month's costs as a grid where they are
 * added, the total of the month, and (store only) the Mercadería bought in the month. Below it, the
 * break-even scenario of the area. Every amount comes calculated by the API.
 */
export async function NegocioVistas({
  vista,
  periodo,
}: {
  vista: "fabrica" | "tienda";
  periodo: string;
}) {
  const area: AreaDelNegocio = vista === "fabrica" ? "FABRICA" : "TIENDA";
  const query = PERIODO.test(periodo)
    ? `?periodo=${encodeURIComponent(periodo)}`
    : "";
  // SUPUESTO: 500 is the API's page maximum; it only feeds the product suggestions.
  const [costos, personas, mes, productos] = await Promise.all([
    apiGet<CostosFijos>(`/costos-fijos${query}`),
    apiGet<Persona[]>("/personas"),
    apiGet<{ periodo: string }>("/cvu/periodo"),
    apiGet<ProductoResumen[]>("/productos?limit=500"),
  ]);
  if (!costos.ok) {
    return (
      <ErrorNotice
        title="No pudimos cargar los costos."
        message={costos.message}
      />
    );
  }
  const mesDeCostos = costos.data.periodo;
  // Mercadería lives in the store: it is read with the same month the costs came for.
  const [mercaderia, listaMercaderia] =
    area === "TIENDA"
      ? await Promise.all([
          apiGet<MercaderiaDelMes>(
            `/costos-fijos/mercaderia?periodo=${encodeURIComponent(mesDeCostos)}`,
          ),
          apiGet<ProductoReventa[]>("/reventa"),
        ])
      : [null, null];

  const gastos = costos.data.gastos
    .filter((gasto) => gasto.fabrica_o_tienda === area)
    .sort(
      (a, b) =>
        a.categoria.localeCompare(b.categoria, "es-AR") ||
        a.concepto.localeCompare(b.concepto, "es-AR"),
    );
  const pendientes = gastos.filter((g) => g.monto_ars_del_mes === null).length;
  const totalGastos =
    area === "FABRICA" ? costos.data.total_fabrica : costos.data.total_tienda;

  return (
    <div className="space-y-8">
      <form method="get" className="flex flex-wrap items-end gap-3">
        <input type="hidden" name="vista" value={vista} />
        <label className="text-sm text-muted" htmlFor="negocio-mes">
          Mes
          <input
            id="negocio-mes"
            name="periodo"
            type="month"
            defaultValue={mesDeCostos}
            className="mt-1 block min-h-11 rounded-card border border-line bg-surface px-3 text-sm text-ink"
          />
        </label>
        <button
          type="submit"
          className="min-h-11 rounded-card border border-ink px-5 py-2 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white"
        >
          Ver mes
        </button>
      </form>

      <div className="grid gap-5 lg:grid-cols-2">
        {area === "TIENDA" && mercaderia?.ok ? (
          <Total
            label={`Costos de la tienda de ${formatPeriod(mesDeCostos)}`}
            value={mercaderia.data.total_tienda}
            detail={`Costos cargados ${formatArs(mercaderia.data.total_gastos_tienda)} más Mercadería ${formatArs(mercaderia.data.total_mercaderia)}.`}
          />
        ) : (
          <Total
            label={`Costos de ${area === "FABRICA" ? "la fábrica" : "la tienda"} de ${formatPeriod(mesDeCostos)}`}
            value={totalGastos}
            detail={
              pendientes > 0
                ? `${pendientes} ${pendientes === 1 ? "costo sin monto" : "costos sin monto"}: no entran en el total hasta cargarlo.`
                : undefined
            }
          />
        )}
      </div>

      {area === "TIENDA" && mercaderia && !mercaderia.ok ? (
        <Notice tone="info" title="No pudimos cargar la Mercadería">
          {mercaderia.message}
        </Notice>
      ) : null}

      <section aria-label="Costos del área" className="space-y-3">
        <SectionTitle>
          Costos de {area === "FABRICA" ? "la fábrica" : "la tienda"}
        </SectionTitle>
        <p className="max-w-3xl text-sm text-muted">
          Sueldos, servicios, alquiler y todo lo que{" "}
          {area === "FABRICA" ? "la fábrica" : "la tienda"} gasta en el mes,
          venda o no venda. Agregá, cambiá o quitá cada línea: un monto cambiado
          queda como corrección y el anterior se conserva en el historial.
        </p>
        <CostosAreaGrid
          key={`${mesDeCostos}|${area}`}
          periodo={mesDeCostos}
          area={area}
          gastos={gastos}
          personas={personas.ok ? personas.data : []}
        />
      </section>

      {area === "TIENDA" && mercaderia?.ok ? (
        <MercaderiaDelMesTabla datos={mercaderia.data} />
      ) : null}

      <section aria-label="Punto de equilibrio" className="space-y-3">
        <SectionTitle>Punto de equilibrio</SectionTitle>
        <p className="max-w-3xl text-sm text-muted">
          {area === "FABRICA"
            ? "Cuánto tiene que vender la fábrica para pagar sus costos fijos."
            : "Cuánto tiene que vender la tienda para pagar sus costos fijos, con la Mercadería que compra hecha."}
        </p>
        {!mes.ok ? (
          <ErrorNotice message={mes.message} />
        ) : !productos.ok ? (
          <ErrorNotice
            title="No pudimos cargar los productos."
            message={productos.message}
          />
        ) : (
          <EscenarioDeVentas
            key={vista}
            ambito={area}
            productos={productOptions(
              productos.data,
              listaMercaderia?.ok ? listaMercaderia.data : [],
            )}
            periodo={mesDeCostos || mes.data.periodo}
            puedeCorregir
          />
        )}
      </section>
    </div>
  );
}
