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
import { canWrite } from "@/lib/permissions";
import { requireRole } from "@/lib/session";
import type { DocumentoProveedor, Proveedor } from "@/lib/types";
import { ActivoForm } from "./activo-form";
import { DocumentoCard } from "./documento-card";
import { EditarForm } from "./editar-form";
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
  const [proveedor, documentos] = await Promise.all([
    apiGet<Proveedor>(path),
    apiGet<DocumentoProveedor[]>(
      `${path}/documentos${q ? `?${new URLSearchParams({ q })}` : ""}`,
    ),
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
  const writer = canWrite(user.role);
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
