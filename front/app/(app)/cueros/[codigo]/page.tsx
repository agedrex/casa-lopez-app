import type { Metadata } from "next";
import Link from "next/link";
import { EstadoBadge } from "@/components/cueros/estado-badge";
import { Metric } from "@/components/cueros/grupo-card";
import {
  Card,
  CardItem,
  CardList,
  ErrorNotice,
  Notice,
  numClass,
  PageHeader,
  ResponsiveTable,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { grupoTitulo, movimientoLabel } from "@/lib/cueros";
import { formatDate, formatMoney, formatQuantity } from "@/lib/format";
import { isCorteOnly } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Material, PiezaCueroDetalle } from "@/lib/types";

export const metadata: Metadata = { title: "Historia de una piel" };

const m2 = (value: string | null) => `${formatQuantity(value)} m²`;

export default async function PielPage({
  params,
}: {
  params: Promise<{ codigo: string }>;
}) {
  const { user } = await requireSession();
  const { codigo } = await params;
  const showMoney = !isCorteOnly(user.role);
  const [pieza, materiales] = await Promise.all([
    apiGet<PiezaCueroDetalle>(`/cueros/${encodeURIComponent(codigo)}`),
    apiGet<Material[]>("/materiales"),
  ]);

  const volver = (
    <Link
      href="/cueros"
      className="inline-flex min-h-12 items-center text-base underline decoration-gold underline-offset-4"
    >
      ← Volver a cueros
    </Link>
  );

  if (!pieza.ok) {
    return (
      <>
        <PageHeader eyebrow="Cueros" title="Piel" />
        <ErrorNotice
          title={
            pieza.status === 404
              ? "No encontramos esa piel."
              : "No pudimos cargar la piel."
          }
          message={pieza.message}
        />
        <div className="mt-4">{volver}</div>
      </>
    );
  }

  const data = pieza.data;
  const nombre =
    (materiales.ok
      ? materiales.data.find((item) => item.codigo === data.material)?.nombre
      : undefined) ?? data.material;

  return (
    <>
      <PageHeader
        eyebrow="Cueros"
        title={`Piel ${data.codigo}`}
        description={grupoTitulo(nombre, data.color)}
        actions={volver}
      />
      <div className="space-y-10">
        <Card>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <EstadoBadge estado={data.estado} />
            <span className="text-base text-muted">
              Compra: {formatDate(data.fecha_de_compra)}
              {data.proveedor ? ` · ${data.proveedor}` : ""}
            </span>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
            <Metric label="Disponible" highlight>
              {m2(data.disponible)}
            </Metric>
            <Metric label="Inicial">{m2(data.m2_iniciales)}</Metric>
            <Metric label="Desperdicio natural">{m2(data.natural)}</Metric>
            <Metric label="Cortado">{m2(data.cortado)}</Metric>
            <Metric label="Irrecuperable">{m2(data.irrecuperable)}</Metric>
            {showMoney && data.precio_pagado_por_m2 && data.moneda ? (
              <Metric label="Precio pagado por m²">
                {formatMoney(data.precio_pagado_por_m2, data.moneda)}
              </Metric>
            ) : null}
          </dl>
        </Card>
        <section>
          <SectionTitle>Historia</SectionTitle>
          {data.movimientos.length === 0 ? (
            <Notice tone="info" title="Todavía no tiene movimientos." />
          ) : (
            <ResponsiveTable
              cards={
                <CardList>
                  {data.movimientos.map((movimiento) => (
                    <CardItem key={movimiento.id}>
                      <p className="text-base font-bold">
                        {movimientoLabel(movimiento.tipo)} · {m2(movimiento.m2)}
                      </p>
                      <p className="text-sm text-muted">
                        {formatDate(movimiento.fecha)}
                        {movimiento.orden_item_id
                          ? ` · renglón ${movimiento.orden_item_id}`
                          : ""}
                        {movimiento.unidades
                          ? ` · ${formatQuantity(movimiento.unidades)} unidades`
                          : ""}
                      </p>
                    </CardItem>
                  ))}
                </CardList>
              }
              table={
                <TableWrap>
                  <table className={tableClass}>
                    <thead>
                      <tr>
                        <th className={thClass}>Fecha</th>
                        <th className={thClass}>Movimiento</th>
                        <th className={`${thClass} ${numClass}`}>m²</th>
                        <th className={thClass}>Renglón del lote</th>
                        <th className={`${thClass} ${numClass}`}>Unidades</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.movimientos.map((movimiento) => (
                        <tr key={movimiento.id}>
                          <td className={tdClass}>
                            {formatDate(movimiento.fecha)}
                          </td>
                          <td className={tdClass}>
                            {movimientoLabel(movimiento.tipo)}
                          </td>
                          <td className={`${tdClass} ${numClass}`}>
                            {m2(movimiento.m2)}
                          </td>
                          <td className={tdClass}>
                            {movimiento.orden_item_id ?? "—"}
                          </td>
                          <td className={`${tdClass} ${numClass}`}>
                            {formatQuantity(movimiento.unidades)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableWrap>
              }
            />
          )}
        </section>
      </div>
    </>
  );
}
