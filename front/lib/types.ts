// Mirrors the response models in backend/src/backend/api.py.
// Money and quantities travel as decimal strings: the frontend only formats them.

export type ProductoResumen = {
  codigo: string;
  nombre: string;
  categoria: string | null;
  estado_del_ciclo: string;
  es_kit: boolean;
  costo_hoy_ars: string | null;
  costo_hoy_usd: string | null;
  avisos: string[];
};

export type LineaReceta = {
  etapa: string;
  material: string;
  color: string | null;
  consumo: string;
};

export type Componente = {
  producto: string;
  cantidad: string;
};

export type Desglose = {
  fecha: string;
  dolar: string;
  etapas: Record<string, string>;
  subtotal: string;
  componentes_kit: string;
  iva_compras: string;
  arreglos: string;
  total_ars: string;
  total_usd: string;
};

export type Cotizacion = {
  producto: string;
  tipo: string;
  fecha: string;
  dolar: string;
  cuero: string;
  forro: string;
  flex: string;
  goma_eva: string;
  herrajes: string;
  hilo_cemento: string;
  corte: string;
  confeccion: string;
  subtotal_etapas: string;
  componentes_kit: string;
  iva_compras: string;
  arreglos: string;
  total_ars: string;
  total_usd: string;
  estado: string | null;
};

export type Ficha = {
  codigo: string;
  nombre: string;
  categoria: string | null;
  modelo: string | null;
  cuero: string | null;
  color: string | null;
  quien_lo_confecciona: string | null;
  estado_del_ciclo: string;
  es_kit: boolean;
  nota: string | null;
  fecha_de_alta: string | null;
  fecha_de_recotizacion: string | null;
  fecha_de_cierre: string | null;
  receta: LineaReceta[];
  componentes: Componente[];
  confeccion_estimada_ars: string;
  costo_hoy: Desglose | null;
  avisos: string[];
  recotizar: boolean | null;
  cotizaciones: Cotizacion[];
};

export type Dolar = {
  fecha: string;
  ars_por_usd: string;
  fuente: string;
  tipo: string | null;
  nota: string | null;
};

export type Material = {
  codigo: string;
  nombre: string;
  nombre_corto: string | null;
  etapa: string;
  unidad_de_consumo: string;
  cotizable: boolean;
  controla_inventario: boolean;
  desperdicio_manual: string | null;
};

export type Precio = {
  codigo: string;
  material: string;
  color: string | null;
  proveedor: string | null;
  precio: string;
  moneda: string;
  unidad_del_precio: string;
  iva_incluido: boolean;
  vigente_desde: string;
  nota_fuente: string | null;
  vigente: boolean;
  // Percent change against the previous price of the same material, color and
  // currency, calculated by the API (null for the first price of a series).
  variacion_pct: string | null;
  salto_grande: boolean;
};

export type PrecioChequeo = {
  anterior: string | null;
  variacion_pct: string | null;
  salto_grande: boolean;
};

export type Catalogos = {
  colores: string[];
  categorias: string[];
};

export type Conteo = { total: number };

export type Modelo = {
  codigo: string;
  nombre_del_modelo: string;
  categoria: string | null;
};

// Consumptions are NUMERIC strings; null = missing data, "0" = "no lleva".
export type ModeloLista = Modelo & {
  tamano: string | null;
  cuero_m2_por_unidad: string | null;
  forro: string | null;
  forro_m2_por_unidad: string | null;
  flex_m2_por_unidad: string | null;
  goma_eva_m2_por_unidad: string | null;
  herrajes_usd_por_unidad: string | null;
  hilo_y_cemento: string | null;
  confeccion_estimada_ars: string | null;
  origen_de_los_consumos: string | null;
  validado: boolean;
};

export type ModeloDetalle = ModeloLista & {
  horas_de_confeccion: string | null;
  nota: string | null;
  modelo_excel_viejo: string | null;
  fila_excel_viejo: number | null;
  productos: number;
};

export type Parametro = {
  codigo: string;
  constante: string;
  valor: string | null;
  valor_texto: string | null;
  unidad: string | null;
  que_es: string | null;
  fuente_estado: string | null;
};

export type Impuesto = {
  codigo: string;
  nombre: string;
  alicuota: string | null;
  base: string | null;
  es_costo_del_producto: boolean;
  nota: string | null;
};

export type ItemCatalogo = {
  codigo: string;
  nombre: string;
  nota: string | null;
};

export type EtapaCatalogo = {
  codigo: string;
  orden: number;
  tipo: string;
};

export type Persona = {
  codigo: string;
  nombre: string;
  rol: string;
  activo: boolean;
};

export type Taller = {
  codigo: string;
  nombre: string;
  cuit: string | null;
  telefono: string | null;
  direccion: string | null;
  contacto: string | null;
  activo: boolean;
  nota: string | null;
  // Flagged by the API from the note ("Ejemplo: ..."): a placeholder workshop.
  ejemplo: boolean;
  lotes: number;
  unidades: string;
  ultimo_lote: string | null;
  cobro_total_ars: string;
};

export type TallerDetalle = Taller & { ordenes: OrdenResumen[] };

export type OrdenResumen = {
  codigo: string;
  donde_se_hace: string;
  taller: string | null;
  taller_nombre: string | null;
  persona: string | null;
  persona_nombre: string | null;
  fecha_de_envio: string | null;
  fecha_de_entrega: string | null;
  periodo: string | null;
  estado: string;
  nota: string | null;
  productos: number;
  unidades: string;
  total_cotizado: string;
  total_cobrado: string;
  costo_total: string | null;
  costo_promedio_por_unidad: string | null;
  avisos: string[];
};

export type Renglon = {
  codigo: string;
  producto: string;
  producto_nombre: string;
  categoria: string | null;
  tamano: string | null;
  cantidad: string;
  cotizado: string | null;
  pagado: string | null;
  nota: string | null;
  confeccion_por_unidad: string | null;
  materiales_por_unidad: string | null;
  costo_por_unidad: string | null;
  total_linea: string | null;
  avisos: string[];
};

export type EstadoDeOrden = {
  estado: string;
  fecha: string;
  quien: string | null;
  quien_nombre: string | null;
};

export type OrdenDetalle = OrdenResumen & {
  items: Renglon[];
  estados: EstadoDeOrden[];
};

export type MesCasaTaller = {
  periodo: string;
  lotes_casa: number;
  lotes_taller: number;
  unidades_casa: string;
  unidades_taller: string;
  // Percent of the units made at workshops, calculated by the API (null: no units that month).
  porcentaje_taller: string | null;
  pagado_a_talleres: string;
  unidades_por_taller: Record<string, string>;
};

export type CasaVsTaller = {
  talleres: { codigo: string; nombre: string }[];
  meses: MesCasaTaller[];
};

export type PrecioDeTaller = {
  taller: string;
  taller_nombre: string | null;
  hizo: boolean;
  precio: string | null;
  fecha: string | null;
  lote: string | null;
  cantidad: string | null;
  veces: number;
  precio_anterior: string | null;
  variacion_pct: string | null;
};

export type PrecioParecido = {
  fecha: string;
  producto: string;
  nombre: string;
  tamano: string | null;
  taller: string;
  taller_nombre: string | null;
  cantidad: string;
  precio: string;
  lote: string;
  es_mismo_producto: boolean;
};

export type PreciosTalleres = {
  producto: string;
  nombre: string;
  categoria: string | null;
  tamano: string | null;
  veces_en_taller: number;
  por_taller: PrecioDeTaller[];
  parecidos: PrecioParecido[];
};

export type Gasto = {
  codigo: string;
  concepto: string;
  fabrica_o_tienda: string;
  categoria: string;
  persona: string | null;
  monto_ars_del_mes: string | null;
  ficticio: boolean;
  nota_fuente: string | null;
};

export type CostosFijos = {
  periodo: string;
  total_fabrica: string;
  total_tienda: string;
  total: string;
  pendientes: number;
  incluye_ficticios: boolean;
  gastos: Gasto[];
};

export type PeriodosCostosFijos = {
  vigente: string | null;
  periodos: string[];
};

export type Severidad = "alta" | "media" | "baja";

export type Hallazgo = {
  severidad: Severidad;
  entidad: string;
  mensaje: string;
  ruta: string;
};

export type GrupoCalidad = {
  clave: string;
  titulo: string;
  total: number;
  hallazgos: Hallazgo[];
};

export type Calidad = {
  resumen: { alta: number; media: number; baja: number; total: number };
  grupos: GrupoCalidad[];
};

// Google Sheet display copy (GET/POST /sync/sheets). Counts only: no money crosses this API.

export type SyncPestana = { nombre: string; filas: number };

export type SyncResultado = {
  simulacion: boolean;
  configurado: boolean;
  iniciado: string;
  finalizado: string;
  duracion_ms: number;
  total_filas: number;
  pestanas: SyncPestana[];
};

export type SyncUltima = SyncResultado & { ok: boolean; error: string | null };

export type SyncEstado = {
  configurado: boolean;
  /** Names of the two environment variables, never their values. */
  variables: string[];
  faltantes: string[];
  pestanas: string[];
  en_curso: boolean;
  ultima: SyncUltima | null;
};

/** The first rows of one tab exactly as the Sheet would get them: every cell is text. */
export type SyncVista = {
  pestana: string;
  encabezados: string[];
  filas: string[][];
  total_filas: number;
  mostradas: number;
};
