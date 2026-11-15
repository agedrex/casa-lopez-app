import type { Metadata } from "next";
import Link from "next/link";
import {
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
  expenseCategoryLabel,
  formatArs,
  formatPercent,
  formatPeriod,
} from "@/lib/format";
import { requireRole } from "@/lib/session";
import type {
  ProductoResumen,
  ProductoReventa,
  ResumenGastos,
} from "@/lib/types";
import { EscenarioDeVentas, type ProductOption } from "../cvu/escenario";
import { MargenForm } from "./margen-form";

export const metadata: Metadata = { title: "Negocio" };

const PERIODO = /^\d{4}-(0[1-9]|1[0-2])$/;

const VISTAS = [
  { id: "gastos", title: "Gastos del negocio" },
  { id: "fabrica", title: "Fábrica" },
  { id: "tienda", title: "Tienda" },
] as const;
type Vista = (typeof VISTAS)[number]["id"];

const AMBITO_TEXT = { FABRICA: "Fábrica", TIENDA: "Tienda" } as const;

const linkClass = "underline decoration-gold underline-offset-4";

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
      aria-label="Negocio"
      className="-mx-4 mb-6 overflow-x-auto overscroll-x-contain border-b border-line px-4 sm:mx-0 sm:mb-8 sm:px-0"
    >
      <ul className="flex min-w-max gap-1">
        {VISTAS.map((tab) => {
          const query = new URLSearchParams({ vista: tab.id });
          if (periodo) query.set("periodo", periodo);
          return (
            <li key={tab.id}>
              <Link
                href={`/negocio?${query}`}
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

/**
 * The transfer margin and where it lives. SUPUESTO: the parameter has no edit screen in the front
 * (/admin/parametros only redirects), so it is named, not linked; link it when the screen comes back.
 */
function MargenTransferencia({ pct }: { pct: string | null }) {
  return (
    <span>
      El margen de transferencia es de{" "}
      <strong>{pct === null ? "—" : formatPercent(pct)}</strong> sobre el precio
      de transferencia. Lo cambiás acá abajo.
    </span>
  );
}

function Gastos({ resumen }: { resumen: ResumenGastos }) {
  const pendientes = resumen.por_ambito.reduce(
    (sum, ambito) => sum + ambito.pendientes,
    0,
  );
  return (
    <div className="space-y-5">
      <Card className="space-y-2">
        <p className="text-sm text-muted">
          Costos fijos de {formatPeriod(resumen.periodo)}
        </p>
        <p className="text-3xl font-bold tabular-nums">
          {formatArs(resumen.total)}
        </p>
        <p className="text-sm text-muted">
          Es lo que gasta el negocio por mes, venda o no venda, repartido entre
          la fábrica y la tienda.{" "}
          <Link className={linkClass} href="/costos-fijos">
            Ver y cargar costos fijos
          </Link>
        </p>
      </Card>

      {pendientes > 0 ? (
        <Notice title="Hay costos fijos sin monto">
          {pendientes === 1
            ? "Falta cargar el monto de 1 costo fijo."
            : `Faltan cargar los montos de ${pendientes} costos fijos.`}{" "}
          Los totales de abajo no lo cuentan hasta que lo completes.
        </Notice>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-2">
        {resumen.por_ambito.map((ambito) => (
          <Card key={ambito.ambito} className="space-y-4">
            <div>
              <h3 className="text-lg">{AMBITO_TEXT[ambito.ambito]}</h3>
              <p className="mt-1 text-2xl font-bold tabular-nums">
                {formatArs(ambito.total)}
              </p>
            </div>
            {ambito.categorias.length > 0 ? (
              <TableWrap>
                <table className={tableClass}>
                  <thead>
                    <tr>
                      <th className={thClass}>Categoría</th>
                      <th className={`${thClass} ${numClass}`}>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ambito.categorias.map((categoria) => (
                      <tr key={categoria.categoria}>
                        <td className={tdClass}>
                          {expenseCategoryLabel(categoria.categoria)}
                        </td>
                        <td className={`${tdClass} ${numClass}`}>
                          {formatArs(categoria.total)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            ) : (
              <p className="text-sm text-muted">
                No hay costos fijos cargados para este mes.
              </p>
            )}
            {ambito.pendientes > 0 ? (
              <p className="text-xs text-muted">
                {ambito.pendientes === 1
                  ? "1 costo sin monto"
                  : `${ambito.pendientes} costos sin monto`}
              </p>
            ) : null}
          </Card>
        ))}
      </div>

      <Card className="space-y-4">
        <h3 className="text-lg">Últimos meses</h3>
        {resumen.serie.length > 0 ? (
          <TableWrap>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Mes</th>
                  <th className={`${thClass} ${numClass}`}>Fábrica</th>
                  <th className={`${thClass} ${numClass}`}>Tienda</th>
                  <th className={`${thClass} ${numClass}`}>Total</th>
                </tr>
              </thead>
              <tbody>
                {resumen.serie.map((mes) => (
                  <tr key={mes.periodo}>
                    <td className={tdClass}>{formatPeriod(mes.periodo)}</td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(mes.fabrica)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(mes.tienda)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(mes.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        ) : (
          <p className="text-sm text-muted">Todavía no hay meses cargados.</p>
        )}
      </Card>
    </div>
  );
}

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

export default async function NegocioPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  // Admin only: the menu and the proxy already hide it, this is the check next to the data.
  await requireRole("admin");
  const params = await searchParams;
  const requested = first(params.vista);
  const vista: Vista =
    VISTAS.find((tab) => tab.id === requested)?.id ?? "gastos";
  const requestedPeriodo = first(params.periodo);
  const periodo = PERIODO.test(requestedPeriodo) ? requestedPeriodo : "";
  const query = periodo ? `?periodo=${encodeURIComponent(periodo)}` : "";

  // The summary is loaded in every tab: it also carries the transfer margin the other two explain.
  const [resumen, mes] = await Promise.all([
    apiGet<ResumenGastos>(`/costos-fijos/resumen${query}`),
    apiGet<{ periodo: string }>("/cvu/periodo"),
  ]);
  // SUPUESTO: 500 is the API's page maximum; it only feeds the product suggestions.
  const [productos, mercaderia] =
    vista === "gastos"
      ? [null, null]
      : await Promise.all([
          apiGet<ProductoResumen[]>("/productos?limit=500"),
          vista === "tienda"
            ? apiGet<ProductoReventa[]>("/reventa")
            : Promise.resolve(null),
        ]);
  const margen = resumen.ok ? resumen.data.margen_transferencia_pct : null;

  return (
    <>
      <PageHeader
        eyebrow="Resumen"
        title="Negocio"
        description="Cuánto gasta el negocio por mes y cuánto tienen que vender la fábrica y la tienda para cubrirlo."
      />
      <Tabs vista={vista} periodo={periodo} />

      {vista === "gastos" ? (
        <div className="space-y-5">
          <form method="get" className="flex flex-wrap items-end gap-3">
            <input type="hidden" name="vista" value="gastos" />
            <label className="text-sm text-muted" htmlFor="negocio-mes">
              Mes
              <input
                id="negocio-mes"
                name="periodo"
                type="month"
                defaultValue={resumen.ok ? resumen.data.periodo : periodo}
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
          {resumen.ok ? (
            <Gastos resumen={resumen.data} />
          ) : (
            <ErrorNotice
              title="No pudimos cargar los gastos."
              message={resumen.message}
            />
          )}
        </div>
      ) : (
        <div className="space-y-5">
          <p className="max-w-3xl text-sm text-muted">
            {vista === "fabrica"
              ? "La fábrica le vende a la tienda al costo más el margen de transferencia: acá ves cuánto tiene que vender para pagar sus costos fijos. "
              : "La tienda le compra a la fábrica a ese precio de transferencia (más la Mercadería que compra hecha) y vende al precio de venta: acá ves cuánto tiene que vender para pagar sus costos fijos. "}
            <MargenTransferencia pct={margen} />
          </p>
          <MargenForm pct={margen} />
          {!mes.ok ? (
            <ErrorNotice message={mes.message} />
          ) : !productos?.ok ? (
            <ErrorNotice
              title="No pudimos cargar los productos."
              message={productos?.message ?? "Probá de nuevo en un rato."}
            />
          ) : (
            <EscenarioDeVentas
              key={vista}
              ambito={vista === "fabrica" ? "FABRICA" : "TIENDA"}
              productos={productOptions(
                productos.data,
                mercaderia?.ok ? mercaderia.data : [],
              )}
              periodo={periodo || mes.data.periodo}
              puedeCorregir
            />
          )}
          {vista === "tienda" && mercaderia && !mercaderia.ok ? (
            <Notice tone="info" title="No pudimos cargar la Mercadería">
              {mercaderia.message} Podés escribir el código MER- a mano.
            </Notice>
          ) : null}
        </div>
      )}
    </>
  );
}
