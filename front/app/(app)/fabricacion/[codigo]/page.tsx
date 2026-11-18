import type { Metadata } from "next";
import Link from "next/link";
import { Avisos } from "@/components/avisos";
import { ReadOnlyNote } from "@/components/form";
import { LotStateBadge, whereText } from "@/components/orders-table";
import { PrecioReferencia } from "@/components/precio-referencia";
import {
  Card,
  ErrorNotice,
  Notice,
  numClass,
  PageHeader,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import {
  formatArs,
  formatDate,
  formatQuantity,
  lotStateLabel,
  todayIso,
} from "@/lib/format";
import { resumenDeCuero, type TarjetaDeCuero } from "@/lib/lote-cuero";
import { nombreDeLote } from "@/lib/lotes";
import { canWrite, isTallerOnly } from "@/lib/permissions";
import { collapseSpaces } from "@/lib/productos";
import { requireSession } from "@/lib/session";
import type {
  LoteCuero,
  OrdenDetalle,
  Persona,
  PreciosTalleres,
  ProductoResumen,
  Referencia,
} from "@/lib/types";
import { ConsumoDelLote } from "./consumo-lote";
import { RenglonEditor, RenglonesQuitados } from "./editar-renglones";
import { EstadoForm, ItemForm, PreciosForm } from "./forms";

export const metadata: Metadata = { title: "Lote" };

const PRODUCT_LIMIT = 500;

function decodeCode(raw: string): string | null {
  try {
    return decodeURIComponent(raw);
  } catch {
    return null;
  }
}

function BackLink() {
  return (
    <p className="mb-6 text-sm">
      <Link
        href="/fabricacion"
        className="text-muted underline decoration-gold underline-offset-4"
      >
        ← Lotes
      </Link>
    </p>
  );
}

export default async function LotePage({
  params,
}: {
  params: Promise<{ codigo: string }>;
}) {
  const { user } = await requireSession();
  const code = decodeCode((await params).codigo);
  if (code === null) {
    return (
      <>
        <BackLink />
        <Notice tone="info" title="No encontramos ese lote" />
      </>
    );
  }
  const result = await apiGet<OrdenDetalle>(
    `/ordenes/${encodeURIComponent(code)}`,
  );
  if (!result.ok) {
    return (
      <>
        <BackLink />
        {result.status === 404 ? (
          <Notice tone="info" title="No encontramos ese lote">
            Revisá el código o volvé al listado de lotes.
          </Notice>
        ) : (
          <ErrorNotice message={result.message} />
        )}
      </>
    );
  }

  const orden = result.data;
  const writer = canWrite(user.role);
  if (isTallerOnly(user.role)) return <TallerLote orden={orden} />;
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow={`Lote ${nombreDeLote(orden.codigo, orden.fecha_de_envio)}`}
        title={whereText(orden)}
        actions={<LotStateBadge estado={orden.estado} />}
      />
      <div className="space-y-10">
        <CueroDelLote orden={orden} />
        <QueHayQueHacer orden={orden} />
        <ConsumoDelLote
          codigo={orden.codigo}
          vacio={orden.items.length === 0}
          costoTotal={orden.costo_total}
          fecha={orden.fecha_de_envio}
        />
        <Summary orden={orden} />
        {orden.avisos.length > 0 ? (
          <Notice title="Para revisar en este lote">
            <ul className="list-disc space-y-1 pl-5">
              {orden.avisos.map((aviso) => (
                <li key={aviso}>{aviso}</li>
              ))}
            </ul>
          </Notice>
        ) : null}
        <Items orden={orden} />
        <Timeline orden={orden} />
        {writer ? (
          <WriterSections orden={orden} />
        ) : (
          <section>
            <SectionTitle>Acciones</SectionTitle>
            <ReadOnlyNote />
          </section>
        )}
      </div>
    </>
  );
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-card">
      <dt className="text-xs uppercase tracking-caps-sm text-muted">{label}</dt>
      <dd className="mt-2 font-display text-2xl tabular-nums">{value}</dd>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

function Summary({ orden }: { orden: OrdenDetalle }) {
  return (
    <section aria-label="Resumen del lote">
      <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
        <Metric label="Unidades" value={formatQuantity(orden.unidades)} />
        <Metric
          label="Cotizó el taller"
          value={formatArs(orden.total_cotizado)}
        />
        <Metric
          label="Cobró el taller"
          value={formatArs(orden.total_cobrado)}
        />
        <Metric
          label="Costo del lote"
          value={formatArs(orden.costo_total)}
          hint="Materiales a la fecha del lote más confección"
        />
        <Metric
          label="Costo por unidad"
          value={formatArs(orden.costo_promedio_por_unidad)}
        />
      </dl>
      <p className="mt-4 text-sm text-muted">
        Envío {formatDate(orden.fecha_de_envio)} · Entrega{" "}
        {formatDate(orden.fecha_de_entrega)}
        {orden.nota ? ` · ${orden.nota}` : ""}
      </p>
    </section>
  );
}

function Items({ orden }: { orden: OrdenDetalle }) {
  return (
    <section>
      <SectionTitle>Productos del lote</SectionTitle>
      {orden.items.length === 0 ? (
        <Notice tone="info" title="Este lote todavía no tiene productos." />
      ) : (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Producto</th>
                <th className={`${thClass} ${numClass}`}>Cantidad</th>
                <th className={`${thClass} ${numClass}`}>Cotizado</th>
                <th className={`${thClass} ${numClass}`}>Pagado</th>
                <th className={`${thClass} ${numClass}`}>Confección</th>
                <th className={`${thClass} ${numClass}`}>
                  Materiales (fecha del lote)
                </th>
                <th className={`${thClass} ${numClass}`}>Costo por unidad</th>
                <th className={`${thClass} ${numClass}`}>Total</th>
                <th className={thClass}>Avisos</th>
              </tr>
            </thead>
            <tbody>
              {orden.items.map((item) => (
                <tr key={item.codigo} className="hover:bg-paper-mid/50">
                  <td className={tdClass}>
                    <Link
                      href={`/productos/${encodeURIComponent(item.producto)}`}
                      className="underline decoration-gold underline-offset-4"
                    >
                      {item.producto}
                    </Link>
                    <span className="block text-xs text-muted">
                      {item.producto_nombre}
                    </span>
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatQuantity(item.cantidad)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(item.cotizado)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(item.pagado)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(item.confeccion_por_unidad)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(item.materiales_por_unidad)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(item.costo_por_unidad)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(item.total_linea)}
                  </td>
                  <td className={tdClass}>
                    <Avisos avisos={item.avisos} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
    </section>
  );
}

function Timeline({ orden }: { orden: OrdenDetalle }) {
  return (
    <section>
      <SectionTitle>Estados del lote</SectionTitle>
      {orden.estados.length === 0 ? (
        <Notice tone="info" title="Este lote no tiene historial de estados." />
      ) : (
        <ol className="space-y-0 border-l border-line pl-6">
          {orden.estados.map((estado, index) => (
            <li
              key={`${estado.estado}-${estado.fecha}-${index}`}
              className="relative pb-6 last:pb-0"
              aria-current={
                index === orden.estados.length - 1 ? "step" : undefined
              }
            >
              <span
                aria-hidden="true"
                className="absolute -left-[1.85rem] top-1.5 size-2.5 rounded-full bg-gold"
              />
              <p className="font-bold">{lotStateLabel(estado.estado)}</p>
              <p className="text-sm text-muted">
                {formatDate(estado.fecha)}
                {estado.quien_nombre ? ` · ${estado.quien_nombre}` : ""}
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

async function WriterSections({ orden }: { orden: OrdenDetalle }) {
  // The same endpoint as the product page, once per distinct product of the lot.
  const codigosDeProducto = [...new Set(orden.items.map((i) => i.producto))];
  const [personas, productos, precios] = await Promise.all([
    apiGet<Persona[]>("/personas"),
    apiGet<ProductoResumen[]>(`/productos?limit=${PRODUCT_LIMIT}`),
    orden.donde_se_hace === "EXTERNA"
      ? Promise.all(
          codigosDeProducto.map((producto) =>
            apiGet<PreciosTalleres>(
              `/productos/${encodeURIComponent(producto)}/precios-talleres`,
            ),
          ),
        )
      : Promise.resolve([]),
  ]);
  const referencias = new Map<string, Referencia>(
    codigosDeProducto.flatMap((producto, i) => {
      const respuesta = precios[i];
      return respuesta?.ok
        ? [[producto, respuesta.data.referencia] as const]
        : [];
    }),
  );
  return (
    <>
      <section>
        <SectionTitle>Precios del taller</SectionTitle>
        {orden.donde_se_hace === "INTERNA" ? (
          <Notice tone="info" title="Este lote se hace en casa">
            En casa la confección vale 0 en el lote: los sueldos son costos
            fijos.
          </Notice>
        ) : orden.items.length === 0 ? (
          <Notice tone="info" title="Agregue productos para cargar precios." />
        ) : (
          <Card className="space-y-6">
            <p className="text-sm text-muted">
              El taller pone el precio recién al retirar la mercadería. Lo que
              cargues se guarda sobre el renglón: no queda historial de los
              valores anteriores.
            </p>
            {orden.items.map((item) => {
              const referencia = referencias.get(item.producto);
              return (
                <PreciosForm
                  key={item.codigo}
                  codigo={orden.codigo}
                  item={item.codigo}
                  producto={`${item.producto} · ${item.producto_nombre}`}
                  cotizado={item.cotizado}
                  pagado={item.pagado}
                  referencia={
                    referencia ? (
                      <PrecioReferencia referencia={referencia} />
                    ) : null
                  }
                />
              );
            })}
          </Card>
        )}
      </section>
      <EditarRenglones orden={orden} />
      <section>
        <SectionTitle>Cambiar el estado</SectionTitle>
        {orden.estado === "CERRADA" ? (
          <Notice tone="info" title="Este lote está cerrado">
            Un lote cerrado no cambia de estado ni se reabre.
          </Notice>
        ) : (
          <Card>
            <EstadoForm
              codigo={orden.codigo}
              actual={orden.estado}
              personas={
                personas.ok
                  ? personas.data
                      .filter((p) => p.activo)
                      .map((p) => ({ codigo: p.codigo, label: p.nombre }))
                  : []
              }
              today={todayIso()}
              entrega={orden.fecha_de_entrega}
            />
          </Card>
        )}
      </section>
      <section>
        <SectionTitle>Agregar un producto</SectionTitle>
        <Card>
          <ItemForm
            codigo={orden.codigo}
            productos={
              productos.ok
                ? productos.data.map((p) => ({
                    codigo: p.codigo,
                    label: p.nombre,
                  }))
                : []
            }
          />
        </Card>
      </section>
    </>
  );
}

/**
 * What the taller sees of a lot: state, dates and, per product, the name and how many to make, each
 * linked to its product sheet. No prices, costs or amounts, and no warnings (they quote prices).
 */
function TallerLote({ orden }: { orden: OrdenDetalle }) {
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow={`Lote ${nombreDeLote(orden.codigo, orden.fecha_de_envio)}`}
        title={whereText(orden)}
        actions={<LotStateBadge estado={orden.estado} />}
      />
      <div className="max-w-3xl space-y-10">
        <section aria-label="Resumen del lote">
          <p className="text-sm text-muted">
            Envío {formatDate(orden.fecha_de_envio)} · Entrega{" "}
            {formatDate(orden.fecha_de_entrega)} ·{" "}
            {formatQuantity(orden.unidades)}{" "}
            {Number(orden.unidades) === 1 ? "unidad" : "unidades"} en total
          </p>
          {orden.nota ? <p className="mt-2 text-sm">{orden.nota}</p> : null}
        </section>
        <CueroDelLote orden={orden} />
        <QueHayQueHacer orden={orden} />
        <ConsumoDelLote
          codigo={orden.codigo}
          vacio={orden.items.length === 0}
        />
        <Timeline orden={orden} />
      </div>
    </>
  );
}

const CUERO_STYLE: Record<TarjetaDeCuero["estado"], string> = {
  FALTA: "border-bordeaux/40 bg-bordeaux/5",
  ALCANZA: "border-line bg-surface",
  YA_CORTADO: "border-line bg-paper-mid",
};

function CueroCard({ tarjeta }: { tarjeta: TarjetaDeCuero }) {
  return (
    <li
      className={`rounded-card border p-4 shadow-card ${CUERO_STYLE[tarjeta.estado]}`}
    >
      <p className="break-words font-bold">{tarjeta.titulo}</p>
      <p
        className={`mt-1 font-display text-2xl ${
          tarjeta.estado === "FALTA" ? "text-bordeaux" : ""
        }`}
      >
        {tarjeta.mensaje}
      </p>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        {tarjeta.cifras.map((cifra) => (
          <div key={cifra.label} className="contents">
            <dt className="text-muted">{cifra.label}</dt>
            <dd className="text-right tabular-nums">{cifra.value}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 break-words text-xs text-muted">
        Para: {tarjeta.productos.join(", ")}
      </p>
    </li>
  );
}

/**
 * Leather the lot needs against the leather in stock, one card per leather (material and color). Square
 * meters only: the taller reads it, so there is no money here. The API adds up the products that share a
 * leather and takes out what was already cut. A closed lot has nothing left to cut, so it is not shown.
 */
async function CueroDelLote({ orden }: { orden: OrdenDetalle }) {
  if (orden.estado === "CERRADA" || orden.items.length === 0) return null;
  const result = await apiGet<LoteCuero>(
    `/ordenes/${encodeURIComponent(orden.codigo)}/cuero`,
  );
  if (!result.ok) {
    return (
      <section aria-label="Cuero del lote">
        <SectionTitle>Cuero del lote</SectionTitle>
        <ErrorNotice
          title="No pudimos calcular el cuero del lote."
          message={result.message}
        />
      </section>
    );
  }
  const resumen = resumenDeCuero(result.data);
  return (
    <section aria-label="Cuero del lote">
      <SectionTitle>Cuero del lote</SectionTitle>
      <p
        className={`mb-3 text-sm ${resumen.faltan > 0 ? "font-bold text-bordeaux" : "text-muted"}`}
        role={resumen.faltan > 0 ? "alert" : undefined}
      >
        {resumen.titular}
      </p>
      {resumen.tarjetas.length > 0 ? (
        <ul className="grid gap-3 sm:grid-cols-2">
          {resumen.tarjetas.map((tarjeta) => (
            <CueroCard key={tarjeta.key} tarjeta={tarjeta} />
          ))}
        </ul>
      ) : null}
      {resumen.sinConsumo.length > 0 ? (
        <div className="mt-3">
          <Notice title="Sin consumo de cuero cargado (no se cuentan arriba)">
            {resumen.sinConsumo
              .map((p) => `${p.producto_nombre} (${p.producto})`)
              .join(", ")}
          </Notice>
        </div>
      ) : null}
    </section>
  );
}

/** The list of products to make, with how many of each; every row opens the product sheet. Shared by the taller and the admin. */
function QueHayQueHacer({ orden }: { orden: OrdenDetalle }) {
  return (
    <section>
      <SectionTitle>Qué hay que hacer</SectionTitle>
      {orden.items.length === 0 ? (
        <Notice tone="info" title="Este lote todavía no tiene productos." />
      ) : (
        <>
          <p className="mb-3 text-sm text-muted">
            Tocá un producto para ver sus materiales y consumos.
          </p>
          <ul className="divide-y divide-line/70 rounded-card border border-line bg-surface shadow-card">
            {orden.items.map((item) => (
              <li key={item.codigo}>
                <Link
                  href={`/productos/${encodeURIComponent(item.producto)}`}
                  className="flex min-h-14 items-center justify-between gap-4 px-4 py-3"
                >
                  <span className="min-w-0">
                    <span className="line-clamp-2 break-words underline decoration-gold underline-offset-4">
                      {collapseSpaces(item.producto_nombre)}
                    </span>
                    <span className="block text-xs text-muted">
                      {item.producto}
                    </span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span className="font-display text-3xl tabular-nums">
                      {formatQuantity(item.cantidad)}
                    </span>
                    <span className="block text-xs text-muted">a hacer</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

/**
 * Admin only: change the units of a line or take it out of an open lot. The same product can be several lines, each
 * with any quantity. A closed lot is read only. Removing asks for confirmation and keeps the row (see the quitados list).
 */
function EditarRenglones({ orden }: { orden: OrdenDetalle }) {
  const quitados = orden.quitados ?? [];
  return (
    <section>
      <SectionTitle>Cambiar o quitar productos</SectionTitle>
      {orden.estado === "CERRADA" ? (
        <Notice tone="info" title="Este lote está cerrado">
          Los productos de un lote cerrado no se pueden cambiar ni quitar.
        </Notice>
      ) : orden.items.length === 0 ? (
        <Notice tone="info" title="Este lote no tiene productos para editar." />
      ) : (
        <Card>
          <ul className="divide-y divide-line/70">
            {orden.items.map((item) => (
              <RenglonEditor
                key={item.codigo}
                codigo={orden.codigo}
                item={item.codigo}
                producto={`${item.producto} · ${collapseSpaces(item.producto_nombre)}`}
                cantidad={item.cantidad}
              />
            ))}
          </ul>
        </Card>
      )}
      <RenglonesQuitados quitados={quitados} />
    </section>
  );
}
