import { fractionToPercentInput } from "@/app/(app)/admin/impuestos/percent";
import { inputClass } from "@/components/form";
import {
  ErrorNotice,
  Notice,
  numClass,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import {
  decimalInputText,
  formatArs,
  formatDate,
  formatPercent,
  parseDecimalInput,
} from "@/lib/format";
import type { PrecioSugerido, PrecioVenta, Rentabilidad } from "@/lib/types";
import { PrecioVentaForm } from "./forms";

/** Saved sale prices, newest first. Lives under "Más detalle" in the sheet. */
export async function PriceHistory({ codigo }: { codigo: string }) {
  const history = await apiGet<PrecioVenta[]>(
    `/productos/${encodeURIComponent(codigo)}/precio-venta`,
  );
  return (
    <section>
      <SectionTitle>Precios de venta guardados</SectionTitle>
      {!history.ok ? (
        <ErrorNotice
          title="No pudimos cargar el historial de precios."
          message={history.message}
        />
      ) : history.data.length === 0 ? (
        <Notice
          tone="info"
          title="Todavía no se guardó ningún precio de venta de este producto."
        />
      ) : (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Desde</th>
                <th className={`${thClass} ${numClass}`}>Precio de venta</th>
                <th className={`${thClass} ${numClass}`}>Margen</th>
                <th className={thClass}>Impuestos</th>
                <th className={`${thClass} ${numClass}`}>Precio final</th>
              </tr>
            </thead>
            <tbody>
              {history.data.map((price) => (
                <tr key={`${price.vigente_desde}-${price.creado_en ?? ""}`}>
                  <td className={tdClass}>{formatDate(price.vigente_desde)}</td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(price.precio_ars)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {price.margen !== null
                      ? `${fractionToPercentInput(price.margen)} %`
                      : "—"}
                  </td>
                  <td className={tdClass}>
                    {price.impuestos?.length
                      ? price.impuestos
                          .map(
                            (tax) =>
                              `${tax.nombre} (${fractionToPercentInput(tax.alicuota)} %)`,
                          )
                          .join(", ")
                      : "—"}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {price.impuestos?.length
                      ? formatArs(price.precio_final)
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
    </section>
  );
}

function marginParam(raw: string): string | null {
  const parsed = raw ? parseDecimalInput(raw) : null;
  // One decimal at most: it is what the saving action accepts (percentToFraction).
  return parsed && /^\d{1,2}(\.\d)?$/.test(parsed) ? parsed : null;
}

/**
 * The sale price of the product: one field, with an optional margin that fills it in
 * (price = cost / (1 - margin), computed by the API). The margin travels in the URL (`?margen=`);
 * nothing is calculated here.
 */
export async function PrecioBlock({
  codigo,
  writer,
  typedMargin,
}: {
  codigo: string;
  writer: boolean;
  typedMargin: string;
}) {
  const base = `/productos/${encodeURIComponent(codigo)}`;
  const margin = marginParam(typedMargin);
  const [saved, suggested] = await Promise.all([
    apiGet<Rentabilidad>(`${base}/rentabilidad`),
    margin
      ? apiGet<PrecioSugerido>(
          `${base}/precio-sugerido?${new URLSearchParams({ margen: margin })}`,
        )
      : Promise.resolve(null),
  ]);

  const savedPrice = saved.ok ? saved.data.precio : null;
  const suggestedPrice = suggested?.ok ? suggested.data.precio : null;
  const prefill = decimalInputText(suggestedPrice ?? savedPrice);

  return (
    <section id="precio" className="scroll-mt-6">
      <SectionTitle>Precio de venta</SectionTitle>
      <div className="grid gap-6 rounded-card border border-line p-5 sm:grid-cols-2">
        <div className="space-y-3">
          <form method="get" action={`${base}#precio`} className="space-y-3">
            <div>
              <label
                htmlFor="precio-margen"
                className="mb-1.5 block text-sm uppercase tracking-caps-sm text-muted sm:text-xs"
              >
                Margen que querés ganar (%) — opcional
              </label>
              <input
                id="precio-margen"
                name="margen"
                inputMode="decimal"
                autoComplete="off"
                placeholder="30"
                defaultValue={typedMargin}
                className={inputClass}
              />
            </div>
            <button
              type="submit"
              className="min-h-12 w-full rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white sm:min-h-0 sm:w-auto"
            >
              Calcular precio
            </button>
          </form>
          {typedMargin && margin === null ? (
            <ErrorNotice
              title="No entendimos ese margen."
              message="Escribí un número entre 0 y 99,9 con un decimal como máximo, por ejemplo 30 o 30,5."
            />
          ) : null}
          {suggested && !suggested.ok ? (
            <ErrorNotice
              title="No pudimos calcular el precio."
              message={suggested.message}
            />
          ) : null}
          {suggested?.ok && suggested.data.precio === null ? (
            <Notice tone="info" title="Todavía no hay costo para calcularlo." />
          ) : null}
          <p className="text-xs text-muted">
            Precio = costo ÷ (1 − margen). El margen es sobre el precio de
            venta.
          </p>
        </div>
        <div className="space-y-3">
          {writer ? (
            <PrecioVentaForm
              codigo={codigo}
              precio={prefill}
              margen={suggestedPrice && margin ? margin : undefined}
            />
          ) : (
            <p className="font-display text-3xl">
              {savedPrice ? formatArs(savedPrice) : "Sin precio"}
            </p>
          )}
          {saved.ok && saved.data.margen_pct !== null && !margin ? (
            <p className="text-sm text-muted">
              Con el precio guardado, tu margen es{" "}
              {formatPercent(saved.data.margen_pct)}.
            </p>
          ) : null}
          {suggestedPrice ? (
            <p className="text-sm text-muted">
              Calculado con {typedMargin}% de margen. Guardalo para usarlo.
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
