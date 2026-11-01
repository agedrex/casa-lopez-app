import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { EstadoBadge } from "@/components/cueros/estado-badge";
import {
  buttonClass,
  labelClass,
  linkButtonClass,
} from "@/components/cueros/estilos";
import { inputClass } from "@/components/form";
import { ErrorNotice, Notice, PageHeader } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { compareDecimals, grupoTitulo, isPositive } from "@/lib/cueros";
import { formatQuantity, lotStateLabel, parseDecimalInput } from "@/lib/format";
import { requireSession } from "@/lib/session";
import type {
  AlcanzaCuero,
  GrupoCuero,
  Material,
  OrdenDetalle,
  OrdenResumen,
  PiezaCueroDetalle,
  Renglon,
} from "@/lib/types";
import { ConfirmarCorteForm, SobranteForm } from "./corte-forms";
import { MisCargas } from "./mis-cargas";
import { Paso } from "./paso";

export const metadata: Metadata = { title: "Corte" };

// SUPUESTO: un lote "abierto" es uno que todavía no se cortó del todo: PLANIFICADA o EN_CORTE.
// Validar con Gerardo y Mariano si algún otro estado también necesita cortes.
const ESTADOS_ABIERTOS = ["PLANIFICADA", "EN_CORTE"];

const ALTERNATIVA_AVISO =
  "Cambia el costo del producto: confirmalo con Mariano.";

type Params = Record<string, string | string[] | undefined>;

const first = (value: string | string[] | undefined) =>
  (Array.isArray(value) ? value[0] : value) ?? "";

/** Where the person is: every screen of the flow is one URL, there is no client state. */
type Ruta = {
  lote: string;
  item: string;
  /** Alternative leather chosen instead of the product's own (empty = none). */
  altMaterial: string;
  altColor: string;
  pieza: string;
  m2: string;
};

function href(ruta: Partial<Record<string, string>>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(ruta)) {
    if (value) query.set(key, value);
  }
  return query.size ? `/corte?${query}` : "/corte";
}

const contexto = (ruta: Ruta) => ({
  lote: ruta.lote,
  item: ruta.item,
  alt_material: ruta.altMaterial,
  alt_color: ruta.altColor,
});

export default async function CortePage({
  searchParams,
}: {
  searchParams: Promise<Params>;
}) {
  await requireSession();
  const params = await searchParams;
  const ruta: Ruta = {
    lote: first(params.lote).trim(),
    item: first(params.item).trim(),
    altMaterial: first(params.alt_material).trim(),
    altColor: first(params.alt_color).trim(),
    pieza: first(params.pieza).trim(),
    m2: first(params.m2).trim(),
  };
  const sobrante = first(params.sobrante).trim();
  const listo = first(params.listo).trim();
  const comprar = first(params.comprar) === "1";

  return (
    <>
      <PageHeader eyebrow="Producción" title="Corte" />
      <div className="space-y-10">
        {sobrante ? (
          <SobranteScreen pieza={sobrante} lote={ruta.lote} />
        ) : !ruta.lote ? (
          <LotesScreen listo={listo} />
        ) : !ruta.item ? (
          <ProductosScreen ruta={ruta} listo={listo} />
        ) : ruta.pieza ? (
          <PiezaScreen ruta={ruta} />
        ) : comprar ? (
          <ComprarScreen ruta={ruta} />
        ) : ruta.altMaterial ? (
          <AlternativaScreen ruta={ruta} />
        ) : (
          <TengoCueroScreen ruta={ruta} />
        )}
        <MisCargas />
      </div>
    </>
  );
}

function ListoAviso() {
  return (
    <Notice tone="info" title="Listo, cargado.">
      El corte quedó registrado. Si hay otro producto, seguí con el siguiente.
    </Notice>
  );
}

function Opcion({
  href: destino,
  titulo,
  detalle,
  extra,
}: {
  href: string;
  titulo: string;
  detalle?: string;
  extra?: React.ReactNode;
}) {
  return (
    <Link
      href={destino}
      className="flex min-h-14 flex-col justify-center gap-1 rounded-card border border-line bg-surface px-4 py-3 shadow-card hover:border-gold"
    >
      <span className="flex flex-wrap items-center gap-2 text-base font-bold">
        {titulo}
        {extra}
      </span>
      {detalle ? <span className="text-sm text-muted">{detalle}</span> : null}
    </Link>
  );
}

// --- 1. Lote abierto -------------------------------------------------------------------------

async function LotesScreen({ listo }: { listo: string }) {
  const results = await Promise.all(
    ESTADOS_ABIERTOS.map((estado) =>
      apiGet<OrdenResumen[]>(`/ordenes?estado=${estado}`),
    ),
  );
  const failure = results.find((result) => !result.ok);
  const lotes = results.flatMap((result) => (result.ok ? result.data : []));

  return (
    <Paso titulo="¿En qué lote vas a cortar?">
      {listo ? <ListoAviso /> : null}
      {failure && !failure.ok ? (
        <ErrorNotice message={failure.message} />
      ) : lotes.length === 0 ? (
        <Notice tone="info" title="No hay lotes abiertos.">
          Cuando haya un lote planificado o en corte, aparece acá.
        </Notice>
      ) : (
        <ul className="space-y-3">
          {lotes.map((lote) => (
            <li key={lote.codigo}>
              <Opcion
                href={href({ lote: lote.codigo })}
                titulo={`Lote ${lote.codigo}`}
                detalle={`${lotStateLabel(lote.estado)} · ${
                  lote.taller_nombre ?? lote.persona_nombre ?? "En casa"
                } · ${lote.productos} ${lote.productos === 1 ? "producto" : "productos"}`}
              />
            </li>
          ))}
        </ul>
      )}
    </Paso>
  );
}

// --- 2. Producto del lote --------------------------------------------------------------------

type Cargado =
  | { ok: true; orden: OrdenDetalle; renglon: Renglon }
  | { ok: false; message: string };

async function cargarRenglon(lote: string, item: string): Promise<Cargado> {
  const orden = await apiGet<OrdenDetalle>(
    `/ordenes/${encodeURIComponent(lote)}`,
  );
  if (!orden.ok) return { ok: false, message: orden.message };
  const renglon = orden.data.items.find(
    (candidate) => candidate.codigo === item,
  );
  if (!renglon) {
    return { ok: false, message: "Ese producto no está en el lote." };
  }
  return { ok: true, orden: orden.data, renglon };
}

async function ProductosScreen({ ruta, listo }: { ruta: Ruta; listo: string }) {
  const orden = await apiGet<OrdenDetalle>(
    `/ordenes/${encodeURIComponent(ruta.lote)}`,
  );
  if (!orden.ok) {
    return (
      <Paso titulo="Lote" volver={href({})}>
        <ErrorNotice message={orden.message} />
      </Paso>
    );
  }
  return (
    <Paso
      titulo={`Lote ${orden.data.codigo}: ¿qué producto cortás?`}
      volver={href({})}
    >
      {listo ? <ListoAviso /> : null}
      {orden.data.items.length === 0 ? (
        <Notice tone="info" title="Este lote no tiene productos." />
      ) : (
        <ul className="space-y-3">
          {orden.data.items.map((renglon) => (
            <li key={renglon.codigo}>
              <Opcion
                href={href({ lote: ruta.lote, item: renglon.codigo })}
                titulo={renglon.producto_nombre}
                detalle={`${renglon.producto} · ${formatQuantity(renglon.cantidad)} ${
                  renglon.cantidad === "1" ? "unidad" : "unidades"
                }`}
              />
            </li>
          ))}
        </ul>
      )}
    </Paso>
  );
}

// --- 3. ¿Tengo cuero? ------------------------------------------------------------------------

async function TengoCueroScreen({ ruta }: { ruta: Ruta }) {
  const cargado = await cargarRenglon(ruta.lote, ruta.item);
  if (!cargado.ok) {
    return (
      <Paso titulo="¿Tengo cuero?" volver={href({ lote: ruta.lote })}>
        <ErrorNotice message={cargado.message} />
      </Paso>
    );
  }
  const { renglon } = cargado;
  const alcanza = await apiGet<AlcanzaCuero>(
    `/cueros/alcanza?${new URLSearchParams({
      producto: renglon.producto,
      cantidad: renglon.cantidad,
    })}`,
  );
  const volver = href({ lote: ruta.lote });
  if (!alcanza.ok) {
    return (
      <Paso titulo="¿Tengo cuero?" volver={volver}>
        <ErrorNotice
          title="No pudimos hacer la cuenta."
          message={alcanza.message}
        />
      </Paso>
    );
  }
  const data = alcanza.data;
  const nombres = await nombresDeMateriales();

  return (
    <Paso
      titulo="¿Tengo cuero?"
      detalle={`${renglon.producto_nombre} · ${formatQuantity(renglon.cantidad)} ${
        renglon.cantidad === "1" ? "unidad" : "unidades"
      }`}
      volver={volver}
    >
      {data.alcanza ? (
        <>
          <Notice tone="info" title="Sí, alcanza.">
            {data.necesario
              ? `Necesitás ${formatQuantity(data.necesario)} m² y hay ${formatQuantity(data.disponible)} m² disponibles.`
              : (data.mensaje ?? undefined)}
          </Notice>
          <h2 className="text-xl">Elegí la piel</h2>
          <p className="text-sm text-muted">
            Primero van los retazos, después las que ya están en uso y al final
            las nuevas.
          </p>
          <ul className="space-y-3">
            {data.piezas.map((pieza) => (
              <li key={pieza.codigo}>
                <Opcion
                  href={href({ ...contexto(ruta), pieza: pieza.codigo })}
                  titulo={pieza.codigo}
                  detalle={`${grupoTitulo(nombres[pieza.material] ?? pieza.material, pieza.color)} · ${formatQuantity(pieza.disponible)} m² disponibles`}
                  extra={<EstadoBadge estado={pieza.estado} />}
                />
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <Notice
            title={
              data.faltante
                ? `Faltan ${formatQuantity(data.faltante)} m².`
                : "No alcanza el cuero."
            }
          >
            {data.mensaje ?? undefined}
          </Notice>
          <Link
            href={href({ ...contexto(ruta), comprar: "1" })}
            className={buttonClass}
          >
            Hay que comprar
          </Link>
          {data.alternativas.length > 0 ? (
            <>
              <h2 className="text-xl">O usar otro cuero</h2>
              <ul className="space-y-3">
                {data.alternativas.map((alternativa) => (
                  <li
                    key={`${alternativa.material}|${alternativa.color ?? ""}`}
                  >
                    <Opcion
                      href={href({
                        lote: ruta.lote,
                        item: ruta.item,
                        alt_material: alternativa.material,
                        alt_color: alternativa.color ?? "",
                      })}
                      titulo={grupoTitulo(
                        nombres[alternativa.material] ?? alternativa.material,
                        alternativa.color,
                      )}
                      detalle={`${formatQuantity(alternativa.disponible)} m² disponibles. ${ALTERNATIVA_AVISO}`}
                    />
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </>
      )}
    </Paso>
  );
}

async function nombresDeMateriales(): Promise<Record<string, string>> {
  const materiales = await apiGet<Material[]>("/materiales");
  return materiales.ok
    ? Object.fromEntries(
        materiales.data.map((item) => [item.codigo, item.nombre]),
      )
    : {};
}

// --- Hay que comprar -------------------------------------------------------------------------

// Nothing is saved: there is no purchase endpoint, this screen only shows what to ask for.
async function ComprarScreen({ ruta }: { ruta: Ruta }) {
  const cargado = await cargarRenglon(ruta.lote, ruta.item);
  const volver = href(contexto(ruta));
  if (!cargado.ok) {
    return (
      <Paso titulo="Hay que comprar" volver={volver}>
        <ErrorNotice message={cargado.message} />
      </Paso>
    );
  }
  const { renglon } = cargado;
  const alcanza = await apiGet<AlcanzaCuero>(
    `/cueros/alcanza?${new URLSearchParams({
      producto: renglon.producto,
      cantidad: renglon.cantidad,
    })}`,
  );
  return (
    <Paso
      titulo="Hay que comprar"
      volver={href({ lote: ruta.lote, item: ruta.item })}
    >
      <Notice tone="info" title="Pasale este pedido a Mariano.">
        Esto todavía no se guarda en ningún lado: es un resumen para avisar.
      </Notice>
      <dl className="space-y-3 rounded-card border border-line bg-surface p-4">
        <Dato label="Producto">
          {renglon.producto_nombre} ({renglon.producto})
        </Dato>
        <Dato label="Cantidad">{formatQuantity(renglon.cantidad)}</Dato>
        <Dato label="Lote">{ruta.lote}</Dato>
        <Dato label="Cuero que falta">
          {alcanza.ok && alcanza.data.faltante
            ? `${formatQuantity(alcanza.data.faltante)} m²`
            : "No se pudo calcular"}
        </Dato>
      </dl>
      <Link href={volver} className={linkButtonClass}>
        Ver las alternativas
      </Link>
    </Paso>
  );
}

function Dato({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="text-base font-bold">{children}</dd>
    </div>
  );
}

// --- Alternativa -----------------------------------------------------------------------------

async function AlternativaScreen({ ruta }: { ruta: Ruta }) {
  const query = new URLSearchParams({ material: ruta.altMaterial });
  if (ruta.altColor) query.set("color", ruta.altColor);
  const [grupos, nombres] = await Promise.all([
    apiGet<GrupoCuero[]>(`/cueros?${query}`),
    nombresDeMateriales(),
  ]);
  const volver = href({ lote: ruta.lote, item: ruta.item });
  const titulo = grupoTitulo(
    nombres[ruta.altMaterial] ?? ruta.altMaterial,
    ruta.altColor || null,
  );
  if (!grupos.ok) {
    return (
      <Paso titulo={titulo} volver={volver}>
        <ErrorNotice message={grupos.message} />
      </Paso>
    );
  }
  const piezas = grupos.data
    .filter((grupo) => grupo.material === ruta.altMaterial)
    .flatMap((grupo) => grupo.piezas)
    .filter(
      (pieza) =>
        (pieza.color ?? "") === ruta.altColor && isPositive(pieza.disponible),
    );

  return (
    <Paso titulo={titulo} detalle="Elegí la piel" volver={volver}>
      <Notice title="Ojo: es otro cuero.">{ALTERNATIVA_AVISO}</Notice>
      {piezas.length === 0 ? (
        <Notice tone="info" title="No hay pieles con cuero disponible." />
      ) : (
        <ul className="space-y-3">
          {piezas.map((pieza) => (
            <li key={pieza.codigo}>
              <Opcion
                href={href({ ...contexto(ruta), pieza: pieza.codigo })}
                titulo={pieza.codigo}
                detalle={`${formatQuantity(pieza.disponible)} m² disponibles`}
                extra={<EstadoBadge estado={pieza.estado} />}
              />
            </li>
          ))}
        </ul>
      )}
    </Paso>
  );
}

// --- 4 y 5. m² cortados y resumen ------------------------------------------------------------

async function PiezaScreen({ ruta }: { ruta: Ruta }) {
  const volverAPieles = href(
    ruta.altMaterial
      ? { ...contexto(ruta) }
      : { lote: ruta.lote, item: ruta.item },
  );
  const [pieza, cargado] = await Promise.all([
    apiGet<PiezaCueroDetalle>(`/cueros/${encodeURIComponent(ruta.pieza)}`),
    cargarRenglon(ruta.lote, ruta.item),
  ]);
  if (!pieza.ok || !cargado.ok) {
    return (
      <Paso titulo="Piel" volver={volverAPieles}>
        <ErrorNotice
          message={
            !pieza.ok ? pieza.message : !cargado.ok ? cargado.message : ""
          }
        />
      </Paso>
    );
  }
  const { renglon } = cargado;
  const disponible = pieza.data.disponible;
  if (pieza.data.estado === "CERRADA" || !isPositive(disponible)) {
    return (
      <Paso titulo={`Piel ${pieza.data.codigo}`} volver={volverAPieles}>
        <Notice title="Esta piel no tiene cuero disponible.">
          Elegí otra.
        </Notice>
      </Paso>
    );
  }

  const m2 = parseDecimalInput(ruta.m2);
  const m2Valido = m2 !== null && isPositive(m2);
  const entraEnLaPiel = m2Valido && compareDecimals(m2, disponible) !== 1;

  if (m2 !== null && m2Valido && entraEnLaPiel) {
    return (
      <Paso
        titulo="Resumen"
        volver={href({ ...contexto(ruta), pieza: ruta.pieza })}
      >
        <dl className="space-y-3 rounded-card border border-line bg-surface p-4">
          <Dato label="Piel">{pieza.data.codigo}</Dato>
          <Dato label="m² cortados">{formatQuantity(m2)} m²</Dato>
          <Dato label="Producto">
            {renglon.producto_nombre} ({renglon.producto})
          </Dato>
          <Dato label="Lote">{ruta.lote}</Dato>
        </dl>
        <ConfirmarCorteForm
          pieza={pieza.data.codigo}
          item={ruta.item}
          lote={ruta.lote}
          producto={renglon.producto_nombre}
          m2={m2}
        />
      </Paso>
    );
  }

  // Preloaded with what the product needs, as calculated by the API.
  const alcanza = await apiGet<AlcanzaCuero>(
    `/cueros/alcanza?${new URLSearchParams({
      producto: renglon.producto,
      cantidad: renglon.cantidad,
    })}`,
  );
  const sugerido = alcanza.ok ? (alcanza.data.necesario ?? "") : "";
  const mensaje = !ruta.m2
    ? null
    : m2Valido
      ? `La piel tiene ${formatQuantity(disponible)} m² disponibles.`
      : "Ingresá los m² cortados, por ejemplo 0,25.";

  return (
    <Paso
      titulo="¿Cuántos m² cortaste?"
      detalle={`Piel ${pieza.data.codigo} · ${formatQuantity(disponible)} m² disponibles`}
      volver={volverAPieles}
    >
      {mensaje ? (
        <ErrorNotice title="Revisá los m²." message={mensaje} />
      ) : null}
      <form method="get" action="/corte" className="space-y-4">
        {Object.entries(contexto(ruta)).map(([name, value]) =>
          value ? (
            <input key={name} type="hidden" name={name} value={value} />
          ) : null,
        )}
        <input type="hidden" name="pieza" value={pieza.data.codigo} />
        <div>
          <label htmlFor="corte-m2" className={labelClass}>
            m² cortados
          </label>
          <input
            id="corte-m2"
            name="m2"
            inputMode="decimal"
            autoComplete="off"
            required
            defaultValue={ruta.m2 || sugerido}
            className={inputClass}
          />
        </div>
        <button type="submit" className={buttonClass}>
          Seguir
        </button>
      </form>
    </Paso>
  );
}

// --- 6. ¿Lo que sobró sirve? -----------------------------------------------------------------

async function SobranteScreen({
  pieza,
  lote,
}: {
  pieza: string;
  lote: string;
}) {
  const detalle = await apiGet<PiezaCueroDetalle>(
    `/cueros/${encodeURIComponent(pieza)}`,
  );
  const seguir = href(lote ? { lote, listo: pieza } : { listo: pieza });
  if (!detalle.ok) {
    return (
      <Paso titulo="¿Lo que sobró sirve para otro producto?" volver={seguir}>
        <ErrorNotice message={detalle.message} />
      </Paso>
    );
  }
  const data = detalle.data;
  // Nothing left (or the skin is closed): there is nothing to decide.
  if (data.estado === "CERRADA" || !isPositive(data.disponible)) {
    redirect(seguir);
  }

  const query = new URLSearchParams({ material: data.material });
  if (data.color) query.set("color", data.color);
  const grupos = await apiGet<GrupoCuero[]>(`/cueros?${query}`);
  const umbral = grupos.ok
    ? (grupos.data.find((grupo) =>
        grupo.piezas.some((candidate) => candidate.codigo === data.codigo),
      )?.umbral_retazo_m2 ?? null)
    : null;
  const sugerirDescarte =
    umbral !== null && compareDecimals(data.disponible, umbral) === -1;

  return (
    <Paso
      titulo="¿Lo que sobró sirve para otro producto?"
      detalle={`Piel ${data.codigo} · quedan ${formatQuantity(data.disponible)} m²`}
    >
      {sugerirDescarte ? (
        <Notice tone="info" title="Sugerido: se descarta.">
          Es menos de {formatQuantity(umbral)} m². Igual lo decidís vos.
        </Notice>
      ) : null}
      <SobranteForm pieza={data.codigo} lote={lote} seguirHref={seguir} />
    </Paso>
  );
}
