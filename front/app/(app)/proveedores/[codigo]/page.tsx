import type { Metadata } from "next";
import Link from "next/link";
import { buttonClass, labelClass } from "@/components/cueros/estilos";
import { inputClass } from "@/components/form";
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
  DocumentoProveedor,
  EtapaCatalogo,
  Material,
  MaterialesDeProveedor,
  PedidoProveedor,
  Proveedor,
} from "@/lib/types";
import { MaterialesQueProveeForm } from "../materiales-que-provee";
import { DocumentoCard } from "./documento-card";
import { MaterialNuevoForm } from "./material-nuevo-form";
import { MaterialesDelProveedor } from "./materiales-del-proveedor";
import { PedidoForm } from "./pedido-form";
import { PedidosRecibidos } from "./pedidos-recibidos";

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

const first = (value: string | string[] | undefined) =>
  (Array.isArray(value) ? value[0] : value) ?? "";

export default async function ProveedorPage({
  params,
  searchParams,
}: {
  params: Promise<{ codigo: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { user } = await requireRole("admin");
  const code = decodeCode((await params).codigo);
  const q = first((await searchParams).q).trim();
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
  const [proveedor, documentos, historia, materiales, pedidos, provee, etapas] =
    await Promise.all([
      apiGet<Proveedor>(path),
      apiGet<DocumentoProveedor[]>(
        `${path}/documentos${q ? `?${new URLSearchParams({ q })}` : ""}`,
      ),
      apiGet<MaterialesDeProveedor>(`${path}/materiales`),
      // Only the form needs the catalogs, and only a writer sees it.
      writer ? apiGet<Material[]>("/materiales") : null,
      readsPedidos ? apiGet<PedidoProveedor[]>(`${path}/pedidos`) : null,
      apiGet<string[]>(`${path}/provee`),
      writer ? apiGet<EtapaCatalogo[]>("/catalogo/etapas") : null,
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
          <SectionTitle>Productos que provee</SectionTitle>
          <div className="space-y-6">
            {provee.ok ? (
              writer && materiales?.ok ? (
                <MaterialesQueProveeForm
                  codigo={data.codigo}
                  materials={materialOptions(materiales.data)}
                  selected={provee.data}
                />
              ) : provee.data.length === 0 ? (
                <Notice
                  tone="info"
                  title="Todavía no hay productos marcados."
                />
              ) : (
                <p className="text-sm">{provee.data.join(" · ")}</p>
              )
            ) : (
              <ErrorNotice message={provee.message} />
            )}
          </div>
        </section>

        <section>
          <SectionTitle>Materiales y precios</SectionTitle>
          <div className="space-y-6">
            <p className="text-sm text-muted">
              Lo que este proveedor nos cobra por cada material, con la historia
              de sus precios. Un precio nuevo no reemplaza al anterior: se suma
              y queda la variación.
            </p>
            {historia.ok ? (
              historia.data.materiales.length === 0 ? (
                <Notice
                  tone="info"
                  title="Este proveedor todavía no tiene precios cargados."
                >
                  Cargue el primero abajo y va a aparecer acá con su historia.
                </Notice>
              ) : (
                <MaterialesDelProveedor materiales={historia.data.materiales} />
              )
            ) : (
              <ErrorNotice message={historia.message} />
            )}
          </div>
        </section>

        {readsPedidos ? (
          <section>
            <SectionTitle>Pedidos recibidos</SectionTitle>
            <div className="space-y-6">
              <p className="text-sm text-muted">
                Lo que llegó de este proveedor: qué materiales, cómo vinieron y
                cuánto costó cada unidad. Cada línea carga el precio del
                material desde la fecha de recepción. Un pedido no se edita ni
                se borra: si hay un error, se registra otro.
              </p>
              {writer && materiales?.ok ? (
                <div className="space-y-4">
                  <Card>
                    <h3 className="mb-4 font-bold">
                      Registrar pedido recibido
                    </h3>
                    <PedidoForm
                      codigo={data.codigo}
                      materials={materialOptions(materiales.data)}
                      today={todayIso()}
                    />
                  </Card>
                  <MaterialNuevoForm
                    etapas={materialStages(etapas?.ok ? etapas.data : null)}
                  />
                </div>
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

        <section>
          <SectionTitle>Facturas e imágenes</SectionTitle>
          <div className="space-y-6">
            <form method="get" className="grid gap-4 sm:grid-cols-[1fr_auto]">
              <div>
                <label htmlFor="buscar-documentos" className={labelClass}>
                  Buscar en los archivos
                </label>
                <input
                  id="buscar-documentos"
                  name="q"
                  type="search"
                  defaultValue={q}
                  autoComplete="off"
                  placeholder="Nombre del archivo, número o una palabra del texto"
                  className={inputClass}
                />
              </div>
              <div className="flex items-end">
                <button type="submit" className={buttonClass}>
                  Buscar
                </button>
              </div>
            </form>

            {documentos.ok ? (
              documentos.data.length === 0 ? (
                <Notice
                  tone="info"
                  title={
                    q
                      ? "Ningún archivo coincide con la búsqueda."
                      : "Este proveedor todavía no tiene archivos."
                  }
                />
              ) : (
                <ul className="space-y-4">
                  {documentos.data.map((documento) => (
                    <DocumentoCard key={documento.id} documento={documento} />
                  ))}
                </ul>
              )
            ) : (
              <ErrorNotice message={documentos.message} />
            )}
          </div>
        </section>
      </div>
    </>
  );
}
