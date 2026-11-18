// Mirrors the response models in backend/src/backend/api.py.
// Money and quantities travel as decimal strings: the frontend only formats them.

export type ProductoResumen = {
  codigo: string;
  nombre: string;
  categoria: string | null;
  /** Leather (short name, else code) and color of the product; `null` when it has none. Optional: an older API does not send them. */
  cuero?: string | null;
  color?: string | null;
  /** Model code (not unique: some codes repeat in the imported products). */
  modelo: string | null;
  estado_del_ciclo: string;
  es_kit: boolean;
  costo_hoy_ars: string | null;
  costo_hoy_usd: string | null;
  avisos: string[];
  /** The note has `REVISAR: <reason>` marks; `motivos_revisar` holds the reasons. */
  revisar: boolean;
  motivos_revisar: string[];
  /** Net sale price in force; `null` without a saved price (and always for the taller role). */
  precio_venta_ars: string | null;
  /** Margin over the sale price, already a percentage (`"30"` = 30 %). */
  margen_pct: string | null;
  /** Net price plus the active taxes. */
  precio_final_ars: string | null;
  // Fields added with the grid reorder (demo-staging-taller-grilla S5/S6). Optional: an older API does not send them.
  /** Code of the model (`MOD-nnnn`, unique), unlike `modelo`, which is the Excel's model code. */
  modelo_codigo?: string | null;
  modelo_nombre?: string | null;
  /** Date and dollar of the latest saved quote of the product; `null` without a quote. */
  cotizacion_fecha?: string | null;
  cotizacion_dolar?: string | null;
  /** Total of that quote, as the API calculated it (in pesos and in dollars). */
  costo_cotizado_ars?: string | null;
  costo_cotizado_usd?: string | null;
  /** When the product was created (ISO datetime) and by whom (display name, or the raw user id when the name cannot be read). `null` for products created before the column existed. */
  creado_en?: string | null;
  creado_por?: string | null;
};

export type LineaReceta = {
  etapa: string;
  material: string;
  /** Name of the material: what the screens show (the code stays for the engine). */
  material_nombre?: string | null;
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
  modelo_nombre?: string | null;
  cuero: string | null;
  cuero_nombre?: string | null;
  color: string | null;
  quien_lo_confecciona: string | null;
  estado_del_ciclo: string;
  es_kit: boolean;
  nota: string | null;
  /** Hours the model takes to make: informative, outside the cost. */
  horas_de_confeccion?: string | null;
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
  horas_de_confeccion: string | null;
  /** True when a photo was uploaded; it is read at `/api/modelos/{codigo}/foto`. */
  tiene_foto: boolean;
  /** Newest consumption sheet of the model; only the list fills them (the detail leaves them empty). */
  hoja_codigo?: string | null;
  hoja_estado?: string | null;
};

/** Answer of `POST /modelos/consumos/lote`. */
export type ResultadoLoteConsumos = { guardados: number; modelos: string[] };

// A supply the model carries per unit (filled when its consumption sheet is validated), mirrors InsumoModeloOut.
// `precio_unitario` is the generic price in force today, in `moneda`; null when the material has none.
export type InsumoModelo = {
  codigo: string;
  material: string;
  nombre: string;
  etapa: string;
  unidad_de_consumo: string;
  cantidad_por_unidad: string;
  precio_unitario: string | null;
  moneda: string | null;
};

export type ModeloDetalle = ModeloLista & {
  nota: string | null;
  modelo_excel_viejo: string | null;
  fila_excel_viejo: number | null;
  productos: number;
  insumos: InsumoModelo[];
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
  activo: boolean;
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
  // Code of the most recent lot of the workshop (null: no lots yet).
  ultimo_lote_codigo: string | null;
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
  // The logged-in user who saved the change (null on the creation row) and the moment it was saved.
  cambiado_por?: string | null;
  registrado_en?: string | null;
};

/** A line an admin took out of the lot: the row is kept and its note holds the log (date, quantity it had, who). */
export type RenglonQuitado = {
  codigo: string;
  producto: string;
  producto_nombre: string;
  nota: string | null;
};

export type OrdenDetalle = OrdenResumen & {
  /** The lot already adds its cost and units to the variable cost of its month (it is finished: Lista or Cerrada). */
  cuenta_en_costo_variable: boolean;
  /** The state from which a lot counts (`LISTA`). */
  cuenta_desde_estado: string;
  items: Renglon[];
  estados: EstadoDeOrden[];
  quitados: RenglonQuitado[];
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

export type ReferenciaNivel =
  | "MISMO_PRODUCTO"
  | "MISMA_CATEGORIA_Y_TAMANO"
  | "MISMA_CATEGORIA"
  | "SIN_DATOS";

export type ReferenciaItem = {
  fecha: string;
  dias: number;
  producto: string;
  nombre: string;
  tamano: string | null;
  taller: string;
  taller_nombre: string | null;
  cantidad: string;
  precio: string;
  lote: string;
  veces: number;
  precio_anterior: string | null;
  variacion_pct: string | null;
};

export type Referencia = {
  nivel: ReferenciaNivel;
  categoria: string | null;
  tamano: string | null;
  items: ReferenciaItem[];
};

export type PreciosTalleres = {
  producto: string;
  nombre: string;
  categoria: string | null;
  tamano: string | null;
  veces_en_taller: number;
  por_taller: PrecioDeTaller[];
  parecidos: PrecioParecido[];
  referencia: Referencia;
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
  /** Code of the row this one corrects, or null when it is not a correction. */
  reemplaza_a: string | null;
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

// GET /costos-fijos/mercaderia (MercaderiaDelMesOut): Mercadería comprada en el mes, imputada a la tienda.
export type CompraDelMes = {
  producto: string;
  producto_nombre: string;
  fecha: string;
  unidades: string;
  costo_unitario_ars: string;
  total_ars: string;
  proveedor: string | null;
  nota: string | null;
};

export type MercaderiaDelMes = {
  periodo: string;
  total_mercaderia: string;
  total_gastos_tienda: string;
  total_tienda: string;
  compras: CompraDelMes[];
};

// GET /costos-fijos/retazos (RetazosDelMesOut): leather remainders written off in the month, imputed to the factory.
// Calculated by the API; null price/total = the piece has no price (never 0).
export type RetazoDelMes = {
  pieza: string;
  material: string;
  color: string | null;
  fecha: string;
  m2: string;
  precio_por_m2_ars: string | null;
  total_ars: string | null;
};

export type RetazosDelMes = {
  periodo: string;
  total_retazos: string;
  sin_precio: number;
  total_gastos_fabrica: string;
  total_fabrica: string;
  retazos: RetazoDelMes[];
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

// Voice module (GET /voz/estado, POST /voz/interpretar). The model only extracts words; the API resolves them and answers
// a proposal. Money travels as decimal strings and nothing is calculated here.

export type VozEstado = {
  configurado: boolean;
  acciones: string[];
  max_caracteres: number;
  limite_por_minuto: number;
};

export type VozAccion =
  | "cargar_precio"
  | "cargar_dolar"
  | "agregar_extra"
  | "registrar_precio_taller"
  | "cargar_monto_gasto"
  | "desconocida";

export type VozCampo = { valor: string; texto: string | null };

/** `codigo` is the value to send (for a color it is the color's name). */
export type VozCandidato = { codigo: string; nombre: string };

export type VozPropuesta = {
  accion: VozAccion;
  resumen: string;
  campos_resueltos: Record<string, VozCampo>;
  /** Only for ambiguous fields: up to five options, the person picks one. */
  candidatos: Record<string, VozCandidato[]>;
  /** Names of the fields that are missing, unknown or ambiguous. */
  faltantes: string[];
  avisos: string[];
  endpoint_destino: string | null;
  payload_propuesto: Record<string, unknown> | null;
};

// Leather inventory (GET /cueros, /cueros/{codigo}, /cueros/alcanza). Square meters and money come
// calculated by the API as decimal strings: the frontend only formats and compares them.

export type EstadoPiel = "ENTERA" | "EN_USO" | "RETAZO" | "CERRADA";

export type PiezaCuero = {
  codigo: string;
  material: string;
  color: string | null;
  fecha_de_compra: string | null;
  proveedor: string | null;
  m2_iniciales: string;
  precio_pagado_por_m2: string | null;
  moneda: "ARS" | "USD" | null;
  estado: EstadoPiel;
  disponible: string;
  irrecuperable: string;
  cortado: string;
  porcentaje_usado: string;
};

export type MovimientoCuero = {
  id: number;
  fecha: string;
  tipo: "CORTE" | "DESPERDICIO" | "AJUSTE" | "ENTRADA";
  m2: string;
  orden_item_id: number | null;
  registro_id: number | null;
  unidades: string | null;
};

export type PiezaCueroDetalle = PiezaCuero & {
  movimientos: MovimientoCuero[];
};

export type UmbralMedido = {
  casos: number;
  promedio_m2: string;
  promedio_pct_comprado: string | null;
};

export type GrupoCuero = {
  material: string;
  color: string | null;
  comprado: string;
  cortado: string;
  irrecuperable: string;
  disponible: string;
  porcentaje_desperdicio_neto: string | null;
  costo_desperdicio_ars: string | null;
  piezas: PiezaCuero[];
  umbral_medido: UmbralMedido | null;
  umbral_retazo_m2: string | null;
  avisos: string[];
};

export type PiezaDisponible = {
  codigo: string;
  material: string;
  color: string | null;
  estado: Exclude<EstadoPiel, "CERRADA">;
  disponible: string;
};

export type AlternativaCuero = {
  material: string;
  color: string | null;
  disponible: string;
};

export type AlcanzaCuero = {
  producto: string;
  cantidad: string;
  necesario: string | null;
  disponible: string;
  alcanza: boolean;
  faltante: string | null;
  piezas: PiezaDisponible[];
  alternativas: AlternativaCuero[];
  mensaje: string | null;
};

/** One leather (material + color) a lot needs (GET /ordenes/{codigo}/cuero). Square meters only: no money, the taller reads it. */
export type LoteCueroGrupo = {
  material: string;
  material_nombre: string;
  color: string | null;
  /** m² the lot's products need of this leather. */
  necesario: string;
  /** m² already cut against the lot's items (they are no longer in the stock). */
  ya_cortado: string;
  /** m² still to cut: `necesario` minus `ya_cortado`. */
  por_cortar: string;
  /** m² in stock of this same leather (the source of GET /cueros/alcanza). */
  disponible: string;
  /** m² the OTHER open lots still have to cut of this leather (derived reservation; it blocks nothing). */
  reservado_por_otros: string;
  /** Codes of those lots. */
  reservado_por: string[];
  /** m² left for this lot: stock minus reserved, never below 0. `alcanza` is checked against it. */
  libre: string;
  alcanza: boolean;
  faltante: string;
  sobrante: string;
  /** Shortage message in Spanish written by the API; null when the lot fits. */
  mensaje: string | null;
  productos: string[];
};

/** The leathers of a lot, against the stock and what the other open lots reserve; no code or state yet while it is being created. */
export type AlcanzaLote = {
  cueros: LoteCueroGrupo[];
  /** Products without a model, a leather or a leather consumption: they cannot be counted. */
  sin_consumo: { producto: string; producto_nombre: string }[];
};

export type LoteCuero = AlcanzaLote & {
  lote: string;
  estado: string;
};

/** One supply a product of a lot consumes (GET /ordenes/{codigo}/consumo). Quantities only: no money, the taller reads it. */
export type ConsumoInsumo = {
  material: string;
  material_nombre: string;
  color: string | null;
  /** Consumption unit of the material (`m2`, `juego`, `unidad`, ...). */
  unidad: string;
  /** Quantity for ONE unit of the product. */
  por_unidad: string;
  /** `por_unidad` times the lot quantity, calculated by the API. */
  total: string;
};

export type ConsumoProducto = {
  item: string;
  producto: string;
  producto_nombre: string;
  cantidad: string;
  insumos: ConsumoInsumo[];
};

/** Total of one supply across every product of the lot. */
export type ConsumoTotal = {
  material: string;
  material_nombre: string;
  color: string | null;
  unidad: string;
  total: string;
  productos: string[];
};

export type ConsumoLote = {
  lote: string;
  estado: string;
  productos: ConsumoProducto[];
  totales: ConsumoTotal[];
  /** Products of the lot with no supply loaded: their consumption cannot be counted. */
  sin_consumo: { producto: string; producto_nombre: string }[];
};

// Cost panel (GET /panel/costos). Every amount is computed by the API; the front only displays it.

export type MotivoEquilibrio =
  | "SIN_PRECIO"
  | "PRECIO_NO_CUBRE_COSTO_VARIABLE"
  | "SIN_COSTO_VARIABLE"
  | "SIN_FIJOS";

export type EquilibrioPanel = {
  margen_por_unidad: string | null;
  unidades: string | null;
  motivo: MotivoEquilibrio | null;
};

export type CvuMes = {
  ingresos: string;
  costo_variable_total: string;
  margen_contribucion: string;
  margen_contribucion_unidad: string;
  margen_contribucion_pct: string;
  costos_fijos: string;
  utilidad: string;
  equilibrio_unidades: string;
  equilibrio_ingresos: string;
  margen_seguridad_pct: string;
};

export type BloqueCostoMes = {
  periodo: string;
  unidades: string;
  unidades_sin_costo: string;
  costo_variable_por_unidad: string | null;
  fijos_fabrica: string;
  fijos_cargados: boolean;
  fijos_pendientes: number;
  fijos_ficticios: boolean;
  sueldos_fabrica: string;
  fijo_por_unidad: string | null;
  total_por_unidad: string | null;
  equilibrio: EquilibrioPanel;
  cvu: CvuMes | null;
  costo_variable_total: string | null;
  costo_total: string | null;
  fijos_pct_del_total: string | null;
};

export type PrecioQueSubio = {
  material: string;
  color: string | null;
  precio: string;
  moneda: string;
  vigente_desde: string;
  variacion_pct: string;
  salto_grande: boolean;
};

export type PrecioViejo = {
  material: string;
  color: string | null;
  vigente_desde: string;
};

export type AvisoPanel = { codigo: string; texto: string };

export type PanelCostos = {
  periodo: string;
  periodo_anterior: string;
  actual: BloqueCostoMes;
  anterior: BloqueCostoMes;
  variacion_pct: {
    costo_variable_por_unidad: string | null;
    fijos_fabrica: string | null;
    total_por_unidad: string | null;
  };
  precios_que_subieron: PrecioQueSubio[];
  precios_viejos: { cantidad: number; mas_viejos: PrecioViejo[] };
  dolar: { fecha: string; ars_por_usd: string; fuente: string } | null;
  dolar_viejo: boolean;
  avisos: AvisoPanel[];
};

// Trend of the last months (GET /panel/tendencia). Oldest month first; amounts come computed by the API.

export type MotivoIncompleto =
  | "SIN_FIJOS"
  | "FIJOS_PENDIENTES"
  | "FIJOS_FICTICIOS"
  | "SIN_UNIDADES"
  | "PRODUCTOS_SIN_COSTO";

export type MesTendencia = {
  periodo: string;
  unidades: string;
  unidades_sin_costo: string;
  fijos_fabrica: string;
  fijos_cargados: boolean;
  fijos_pendientes: number;
  fijos_ficticios: boolean;
  costo_variable_por_unidad: string | null;
  fijo_por_unidad: string | null;
  total_por_unidad: string | null;
  incompleto: MotivoIncompleto[];
  variacion_pct_total_por_unidad: string | null;
};

export type TendenciaCostos = {
  hasta: string;
  meses: MesTendencia[];
  nota: string;
};

// Sale price and profitability (CVU). Mirrors PrecioVentaOut, RentabilidadOut and EscenarioOut in api.py.

export type ImpuestoDelPrecio = {
  codigo: string;
  nombre: string;
  alicuota: string;
  monto: string;
};

export type PrecioVenta = {
  producto: string;
  precio_ars: string;
  // Margin used to reach the price, a fraction of the price ("0.300" = 30 %); null = typed by hand.
  margen: string | null;
  vigente_desde: string;
  nota: string | null;
  creado_por: string | null;
  creado_en: string | null;
  // Taxes of today over `precio_ars` (the price without taxes); the cost never carries them.
  impuestos?: ImpuestoDelPrecio[];
  total_impuestos?: string | null;
  precio_final?: string | null;
};

export type VeredictoCvu = "NO_CUBRE_VARIABLE" | "MC_BAJO" | "SALUDABLE";

// TRANSFERENCIA: the price the factory charges the store (cost + transfer margin); only in /cvu/fabrica and /cvu/tienda.
export type FuentePrecio = "INGRESADO" | "GUARDADO" | "TRANSFERENCIA";

export type Rentabilidad = {
  producto: string;
  fuente_precio: FuentePrecio | null;
  precio: string | null;
  costo_variable: string | null;
  margen_unidad: string | null;
  margen_pct: string | null;
  markup_pct: string | null;
  veredicto: VeredictoCvu | null;
  motivo: "SIN_PRECIO" | "SIN_COSTO_VARIABLE" | null;
};

export type PrecioSugerido = {
  producto: string;
  costo: string | null;
  margen_pct: string;
  precio: string | null;
};

export type EscenarioResultado = {
  ingresos: string | null;
  margen_contribucion: string | null;
  margen_contribucion_pct: string | null;
  costos_fijos: string | null;
  utilidad: string | null;
  equilibrio_ingresos: string | null;
  equilibrio_unidades: string | null;
  margen_seguridad_pct: string | null;
  motivo: "SIN_VENTAS" | "MC_NO_POSITIVO" | null;
};

export type EscenarioLinea = {
  codigo: string;
  unidades: string;
  precio: string;
  fuente_precio: FuentePrecio;
  costo_variable: string;
  gasto_venta_unidad: string;
  iibb_unidad: string;
  margen_unidad: string;
  margen_pct: string | null;
  veredicto: VeredictoCvu;
  contribucion_total: string;
  participacion_pct: string | null;
  horas_confeccion: string | null;
  margen_por_hora: string | null;
  ranking_por_hora: number | null;
};

export type EscenarioOmitido = {
  codigo: string;
  motivo: "PRODUCTO_NO_ENCONTRADO" | "SIN_PRECIO" | "SIN_COSTO_VARIABLE";
};

export type Escenario = {
  periodo: string;
  fijos: {
    total_fabrica: string;
    cargados: boolean;
    pendientes: number;
    ficticios: boolean;
  };
  resultado: EscenarioResultado;
  lineas: EscenarioLinea[];
  omitidos: EscenarioOmitido[];
  mejor_por_hora: string | null;
  avisos: AvisoPanel[];
  confiable: boolean;
};

export type AmbitoNegocio = "FABRICA" | "TIENDA";

// POST /cvu/fabrica and /cvu/tienda (CvuNegocioOut): the scenario plus the ámbito and the transfer margin.
// `fijos.total_fabrica` holds the fixed costs of the requested ámbito (the name comes from the single-ámbito scenario).
export type CvuNegocio = Escenario & {
  ambito: AmbitoNegocio;
  // A percent number as text ("20.000"), already multiplied by 100 by the API.
  margen_transferencia_pct: string;
};

// GET /costos-fijos/resumen (ResumenGastosOut). Every amount comes calculated by the API.
export type GastoCategoriaResumen = { categoria: string; total: string };

export type GastoAmbitoResumen = {
  ambito: AmbitoNegocio;
  total: string;
  pendientes: number;
  categorias: GastoCategoriaResumen[];
};

export type GastoMesResumen = {
  periodo: string;
  fabrica: string;
  tienda: string;
  total: string;
};

export type ResumenGastos = {
  periodo: string;
  total: string;
  por_ambito: GastoAmbitoResumen[];
  // Oldest month first, at most the last six.
  serie: GastoMesResumen[];
  margen_transferencia_pct: string;
};

// Proveedores and their invoices/images. The API never sends the file bytes in a document;
// the file is opened through /proveedores/documentos/{id}/archivo.
export type Proveedor = {
  codigo: string;
  nombre: string;
  cuit: string | null;
  contacto: string | null;
  telefono: string | null;
  direccion: string | null;
  nota: string | null;
  activo: boolean;
};

export type DocumentoTipo = "FACTURA" | "IMAGEN" | "OTRO";

export type OcrEstado = "PENDIENTE" | "LISTO" | "ERROR" | "NO_CONFIGURADO";

/** What the OCR thinks the document says. Only a suggestion until a person confirms it. */
export type OcrSugerencia = {
  numero: string | null;
  fecha: string | null;
  total: string | null;
  moneda: string | null;
};

export type DocumentoProveedor = {
  id: number;
  tipo: DocumentoTipo;
  nombre_archivo: string;
  mime: string;
  tamano_bytes: number;
  numero: string | null;
  fecha_documento: string | null;
  total: string | null;
  moneda: "ARS" | "USD" | null;
  ocr_estado: OcrEstado;
  ocr_texto: string | null;
  ocr_sugerencia: OcrSugerencia | null;
  ocr_error: string | null;
  subido_por: string;
  created_at: string;
};

export type ProductoReventa = {
  codigo: string;
  nombre: string;
  categoria: string | null;
  proveedor: string | null;
  nota: string | null;
  activo: boolean;
  // Everything below comes calculated by the API; null while there is no purchase.
  costo_unitario_ars: string | null;
  precio_venta_unitario_ars: string | null;
  margen_unitario_ars: string | null;
  // A fraction: 0.4 = 40 %.
  margen_pct: string | null;
  ultima_compra: string | null;
  compras: number;
  unidades_compradas: string;
};

export type CompraReventa = {
  fecha: string;
  // Both null in a price update (a row without units).
  unidades: string | null;
  costo_unitario_ars: string;
  costo_total_ars: string | null;
  precio_venta_unitario_ars: string | null;
  margen_unitario_ars: string | null;
  margen_pct: string | null;
  proveedor: string | null;
  nota: string | null;
  creado_por: string | null;
  creado_en: string | null;
};

export type ProductoReventaDetalle = ProductoReventa & {
  // Newest first.
  historial: CompraReventa[];
};

export type UnidadProducto = {
  producto: string;
  producto_nombre: string;
  categoria: string | null;
  unidades: string;
  lotes: number;
};

export type UnidadesProducidas = {
  periodo: string | null;
  productos: UnidadProducto[];
  total_unidades: string;
};

// Price history of a supplier and payment history of a workshop. Mirror MaterialesDeProveedorOut and
// HistorialDeTallerOut in api.py. Every amount, variation and bar length comes calculated by the API.
export type PrecioHistorial = {
  codigo: string;
  vigente_desde: string;
  precio: string;
  moneda: "ARS" | "USD";
  unidad_del_precio: string;
  iva_incluido: boolean;
  nota_fuente: string | null;
  // Percent change against the previous price of the same material, color and currency (null for the first).
  variacion_pct: string | null;
  salto_grande: boolean;
  // 0 to 100, against the biggest price of the same currency in this series.
  barra_pct: number | null;
};

export type MaterialDeProveedor = {
  material: string;
  material_nombre: string;
  color: string | null;
  ultimo_precio: string;
  moneda: "ARS" | "USD";
  unidad_del_precio: string;
  ultima_fecha: string;
  variacion_ultima_pct: string | null;
  variacion_total_pct: string | null;
  cargas: number;
  // Newest first.
  historial: PrecioHistorial[];
};

export type MaterialesDeProveedor = {
  proveedor: string;
  proveedor_nombre: string;
  materiales: MaterialDeProveedor[];
};

// Orders received from a supplier. Mirror PedidoProveedorOut / PedidoLineaOut. Only added, never edited.
export type PedidoLinea = {
  orden: number;
  material: string;
  material_nombre: string;
  unidad_de_consumo: string;
  cantidad_presentaciones: string;
  presentacion: string;
  contenido_por_presentacion: string;
  precio_por_presentacion: string;
  moneda: "ARS" | "USD";
  iva_incluido: boolean;
  // Price per consumption unit that the API stored (price per presentation / content).
  precio_unitario: string;
  precio_codigo: string;
};

export type PedidoProveedor = {
  codigo: string;
  proveedor: string;
  fecha_de_recepcion: string;
  remito: string | null;
  documento_id: number | null;
  nota: string | null;
  creado_por: string;
  created_at: string;
  lineas: PedidoLinea[];
};

export type LoteDeTaller = {
  lote: string;
  fecha: string | null;
  estado: string;
  productos: number;
  unidades: string;
  unidades_con_precio_pagado: string;
  total_cotizado: string;
  total_pagado: string;
  // Average over the units with a paid price; a mix of products, so it is not compared lot to lot.
  precio_pagado_promedio: string | null;
  barra_pct: number | null;
};

export type PagoDeProducto = {
  // Code of the lot line (LIT-nnnn).
  item: string;
  fecha: string | null;
  lote: string;
  cantidad: string;
  cotizado: string | null;
  pagado: string | null;
  variacion_pct: string | null;
  salto_grande: boolean;
  barra_pct: number | null;
};

export type ProductoDeTaller = {
  producto: string;
  producto_nombre: string;
  categoria: string | null;
  lotes: number;
  unidades: string;
  primer_pagado: string | null;
  ultimo_pagado: string | null;
  variacion_ultima_pct: string | null;
  variacion_total_pct: string | null;
  ultima_fecha: string | null;
  // Newest first, undated last.
  historial: PagoDeProducto[];
};

export type HistorialDeTaller = {
  taller: string;
  taller_nombre: string;
  // Newest first.
  lotes: LoteDeTaller[];
  productos: ProductoDeTaller[];
};

/** Answer of `POST /materiales/lote`: the prices the save added and the codes of the new materials. */
export type MaterialesLote = {
  precios: Precio[];
  materiales_nuevos: string[];
};

// What a supplier sells. Mirror ProveedorProductoOut. A change is a new row of the same product, never an edit.
export type ProveedorProducto = {
  codigo: string;
  proveedor: string;
  nombre: string;
  material: string | null;
  material_nombre: string | null;
  unidad: string;
  cantidad: string | null;
  // Price of one presentation of `cantidad` `unidad`; the API calculates `precio_por_unidad`.
  precio_referencial: string;
  precio_por_unidad: string;
  moneda: "ARS" | "USD";
  iva_incluido: boolean;
  vigente_desde: string;
  nota: string | null;
  cargas: number;
  precio_anterior: string | null;
};

// Transfers to the store, real sales, derived stock and real margin. Mirror the *Out models of the API.
// Every amount and quantity is a Decimal string calculated by the backend; the front never computes with them.

/** One transfer to the store. The factory cost and the transfer price are frozen at that moment. */
export type Transferencia = {
  codigo: string;
  fecha: string;
  producto: string;
  producto_nombre: string;
  unidades: string;
  costo_fabrica_unitario_ars: string;
  precio_transferencia_unitario_ars: string;
  // A fraction: 0.2 = 20 %.
  margen_transferencia_pct: string;
  total_transferido_ars: string;
  nota: string | null;
  creado_por: string | null;
  creado_en: string | null;
};

/** One real sale (own product or Mercadería). The costs of that moment are frozen by the API. */
export type Venta = {
  codigo: string;
  fecha: string;
  producto: string;
  producto_nombre: string;
  tipo: "PRODUCTO" | "MERCADERIA";
  unidades: string;
  precio_unitario_ars: string;
  ingresos_ars: string;
  canal: string | null;
  nota: string | null;
  costo_fabrica_unitario_ars: string | null;
  precio_transferencia_unitario_ars: string | null;
  costo_compra_unitario_ars: string | null;
  creado_por: string | null;
  creado_en: string | null;
};

export type StockFila = {
  codigo: string;
  nombre: string;
  tipo: "PRODUCTO" | "MERCADERIA";
  producido: string | null;
  transferido: string | null;
  comprado: string | null;
  vendido: string;
  // Null for a Mercadería product: it has no factory.
  stock_fabrica: string | null;
  stock_tienda: string;
  // A negative stock is flagged, never hidden; `aviso` explains it.
  inconsistente: boolean;
  aviso: string | null;
};

export type Stock = {
  filas: StockFila[];
  inconsistentes: number;
};

export type MargenFijos = {
  total: string;
  cargados: boolean;
  pendientes: number;
  ficticios: boolean;
};

export type MargenAmbito = {
  margen: string;
  fijos: MargenFijos;
  utilidad: string;
};

export type MargenLinea = {
  codigo: string;
  nombre: string;
  tipo: "PRODUCTO" | "MERCADERIA";
  unidades: string;
  ingresos: string;
  margen_fabrica: string | null;
  margen_tienda: string;
  margen_consolidado: string;
};

export type MargenReal = {
  periodo: string;
  ventas: number;
  unidades: string;
  ingresos: string;
  fabrica: MargenAmbito;
  tienda: MargenAmbito;
  consolidado: MargenAmbito;
  lineas: MargenLinea[];
  avisos: { codigo: string; texto: string }[];
  // False when the month cannot be trusted (see `avisos`).
  confiable: boolean;
};

// Consumption sheet of a new model (backend formulario.py). Quantities are NUMERIC strings; null = not filled in yet.
export type FormularioEstado =
  | "BORRADOR"
  | "ENVIADO"
  | "COMPLETADO"
  | "VALIDADO";

export type FormularioResumen = {
  codigo: string;
  articulo: string;
  estado: FormularioEstado;
  producto: string | null;
  modelo: string | null;
  taller: string | null;
  creado_por: string;
  created_at: string;
  enviado_en: string | null;
  completado_en: string | null;
  validado_en: string | null;
};

export type FormularioLinea = {
  seccion: "CONSUMO" | "HERRAJE";
  orden: number;
  nombre: string;
  cantidad: string | null;
  comentario: string | null;
  /** Unit of the row (m², horas, $, unidades): decided by the API from the row name and section. */
  unidad: string;
};

/** A row with a quantity that validating did not copy to the model, and why. */
export type FormularioNoAplicada = { nombre: string; motivo: string };

export type FormularioDetalle = FormularioResumen & {
  nota: string | null;
  comentario_revision: string | null;
  completado_por: string | null;
  validado_por: string | null;
  lineas: FormularioLinea[];
  /** Only the answer of "validar": rows with a quantity that matched no material. */
  sin_material?: string[] | null;
  /** The answer of "validar" and the sheet of a VALIDADO form (admin only): every row that did not reach the model. */
  no_aplicadas?: FormularioNoAplicada[] | null;
};

/** What `POST /productos/nuevo` answers: the codes of the new model and of its sheet. */

// Mirror MaterialHistorialOut: every supplier order that brought a material and the unit price it arrived at.
export type MaterialPedido = {
  pedido: string;
  fecha_de_recepcion: string;
  proveedor: string;
  proveedor_nombre: string;
  cantidad_presentaciones: string;
  presentacion: string;
  contenido_por_presentacion: string;
  cantidad_recibida: string;
  precio_por_presentacion: string;
  moneda: string;
  iva_incluido: boolean;
  precio_unitario: string;
};

export type MaterialHistorial = {
  codigo: string;
  nombre: string;
  unidad_de_consumo: string;
  recibido: string;
  pedidos: MaterialPedido[];
};
