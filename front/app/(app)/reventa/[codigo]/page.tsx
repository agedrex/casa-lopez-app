import type { Metadata } from "next";
import Link from "next/link";
import { ReadOnlyNote } from "@/components/form";
import {
  Badge,
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
import { formatArs, formatDate, formatQuantity } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { ProductoReventaDetalle } from "@/lib/types";
import { formatMargenPct } from "../margen";
import { ActivoForm } from "./activo-form";
import { CompraForm } from "./compra-form";

export const metadata: Metadata = { title: "Producto de reventa" };

function BackLink() {
  return (
    <p className="mb-6 text-sm">
      <Link
        href="/reventa"
        className="text-muted underline decoration-gold underline-offset-4"
      >
        ← Mercadería
      </Link>
    </p>
  );
}

function decodeCode(raw: string): string | null {
  try {
    return decodeURIComponent(raw);
  } catch {
    return null;
  }
}

export default async function ReventaProductoPage({
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
        <Notice tone="info" title="No encontramos ese producto" />
      </>
    );
  }
  const result = await apiGet<ProductoReventaDetalle>(
    `/reventa/${encodeURIComponent(code)}`,
  );
  if (!result.ok) {
    return (
      <>
        <BackLink />
        {result.status === 404 ? (
          <Notice tone="info" title="No encontramos ese producto">
            Revise el código o vuelva al listado de mercadería.
          </Notice>
        ) : (
          <ErrorNotice message={result.message} />
        )}
      </>
    );
  }

  const producto = result.data;
  const writer = canWrite(user.role);
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow={`Mercadería ${producto.codigo}`}
        title={producto.nombre}
        description="El costo es lo que pagaste por unidad en la última compra. Cada compra nueva queda en el historial."
        actions={
          producto.activo ? undefined : <Badge tone="warn">Archivado</Badge>
        }
      />
      <div className="space-y-10">
        <section aria-label="Resumen del producto">
          <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label="Costo unitario"
              value={formatArs(producto.costo_unitario_ars)}
              hint="De la última compra"
            />
            <Metric
              label="Precio de venta"
              value={formatArs(producto.precio_venta_unitario_ars)}
            />
            <Metric
              label="Margen"
              value={formatArs(producto.margen_unitario_ars)}
              hint={formatMargenPct(producto.margen_pct)}
            />
            <Metric
              label="Última compra"
              value={formatDate(producto.ultima_compra)}
              hint={`${producto.compras} ${producto.compras === 1 ? "compra" : "compras"} · ${formatQuantity(producto.unidades_compradas)} unidades en total`}
            />
          </dl>
        </section>
        <section>
          <SectionTitle>Datos</SectionTitle>
          <Card>
            <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-3">
              <Datum label="Categoría" value={producto.categoria} />
              <Datum label="Proveedor" value={producto.proveedor} />
              <Datum label="Nota" value={producto.nota} />
            </dl>
          </Card>
        </section>
        <section>
          <SectionTitle>Registrar compra</SectionTitle>
          {writer ? (
            <Card>
              <CompraForm
                codigo={producto.codigo}
                proveedor={producto.proveedor}
              />
            </Card>
          ) : (
            <ReadOnlyNote />
          )}
        </section>
        <section>
          <SectionTitle>Historial de compras y precios</SectionTitle>
          {producto.historial.length === 0 ? (
            <Notice
              tone="info"
              title="Todavía no hay compras ni precios registrados."
            />
          ) : (
            <TableWrap>
              <table className={tableClass}>
                <thead>
                  <tr>
                    <th className={thClass}>Fecha</th>
                    <th className={`${thClass} ${numClass}`}>Unidades</th>
                    <th className={`${thClass} ${numClass}`}>Costo unitario</th>
                    <th className={`${thClass} ${numClass}`}>Costo total</th>
                    <th className={`${thClass} ${numClass}`}>
                      Precio de venta
                    </th>
                    <th className={`${thClass} ${numClass}`}>Margen</th>
                    <th className={thClass}>Proveedor</th>
                    <th className={thClass}>Nota</th>
                  </tr>
                </thead>
                <tbody>
                  {producto.historial.map((compra) => (
                    <tr
                      key={`${compra.creado_en}-${compra.fecha}-${compra.costo_unitario_ars}`}
                      className="hover:bg-paper-mid/50"
                    >
                      <td className={tdClass}>
                        {formatDate(compra.fecha)}
                        {compra.unidades === null ? (
                          <span className="block text-xs text-muted">
                            Actualización de precio
                          </span>
                        ) : null}
                      </td>
                      <td className={`${tdClass} ${numClass}`}>
                        {formatQuantity(compra.unidades)}
                      </td>
                      <td className={`${tdClass} ${numClass}`}>
                        {formatArs(compra.costo_unitario_ars)}
                      </td>
                      <td className={`${tdClass} ${numClass}`}>
                        {formatArs(compra.costo_total_ars)}
                      </td>
                      <td className={`${tdClass} ${numClass}`}>
                        {formatArs(compra.precio_venta_unitario_ars)}
                      </td>
                      <td className={`${tdClass} ${numClass}`}>
                        {formatArs(compra.margen_unitario_ars)}
                        <span className="block text-xs text-muted">
                          {formatMargenPct(compra.margen_pct)}
                        </span>
                      </td>
                      <td className={tdClass}>{compra.proveedor ?? "—"}</td>
                      <td className={tdClass}>{compra.nota ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          )}
        </section>
        <section>
          <SectionTitle>Activo o archivado</SectionTitle>
          {writer ? (
            <Card>
              <ActivoForm codigo={producto.codigo} activo={producto.activo} />
            </Card>
          ) : (
            <ReadOnlyNote />
          )}
        </section>
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

function Datum({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-caps-sm text-muted">{label}</dt>
      <dd className="mt-0.5">{value ?? "—"}</dd>
    </div>
  );
}
