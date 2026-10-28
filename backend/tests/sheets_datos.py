"""In-memory data for the Sheet export tests: same dict shapes `servicios` returns, with a `Fuente` over them."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D

AR = timezone(timedelta(hours=-3))
AHORA = datetime(2026, 10, 28, 15, 30, 5, tzinfo=AR)

ETAPAS = ("CUERO", "FORRO", "FLEX", "GOMA_EVA", "HERRAJES", "HILO_CEMENTO", "CORTE", "CONFECCION")


def costo(total="20760.6"):
    return {
        "fecha": date(2026, 9, 1), "dolar": D("1545"),
        "etapas": {"CUERO": D("9270"), "FORRO": D("810.6"), "FLEX": D("4500"), "GOMA_EVA": D("0"),
                   "HERRAJES": D("3090"), "HILO_CEMENTO": D("3090"), "CORTE": D("0"), "CONFECCION": D("12000.1234")},
        "subtotal": D(total), "componentes_kit": D("0"), "iva_compras": D("0"), "arreglos": D("0"),
        "total_ars": D(total), "total_usd": D("13.4375"),
    }


def producto_costeado(**cambios):
    base = {
        "codigo": "PRD-0001", "nombre": "Portafolio Simple Ch. - Estándar", "categoria": "Portafolios",
        "estado_del_ciclo": "COTIZADO", "quien_lo_confecciona": "INTERNA", "es_kit": False,
        "fecha_de_alta": date(2026, 9, 3), "costo": costo(), "avisos": [], "recotizar": False,
        "inicial_ars": D("20760.6"), "final_ars": None, "ultima_ars": D("20760.6"), "ultima_fecha": date(2026, 9, 3),
    }
    return {**base, **cambios}


def cotizacion(**cambios):
    base = {
        "producto": "PRD-0001", "producto_nombre": "Portafolio Simple Ch. - Estándar", "tipo": "INICIAL",
        "fecha": date(2026, 9, 3), "dolar": D("1545"), "cuero": D("9270"), "forro": D("810.6"), "flex": D("4500"),
        "goma_eva": D("0"), "herrajes": D("3090"), "hilo_cemento": D("3090"), "corte": D("0"), "confeccion": D("0"),
        "subtotal_etapas": D("20760.6"), "componentes_kit": D("0"), "iva_compras": D("0"), "arreglos": D("0"),
        "total_ars": D("20760.6"), "total_usd": D("13.4375"), "estado": "COMPLETA",
    }
    return {**base, **cambios}


def item(**cambios):
    base = {
        "codigo": "LIT-0001", "producto": "PRD-0001", "producto_nombre": "Portafolio Simple Ch.", "categoria": "Portafolios",
        "tamano": "CHICO", "cantidad": D("10"), "cotizado": D("9000"), "pagado": D("8500"), "nota": None,
        "confeccion_por_unidad": D("8500"), "materiales_por_unidad": D("20760.6"), "costo_por_unidad": D("29260.6"),
        "total_linea": D("292606"), "avisos": [],
    }
    return {**base, **cambios}


def lote(**cambios):
    base = {
        "codigo": "LOT-0001", "donde_se_hace": "EXTERNA", "taller": "TAL-0001", "taller_nombre": "Taller A", "persona": None,
        "persona_nombre": None, "fecha_de_envio": date(2026, 9, 10), "fecha_de_entrega": date(2026, 9, 20),
        "periodo": "2026-09", "estado": "CERRADA", "nota": None, "productos": 1, "unidades": D("10"),
        "total_cotizado": D("90000"), "total_cobrado": D("85000"), "costo_total": D("292606"),
        "costo_promedio_por_unidad": D("29260.6"), "avisos": [], "items": [item()],
    }
    return {**base, **cambios}


@dataclass
class FuenteEnMemoria:
    """Same methods as `FuenteSQL`, over literals."""

    productos_costeados_: list = field(default_factory=lambda: [producto_costeado()])
    cotizaciones_: list = field(default_factory=lambda: [cotizacion()])
    productos_: list = field(default_factory=lambda: [{
        "codigo": "PRD-0001", "nombre": "Portafolio Simple Ch. - Estándar", "categoria": "Portafolios",
        "modelo": "MOD-0001", "cuero": "MAT-CU01", "color": None, "quien_lo_confecciona": "INTERNA",
        "estado_del_ciclo": "COTIZADO", "fecha_de_alta": date(2026, 9, 3), "fecha_de_recotizacion": None,
        "fecha_de_cierre": None, "nombre_propio": None, "es_kit": False, "nota": None,
    }])
    modelos_: list = field(default_factory=lambda: [{
        "codigo": "MOD-0001", "nombre_del_modelo": "Portafolio Simple Ch.", "categoria": "Portafolios",
        "modelo_excel_viejo": "6", "fila_excel_viejo": 22, "cuero_m2_por_unidad": D("0.25"), "forro": "MAT-FO02",
        "forro_m2_por_unidad": D("0.2"), "flex_m2_por_unidad": D("0.45"), "goma_eva_m2_por_unidad": None,
        "herrajes_usd_por_unidad": D("2"), "hilo_y_cemento": D("1"), "confeccion_estimada_ars": D("12000"),
        "horas_de_confeccion": None, "origen_de_los_consumos": "EXCEL", "validado": False, "nota": None,
        "tamano": "CHICO", "productos": 1,
    }])
    precios_: list = field(default_factory=lambda: [{
        "codigo": "PRE-0001", "material": "MAT-CU01", "color": None, "proveedor": None, "precio": D("24"),
        "moneda": "USD", "unidad_del_precio": "m2", "iva_incluido": False, "vigente_desde": date(2026, 9, 1),
        "nota_fuente": "manual Excel", "vigente": True, "variacion_pct": None, "salto_grande": False,
    }])
    dolar_: list = field(default_factory=lambda: [{
        "fecha": date(2026, 9, 1), "ars_por_usd": D("1545"), "fuente": "EXCEL_VIEJO", "tipo": None, "nota": None,
    }])
    ordenes_: list = field(default_factory=lambda: [lote()])
    costos_fijos_: list = field(default_factory=lambda: [{
        "periodo": "2026-10", "total_fabrica": D("4000000"), "total_tienda": D("3000000"), "total": D("7000000"),
        "pendientes": 1, "incluye_ficticios": True, "gastos": [
            {"codigo": "GF-0001", "concepto": "Sueldo Mariano", "fabrica_o_tienda": "FABRICA", "categoria": "SUELDOS",
             "persona": "PER-0001", "monto_ars_del_mes": D("1000000"), "ficticio": True, "nota_fuente": "Ficticio"},
            {"codigo": "GF-0002", "concepto": "Alquiler", "fabrica_o_tienda": "TIENDA", "categoria": "ALQUILER",
             "persona": None, "monto_ars_del_mes": None, "ficticio": False, "nota_fuente": None},
        ],
    }])
    talleres_: list = field(default_factory=lambda: [{
        "codigo": "TAL-0001", "nombre": "Taller A", "cuit": None, "telefono": "+54 11 5555-0000", "direccion": None,
        "contacto": None, "activo": True, "nota": "Ejemplo", "ejemplo": True, "lotes": 1, "unidades": D("10"),
        "ultimo_lote": date(2026, 9, 20), "cobro_total_ars": D("85000"),
    }])
    parametros_: list = field(default_factory=lambda: [
        {"codigo": "ARREGLOS_PCT", "constante": "Arreglos", "valor": D("0"), "valor_texto": None, "unidad": "%",
         "que_es": "Recargo", "fuente_estado": "Propuesta: Robert"},
        {"codigo": "PERIODO_VIGENTE", "constante": "Período vigente", "valor": None, "valor_texto": "2026-10",
         "unidad": "AAAA-MM", "que_es": "Mes de costos fijos", "fuente_estado": "Confirmado"},
    ])
    materiales_: list = field(default_factory=lambda: [{
        "codigo": "MAT-CU01", "nombre": "Cuero estándar", "nombre_corto": "Estándar", "etapa": "CUERO",
        "unidad_de_consumo": "m2", "cotizable": True, "controla_inventario": True, "desperdicio_manual": None,
    }])
    calidad_: dict = field(default_factory=lambda: {
        "resumen": {"alta": 1, "media": 0, "baja": 0, "total": 1},
        "grupos": [
            {"clave": "productos", "titulo": "Productos con avisos", "total": 1, "hallazgos": [
                {"severidad": "alta", "entidad": "PRD-0002", "mensaje": "Falta el consumo de cuero", "ruta": "/productos/PRD-0002"}]},
            {"clave": "lotes", "titulo": "Lotes con problemas", "total": 0, "hallazgos": []},
        ],
    })

    def productos_costeados(self): return self.productos_costeados_
    def cotizaciones(self): return self.cotizaciones_
    def productos(self): return self.productos_
    def modelos(self): return self.modelos_
    def precios(self, hoy): return self.precios_
    def dolar(self): return self.dolar_
    def ordenes(self): return self.ordenes_
    def costos_fijos(self): return self.costos_fijos_
    def talleres(self): return self.talleres_
    def parametros(self): return self.parametros_
    def materiales(self): return self.materiales_
    def calidad(self, hoy): return self.calidad_
