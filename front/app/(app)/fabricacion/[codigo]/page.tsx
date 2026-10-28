import type { Metadata } from "next";
import Link from "next/link";
import { Avisos } from "@/components/avisos";
import { ReadOnlyNote } from "@/components/form";
import { LotStateBadge, whereText } from "@/components/orders-table";
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
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { OrdenDetalle, Persona, ProductoResumen } from "@/lib/types";
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
        ← Fabricación
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
            Revise el código o vuelva al listado de fabricación.
          </Notice>
        ) : (
          <ErrorNotice message={result.message} />
        )}
      </>
    );
  }

  const orden = result.data;
  const writer = canWrite(user.role);
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow={`Lote ${orden.codigo}`}
        title={whereText(orden)}
        actions={<LotStateBadge estado={orden.estado} />}
      />
      <div className="space-y-10">
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
          hint="Materiales de hoy más confección"
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
                <th className={`${thClass} ${numClass}`}>Materiales (hoy)</th>
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
  const [personas, productos] = await Promise.all([
    apiGet<Persona[]>("/personas"),
    apiGet<ProductoResumen[]>(`/productos?limit=${PRODUCT_LIMIT}`),
  ]);
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
              El taller manda su precio después de recibir el lote. Estos dos
              precios se guardan sobre el renglón: no queda historial de los
              valores anteriores.
            </p>
            {orden.items.map((item) => (
              <PreciosForm
                key={item.codigo}
                codigo={orden.codigo}
                item={item.codigo}
                producto={`${item.producto} · ${item.producto_nombre}`}
                cotizado={item.cotizado}
                pagado={item.pagado}
              />
            ))}
          </Card>
        )}
      </section>
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
