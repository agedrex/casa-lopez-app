import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FormularioConsumos } from "@/components/formulario-consumos";
import { Badge, ErrorNotice, Notice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { accionesDe, estadoLabel, estadoTone } from "@/lib/formulario";
import { isTallerOnly } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { Formulario } from "@/lib/types";
import { DuplicarForm } from "./duplicar-form";
import { FormularioEditor } from "./editor";
import { PrintButton } from "./print-button";

export const metadata: Metadata = { title: "Formulario de consumos" };

function decodeCode(raw: string): string | null {
  try {
    return decodeURIComponent(raw);
  } catch {
    return null;
  }
}

export default async function FormularioPage({
  params,
}: {
  params: Promise<{ codigo: string }>;
}) {
  const { user } = await requireSession();
  const codigo = decodeCode((await params).codigo);
  if (codigo === null) notFound();

  const result = await apiGet<Formulario>(
    `/formularios/${encodeURIComponent(codigo)}`,
  );
  if (!result.ok) {
    // Rendered inline: notFound() would be streamed as a late swap because the page sits inside a Suspense boundary.
    return (
      <>
        <BackLink />
        {result.status === 404 ? (
          <Notice tone="info" title="No encontramos ese formulario">
            Revisá el código o volvé al listado de formularios.
          </Notice>
        ) : (
          <ErrorNotice message={result.message} />
        )}
      </>
    );
  }

  const formulario = result.data;
  const acciones = accionesDe(user.role, formulario.estado);
  const hechos = [
    ["Creado", formulario.created_at],
    ["Enviado al taller", formulario.enviado_en],
    ["Completado", formulario.completado_en],
    ["Validado", formulario.validado_en],
  ].filter((hecho): hecho is [string, string] => hecho[1] !== null);

  return (
    <>
      <div className="print:hidden">
        <BackLink />
        <PageHeader
          eyebrow={`Formulario ${formulario.codigo}`}
          title={formulario.articulo}
          clampTitle
          actions={
            <Badge tone={estadoTone(formulario.estado)}>
              {estadoLabel(formulario.estado)}
            </Badge>
          }
        />
        <p className="-mt-4 mb-6 text-sm text-muted">
          {formulario.producto ? (
            <>
              {isTallerOnly(user.role) ? (
                `Producto ${formulario.producto}`
              ) : (
                <Link
                  href={`/productos/${encodeURIComponent(formulario.producto)}`}
                  className="underline decoration-gold underline-offset-4"
                >
                  Producto {formulario.producto}
                </Link>
              )}
              {" · "}
            </>
          ) : null}
          {formulario.taller ? `Taller ${formulario.taller} · ` : ""}
          {hechos
            .map(([etiqueta, fecha]) => `${etiqueta} ${formatDate(fecha)}`)
            .join(" · ")}
        </p>
        <Aviso formulario={formulario} />
      </div>
      <div className="space-y-6">
        {acciones.editar ? (
          <FormularioEditor formulario={formulario} acciones={acciones} />
        ) : (
          <>
            <FormularioConsumos formulario={formulario} mode="readonly" />
            <div className="print:hidden">
              <PrintButton />
            </div>
          </>
        )}
        {acciones.duplicar ? <DuplicarForm codigo={formulario.codigo} /> : null}
      </div>
    </>
  );
}

function BackLink() {
  return (
    <p className="mb-6 text-sm print:hidden">
      <Link
        href="/formularios"
        className="text-muted underline decoration-gold underline-offset-4"
      >
        ← Formularios
      </Link>
    </p>
  );
}

/** The review comment the admin left: a request to the taller while ENVIADO, history afterwards. */
function Aviso({ formulario }: { formulario: Formulario }) {
  if (!formulario.comentario_revision) return null;
  const pendiente = formulario.estado === "ENVIADO";
  return (
    <div className="mb-6">
      <Notice
        tone={pendiente ? "warn" : "info"}
        title={
          pendiente
            ? "El administrador pidió cambios"
            : "Último comentario de revisión"
        }
      >
        <p className="whitespace-pre-wrap break-words">
          {formulario.comentario_revision}
        </p>
      </Notice>
    </div>
  );
}
