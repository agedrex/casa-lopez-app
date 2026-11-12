import { ErrorNotice, SectionTitle } from "@/components/ui";
import { apiGet } from "@/lib/api";
import type { ModeloDetalle } from "@/lib/types";
import {
  ConsumosTable,
  EditarConsumos,
  loadForros,
} from "../modelos/modelo-consumos";

/**
 * "Consumo": the consumptions per unit of the product's model, editable. Admin only: `/modelos`
 * is closed to the other roles. A change reaches every product of the model.
 */
export async function ModeloBlock({ codigo }: { codigo: string }) {
  const [result, forros] = await Promise.all([
    apiGet<ModeloDetalle>(`/modelos/${encodeURIComponent(codigo)}`),
    loadForros(),
  ]);
  return (
    <section id="consumo" className="space-y-4">
      <SectionTitle>Consumo</SectionTitle>
      {result.ok ? (
        <>
          <ConsumosTable modelo={result.data} />
          <EditarConsumos modelo={result.data} forros={forros} />
        </>
      ) : (
        <ErrorNotice
          title="No pudimos cargar los consumos."
          message={result.message}
        />
      )}
    </section>
  );
}
