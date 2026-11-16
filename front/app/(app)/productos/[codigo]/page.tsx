import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  Badge,
  ErrorNotice,
  Notice,
  numClass,
  PageHeader,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { formatQuantity, lifecycleLabel } from "@/lib/format";
import { isTallerOnly } from "@/lib/permissions";
import { collapseSpaces } from "@/lib/productos";
import { requireSession } from "@/lib/session";
import type { Ficha } from "@/lib/types";
import { ConsumoBlock } from "./consumo-block";

export const metadata: Metadata = { title: "Ficha de producto" };

function decodeCode(raw: string): string | null {
  try {
    return decodeURIComponent(raw);
  } catch {
    return null;
  }
}

export default async function FichaPage({
  params,
}: {
  params: Promise<{ codigo: string }>;
}) {
  const { user } = await requireSession();
  const code = decodeCode((await params).codigo);
  if (code === null) notFound();

  const result = await apiGet<Ficha>(`/productos/${encodeURIComponent(code)}`);

  if (!result.ok) {
    // A missing product is rendered inline: notFound() would be streamed as a late
    // client-side swap here because the page already sits inside a Suspense boundary.
    return (
      <>
        <BackLink taller={isTallerOnly(user.role)} />
        {result.status === 404 ? (
          <Notice tone="info" title="No encontramos ese producto">
            Revise el código o vuelva al listado de productos.
          </Notice>
        ) : (
          <ErrorNotice message={result.message} />
        )}
      </>
    );
  }

  const ficha = result.data;
  return (
    <>
      <BackLink taller={isTallerOnly(user.role)} />
      <PageHeader
        eyebrow={`Producto ${ficha.codigo}`}
        title={collapseSpaces(ficha.nombre)}
        clampTitle
        actions={
          <div className="flex flex-wrap gap-2">
            <Badge>{lifecycleLabel(ficha.estado_del_ciclo)}</Badge>
            {ficha.es_kit ? <Badge>Kit</Badge> : null}
          </div>
        }
      />
      <p className="-mt-4 mb-8 text-sm text-muted">
        {[ficha.modelo, ficha.cuero, ficha.color].filter(Boolean).join(" · ")}
      </p>

      <div className="space-y-10">
        <ConsumoBlock ficha={ficha} />
        {ficha.componentes.length > 0 ? <Components ficha={ficha} /> : null}
      </div>
    </>
  );
}

function BackLink({ taller }: { taller: boolean }) {
  return (
    <p className="mb-6 text-sm">
      <Link
        href={taller ? "/fabricacion" : "/productos"}
        className="text-muted underline decoration-gold underline-offset-4"
      >
        {taller ? "← Lotes" : "← Productos"}
      </Link>
    </p>
  );
}

function Components({ ficha }: { ficha: Ficha }) {
  return (
    <section>
      <SectionTitle>Componentes del kit</SectionTitle>
      <TableWrap>
        <table className={tableClass}>
          <thead>
            <tr>
              <th className={thClass}>Producto</th>
              <th className={`${thClass} ${numClass}`}>Cantidad</th>
            </tr>
          </thead>
          <tbody>
            {ficha.componentes.map((componente) => (
              <tr key={componente.producto}>
                <td className={tdClass}>
                  <Link
                    href={`/productos/${encodeURIComponent(componente.producto)}`}
                    className="underline decoration-gold underline-offset-4"
                  >
                    {componente.producto}
                  </Link>
                </td>
                <td className={`${tdClass} ${numClass}`}>
                  {formatQuantity(componente.cantidad)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
    </section>
  );
}
