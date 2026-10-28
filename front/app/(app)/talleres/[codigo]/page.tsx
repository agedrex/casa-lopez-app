import type { Metadata } from "next";
import Link from "next/link";
import { ReadOnlyNote } from "@/components/form";
import { OrdersTable } from "@/components/orders-table";
import { TallerBadges } from "@/components/taller-badges";
import {
  Card,
  ErrorNotice,
  Notice,
  PageHeader,
  SectionTitle,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatArs, formatDate, formatQuantity } from "@/lib/format";
import { canWrite } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { TallerDetalle } from "@/lib/types";
import { ActivoForm } from "./activo-form";

export const metadata: Metadata = { title: "Taller" };

function BackLink() {
  return (
    <p className="mb-6 text-sm">
      <Link
        href="/talleres"
        className="text-muted underline decoration-gold underline-offset-4"
      >
        ← Talleres
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

export default async function TallerPage({
  params,
}: {
  params: Promise<{ codigo: string }>;
}) {
  const { user } = await requireSession();
  const code = decodeCode((await params).codigo);
  if (code === null) {
    return (
      <>
        <BackLink />
        <Notice tone="info" title="No encontramos ese taller" />
      </>
    );
  }
  const result = await apiGet<TallerDetalle>(
    `/talleres/${encodeURIComponent(code)}`,
  );
  if (!result.ok) {
    return (
      <>
        <BackLink />
        {result.status === 404 ? (
          <Notice tone="info" title="No encontramos ese taller">
            Revise el código o vuelva al listado de talleres.
          </Notice>
        ) : (
          <ErrorNotice message={result.message} />
        )}
      </>
    );
  }

  const taller = result.data;
  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow={`Taller ${taller.codigo}`}
        title={taller.nombre}
        actions={<TallerBadges taller={taller} />}
      />
      <div className="space-y-10">
        {taller.ejemplo ? (
          <Notice title="Este es un taller de ejemplo">
            Se cargó para probar la aplicación: reemplácelo por el taller real
            antes de registrar precios verdaderos.
          </Notice>
        ) : null}
        <section aria-label="Resumen del taller">
          <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Lotes" value={String(taller.lotes)} />
            <Metric label="Unidades" value={formatQuantity(taller.unidades)} />
            <Metric
              label="Cobró en total"
              value={formatArs(taller.cobro_total_ars)}
              hint="Cantidad por precio pagado, en todos sus lotes"
            />
            <Metric
              label="Último lote"
              value={formatDate(taller.ultimo_lote)}
            />
          </dl>
        </section>
        <section>
          <SectionTitle>Datos</SectionTitle>
          <Card>
            <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
              <Datum label="CUIT" value={taller.cuit} />
              <Datum label="Teléfono" value={taller.telefono} />
              <Datum label="Contacto" value={taller.contacto} />
              <Datum label="Dirección" value={taller.direccion} />
              <Datum label="Nota" value={taller.nota} />
            </dl>
          </Card>
        </section>
        <section>
          <SectionTitle>Lotes</SectionTitle>
          {taller.ordenes.length === 0 ? (
            <Notice tone="info" title="Este taller todavía no tiene lotes." />
          ) : (
            <OrdersTable ordenes={taller.ordenes} />
          )}
        </section>
        <section>
          <SectionTitle>Activo o inactivo</SectionTitle>
          {canWrite(user.role) ? (
            <Card>
              <ActivoForm codigo={taller.codigo} activo={taller.activo} />
            </Card>
          ) : (
            <ReadOnlyNote />
          )}
        </section>
      </div>
    </>
  );
}

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-card">
      <dt className="text-xs uppercase tracking-caps-sm text-muted">{label}</dt>
      <dd className="mt-2 font-display text-2xl tabular-nums">{value}</dd>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </div>
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
