import type { Metadata } from "next";
import {
  Badge,
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
import { formatQuantity } from "@/lib/format";
import { requireRole } from "@/lib/session";
import type { Impuesto } from "@/lib/types";
import { BackToAdmin } from "../back-link";

export const metadata: Metadata = { title: "Impuestos" };

const BASE_LABELS: Record<string, string> = {
  COMPRA: "Sobre las compras",
  VENTA: "Sobre las ventas",
  RESULTADO: "Sobre el resultado de la empresa",
};

export default async function ImpuestosPage() {
  await requireRole("admin");
  const result = await apiGet<Impuesto[]>("/impuestos");

  return (
    <>
      <BackToAdmin />
      <PageHeader
        eyebrow="Administración"
        title="Impuestos"
        description="Solo lectura. Si el IVA cuenta como costo del producto es una decisión de negocio todavía abierta (hay que validarla con el contador), por eso no se edita desde acá."
      />
      {result.ok ? (
        <TableWrap>
          <table className={tableClass}>
            <caption className="sr-only">Impuestos y cómo se tratan</caption>
            <thead>
              <tr>
                <th className={thClass}>Impuesto</th>
                <th className={`${thClass} ${numClass}`}>Alícuota</th>
                <th className={thClass}>Base</th>
                <th className={thClass}>¿Es costo del producto?</th>
                <th className={thClass}>Nota</th>
              </tr>
            </thead>
            <tbody>
              {result.data.map((impuesto) => (
                <tr key={impuesto.codigo} className="hover:bg-paper-mid/50">
                  <td className={tdClass}>
                    {impuesto.nombre}
                    <span className="block text-xs text-muted">
                      {impuesto.codigo}
                    </span>
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {impuesto.alicuota === null
                      ? "A confirmar"
                      : formatQuantity(impuesto.alicuota)}
                  </td>
                  <td className={tdClass}>
                    {impuesto.base
                      ? (BASE_LABELS[impuesto.base] ?? impuesto.base)
                      : "—"}
                  </td>
                  <td className={tdClass}>
                    <Badge
                      tone={impuesto.es_costo_del_producto ? "warn" : "neutral"}
                    >
                      {impuesto.es_costo_del_producto ? "Sí" : "No"}
                    </Badge>
                  </td>
                  <td className={`${tdClass} max-w-md text-muted`}>
                    {impuesto.nota ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      ) : (
        <ErrorNotice message={result.message} />
      )}
      <div className="mt-6">
        <Notice tone="info" title="La alícuota es una fracción">
          0,21 es un 21 %. Los impuestos que no son costo no entran en el costo
          del producto.
        </Notice>
      </div>
    </>
  );
}
