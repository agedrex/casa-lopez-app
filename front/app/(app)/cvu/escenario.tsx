"use client";

import Link from "next/link";
import {
  type FormEvent,
  startTransition,
  useActionState,
  useRef,
  useState,
} from "react";
import { MC_EXPLICACION, VeredictoBadge } from "@/components/cvu";
import {
  Field,
  FormFeedback,
  inputClass,
  PrimaryButton,
} from "@/components/form";
import {
  Card,
  Notice,
  numClass,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { IDLE } from "@/lib/action-state";
import {
  formatArs,
  formatPercent,
  formatPeriod,
  formatQuantity,
} from "@/lib/format";
import type { Escenario } from "@/lib/types";
import { type EscenarioState, runEscenario } from "./actions";

export type ProductOption = { codigo: string; nombre: string };

const linkClass = "underline decoration-gold underline-offset-4";

const OMITIDO_SENTENCE: Record<string, string> = {
  PRODUCTO_NO_ENCONTRADO: "No encontramos ese producto.",
  SIN_PRECIO:
    "No tiene precio de venta: escribí uno en esta fila o guardalo en su ficha.",
  SIN_COSTO_VARIABLE: "Todavía no se puede calcular cuánto cuesta fabricarlo.",
};

const RESULT_SENTENCE = {
  SIN_VENTAS: "Con estas filas no hay ventas para calcular el equilibrio.",
  MC_NO_POSITIVO:
    "Con estos precios no te queda nada de cada unidad para pagar los costos fijos, así que no hay un punto de equilibrio.",
} as const;

// Where to fix each notice the API raises (same destinations as the rest of the panel).
const AVISO_LINK: Record<string, { text: string; href: string }> = {
  SIN_FIJOS: { text: "Cargar costos fijos", href: "/costos-fijos" },
  FIJOS_PENDIENTES: { text: "Completar montos", href: "/costos-fijos" },
  FIJOS_FICTICIOS: { text: "Revisar costos fijos", href: "/costos-fijos" },
  IIBB_SIN_ALICUOTA: { text: "Cargar impuestos", href: "/admin/impuestos" },
};

function Cifra({
  titulo,
  valor,
  detalle,
}: {
  titulo: string;
  valor: string;
  detalle?: string;
}) {
  return (
    <div className="rounded-card border border-line p-4">
      <h4 className="text-sm text-muted">{titulo}</h4>
      <p className="mt-2 text-2xl font-bold tabular-nums">{valor}</p>
      {detalle ? <p className="mt-1 text-xs text-muted">{detalle}</p> : null}
    </div>
  );
}

function Resultado({ data }: { data: Escenario }) {
  const { resultado, fijos } = data;
  const perdida = resultado.utilidad?.startsWith("-") ?? false;
  return (
    <div className="space-y-5">
      {data.confiable ? null : (
        <Notice title="Este resultado no es confiable">
          Los costos fijos de {formatPeriod(data.periodo)} están incompletos o
          son de prueba. Mirá las cifras como una referencia, no como un dato
          firme.
        </Notice>
      )}

      {resultado.motivo ? (
        <Notice tone="info" title="No se pudo calcular el equilibrio">
          {RESULT_SENTENCE[resultado.motivo]}
        </Notice>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Cifra
            titulo="Para no perder, tenés que vender"
            valor={formatArs(resultado.equilibrio_ingresos)}
            detalle={`Son unas ${formatQuantity(resultado.equilibrio_unidades)} unidades con esta mezcla`}
          />
          <Cifra
            titulo="Con tu escenario"
            valor={formatArs(resultado.ingresos)}
            detalle="Lo que vendés según las filas cargadas"
          />
          <Cifra
            titulo={perdida ? "Pérdida" : "Ganancia"}
            valor={formatArs(resultado.utilidad)}
            detalle={`Después de pagar ${formatArs(resultado.costos_fijos)} de costos fijos`}
          />
          <Cifra
            titulo="Margen de seguridad"
            valor={formatPercent(resultado.margen_seguridad_pct)}
            detalle="Cuánto podrían bajar tus ventas antes de perder plata"
          />
        </div>
      )}

      <p className="text-sm text-muted">
        Costos fijos de {formatPeriod(data.periodo)}:{" "}
        <strong>{fijos.cargados ? formatArs(fijos.total_fabrica) : "—"}</strong>
        . {MC_EXPLICACION}
      </p>

      {data.lineas.length > 0 ? (
        <TableWrap>
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Producto</th>
                <th className={`${thClass} ${numClass}`}>Unidades</th>
                <th className={`${thClass} ${numClass}`}>Precio</th>
                <th className={`${thClass} ${numClass}`}>
                  Gastos de venta por unidad
                </th>
                <th className={`${thClass} ${numClass}`}>
                  Ingresos Brutos por unidad
                </th>
                <th className={`${thClass} ${numClass}`}>
                  Te queda por unidad
                </th>
                <th className={`${thClass} ${numClass}`}>
                  Te queda por hora de taller
                </th>
                <th className={thClass}>Resultado</th>
                <th className={`${thClass} ${numClass}`}>Aporte total</th>
                <th className={`${thClass} ${numClass}`}>% del aporte</th>
              </tr>
            </thead>
            <tbody>
              {data.lineas.map((line, index) => (
                <tr key={`${line.codigo}-${index}`}>
                  <td className={tdClass}>
                    <Link
                      className={linkClass}
                      href={`/productos/${encodeURIComponent(line.codigo)}`}
                    >
                      {line.codigo}
                    </Link>
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatQuantity(line.unidades)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(line.precio)}
                    <span className="block text-xs text-muted">
                      {line.fuente_precio === "INGRESADO"
                        ? "escrito acá"
                        : "guardado"}
                    </span>
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(line.gasto_venta_unidad)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(line.iibb_unidad)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(line.margen_unidad)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(line.margen_por_hora)}
                    {line.horas_confeccion ? (
                      <span className="block text-xs text-muted">
                        {formatQuantity(line.horas_confeccion)} h por unidad
                      </span>
                    ) : (
                      <span className="block text-xs text-muted">
                        sin horas cargadas
                      </span>
                    )}
                    {line.ranking_por_hora === 1 ? (
                      <span className="block text-xs font-bold">
                        Rinde más por hora
                      </span>
                    ) : null}
                  </td>
                  <td className={tdClass}>
                    <VeredictoBadge veredicto={line.veredicto} />
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatArs(line.contribucion_total)}
                  </td>
                  <td className={`${tdClass} ${numClass}`}>
                    {formatPercent(line.participacion_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      ) : null}

      {data.omitidos.length > 0 ? (
        <Notice tone="info" title="Estos productos quedaron afuera del cálculo">
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {data.omitidos.map((omitted, index) => (
              <li key={`${omitted.codigo}-${index}`}>
                <strong>{omitted.codigo}</strong>:{" "}
                {OMITIDO_SENTENCE[omitted.motivo] ?? omitted.motivo}
              </li>
            ))}
          </ul>
        </Notice>
      ) : null}

      {data.avisos.length > 0 ? (
        <ul className="space-y-2 text-sm">
          {data.avisos.map((aviso) => {
            const destino = AVISO_LINK[aviso.codigo];
            return (
              <li key={aviso.codigo}>
                {aviso.texto}{" "}
                {destino ? (
                  <Link className={linkClass} href={destino.href}>
                    {destino.text}
                  </Link>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

export function EscenarioDeVentas({
  productos,
  periodo,
}: {
  productos: ProductOption[];
  periodo: string;
}) {
  const [state, dispatch, pending] = useActionState<EscenarioState, FormData>(
    runEscenario,
    IDLE,
  );
  const [rows, setRows] = useState([0]);
  const nextId = useRef(1);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Not a plain `<form action>`: React would reset the fields and the person would retype the rows.
    const data = new FormData(event.currentTarget);
    startTransition(() => dispatch(data));
  }

  function addRow() {
    setRows((current) => [...current, nextId.current++]);
  }

  function removeRow(id: number) {
    setRows((current) => current.filter((row) => row !== id));
  }

  return (
    <Card className="space-y-6">
      <div>
        <h2 className="text-xl">Escenario de ventas</h2>
        <p className="mt-2 text-sm text-muted">
          Cargá qué productos pensás vender y cuántas unidades, y te decimos
          cuánto tenés que vender para cubrir los costos fijos. Los volúmenes
          son los que escribas acá, no ventas reales. {MC_EXPLICACION}
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-5">
        <datalist id="escenario-productos">
          {productos.map((product) => (
            <option key={product.codigo} value={product.codigo}>
              {product.nombre}
            </option>
          ))}
        </datalist>
        <div className="w-full sm:w-48">
          <Field id="escenario-periodo" label="Costos fijos de">
            <input
              id="escenario-periodo"
              name="periodo"
              type="month"
              defaultValue={periodo}
              className={inputClass}
            />
          </Field>
        </div>
        <ul className="space-y-3">
          {rows.map((id, index) => (
            <li
              key={id}
              className="grid items-end gap-3 sm:grid-cols-[2fr_1fr_1fr_auto]"
            >
              <Field
                id={`escenario-codigo-${id}`}
                label={`Producto ${index + 1}`}
              >
                <input
                  id={`escenario-codigo-${id}`}
                  name="codigo"
                  list="escenario-productos"
                  autoComplete="off"
                  placeholder="Código del producto"
                  className={inputClass}
                />
              </Field>
              <Field id={`escenario-unidades-${id}`} label="Unidades">
                <input
                  id={`escenario-unidades-${id}`}
                  name="unidades"
                  inputMode="decimal"
                  autoComplete="off"
                  placeholder="10"
                  className={inputClass}
                />
              </Field>
              <Field id={`escenario-precio-${id}`} label="Precio (opcional)">
                <input
                  id={`escenario-precio-${id}`}
                  name="precio"
                  inputMode="decimal"
                  autoComplete="off"
                  placeholder="El guardado"
                  className={inputClass}
                />
              </Field>
              <button
                type="button"
                onClick={() => removeRow(id)}
                disabled={rows.length === 1}
                aria-label={`Quitar el producto ${index + 1}`}
                className="min-h-12 rounded-card border border-line px-4 py-2 text-sm text-muted hover:border-ink hover:text-ink disabled:opacity-40 sm:min-h-0"
              >
                Quitar
              </button>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={addRow}
            className="min-h-12 w-full rounded-card border border-ink px-5 py-2.5 text-sm uppercase tracking-caps-sm hover:bg-ink hover:text-white sm:min-h-0 sm:w-auto"
          >
            Agregar producto
          </button>
          <PrimaryButton pending={pending}>
            {pending ? "Calculando…" : "Calcular escenario"}
          </PrimaryButton>
        </div>
        <FormFeedback state={state.data ? IDLE : state} />
      </form>
      {state.data ? <Resultado data={state.data} /> : null}
    </Card>
  );
}
