import type { Metadata } from "next";
import Link from "next/link";
import {
  Badge,
  Card,
  ErrorNotice,
  Notice,
  numClass,
  PageHeader,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import {
  formatArs,
  formatDate,
  formatPeriod,
  formatQuantity,
  todayIso,
} from "@/lib/format";
import { requireRole } from "@/lib/session";
import type {
  MargenAmbito,
  MargenReal,
  ProductoResumen,
  ProductoReventa,
  Stock,
  Transferencia,
  Venta,
} from "@/lib/types";
import { type ProductOption, TransferenciaForm, VentaForm } from "./forms";

export const metadata: Metadata = { title: "Ventas y stock" };

const PERIODO = /^\d{4}-(0[1-9]|1[0-2])$/;

const VISTAS = [
  { id: "ventas", title: "Ventas" },
  { id: "stock", title: "Stock" },
  { id: "margen", title: "Margen real" },
] as const;
type Vista = (typeof VISTAS)[number]["id"];

type Search = Promise<{
  vista?: string | string[];
  periodo?: string | string[];
}>;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

function Tabs({ vista, periodo }: { vista: Vista; periodo: string }) {
  return (
    <nav
      aria-label="Ventas y stock"
      className="-mx-4 mb-6 overflow-x-auto overscroll-x-contain border-b border-line px-4 sm:mx-0 sm:mb-8 sm:px-0"
    >
      <ul className="flex min-w-max gap-1">
        {VISTAS.map((tab) => {
          const query = new URLSearchParams({ vista: tab.id });
          // Stock is the current picture: it has no month.
          if (periodo && tab.id !== "stock") query.set("periodo", periodo);
          return (
            <li key={tab.id}>
              <Link
                href={`/ventas?${query}`}
                aria-current={vista === tab.id ? "page" : undefined}
                className={`-mb-px flex min-h-11 items-center whitespace-nowrap border-b-2 px-3 text-sm transition-colors ${
                  vista === tab.id
                    ? "border-gold text-ink"
                    : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {tab.title}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function MonthSelector({ vista, periodo }: { vista: Vista; periodo: string }) {
  return (
    <form method="get" className="flex flex-wrap items-end gap-3">
      <input type="hidden" name="vista" value={vista} />
      <label className="text-sm text-muted" htmlFor="ventas-mes">
        Mes
        <input
          id="ventas-mes"
          name="periodo"
          type="month"
          defaultValue={periodo}
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
  );
}

function productOptions(
  productos: ProductoResumen[],
  mercaderia: ProductoReventa[],
): { propios: ProductOption[]; todos: ProductOption[] } {
  const propios = productos.map(({ codigo, nombre }) => ({ codigo, nombre }));
  const resale = mercaderia
    .filter((item) => item.activo)
    .map(({ codigo, nombre }) => ({ codigo, nombre }));
  return { propios, todos: [...propios, ...resale] };
}

function VentasList({ ventas, periodo }: { ventas: Venta[]; periodo: string }) {
  if (ventas.length === 0) {
    return (
      <p className="text-sm text-muted">
        No hay ventas cargadas en {formatPeriod(periodo)}.
      </p>
    );
  }
  return (
    <TableWrap>
      <table className={tableClass}>
        <thead>
          <tr>
            <th className={thClass}>Fecha</th>
            <th className={thClass}>Producto</th>
            <th className={`${thClass} ${numClass}`}>Unidades</th>
            <th className={`${thClass} ${numClass}`}>Precio cobrado</th>
            <th className={`${thClass} ${numClass}`}>Total</th>
            <th className={thClass}>Canal</th>
            <th className={thClass}>Nota</th>
          </tr>
        </thead>
        <tbody>
          {ventas.map((venta) => (
            <tr key={venta.codigo}>
              <td className={tdClass}>{formatDate(venta.fecha)}</td>
              <td className={tdClass}>
                <span className="block">{venta.producto_nombre}</span>
                <span className="text-xs text-muted">
                  {venta.producto}
                  {venta.tipo === "MERCADERIA" ? " · Mercadería" : ""}
                </span>
              </td>
              <td className={`${tdClass} ${numClass}`}>
                {formatQuantity(venta.unidades)}
              </td>
              <td className={`${tdClass} ${numClass}`}>
                {formatArs(venta.precio_unitario_ars)}
              </td>
              <td className={`${tdClass} ${numClass}`}>
                {formatArs(venta.ingresos_ars)}
              </td>
              <td className={tdClass}>{venta.canal ?? "—"}</td>
              <td className={tdClass}>{venta.nota ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}

function TransferenciasList({
  transferencias,
  periodo,
}: {
  transferencias: Transferencia[];
  periodo: string;
}) {
  if (transferencias.length === 0) {
    return (
      <p className="text-sm text-muted">
        No hay pases a la tienda cargados en {formatPeriod(periodo)}.
      </p>
    );
  }
  return (
    <TableWrap>
      <table className={tableClass}>
        <thead>
          <tr>
            <th className={thClass}>Fecha</th>
            <th className={thClass}>Producto</th>
            <th className={`${thClass} ${numClass}`}>Unidades</th>
            <th className={`${thClass} ${numClass}`}>Costo de fábrica</th>
            <th className={`${thClass} ${numClass}`}>
              Precio de transferencia
            </th>
            <th className={`${thClass} ${numClass}`}>Total</th>
            <th className={thClass}>Nota</th>
          </tr>
        </thead>
        <tbody>
          {transferencias.map((pase) => (
            <tr key={pase.codigo}>
              <td className={tdClass}>{formatDate(pase.fecha)}</td>
              <td className={tdClass}>
                <span className="block">{pase.producto_nombre}</span>
                <span className="text-xs text-muted">{pase.producto}</span>
              </td>
              <td className={`${tdClass} ${numClass}`}>
                {formatQuantity(pase.unidades)}
              </td>
              <td className={`${tdClass} ${numClass}`}>
                {formatArs(pase.costo_fabrica_unitario_ars)}
              </td>
              <td className={`${tdClass} ${numClass}`}>
                {formatArs(pase.precio_transferencia_unitario_ars)}
              </td>
              <td className={`${tdClass} ${numClass}`}>
                {formatArs(pase.total_transferido_ars)}
              </td>
              <td className={tdClass}>{pase.nota ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}

function VentasVista({
  periodo,
  hoy,
  ventas,
  transferencias,
  productos,
  mercaderia,
}: {
  periodo: string;
  hoy: string;
  ventas: Awaited<ReturnType<typeof apiGet<Venta[]>>>;
  transferencias: Awaited<ReturnType<typeof apiGet<Transferencia[]>>>;
  productos: Awaited<ReturnType<typeof apiGet<ProductoResumen[]>>>;
  mercaderia: Awaited<ReturnType<typeof apiGet<ProductoReventa[]>>>;
}) {
  const options = productOptions(
    productos.ok ? productos.data : [],
    mercaderia.ok ? mercaderia.data : [],
  );
  return (
    <div className="space-y-5">
      {!productos.ok ? (
        <Notice tone="info" title="No pudimos cargar la lista de productos">
          {productos.message} Podés escribir el código a mano (PRD- o MER-).
        </Notice>
      ) : !mercaderia.ok ? (
        <Notice tone="info" title="No pudimos cargar la Mercadería">
          {mercaderia.message} Podés escribir el código MER- a mano.
        </Notice>
      ) : null}

      <Card className="space-y-4">
        <div>
          <h3 className="text-lg">Registrar una venta</h3>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Anotá lo que se vendió y a qué precio. Con la venta se guarda el
            costo de ese momento: si después cambia el dólar o un precio, esta
            venta no se recalcula.
          </p>
        </div>
        <VentaForm productos={options.todos} hoy={hoy} />
      </Card>

      <Card className="space-y-4">
        <h3 className="text-lg">Ventas de {formatPeriod(periodo)}</h3>
        {ventas.ok ? (
          <VentasList ventas={ventas.data} periodo={periodo} />
        ) : (
          <ErrorNotice
            title="No pudimos cargar las ventas."
            message={ventas.message}
          />
        )}
      </Card>

      <details className="group rounded-card border border-line bg-surface">
        <summary className="flex min-h-11 cursor-pointer items-center px-5 py-3 text-lg">
          Pasar a la tienda
        </summary>
        <div className="space-y-5 border-t border-line px-5 py-5">
          <p className="max-w-3xl text-sm text-muted">
            Cuando la fábrica manda productos a la tienda, anotalo acá. Se
            guarda el costo de fábrica y el precio de transferencia (con el
            margen) de ese momento, y no cambian aunque después suba el dólar.
            Esto mueve el stock de la fábrica a la tienda.
          </p>
          <TransferenciaForm productos={options.propios} hoy={hoy} />
          <h3 className="text-lg">Pases de {formatPeriod(periodo)}</h3>
          {transferencias.ok ? (
            <TransferenciasList
              transferencias={transferencias.data}
              periodo={periodo}
            />
          ) : (
            <ErrorNotice
              title="No pudimos cargar los pases."
              message={transferencias.message}
            />
          )}
        </div>
      </details>
    </div>
  );
}

function StockVista({ stock }: { stock: Stock }) {
  return (
    <div className="space-y-5">
      <p className="max-w-3xl text-sm text-muted">
        El stock no se escribe: sale de lo que se produjo en los lotes, lo que
        se pasó a la tienda y lo que se vendió. Si algo da negativo, falta
        cargar un lote, un pase o una compra; lo marcamos y no lo escondemos.
      </p>
      {stock.inconsistentes > 0 ? (
        <Notice
          title={
            stock.inconsistentes === 1
              ? "Hay 1 producto con el stock inconsistente"
              : `Hay ${stock.inconsistentes} productos con el stock inconsistente`
          }
        >
          Están resaltados abajo, con el motivo.
        </Notice>
      ) : null}
      {stock.filas.length === 0 ? (
        <p className="text-sm text-muted">
          Todavía no hay movimientos de stock.
        </p>
      ) : (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Producto</th>
                <th className={`${thClass} ${numClass}`}>En fábrica</th>
                <th className={`${thClass} ${numClass}`}>En tienda</th>
                <th className={thClass}>Aviso</th>
              </tr>
            </thead>
            <tbody>
              {stock.filas.map((fila) => (
                <tr
                  key={fila.codigo}
                  className={fila.inconsistente ? "bg-bordeaux/5" : undefined}
                >
                  <td className={tdClass}>
                    <span className="block">{fila.nombre}</span>
                    <span className="text-xs text-muted">
                      {fila.codigo}
                      {fila.tipo === "MERCADERIA" ? " · Mercadería" : ""}
                    </span>
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {fila.stock_fabrica === null
                      ? "—"
                      : formatQuantity(fila.stock_fabrica)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatQuantity(fila.stock_tienda)}
                  </td>
                  <td className={tdClass}>
                    {fila.inconsistente ? (
                      <span className="flex flex-wrap items-start gap-2">
                        <Badge tone="warn">Revisar</Badge>
                        <span className="max-w-md text-sm text-bordeaux">
                          {fila.aviso ?? "El stock no cierra."}
                        </span>
                      </span>
                    ) : (
                      (fila.aviso ?? "—")
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
    </div>
  );
}

function FijosNote({ ambito }: { ambito: MargenAmbito }) {
  const { fijos } = ambito;
  const notes = [
    !fijos.cargados ? "sin costos fijos cargados" : null,
    fijos.pendientes > 0
      ? fijos.pendientes === 1
        ? "1 costo sin monto"
        : `${fijos.pendientes} costos sin monto`
      : null,
    fijos.ficticios ? "incluye costos de ejemplo" : null,
  ].filter((note): note is string => note !== null);
  if (notes.length === 0) return null;
  return (
    <span className="mt-0.5 block text-xs text-muted">{notes.join(" · ")}</span>
  );
}

function MargenVista({ margen }: { margen: MargenReal }) {
  const columnas = [
    { titulo: "Fábrica", ambito: margen.fabrica },
    { titulo: "Tienda", ambito: margen.tienda },
    { titulo: "Consolidado", ambito: margen.consolidado },
  ];
  return (
    <div className="space-y-5">
      {!margen.confiable ? (
        <div
          role="alert"
          className="rounded-card border border-bordeaux/30 bg-bordeaux/5 px-5 py-4 text-sm"
        >
          <p className="font-bold text-bordeaux">
            Estos números no son confiables todavía
          </p>
          <p className="mt-1 text-muted">
            Hay datos que faltan o no cierran (te los detallamos abajo). No te
            apoyes en el margen ni en la utilidad hasta resolverlos.
          </p>
        </div>
      ) : null}

      <p className="max-w-3xl text-sm text-muted">
        El margen de cada venta sale de los costos que quedaron guardados ese
        día. El consolidado suma la fábrica y la tienda sin contar dos veces lo
        que la fábrica le cobra a la tienda: ese margen de transferencia se
        cuenta una sola vez.
      </p>

      <Card className="space-y-2">
        <p className="text-sm text-muted">
          Ventas de {formatPeriod(margen.periodo)}
        </p>
        <p className="text-3xl font-bold tabular-nums">
          {formatArs(margen.ingresos)}
        </p>
        <p className="text-sm text-muted">
          {margen.ventas === 1 ? "1 venta" : `${margen.ventas} ventas`} ·{" "}
          {formatQuantity(margen.unidades)} unidades vendidas
        </p>
      </Card>

      <Card className="space-y-4">
        <h3 className="text-lg">Resultado del mes</h3>
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>&nbsp;</th>
                {columnas.map(({ titulo }) => (
                  <th key={titulo} className={`${thClass} ${numClass}`}>
                    {titulo}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className={tdClass}>Ingresos por ventas</td>
                <td className={`${tdClass} ${numClass}`} colSpan={3}>
                  {formatArs(margen.ingresos)}
                </td>
              </tr>
              <tr>
                <td className={tdClass}>Margen</td>
                {columnas.map(({ titulo, ambito }) => (
                  <td key={titulo} className={`${tdClass} ${numClass}`}>
                    {formatArs(ambito.margen)}
                  </td>
                ))}
              </tr>
              <tr>
                <td className={tdClass}>Costos fijos</td>
                {columnas.map(({ titulo, ambito }) => (
                  <td key={titulo} className={`${tdClass} ${numClass}`}>
                    {formatArs(ambito.fijos.total)}
                    <FijosNote ambito={ambito} />
                  </td>
                ))}
              </tr>
              <tr className="font-bold">
                <td className={tdClass}>Utilidad</td>
                {columnas.map(({ titulo, ambito }) => (
                  <td key={titulo} className={`${tdClass} ${numClass}`}>
                    {formatArs(ambito.utilidad)}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </TableWrap>
      </Card>

      {margen.avisos.length > 0 ? (
        <Notice title="Para tener en cuenta">
          <ul className="list-disc space-y-1 pl-5">
            {margen.avisos.map((aviso) => (
              <li key={`${aviso.codigo}-${aviso.texto}`}>{aviso.texto}</li>
            ))}
          </ul>
        </Notice>
      ) : null}

      <Card className="space-y-4">
        <h3 className="text-lg">Margen por producto</h3>
        {margen.lineas.length === 0 ? (
          <p className="text-sm text-muted">
            No hay ventas cargadas en {formatPeriod(margen.periodo)}.
          </p>
        ) : (
          <TableWrap>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Producto</th>
                  <th className={`${thClass} ${numClass}`}>Unidades</th>
                  <th className={`${thClass} ${numClass}`}>Ingresos</th>
                  <th className={`${thClass} ${numClass}`}>Margen fábrica</th>
                  <th className={`${thClass} ${numClass}`}>Margen tienda</th>
                  <th className={`${thClass} ${numClass}`}>Consolidado</th>
                </tr>
              </thead>
              <tbody>
                {margen.lineas.map((linea) => (
                  <tr key={linea.codigo}>
                    <td className={tdClass}>
                      <span className="block">{linea.nombre}</span>
                      <span className="text-xs text-muted">
                        {linea.codigo}
                        {linea.tipo === "MERCADERIA" ? " · Mercadería" : ""}
                      </span>
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatQuantity(linea.unidades)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(linea.ingresos)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(linea.margen_fabrica)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(linea.margen_tienda)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(linea.margen_consolidado)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </Card>
    </div>
  );
}

export default async function VentasPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  // Admin only: the menu and the proxy already hide it, this is the check next to the data.
  await requireRole("admin");
  const params = await searchParams;
  const requested = first(params.vista);
  const vista: Vista =
    VISTAS.find((tab) => tab.id === requested)?.id ?? "ventas";
  const hoy = todayIso();
  const requestedPeriodo = first(params.periodo);
  const periodo = PERIODO.test(requestedPeriodo)
    ? requestedPeriodo
    : hoy.slice(0, 7);
  const query = `?periodo=${encodeURIComponent(periodo)}`;

  const header = (
    <>
      <PageHeader
        eyebrow="Resumen"
        title="Ventas y stock"
        description="Lo que se vendió, lo que pasó de la fábrica a la tienda, lo que queda en cada lugar y cuánto se ganó de verdad."
      />
      <Tabs vista={vista} periodo={periodo} />
    </>
  );

  if (vista === "ventas") {
    // SUPUESTO: 500 is the API's page maximum; it only feeds the product suggestions.
    const [ventas, transferencias, productos, mercaderia] = await Promise.all([
      apiGet<Venta[]>(`/ventas${query}`),
      apiGet<Transferencia[]>(`/transferencias${query}`),
      apiGet<ProductoResumen[]>("/productos?limit=500"),
      apiGet<ProductoReventa[]>("/reventa"),
    ]);
    return (
      <>
        {header}
        <div className="space-y-5">
          <MonthSelector vista="ventas" periodo={periodo} />
          <VentasVista
            periodo={periodo}
            hoy={hoy}
            ventas={ventas}
            transferencias={transferencias}
            productos={productos}
            mercaderia={mercaderia}
          />
        </div>
      </>
    );
  }

  if (vista === "stock") {
    const stock = await apiGet<Stock>("/stock");
    return (
      <>
        {header}
        {stock.ok ? (
          <StockVista stock={stock.data} />
        ) : (
          <ErrorNotice
            title="No pudimos cargar el stock."
            message={stock.message}
          />
        )}
      </>
    );
  }

  const margen = await apiGet<MargenReal>(`/margen-real${query}`);
  return (
    <>
      {header}
      <div className="space-y-5">
        <MonthSelector vista="margen" periodo={periodo} />
        {margen.ok ? (
          <MargenVista margen={margen.data} />
        ) : (
          <ErrorNotice
            title="No pudimos cargar el margen real."
            message={margen.message}
          />
        )}
      </div>
    </>
  );
}
