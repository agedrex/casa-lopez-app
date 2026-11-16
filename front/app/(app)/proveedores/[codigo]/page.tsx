import type { Metadata } from "next";
import Link from "next/link";
import {
  Badge,
  Card,
  ErrorNotice,
  Notice,
  PageHeader,
  SectionTitle,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { todayIso } from "@/lib/format";
import { materialStages } from "@/lib/materiales";
import { canWrite, hasRole } from "@/lib/permissions";
import { materialOptions } from "@/lib/proveedores";
import { requireRole } from "@/lib/session";
import type {
  EtapaCatalogo,
  Material,
  PedidoProveedor,
  Proveedor,
  ProveedorProducto,
} from "@/lib/types";
import { PedidoForm } from "./pedido-form";
import { PedidosRecibidos } from "./pedidos-recibidos";
import { ProductosQueVende } from "./productos-que-vende";

export const metadata: Metadata = { title: "Proveedor" };

function BackLink() {
  return (
    <p className="mb-6 text-sm">
      <Link
        href="/proveedores"
        className="text-muted underline decoration-gold underline-offset-4"
      >
        ← Proveedores
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

export default async function ProveedorPage({
  params,
}: {
  params: Promise<{ codigo: string }>;
}) {
  const { user } = await requireRole("admin");
  const code = decodeCode((await params).codigo);
  if (code === null) {
    return (
      <>
        <BackLink />
        <Notice tone="info" title="No encontramos ese proveedor" />
      </>
    );
  }

  const path = `/proveedores/${encodeURIComponent(code)}`;
  const writer = canWrite(user.role);
  // Orders are read by admin and gerente; the taller never sees them (the API refuses them too).
  const readsPedidos =
    hasRole(user.role, "admin") || hasRole(user.role, "gerente");
  const [proveedor, materiales, pedidos, provee, etapas, productos] =
    await Promise.all([
      apiGet<Proveedor>(path),
      // Only the form needs the catalogs, and only a writer sees it.
      writer ? apiGet<Material[]>("/materiales") : null,
      readsPedidos ? apiGet<PedidoProveedor[]>(`${path}/pedidos`) : null,
      apiGet<string[]>(`${path}/provee`),
      writer ? apiGet<EtapaCatalogo[]>("/catalogo/etapas") : null,
      apiGet<ProveedorProducto[]>(`${path}/productos`),
    ]);

  if (!proveedor.ok) {
    return (
      <>
        <BackLink />
        {proveedor.status === 404 ? (
          <Notice tone="info" title="No encontramos ese proveedor">
            Revise el código o vuelva al listado de proveedores.
          </Notice>
        ) : (
          <ErrorNotice message={proveedor.message} />
        )}
      </>
    );
  }

  const data = proveedor.data;
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow={`Proveedor ${data.codigo}`}
        title={data.nombre}
        actions={
          data.activo ? undefined : <Badge tone="neutral">Inactivo</Badge>
        }
      />
      <div className="space-y-10">
        <section>
          <SectionTitle>Productos que ofrece</SectionTitle>
          <div className="space-y-6">
            <p className="text-sm text-muted">
              Elija el tipo (cuero, flex, herrajes…) y escriba el detalle, por
              ejemplo &ldquo;Cuero de carpincho&rdquo;. Al guardar, el producto
              queda también en Materiales. Un precio nuevo se suma y queda el
              anterior.
            </p>
            {productos.ok ? (
              <ProductosQueVende
                codigo={data.codigo}
                productos={productos.data}
                etapas={materialStages(etapas?.ok ? etapas.data : null)}
                materiales={
                  materiales?.ok
                    ? materiales.data.map((m) => ({
                        codigo: m.codigo,
                        label: m.nombre,
                        etapa: m.etapa,
                      }))
                    : []
                }
              />
            ) : (
              <ErrorNotice message={productos.message} />
            )}
          </div>
        </section>

        {readsPedidos ? (
          <section>
            <SectionTitle>Pedidos recibidos</SectionTitle>
            <div className="space-y-6">
              {writer && materiales?.ok ? (
                <Card>
                  <h3 className="mb-3 font-bold">Registrar pedido recibido</h3>
                  <PedidoForm
                    codigo={data.codigo}
                    materials={materialOptions(
                      materiales.data.filter(
                        (m) =>
                          !provee.ok ||
                          provee.data.length === 0 ||
                          provee.data.includes(m.codigo),
                      ),
                    )}
                    today={todayIso()}
                  />
                </Card>
              ) : null}
              {pedidos?.ok ? (
                pedidos.data.length === 0 ? (
                  <Notice
                    tone="info"
                    title="Este proveedor todavía no tiene pedidos registrados."
                  />
                ) : (
                  <PedidosRecibidos pedidos={pedidos.data} />
                )
              ) : pedidos ? (
                <ErrorNotice message={pedidos.message} />
              ) : null}
            </div>
          </section>
        ) : null}
      </div>
    </>
  );
}
