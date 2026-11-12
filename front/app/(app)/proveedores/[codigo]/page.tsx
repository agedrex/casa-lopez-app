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
import { stageLabel, todayIso } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireRole } from "@/lib/session";
import type {
  Catalogos,
  DocumentoProveedor,
  Material,
  MaterialesDeProveedor,
  Proveedor,
} from "@/lib/types";
import { ActivoForm } from "./activo-form";
import { DocumentoCard } from "./documento-card";
import { EditarForm } from "./editar-form";
import { MaterialesDelProveedor } from "./materiales-del-proveedor";
import { type MaterialOption, PrecioForm } from "./precio-form";
import { SubirDocumentosForm } from "./subir-documentos-form";

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
  const [proveedor, documentos, historia, materiales, catalogos] =
    await Promise.all([
      apiGet<Proveedor>(path),
      apiGet<DocumentoProveedor[]>(
        `${path}/documentos${q ? `?${new URLSearchParams({ q })}` : ""}`,
      ),
      apiGet<MaterialesDeProveedor>(`${path}/materiales`),
      // Only the form needs the catalogs, and only a writer sees it.
      writer ? apiGet<Material[]>("/materiales") : null,
      writer ? apiGet<Catalogos>("/catalogos") : null,
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
            {writer && materiales?.ok ? (
              <Card>
                <h3 className="mb-1 font-bold">
                  Cargar un precio de este proveedor
                </h3>
                <p className="mb-4 text-sm text-muted">
                  Desde esa fecha, este pasa a ser el precio que usan los costos
                  para ese material.
                </p>
                <PrecioForm
                  codigo={data.codigo}
                  materials={materialOptions(materiales.data)}
                  colores={catalogos?.ok ? catalogos.data.colores : []}
                  today={todayIso()}
                />
              </Card>
            ) : null}
            {writer && materiales && !materiales.ok ? (
              <ErrorNotice message={materiales.message} />
            ) : null}
          </div>
        </section>

        <section>
          <SectionTitle>Facturas e imágenes</SectionTitle>
          <div className="space-y-6">
            {writer ? (
              <Card>
                <SubirDocumentosForm codigo={data.codigo} />
              </Card>
            ) : null}

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
                    <DocumentoCard
                      key={documento.id}
                      documento={documento}
                      writer={writer}
                    />
                  ))}
                </ul>
              )
            ) : (
              <ErrorNotice message={documentos.message} />
            )}
          </div>
        </section>

        <section>
          <SectionTitle>Datos del proveedor</SectionTitle>
          <Card>
            <EditarForm
              codigo={data.codigo}
              initial={{
                nombre: data.nombre,
                cuit: data.cuit,
                contacto: data.contacto,
                telefono: data.telefono,
                direccion: data.direccion,
                nota: data.nota,
              }}
            />
          </Card>
        </section>

        <section>
          <SectionTitle>Activo o inactivo</SectionTitle>
          <Card>
            <ActivoForm codigo={data.codigo} activo={data.activo} />
          </Card>
        </section>
      </div>
    </>
  );
}

function materialOptions(materiales: Material[]): MaterialOption[] {
  return materiales
    .filter((m) => m.cotizable)
    .map((m) => ({
      codigo: m.codigo,
      label: `${m.codigo} · ${m.nombre} (${m.unidad_de_consumo})`,
      unidad: m.unidad_de_consumo,
      group: stageLabel(m.etapa),
    }));
}
