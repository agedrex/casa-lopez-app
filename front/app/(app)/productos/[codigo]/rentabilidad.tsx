import { fractionToPercentInput } from "@/app/(app)/admin/impuestos/percent";
import {
  MC_EXPLICACION,
  VERDICT_SENTENCE,
  VeredictoBadge,
} from "@/components/cvu";
import { inputClass } from "@/components/form";
import {
  Card,
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
  sameDecimalText,
} from "@/lib/format";
import type { PrecioVenta, Rentabilidad } from "@/lib/types";
import { PrecioVentaForm } from "./forms";

const MOTIVO_SENTENCE = {
  SIN_PRECIO:
    "Todavía no hay un precio de venta para este producto. Escribí uno arriba para ver si te conviene.",
  SIN_COSTO_VARIABLE:
    "Todavía no se puede calcular cuánto cuesta fabricar este producto: falta cargar el dólar o algún precio.",
} as const;

function Cifra({
  titulo,
  valor,
  detalle,
}: {
  titulo: string;
  valor: string;
  detalle: string;
}) {
  return (
    <div className="rounded-card border border-line p-4">
      <h3 className="text-sm text-muted">{titulo}</h3>
      <p className="mt-2 text-2xl font-bold tabular-nums">{valor}</p>
      <p className="mt-1 text-xs text-muted">{detalle}</p>
    </div>
  );
}

function Resultado({ result }: { result: Rentabilidad }) {
  if (result.motivo !== null || result.veredicto === null) {
    return (
      <Notice tone="info" title="Todavía no hay resultado para mostrar">
        {MOTIVO_SENTENCE[result.motivo ?? "SIN_PRECIO"]}
      </Notice>
    );
  }
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">
        {result.fuente_precio === "INGRESADO"
          ? "Resultado con el precio que escribiste (todavía no está guardado)."
          : "Resultado con el último precio guardado."}
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <VeredictoBadge veredicto={result.veredicto} />
        <p className="text-base">{VERDICT_SENTENCE[result.veredicto]}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Cifra
          titulo="Precio de venta"
          valor={formatArs(result.precio)}
          detalle="El que estás evaluando"
        />
        <Cifra
          titulo="Cuesta fabricarla"
          valor={formatArs(result.costo_variable)}
          detalle="Materiales y mano de obra de cada unidad"
        />
        <Cifra
          titulo="Te queda por unidad"
          valor={formatArs(result.margen_unidad)}
          detalle="Lo que queda para pagar los costos fijos"
        />
        <Cifra
          titulo="Del precio, te queda"
          valor={formatPercent(result.margen_pct)}
          detalle={`Sobre el costo de fabricarla: ${formatPercent(result.markup_pct)}`}
        />
      </div>
      <p className="text-sm text-muted">{MC_EXPLICACION}</p>
    </div>
  );
}

function History({ history }: { history: PrecioVenta[] }) {
  if (history.length === 0) {
    return (
      <Notice
        tone="info"
        title="Todavía no se guardó ningún precio de venta de este producto."
      />
    );
  }
  return (
    <TableWrap>
      <table className={tableClass}>
        <thead>
          <tr>
            <th className={thClass}>Desde</th>
            <th className={`${thClass} ${numClass}`}>Precio de venta</th>
            <th className={thClass}>Impuestos</th>
            <th className={`${thClass} ${numClass}`}>Precio final</th>
            <th className={thClass}>Nota</th>
          </tr>
        </thead>
        <tbody>
          {history.map((price) => (
            <tr key={`${price.vigente_desde}-${price.creado_en ?? ""}`}>
              <td className={tdClass}>{formatDate(price.vigente_desde)}</td>
              <td className={`${tdClass} ${numClass}`}>
                {formatArs(price.precio_ars)}
              </td>
              <td className={tdClass}>
                {price.impuestos?.length ? (
                  <ul className="space-y-0.5">
                    {price.impuestos.map((tax) => (
                      <li key={tax.codigo}>
                        {tax.nombre} ({fractionToPercentInput(tax.alicuota)} %):{" "}
                        {formatArs(tax.monto)}
                      </li>
                    ))}
                  </ul>
                ) : (
                  "—"
                )}
              </td>
              <td className={`${tdClass} ${numClass}`}>
                {price.impuestos?.length ? formatArs(price.precio_final) : "—"}
              </td>
              <td className={tdClass}>{price.nota ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}

/**
 * "¿Es rentable este precio?": the price travels in the URL (`?precio=`) so the check is a
 * plain GET and the API answers every number; nothing is calculated here.
 */
export async function RentabilidadBlock({
  codigo,
  writer,
  typedPrice,
}: {
  codigo: string;
  writer: boolean;
  typedPrice: string;
}) {
  const parsed = typedPrice ? parseDecimalInput(typedPrice) : null;
  const base = `/productos/${encodeURIComponent(codigo)}`;
  const [history, result] = await Promise.all([
    apiGet<PrecioVenta[]>(`${base}/precio-venta`),
    apiGet<Rentabilidad>(
      `${base}/rentabilidad${parsed ? `?${new URLSearchParams({ precio: parsed })}` : ""}`,
    ),
  ]);

  const latest = history.ok ? (history.data[0] ?? null) : null;
  // SUPUESTO: the field starts with the latest saved price; a typed one wins until it is saved.
  const prefill = typedPrice || decimalInputText(latest?.precio_ars);
  const canSave =
    writer &&
    parsed !== null &&
    result.ok &&
    result.data.fuente_precio === "INGRESADO" &&
    !(latest && sameDecimalText(parsed, latest.precio_ars));

  return (
    <section id="rentabilidad" className="scroll-mt-6">
      <SectionTitle>¿Es rentable este precio?</SectionTitle>
      <p className="mb-4 text-sm text-muted">
        Escribí el precio al que querés vender y mirá cuánto te queda de cada
        unidad. {MC_EXPLICACION}
      </p>
      <Card className="space-y-6">
        <form
          method="get"
          action={`${base}#rentabilidad`}
          className="flex flex-wrap items-end gap-4"
        >
          <div className="w-full sm:w-64">
            <label
              htmlFor="rentabilidad-precio"
              className="mb-1.5 block text-sm uppercase tracking-caps-sm text-muted sm:text-xs"
            >
              Precio de venta (ARS)
            </label>
            <input
              id="rentabilidad-precio"
              name="precio"
              inputMode="decimal"
              autoComplete="off"
              placeholder="45000"
              defaultValue={prefill}
              className={inputClass}
            />
          </div>
          <button
            type="submit"
            className="min-h-12 w-full rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white sm:min-h-0 sm:w-auto"
          >
            Ver si es rentable
          </button>
        </form>

        {typedPrice && parsed === null ? (
          <ErrorNotice
            title="No entendimos ese precio."
            message="Escribí solo números, por ejemplo 45000 o 45000,50."
          />
        ) : null}

        {result.ok ? (
          <Resultado result={result.data} />
        ) : (
          <ErrorNotice
            title="No pudimos calcular la rentabilidad."
            message={result.message}
          />
        )}

        {canSave && parsed ? (
          <div className="border-t border-line pt-6">
            <h3 className="mb-4 font-display text-lg">Guardar este precio</h3>
            <PrecioVentaForm codigo={codigo} precio={parsed} />
          </div>
        ) : null}
      </Card>

      <h3 className="mb-1 mt-8 font-display text-lg">
        Precios de venta guardados
      </h3>
      <p className="mb-3 text-sm text-muted">
        Los impuestos activos se suman al precio de venta; el costo y el margen
        se calculan sobre el precio sin impuestos.
      </p>
      {history.ok ? (
        <History history={history.data} />
      ) : (
        <ErrorNotice
          title="No pudimos cargar el historial de precios."
          message={history.message}
        />
      )}
    </section>
  );
}
