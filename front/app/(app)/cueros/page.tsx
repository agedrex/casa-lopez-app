import type { Metadata } from "next";
import Link from "next/link";
import { AlcanzaResumen } from "@/components/cueros/alcanza-resumen";
import {
  buttonClass,
  labelClass,
  linkButtonClass,
} from "@/components/cueros/estilos";
import { GrupoCard, UmbralLinea } from "@/components/cueros/grupo-card";
import { GruposTabla, PiezasTabla } from "@/components/cueros/tablas";
import { inputClass } from "@/components/form";
import {
  Card,
  CardList,
  ErrorNotice,
  Notice,
  PageHeader,
  SectionTitle,
} from "@/components/ui";
import { selectedView, ViewSelector } from "@/components/view-selector";
import { apiGet } from "@/lib/api";
import { grupoTitulo, isPositive } from "@/lib/cueros";
import { parseDecimalInput, todayIso } from "@/lib/format";
import { canWrite, isCorteOnly } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type {
  AlcanzaCuero,
  GrupoCuero,
  ItemCatalogo,
  Material,
  ProductoResumen,
} from "@/lib/types";
import { CargarCueroForm } from "./cargar-cuero-form";

export const metadata: Metadata = { title: "Cueros" };

type Params = Record<string, string | string[] | undefined>;

const SIN_COLOR = "__sin_color__";

const first = (value: string | string[] | undefined) =>
  (Array.isArray(value) ? value[0] : value) ?? "";

const groupKey = (grupo: GrupoCuero) =>
  `${grupo.material}|${grupo.color ?? ""}`;

export default async function CuerosPage({
  searchParams,
}: {
  searchParams: Promise<Params>;
}) {
  const { user } = await requireSession();
  const params = await searchParams;
  const writer = canWrite(user.role);
  const showMoney = !isCorteOnly(user.role);
  const view = selectedView(params.vista);
  const material = first(params.material);
  const color = first(params.color);
  const solo = first(params.solo) === "1";
  const producto = first(params.producto).trim();
  const cantidadTexto = first(params.cantidad).trim();
  const cantidad = parseDecimalInput(cantidadTexto);
  const quiereAlcanza = Boolean(producto || cantidadTexto);
  const cantidadValida = cantidad !== null && /[1-9]/.test(cantidad);

  const [grupos, materiales, colores, productos, alcanza] = await Promise.all([
    apiGet<GrupoCuero[]>("/cueros"),
    apiGet<Material[]>("/materiales"),
    writer ? apiGet<ItemCatalogo[]>("/colores") : null,
    apiGet<ProductoResumen[]>("/productos"),
    producto && cantidadValida
      ? apiGet<AlcanzaCuero>(
          `/cueros/alcanza?${new URLSearchParams({ producto, cantidad })}`,
        )
      : null,
  ]);

  const cueros = materiales.ok
    ? materiales.data.filter((item) => item.etapa === "CUERO")
    : [];
  const nombres: Record<string, string> = Object.fromEntries(
    (materiales.ok ? materiales.data : []).map((item) => [
      item.codigo,
      item.nombre,
    ]),
  );

  const filtrados = grupos.ok
    ? grupos.data
        .filter(
          (grupo) =>
            (!material || grupo.material === material) &&
            (!color ||
              (color === SIN_COLOR
                ? grupo.color === null
                : grupo.color === color)),
        )
        .map((grupo) => ({
          ...grupo,
          piezas: solo
            ? grupo.piezas.filter((pieza) => isPositive(pieza.disponible))
            : grupo.piezas,
        }))
        .filter((grupo) => !solo || isPositive(grupo.disponible))
    : [];

  const filterParams = new URLSearchParams();
  if (material) filterParams.set("material", material);
  if (color) filterParams.set("color", color);
  if (solo) filterParams.set("solo", "1");
  const hayFiltros = Boolean(material || color || solo);

  return (
    <>
      <PageHeader
        eyebrow="Datos de base"
        title="Cueros"
        description="Cuánto cuero hay, cuánto se cortó y cuánto se perdió. Los m² y los montos los calcula la aplicación."
        actions={
          writer ? (
            <a href="#cargar" className={buttonClass}>
              Cargar cuero
            </a>
          ) : undefined
        }
      />
      <div className="space-y-10">
        <section aria-labelledby="alcanza-titulo">
          <h2 id="alcanza-titulo" className="mb-4 text-xl">
            ¿Me alcanza?
          </h2>
          <Card>
            <form method="get" className="space-y-4">
              {material ? (
                <input type="hidden" name="material" value={material} />
              ) : null}
              {color ? (
                <input type="hidden" name="color" value={color} />
              ) : null}
              {solo ? <input type="hidden" name="solo" value="1" /> : null}
              {view === "tabla" ? (
                <input type="hidden" name="vista" value="tabla" />
              ) : null}
              <div className="grid gap-4 sm:grid-cols-[2fr_1fr]">
                <div>
                  <label htmlFor="alcanza-producto" className={labelClass}>
                    Producto
                  </label>
                  <input
                    id="alcanza-producto"
                    name="producto"
                    list="alcanza-productos"
                    defaultValue={producto}
                    autoComplete="off"
                    required
                    placeholder="Código del producto"
                    className={inputClass}
                  />
                  {productos.ok ? (
                    <datalist id="alcanza-productos">
                      {productos.data.map((item) => (
                        <option key={item.codigo} value={item.codigo}>
                          {item.nombre}
                        </option>
                      ))}
                    </datalist>
                  ) : null}
                </div>
                <div>
                  <label htmlFor="alcanza-cantidad" className={labelClass}>
                    Cantidad
                  </label>
                  <input
                    id="alcanza-cantidad"
                    name="cantidad"
                    inputMode="decimal"
                    defaultValue={cantidadTexto}
                    autoComplete="off"
                    required
                    placeholder="10"
                    className={inputClass}
                  />
                </div>
              </div>
              <button type="submit" className={buttonClass}>
                Ver si me alcanza
              </button>
            </form>
            {quiereAlcanza ? (
              <div className="mt-5 border-t border-line pt-5">
                {!producto || !cantidadValida ? (
                  <Notice title="Revisá los datos.">
                    Indicá el producto y una cantidad mayor que cero, por
                    ejemplo 10.
                  </Notice>
                ) : alcanza?.ok ? (
                  <AlcanzaResumen resultado={alcanza.data} nombres={nombres} />
                ) : alcanza ? (
                  <ErrorNotice
                    title="No pudimos hacer la cuenta."
                    message={alcanza.message}
                  />
                ) : null}
              </div>
            ) : null}
          </Card>
        </section>

        {writer ? (
          <section
            id="cargar"
            aria-labelledby="cargar-titulo"
            className="scroll-mt-20"
          >
            <h2 id="cargar-titulo" className="mb-4 text-xl">
              Cargar cuero
            </h2>
            <Card>
              {cueros.length === 0 ? (
                <ErrorNotice
                  title="No se puede cargar cuero todavía."
                  message={
                    materiales.ok
                      ? "No hay materiales de tipo cuero cargados."
                      : materiales.message
                  }
                />
              ) : (
                <CargarCueroForm
                  materiales={cueros.map((item) => ({
                    value: item.codigo,
                    label: item.nombre,
                  }))}
                  colores={
                    colores?.ok
                      ? colores.data.map((item) => ({
                          value: item.nombre,
                          label: item.nombre,
                        }))
                      : []
                  }
                  today={todayIso()}
                />
              )}
            </Card>
          </section>
        ) : null}

        <section aria-labelledby="resumen-titulo" className="space-y-5">
          <h2 id="resumen-titulo" className="text-xl">
            Resumen por cuero y color
          </h2>
          {!grupos.ok ? (
            <ErrorNotice message={grupos.message} />
          ) : (
            <>
              <FiltrosForm
                grupos={grupos.data}
                nombres={nombres}
                material={material}
                color={color}
                solo={solo}
                vista={view}
                hayFiltros={hayFiltros}
              />
              <ViewSelector path="/cueros" params={filterParams} view={view} />
              {filtrados.length === 0 ? (
                <Notice
                  tone="info"
                  title={
                    hayFiltros
                      ? "No hay cueros con esos filtros."
                      : "Todavía no hay cueros cargados."
                  }
                />
              ) : view === "tabla" ? (
                <div className="space-y-8">
                  <GruposTabla
                    grupos={filtrados}
                    nombres={nombres}
                    showMoney={showMoney}
                  />
                  <div className="space-y-3">
                    <SectionTitle>Pieles</SectionTitle>
                    <PiezasTabla
                      piezas={filtrados.flatMap((grupo) => grupo.piezas)}
                      nombres={nombres}
                      showMoney={showMoney}
                    />
                  </div>
                </div>
              ) : (
                <CardList>
                  {filtrados.map((grupo) => (
                    <GrupoCard
                      key={groupKey(grupo)}
                      grupo={grupo}
                      titulo={grupoTitulo(
                        nombres[grupo.material] ?? grupo.material,
                        grupo.color,
                      )}
                      showMoney={showMoney}
                      conPiezas
                    />
                  ))}
                </CardList>
              )}
              {view === "tabla" && filtrados.length > 0 ? (
                <Umbrales grupos={filtrados} nombres={nombres} />
              ) : null}
            </>
          )}
        </section>
      </div>
    </>
  );
}

function FiltrosForm({
  grupos,
  nombres,
  material,
  color,
  solo,
  vista,
  hayFiltros,
}: {
  grupos: GrupoCuero[];
  nombres: Record<string, string>;
  material: string;
  color: string;
  solo: boolean;
  vista: string;
  hayFiltros: boolean;
}) {
  const materialesPresentes = [
    ...new Set(grupos.map((grupo) => grupo.material)),
  ];
  const coloresPresentes = [
    ...new Set(grupos.map((grupo) => grupo.color ?? SIN_COLOR)),
  ];
  return (
    <Card>
      <form method="get" className="space-y-4">
        {vista === "tabla" ? (
          <input type="hidden" name="vista" value="tabla" />
        ) : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="filtro-material" className={labelClass}>
              Cuero
            </label>
            <select
              id="filtro-material"
              name="material"
              defaultValue={material}
              className={inputClass}
            >
              <option value="">Todos</option>
              {materialesPresentes.map((codigo) => (
                <option key={codigo} value={codigo}>
                  {nombres[codigo] ?? codigo}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="filtro-color" className={labelClass}>
              Color
            </label>
            <select
              id="filtro-color"
              name="color"
              defaultValue={color}
              className={inputClass}
            >
              <option value="">Todos</option>
              {coloresPresentes.map((valor) => (
                <option key={valor} value={valor}>
                  {valor === SIN_COLOR ? "Sin color" : valor}
                </option>
              ))}
            </select>
          </div>
        </div>
        <label className="flex min-h-12 cursor-pointer items-center gap-3 text-base">
          <input
            type="checkbox"
            name="solo"
            value="1"
            defaultChecked={solo}
            className="size-5"
          />
          Solo con disponible
        </label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <button type="submit" className={buttonClass}>
            Filtrar
          </button>
          {hayFiltros ? (
            <Link
              href={vista === "tabla" ? "/cueros?vista=tabla" : "/cueros"}
              className={linkButtonClass}
            >
              Quitar filtros
            </Link>
          ) : null}
        </div>
      </form>
    </Card>
  );
}

function Umbrales({
  grupos,
  nombres,
}: {
  grupos: GrupoCuero[];
  nombres: Record<string, string>;
}) {
  return (
    <section
      aria-label="Umbral de irrecuperable"
      className="hidden space-y-2 md:block"
    >
      {grupos.map((grupo) => (
        <div key={groupKey(grupo)}>
          <p className="text-base font-bold">
            {grupoTitulo(
              nombres[grupo.material] ?? grupo.material,
              grupo.color,
            )}
          </p>
          <UmbralLinea umbral={grupo.umbral_medido} />
        </div>
      ))}
    </section>
  );
}
