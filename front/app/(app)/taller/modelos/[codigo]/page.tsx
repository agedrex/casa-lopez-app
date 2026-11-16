import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { HojaConsumos } from "@/components/formulario-consumos";
import {
  Badge,
  Card,
  ErrorNotice,
  Notice,
  PageHeader,
  SectionTitle,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import {
  ESTADO_TONE,
  estadoLabel,
  modoDeHoja,
  puedeSubirFoto,
} from "@/lib/formularios";
import { sizeLabel } from "@/lib/modelos";
import { canFillFormularios, hasRole } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { FormularioDetalle, ModeloDetalle } from "@/lib/types";
import { FotoModelo } from "../../../productos/modelos/[codigo]/foto-modelo";
import { RevisionHoja } from "./revision";

export const metadata: Metadata = { title: "Hoja de consumos" };

function decodeCode(raw: string): string | null {
  try {
    return decodeURIComponent(raw);
  } catch {
    return null;
  }
}

export default async function HojaDelModeloPage({
  params,
}: {
  params: Promise<{ codigo: string }>;
}) {
  const { user } = await requireSession();
  if (!canFillFormularios(user.role)) redirect("/");
  const esAdmin = hasRole(user.role, "admin");
  const volver = (
    <p className="mb-3 text-sm">
      <Link
        href="/taller/modelos"
        className="text-muted underline decoration-gold underline-offset-4"
      >
        ← {esAdmin ? "Hojas de consumos" : "Mis modelos"}
      </Link>
    </p>
  );

  const codigo = decodeCode((await params).codigo);
  const result = codigo
    ? await apiGet<FormularioDetalle>(
        `/formularios/${encodeURIComponent(codigo)}`,
      )
    : null;
  if (!result || !result.ok) {
    return (
      <>
        {volver}
        {result && !result.ok && result.status !== 404 ? (
          <ErrorNotice message={result.message} />
        ) : (
          <Notice tone="info" title="No encontramos esa hoja">
            Puede que no exista o que todavía no esté disponible para vos.
          </Notice>
        )}
      </>
    );
  }

  const hoja = result.data;
  const modelo = hoja.modelo
    ? await apiGet<ModeloDetalle>(`/modelos/${encodeURIComponent(hoja.modelo)}`)
    : null;
  const datos = modelo?.ok ? modelo.data : null;
  const modo = modoDeHoja(user.role, hoja.estado);

  return (
    <>
      {volver}
      <PageHeader
        eyebrow="Hoja de consumos"
        title={hoja.articulo}
        clampTitle
        actions={
          <div className="flex flex-col items-start gap-2 sm:items-end">
            <div className="sm:text-right">
              <p className="text-xs uppercase tracking-caps-sm text-muted">
                ID del modelo
              </p>
              <h2 className="text-lg tabular-nums">{hoja.modelo ?? "—"}</h2>
            </div>
            <Badge tone={ESTADO_TONE[hoja.estado]}>
              {estadoLabel(hoja.estado)}
            </Badge>
          </div>
        }
      />
      <div className="space-y-5">
        {hoja.comentario_revision && hoja.estado === "ENVIADO" ? (
          <Notice title="El administrador devolvió esta hoja con un comentario">
            {hoja.comentario_revision}
          </Notice>
        ) : null}
        {hoja.estado === "COMPLETADO" && !esAdmin ? (
          <Notice tone="info" title="La hoja está en revisión">
            El administrador la va a validar o te la devuelve con comentarios.
          </Notice>
        ) : null}
        {hoja.estado === "VALIDADO" ? (
          <Notice tone="info" title="La hoja está validada">
            Las medidas pasaron al modelo y la hoja ya no se puede modificar.
            {esAdmin && hoja.modelo ? (
              <>
                {" "}
                <Link
                  href={`/productos/modelos/${encodeURIComponent(hoja.modelo)}`}
                  className="underline decoration-gold underline-offset-4"
                >
                  Ver el modelo {hoja.modelo}
                </Link>
              </>
            ) : null}
          </Notice>
        ) : null}

        <section aria-label="Datos del modelo">
          <Card>
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
              <Datum label="Categoría" value={datos?.categoria ?? null} />
              <Datum
                label="Tamaño"
                value={datos ? sizeLabel(datos.tamano) : null}
              />
              <Datum
                label="Hoja"
                value={`${hoja.codigo} · creada ${formatDateTime(hoja.created_at)}`}
              />
              <div className="sm:col-span-3">
                <Datum label="Notas del modelo" value={hoja.nota} />
              </div>
            </dl>
          </Card>
        </section>

        {hoja.modelo ? (
          <section aria-label="Foto">
            <Card>
              <FotoModelo
                codigo={hoja.modelo}
                nombre={hoja.articulo}
                tieneFoto={datos?.tiene_foto ?? false}
                puedeSubir={puedeSubirFoto(
                  user.role,
                  hoja.estado,
                  hoja.creado_por,
                  user.id,
                )}
              />
            </Card>
          </section>
        ) : null}

        <section>
          <Card>
            <HojaConsumos
              key={`${hoja.estado}-${hoja.completado_en ?? ""}`}
              codigo={hoja.codigo}
              lineas={hoja.lineas}
              modo={modo}
            />
          </Card>
        </section>

        {modo === "revisar" ? (
          <section>
            <SectionTitle>Revisión</SectionTitle>
            <Card>
              <RevisionHoja codigo={hoja.codigo} />
            </Card>
          </section>
        ) : null}
      </div>
    </>
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
