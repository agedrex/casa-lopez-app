import { ErrorNotice, Notice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import type {
  FormularioResumen,
  OrdenDetalle,
  OrdenResumen,
} from "@/lib/types";
import { HojasGrid } from "./hojas-grid";
import { LotesGrid } from "./lotes-grid";

/** The taller sees each lot with its products inline; this caps the detail calls (one per lot). */
const TALLER_DETAIL_LIMIT = 30;

/**
 * The single screen of the taller: its lots and its models, each in the same grid as the admin's, with no
 * filters or extra panels. No money of any kind.
 */
export async function LotesYModelos({ userId }: { userId: string }) {
  const [ordenes, hojas] = await Promise.all([
    apiGet<OrdenResumen[]>("/ordenes"),
    apiGet<FormularioResumen[]>("/formularios"),
  ]);
  // One detail call per lot, in parallel, to list what to make in each.
  const detalles = ordenes.ok
    ? await Promise.all(
        ordenes.data
          .slice(0, TALLER_DETAIL_LIMIT)
          .map((orden) =>
            apiGet<OrdenDetalle>(
              `/ordenes/${encodeURIComponent(orden.codigo)}`,
            ),
          ),
      )
    : [];
  const renglones: Record<string, OrdenDetalle["items"]> = {};
  detalles.forEach((detalle, index) => {
    const orden = ordenes.ok ? ordenes.data[index] : undefined;
    if (orden && detalle.ok) renglones[orden.codigo] = detalle.data.items;
  });

  return (
    <>
      <PageHeader eyebrow="Producción" title="Lotes y modelos" />
      <div className="space-y-10">
        <section aria-labelledby="taller-lotes">
          <h2 id="taller-lotes" className="mb-4 text-xl">
            Lotes
          </h2>
          {ordenes.ok ? (
            ordenes.data.length === 0 ? (
              <Notice tone="info" title="Todavía no hay lotes cargados." />
            ) : (
              <LotesGrid ordenes={ordenes.data} renglones={renglones} taller />
            )
          ) : (
            <ErrorNotice message={ordenes.message} />
          )}
        </section>
        <section aria-labelledby="taller-modelos">
          <h2 id="taller-modelos" className="mb-4 text-xl">
            Modelos
          </h2>
          {hojas.ok ? (
            hojas.data.length === 0 ? (
              <Notice tone="info" title="Todavía no hay modelos.">
                Cuando te envíen un modelo aparece acá.
              </Notice>
            ) : (
              <HojasGrid hojas={hojas.data} userId={userId} />
            )
          ) : (
            <ErrorNotice message={hojas.message} />
          )}
        </section>
      </div>
    </>
  );
}
