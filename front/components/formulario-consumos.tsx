"use client";

import { type ReactNode, useState } from "react";
import { decimalInputText } from "@/lib/format";
import {
  type FilaEditable,
  filasDe,
  lineaVacia,
  SECCIONES,
  type SeccionesEditables,
  serializarFilas,
} from "@/lib/formulario";
import type {
  Formulario,
  FormularioLinea,
  FormularioSeccion,
} from "@/lib/types";

/**
 * The paper "formulario de consumos y herrajes", digital: ARTÍCULO on top and the two tables (CONSUMOS in m2,
 * HERRAJES in units). The same component is the admin's sheet, what the taller fills in and the read-only view
 * inside the product sheet. It calculates nothing: a quantity is the text typed (`0,25`), normalised on the server.
 *
 * `edit` renders inputs plus the hidden fields `articulo`, `nota`, `lineas` (JSON of the typed rows) and `dirty`, so it
 * must sit inside a `<form>` whose action reads them (see formularios/[codigo]/editor.tsx). `readonly` is the same
 * layout as plain text; `compact` also hides the rows nobody filled in (the product sheet). Print styles turn the
 * page into the paper sheet (the "Imprimir" button is window.print()).
 */
export type FormularioConsumosProps = {
  formulario: Pick<Formulario, "articulo" | "nota" | "lineas">;
  mode: "edit" | "readonly";
  /** Readonly only: hide the empty rows and the page-level print rules. */
  compact?: boolean;
  /** Edit only: admin changes the article; a taller user sees it as text. */
  articuloEditable?: boolean;
};

const TABLAS: Record<
  FormularioSeccion,
  { titulo: string; cantidad: string; vacia: string }
> = {
  CONSUMO: {
    titulo: "CONSUMOS",
    cantidad: "M2",
    vacia: "Sin consumos cargados.",
  },
  HERRAJE: {
    titulo: "HERRAJES",
    cantidad: "CANTIDAD",
    vacia: "Sin herrajes cargados.",
  },
};
const COMENTARIOS = "COMENTARIOS / MODIFICACIONES";

// Turns the page into the paper sheet: the app chrome (top bar, side menu, bottom bar) is not printed.
const PRINT_CSS = String.raw`@media print {
  @page { margin: 12mm; }
  header, aside, nav { display: none !important; }
  .lg\:grid { display: block !important; }
  main { padding: 0 !important; }
  html, body { background: #fff !important; }
  table, tr { break-inside: avoid; }
}`;

const th =
  "border border-line bg-paper-mid px-3 py-2 text-left text-xs font-bold uppercase tracking-caps-sm text-ink-soft print:border-ink print:bg-transparent print:px-2 print:py-1";
const td = "border border-line align-top print:border-ink";
const cellInput =
  "block w-full bg-transparent px-3 py-2.5 text-base outline-none focus:bg-paper-mid/60 sm:text-sm print:px-2 print:py-1";
const wrap =
  "overflow-x-auto overscroll-x-contain rounded-card border border-line bg-surface print:overflow-visible print:rounded-none print:border-0";
const table =
  "w-full min-w-[34rem] table-fixed border-collapse text-sm print:min-w-0";

let lastKey = 0;
const newKey = () => `fila-${lastKey++}`;

export function FormularioConsumos({
  formulario,
  mode,
  compact = false,
  articuloEditable = false,
}: FormularioConsumosProps) {
  return (
    <div className="space-y-6">
      {compact ? null : <style>{PRINT_CSS}</style>}
      <p className="hidden text-center text-lg font-bold uppercase tracking-caps-md print:block">
        Formulario de consumos y herrajes
      </p>
      {mode === "edit" ? (
        <Editable formulario={formulario} articuloEditable={articuloEditable} />
      ) : (
        <Lectura formulario={formulario} compact={compact} />
      )}
    </div>
  );
}

function ArticuloLabel({ children }: { children: ReactNode }) {
  return (
    <span className="text-sm font-bold uppercase tracking-caps-sm">
      {children}
    </span>
  );
}

/** The details written when the model was created: what the workshop needs to read before filling the sheet. */
function NotasDelModelo({ nota }: { nota: string | null }) {
  if (!nota) return null;
  return (
    <div className="rounded-card border border-line bg-paper-mid/60 px-3 py-2 print:rounded-none print:border-ink print:bg-transparent">
      <p className="text-xs font-bold uppercase tracking-caps-sm text-ink-soft">
        Notas del modelo
      </p>
      <p className="mt-1 whitespace-pre-wrap break-words text-sm">{nota}</p>
    </div>
  );
}

// --- Readonly -------------------------------------------------------------------------------------------------------

function Lectura({
  formulario,
  compact,
}: {
  formulario: FormularioConsumosProps["formulario"];
  compact: boolean;
}) {
  const tablas = SECCIONES.map((seccion) => {
    const lineas = formulario.lineas
      .filter((linea) => linea.seccion === seccion)
      .sort((a, b) => a.orden - b.orden);
    return {
      seccion,
      lineas: compact ? lineas.filter((l) => !lineaVacia(l)) : lineas,
    };
  }).filter(({ lineas }) => !compact || lineas.length > 0);

  return (
    <>
      <div className="flex flex-wrap items-baseline gap-3 border-b-2 border-ink pb-2">
        <ArticuloLabel>ARTÍCULO</ArticuloLabel>
        <span className="min-w-0 break-words text-lg">
          {formulario.articulo}
        </span>
      </div>
      <NotasDelModelo nota={formulario.nota} />
      {tablas.length === 0 ? (
        <p className="text-sm text-muted">
          El formulario todavía no tiene cantidades ni comentarios cargados.
        </p>
      ) : (
        tablas.map(({ seccion, lineas }) => (
          <TablaLectura key={seccion} seccion={seccion} lineas={lineas} />
        ))
      )}
    </>
  );
}

function TablaLectura({
  seccion,
  lineas,
}: {
  seccion: FormularioSeccion;
  lineas: FormularioLinea[];
}) {
  const { titulo, cantidad, vacia } = TABLAS[seccion];
  return (
    <div className={wrap}>
      <table className={table} aria-label={titulo}>
        <thead>
          <tr>
            <th scope="col" className={`${th} w-[34%]`}>
              {titulo}
            </th>
            <th scope="col" className={`${th} w-[16%]`}>
              {cantidad}
            </th>
            <th scope="col" className={th}>
              {COMENTARIOS}
            </th>
          </tr>
        </thead>
        <tbody>
          {lineas.length === 0 ? (
            <tr>
              <td colSpan={3} className={`${td} px-3 py-3 text-muted`}>
                {vacia}
              </td>
            </tr>
          ) : (
            lineas.map((linea) => (
              <tr key={`${linea.seccion}-${linea.orden}`}>
                <th
                  scope="row"
                  className={`${td} break-words px-3 py-2.5 text-left font-normal print:px-2 print:py-1`}
                >
                  {linea.nombre}
                </th>
                <td
                  className={`${td} px-3 py-2.5 tabular-nums print:px-2 print:py-1`}
                >
                  {decimalInputText(linea.cantidad)}
                </td>
                <td
                  className={`${td} whitespace-pre-wrap break-words px-3 py-2.5 print:px-2 print:py-1`}
                >
                  {linea.comentario}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

// --- Edit -----------------------------------------------------------------------------------------------------------

function Editable({
  formulario,
  articuloEditable,
}: {
  formulario: FormularioConsumosProps["formulario"];
  articuloEditable: boolean;
}) {
  const [articulo, setArticulo] = useState(formulario.articulo);
  const [secciones, setSecciones] = useState<SeccionesEditables>(() =>
    filasDe(formulario.lineas, newKey),
  );
  const lineas = serializarFilas(secciones);
  // Compared with what the server sent: a save is only needed when something changed.
  const [baseline] = useState(() => ({ articulo, lineas }));
  const dirty = articulo !== baseline.articulo || lineas !== baseline.lineas;

  function cambiar(
    seccion: FormularioSeccion,
    key: string,
    campo: keyof Omit<FilaEditable, "key">,
    valor: string,
  ) {
    setSecciones((previous) => ({
      ...previous,
      [seccion]: previous[seccion].map((fila) =>
        fila.key === key ? { ...fila, [campo]: valor } : fila,
      ),
    }));
  }
  function agregar(seccion: FormularioSeccion) {
    setSecciones((previous) => ({
      ...previous,
      [seccion]: [
        ...previous[seccion],
        { key: newKey(), nombre: "", cantidad: "", comentario: "" },
      ],
    }));
  }
  function quitar(seccion: FormularioSeccion, key: string) {
    setSecciones((previous) => ({
      ...previous,
      [seccion]: previous[seccion].filter((fila) => fila.key !== key),
    }));
  }

  return (
    <>
      <div className="flex flex-wrap items-baseline gap-3 border-b-2 border-ink pb-2">
        <label htmlFor="formulario-articulo">
          <ArticuloLabel>ARTÍCULO</ArticuloLabel>
        </label>
        {articuloEditable ? (
          <input
            id="formulario-articulo"
            name="articulo"
            value={articulo}
            onChange={(event) => setArticulo(event.target.value)}
            required
            maxLength={200}
            autoComplete="off"
            className="min-h-11 min-w-0 flex-1 bg-transparent text-lg outline-none focus:bg-paper-mid/60 sm:min-h-0"
          />
        ) : (
          <>
            <span
              id="formulario-articulo"
              className="min-w-0 break-words text-lg"
            >
              {articulo}
            </span>
            <input type="hidden" name="articulo" value={articulo} />
          </>
        )}
      </div>
      <input type="hidden" name="nota" value={formulario.nota ?? ""} />
      <NotasDelModelo nota={formulario.nota} />
      <input type="hidden" name="lineas" value={lineas} />
      <input type="hidden" name="dirty" value={dirty ? "1" : ""} />
      {SECCIONES.map((seccion) => (
        <TablaEditable
          key={seccion}
          seccion={seccion}
          filas={secciones[seccion]}
          onChange={(key, campo, valor) => cambiar(seccion, key, campo, valor)}
          onAdd={() => agregar(seccion)}
          onRemove={(key) => quitar(seccion, key)}
        />
      ))}
    </>
  );
}

function TablaEditable({
  seccion,
  filas,
  onChange,
  onAdd,
  onRemove,
}: {
  seccion: FormularioSeccion;
  filas: FilaEditable[];
  onChange: (
    key: string,
    campo: keyof Omit<FilaEditable, "key">,
    valor: string,
  ) => void;
  onAdd: () => void;
  onRemove: (key: string) => void;
}) {
  const { titulo, cantidad } = TABLAS[seccion];
  return (
    <div>
      <div className={wrap}>
        <table className={table} aria-label={titulo}>
          <thead>
            <tr>
              <th scope="col" className={`${th} w-[34%]`}>
                {titulo}
              </th>
              <th scope="col" className={`${th} w-[16%]`}>
                {cantidad}
              </th>
              <th scope="col" className={th}>
                {COMENTARIOS}
              </th>
              <th scope="col" className={`${th} w-14 print:hidden`}>
                <span className="sr-only">Quitar fila</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {filas.map((fila) => (
              <tr key={fila.key}>
                <td className={td}>
                  <input
                    aria-label={`${titulo}: nombre de la fila`}
                    value={fila.nombre}
                    onChange={(event) =>
                      onChange(fila.key, "nombre", event.target.value)
                    }
                    maxLength={200}
                    autoComplete="off"
                    className={cellInput}
                  />
                </td>
                <td className={td}>
                  <input
                    aria-label={`${cantidad} de ${fila.nombre || "la fila"}`}
                    value={fila.cantidad}
                    onChange={(event) =>
                      onChange(fila.key, "cantidad", event.target.value)
                    }
                    inputMode="decimal"
                    autoComplete="off"
                    className={`${cellInput} tabular-nums`}
                  />
                </td>
                <td className={td}>
                  <textarea
                    aria-label={`Comentarios de ${fila.nombre || "la fila"}`}
                    value={fila.comentario}
                    onChange={(event) =>
                      onChange(fila.key, "comentario", event.target.value)
                    }
                    rows={1}
                    maxLength={2000}
                    className={`${cellInput} field-sizing-content resize-none`}
                  />
                </td>
                <td className={`${td} text-center print:hidden`}>
                  <button
                    type="button"
                    onClick={() => onRemove(fila.key)}
                    aria-label={`Quitar la fila ${fila.nombre || "sin nombre"}`}
                    className="min-h-11 w-full text-lg text-muted hover:text-bordeaux sm:min-h-0 sm:py-2"
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
            {filas.length === 0 ? (
              <tr>
                <td colSpan={4} className={`${td} px-3 py-3 text-muted`}>
                  No hay filas: agregá una.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <button
        type="button"
        onClick={onAdd}
        className="mt-2 min-h-11 text-sm text-muted underline decoration-gold underline-offset-4 hover:text-ink sm:min-h-0 print:hidden"
      >
        Agregar fila a {titulo}
      </button>
    </div>
  );
}
