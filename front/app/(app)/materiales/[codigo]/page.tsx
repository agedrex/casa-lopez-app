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
  formatDate,
  formatMoney,
  formatQuantity,
  formatRate,
} from "@/lib/format";
import { requireRole } from "@/lib/session";
import type { MaterialHistorial } from "@/lib/types";

export const metadata: Metadata = { title: "Material" };

export default async function MaterialPage({
  params,
}: {
  params: Promise<{ codigo: string }>;
}) {
  await requireRole("admin");
  const { codigo } = await params;
  const result = await apiGet<MaterialHistorial>(
    `/materiales/${encodeURIComponent(codigo)}/pedidos`,
  );

  return (
    <>
      <p className="mb-6 text-sm">
        <Link
          href="/materiales"
          className="text-muted underline decoration-gold underline-offset-4"
        >
          ← Materiales
        </Link>
      </p>
      {!result.ok ? (
        <ErrorNotice message={result.message} />
      ) : (
        <Ficha material={result.data} />
      )}
    </>
  );
}

function Ficha({ material }: { material: MaterialHistorial }) {
  const { pedidos } = material;
  return (
    <>
      <PageHeader
        eyebrow={material.codigo}
        title={material.nombre}
        description="Cada pedido que trajo este material y a qué precio llegó. Ese es el costo real que se usa después en los productos y los lotes."
      />
      <div className="mb-8 grid gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-xs uppercase text-muted">Recibido en total</p>
          <p className="text-xl font-bold">
            {formatQuantity(material.recibido)} {material.unidad_de_consumo}
          </p>
          <p className="mt-1 text-xs text-muted">
            Suma de los pedidos. Todavía no se descuenta lo que se usó.
          </p>
        </Card>
        <Card>
          <p className="text-xs uppercase text-muted">Último precio</p>
          <p className="text-xl font-bold">
            {pedidos[0]
              ? `${formatMoney(pedidos[0].precio_unitario, pedidos[0].moneda)} / ${material.unidad_de_consumo}`
              : "—"}
          </p>
        </Card>
        <Card>
          <p className="text-xs uppercase text-muted">Pedidos</p>
          <p className="text-xl font-bold">{pedidos.length}</p>
        </Card>
      </div>
      {pedidos.length === 0 ? (
        <Notice
          tone="info"
          title="Todavía no llegó ningún pedido con este material."
        />
      ) : (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Fecha</th>
                <th className={thClass}>Pedido</th>
                <th className={thClass}>Proveedor</th>
                <th className={`${thClass} ${numClass}`}>Llegó</th>
                <th className={`${thClass} ${numClass}`}>
                  Precio por presentación
                </th>
                <th className={`${thClass} ${numClass}`}>
                  Precio por {material.unidad_de_consumo}
                </th>
              </tr>
            </thead>
            <tbody>
              {pedidos.map((p) => (
                <tr
                  key={`${p.pedido}-${p.precio_unitario}-${p.cantidad_recibida}`}
                >
                  <td className={tdClass}>
                    {formatDate(p.fecha_de_recepcion)}
                  </td>
                  <td className={tdClass}>{p.pedido}</td>
                  <td className={tdClass}>
                    <Link
                      href={`/proveedores/${encodeURIComponent(p.proveedor)}`}
                      className="underline decoration-gold underline-offset-4"
                    >
                      {p.proveedor_nombre}
                    </Link>
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatQuantity(p.cantidad_recibida)}{" "}
                    {material.unidad_de_consumo}
                    <span className="block text-xs text-muted">
                      {formatQuantity(p.cantidad_presentaciones)}{" "}
                      {p.presentacion}
                    </span>
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatMoney(p.precio_por_presentacion, p.moneda)}
                    {p.iva_incluido ? (
                      <span className="block text-xs text-muted">con IVA</span>
                    ) : null}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {p.moneda} {formatRate(p.precio_unitario)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
    </>
  );
}
