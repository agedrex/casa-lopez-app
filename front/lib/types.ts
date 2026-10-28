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
