import Link from "next/link";
import { fractionToPercentInput } from "@/app/(app)/admin/impuestos/percent";
import { Field, inputClass, SecondaryButton } from "@/components/form";
import {
  Badge,
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
import { parseMargenParam } from "@/lib/ficha-consumo";
import {
  formatArs,
  formatDate,
  formatQuantity,
  lotStateLabel,
} from "@/lib/format";
import type { PrecioDesdeLotes, PrecioVenta } from "@/lib/types";
import { PrecioForm } from "./precio-form";

/** 30 -> "30", 32.5 -> "32,5": how the margin is typed and shown. */
const asTyped = (margen: string) => margen.replace(".", ",");

/**
 * "Precio de venta" of the product sheet (admin and gerente). The cost per unit comes from the lots already made (the newest
 * finished one, or today's estimate when there is none), the person chooses the margin over the price, and the active taxes
 * go on top of the net price. Every amount is computed by the API; this block only shows it. Saving adds a dated row.
 */
export async function PrecioBlock({
  codigo,
  margenTyped,
  puedeCargarImpuestos,
}: {
  codigo: string;
  /** What `?margen=` held (raw); empty = start from the margin of the last saved price, if any. */
  margenTyped: string | null;
  puedeCargarImpuestos: boolean;
}) {
  const base = `/productos/${encodeURIComponent(codigo)}`;
  const historial = await apiGet<PrecioVenta[]>(`${base}/precio-venta`);
  const ultimo = historial.ok ? historial.data[0] : undefined;
  const margenDelUltimo = ultimo?.margen
    ? parseMargenParam(fractionToPercentInput(ultimo.margen))
    : null;
  const margen = parseMargenParam(margenTyped) ?? margenDelUltimo;
  const preview = await apiGet<PrecioDesdeLotes>(
    `${base}/precio-desde-lotes${margen === null ? "" : `?margen=${margen}`}`,
  );

  return (
    <section id="precio" className="space-y-4">
      <SectionTitle>Precio de venta</SectionTitle>
      {!preview.ok ? (
        <ErrorNotice
          title="No pudimos calcular el precio."
          message={preview.message}
        />
      ) : (
        <Calculo
          codigo={codigo}
          datos={preview.data}
          margen={margen}
          margenInvalido={
            margenTyped !== null &&
            margenTyped !== "" &&
            parseMargenParam(margenTyped) === null
          }
          puedeCargarImpuestos={puedeCargarImpuestos}
        />
      )}
      {historial.ok ? (
        <Historial precios={historial.data} />
      ) : (
        <ErrorNotice
          title="No pudimos cargar los precios guardados."
          message={historial.message}
        />
      )}
    </section>
  );
}

function Calculo({
  codigo,
  datos,
  margen,
  margenInvalido,
  puedeCargarImpuestos,
}: {
  codigo: string;
  datos: PrecioDesdeLotes;
  margen: string | null;
  margenInvalido: boolean;
  puedeCargarImpuestos: boolean;
}) {
  return (
    <Card className="space-y-6">
      <CostoBase datos={datos} />

      <form
        method="get"
        action={`/productos/${encodeURIComponent(codigo)}#precio`}
        className="flex flex-wrap items-end gap-4"
      >
        <div className="w-48">
          <Field
            id="precio-margen"
            label="Margen sobre el precio (%)"
            hint="Por ejemplo 30 o 32,5."
          >
            <input
              id="precio-margen"
              name="margen"
              inputMode="decimal"
              autoComplete="off"
              defaultValue={margen === null ? "" : asTyped(margen)}
              className={inputClass}
            />
          </Field>
        </div>
        <SecondaryButton pending={false}>Calcular precio</SecondaryButton>
      </form>
      {margenInvalido ? (
        <Notice tone="warn" title="Ese margen no sirve.">
          Escribí un porcentaje entre 0 y 99,9 con un solo decimal, por ejemplo
          30 o 32,5.
        </Notice>
      ) : null}

      {datos.precio_neto !== null && margen !== null ? (
        <>
          <Desglose datos={datos} puedeCargarImpuestos={puedeCargarImpuestos} />
          <PrecioForm codigo={codigo} margen={asTyped(margen)} />
        </>
      ) : datos.costo_por_unidad !== null ? (
        <p className="text-sm text-muted">
          Elegí el margen y calculá el precio: sobre ese precio se aplican los
          impuestos que tengas cargados.
        </p>
      ) : null}
    </Card>
  );
}

function CostoBase({ datos }: { datos: PrecioDesdeLotes }) {
  if (datos.costo_por_unidad === null) {
    return (
      <Notice tone="warn" title="Todavía no se puede calcular el precio.">
        {datos.avisos.join(" ")}
      </Notice>
    );
  }
  return (
    <div className="space-y-3">
      {datos.fuente_costo === "ESTIMADO" ? (
        <Notice tone="warn" title="Es un costo estimado, no real.">
          {datos.avisos.join(" ")}
        </Notice>
      ) : null}
      <p className="text-sm">
        <span className="text-muted">
          {datos.fuente_costo === "LOTE"
            ? `Costo real por unidad (lote ${datos.lote_base}): `
            : "Costo estimado por unidad con los precios de hoy: "}
        </span>
        <strong>{formatArs(datos.costo_por_unidad)}</strong>
      </p>
      {datos.lotes.length > 0 ? (
        <>
          <p className="text-sm text-muted">
            Lotes terminados de este producto (el precio parte del más
            reciente):
          </p>
          <TableWrap>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Lote</th>
                  <th className={thClass}>Estado</th>
                  <th className={thClass}>Fecha</th>
                  <th className={`${thClass} ${numClass}`}>Unidades</th>
                  <th className={`${thClass} ${numClass}`}>Costo por unidad</th>
                  <th className={thClass} />
                </tr>
              </thead>
              <tbody>
                {datos.lotes.map((lote) => (
                  <tr key={lote.codigo}>
                    <td className={tdClass}>{lote.codigo}</td>
                    <td className={tdClass}>{lotStateLabel(lote.estado)}</td>
                    <td className={tdClass}>{formatDate(lote.fecha)}</td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatQuantity(lote.unidades)}
                    </td>
                    <td className={`${tdClass} ${numClass}`}>
                      {formatArs(lote.costo_por_unidad)}
                    </td>
                    <td className={tdClass}>
                      {lote.usado ? <Badge>Se usó este</Badge> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        </>
      ) : null}
    </div>
  );
}

function Desglose({
  datos,
  puedeCargarImpuestos,
}: {
  datos: PrecioDesdeLotes;
  puedeCargarImpuestos: boolean;
}) {
  return (
    <div className="space-y-3">
      <TableWrap>
        <table className={tableClass}>
          <tbody>
            <tr>
              <td className={tdClass}>Costo por unidad</td>
              <td className={`${tdClass} ${numClass}`}>
                {formatArs(datos.costo_por_unidad)}
              </td>
            </tr>
            <tr>
              <td className={tdClass}>
                Precio sin impuestos (margen {asTyped(datos.margen_pct ?? "")} %
                sobre el precio)
              </td>
              <td className={`${tdClass} ${numClass}`}>
                <strong>{formatArs(datos.precio_neto)}</strong>
              </td>
            </tr>
            {datos.impuestos.map((impuesto) => (
              <tr key={impuesto.codigo}>
                <td className={tdClass}>
                  {impuesto.nombre} ({fractionToPercentInput(impuesto.alicuota)}{" "}
                  %)
                </td>
                <td className={`${tdClass} ${numClass}`}>
                  {formatArs(impuesto.monto)}
                </td>
              </tr>
            ))}
            <tr>
              <td className={tdClass}>
                <strong>Precio final con impuestos</strong>
              </td>
              <td className={`${tdClass} ${numClass}`}>
                <strong>{formatArs(datos.precio_final)}</strong>
              </td>
            </tr>
          </tbody>
        </table>
      </TableWrap>
      {datos.sin_impuestos ? (
        <Notice tone="info" title="No hay impuestos cargados.">
          El precio final es igual al precio sin impuestos.{" "}
          {puedeCargarImpuestos ? (
            <Link
              href="/costos-fijos/impuestos"
              className="underline decoration-gold underline-offset-4"
            >
              Cargar impuestos
            </Link>
          ) : (
            "Pedile a quien administra la app que los cargue."
          )}
        </Notice>
      ) : null}
    </div>
  );
}

function Historial({ precios }: { precios: PrecioVenta[] }) {
  if (precios.length === 0) {
    return (
      <Notice
        tone="info"
        title="Todavía no guardaste ningún precio para este producto."
      />
    );
  }
  return (
    <Card>
      <h3 className="mb-3 text-base font-bold">Precios guardados</h3>
      <TableWrap>
        <table className={tableClass}>
          <thead>
            <tr>
              <th className={thClass}>Desde</th>
              <th className={`${thClass} ${numClass}`}>Margen</th>
              <th className={`${thClass} ${numClass}`}>Sin impuestos</th>
              <th className={`${thClass} ${numClass}`}>Con impuestos</th>
              <th className={thClass}>Nota</th>
            </tr>
          </thead>
          <tbody>
            {precios.map((precio, index) => (
              <tr key={`${precio.vigente_desde}-${precio.creado_en}-${index}`}>
                <td className={tdClass}>
                  {formatDate(precio.vigente_desde)}
                  {index === 0 ? (
                    <>
                      {" "}
                      <Badge>Vigente</Badge>
                    </>
                  ) : null}
                </td>
                <td className={`${tdClass} ${numClass}`}>
                  {precio.margen
                    ? `${fractionToPercentInput(precio.margen)} %`
                    : "A mano"}
                </td>
                <td className={`${tdClass} ${numClass}`}>
                  {formatArs(precio.precio_ars)}
                </td>
                <td className={`${tdClass} ${numClass}`}>
                  {formatArs(precio.precio_final ?? precio.precio_ars)}
                </td>
                <td className={tdClass}>{precio.nota ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      <p className="mt-3 text-sm text-muted">
        La columna con impuestos usa los impuestos cargados hoy.
      </p>
    </Card>
  );
}
