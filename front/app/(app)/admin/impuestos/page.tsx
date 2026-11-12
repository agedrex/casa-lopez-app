import type { Metadata } from "next";
import {
  Badge,
  Card,
  ErrorNotice,
  Notice,
  PageHeader,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { requireRole } from "@/lib/session";
import type { Impuesto } from "@/lib/types";
import {
  AlicuotaForm,
  ImpuestoActivoForm,
  ImpuestoForm,
} from "./impuesto-forms";

export const metadata: Metadata = { title: "Impuestos" };

export default async function ImpuestosPage() {
  await requireRole("admin");
  const result = await apiGet<Impuesto[]>("/impuestos");

  return (
    <>
      <PageHeader
        eyebrow="Administración"
        title="Impuestos"
        description="Cada impuesto activo se calcula sobre el precio de venta que designás para un producto, no sobre su costo. Nada se borra: un impuesto que ya no corre se desactiva."
      />
      <div className="space-y-12">
        <section>
          <SectionTitle>Impuestos cargados</SectionTitle>
          {result.ok ? (
            <TableWrap>
              <table className={tableClass}>
                <caption className="sr-only">
                  Impuestos y su porcentaje sobre el precio de venta
                </caption>
                <thead>
                  <tr>
                    <th className={thClass}>Impuesto</th>
                    <th className={thClass}>Porcentaje</th>
                    <th className={thClass}>Estado</th>
                    <th className={thClass}>Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {result.data.length === 0 ? (
                    <tr>
                      <td className={tdClass} colSpan={4}>
                        Todavía no hay impuestos. Los que cargues abajo se suman
                        al precio de venta.
                      </td>
                    </tr>
                  ) : null}
                  {result.data.map((impuesto) => (
                    <tr key={impuesto.codigo} className="hover:bg-paper-mid/50">
                      <td className={tdClass}>
                        {impuesto.nombre}
                        <span className="block text-xs text-muted">
                          {impuesto.codigo}
                        </span>
                      </td>
                      <td className={tdClass}>
                        <AlicuotaForm
                          // The key restarts the field when the saved value changes.
                          key={`${impuesto.codigo}-${impuesto.alicuota}`}
                          codigo={impuesto.codigo}
                          nombre={impuesto.nombre}
                          alicuota={impuesto.alicuota}
                        />
                      </td>
                      <td className={tdClass}>
                        <Badge tone={impuesto.activo ? "good" : "warn"}>
                          {impuesto.activo ? "Activo" : "Desactivado"}
                        </Badge>
                        {impuesto.alicuota === null ? (
                          <span className="block text-xs text-muted">
                            Sin porcentaje: no suma hasta que lo cargue.
                          </span>
                        ) : null}
                      </td>
                      <td className={tdClass}>
                        <ImpuestoActivoForm
                          codigo={impuesto.codigo}
                          nombre={impuesto.nombre}
                          activo={impuesto.activo}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          ) : (
            <ErrorNotice message={result.message} />
          )}
        </section>
        <section>
          <SectionTitle>Nuevo impuesto</SectionTitle>
          <Card>
            <ImpuestoForm />
          </Card>
        </section>
      </div>
      <div className="mt-6">
        <Notice tone="info" title="No cambian el costo">
          Los impuestos se suman al precio de venta (en la ficha del producto
          ves el desglose y el precio final). El costo y las cotizaciones no
          cambian, y el margen real se sigue calculando sobre el precio sin
          impuestos. Si el IVA cuenta como costo del producto es una decisión
          abierta que hay que validar con el contador.
        </Notice>
      </div>
    </>
  );
}
