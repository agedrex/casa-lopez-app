"""In-memory source for the voice resolver tests: the same dict shapes `servicios` returns, behind `FuenteVoz`."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal as D

from backend.voz_llm import Interpretacion

HOY = date(2026, 10, 28)

MATERIALES = [
    {"codigo": "MAT-CU01", "nombre": "Estándar (Anilina Fina Lisa - C Arena)", "nombre_corto": "Estándar", "etapa": "CUERO",
     "unidad_de_consumo": "m2", "cotizable": True},
    {"codigo": "MAT-CU02", "nombre": "Carpincho", "nombre_corto": "Carpincho", "etapa": "CUERO",
     "unidad_de_consumo": "m2", "cotizable": True},
    {"codigo": "MAT-CU03", "nombre": "Lagarto", "nombre_corto": "Lagarto", "etapa": "CUERO",
     "unidad_de_consumo": "cm", "cotizable": False},
    {"codigo": "MAT-CU05", "nombre": "Grano largo", "nombre_corto": "Grano largo", "etapa": "CUERO",
     "unidad_de_consumo": "m2", "cotizable": True},
    {"codigo": "MAT-FO01", "nombre": "Potro / Popurrí / Cuero", "nombre_corto": "Potro", "etapa": "FORRO",
     "unidad_de_consumo": "m2", "cotizable": True},
    {"codigo": "MAT-FO02", "nombre": "Tela forrería (Gross textil 1 × 1,50)", "nombre_corto": "Tela", "etapa": "FORRO",
     "unidad_de_consumo": "m2", "cotizable": True},
    {"codigo": "MAT-FL01", "nombre": "Flex 1 × 1,40 m × 0,8 mm", "nombre_corto": "Flex", "etapa": "FLEX",
     "unidad_de_consumo": "m2", "cotizable": True},
]
COLORES = [{"codigo": "COL-0001", "nombre": "Negro"}, {"codigo": "COL-0002", "nombre": "Marrón claro"},
           {"codigo": "COL-0003", "nombre": "Marrón oscuro"}]
PRODUCTOS = [
    {"codigo": "PRD-0001", "nombre": "Portafolio Simple Ch. - Estándar"},
    {"codigo": "PRD-0002", "nombre": "Cartera Bugatti - Carpincho"},
    {"codigo": "PRD-0003", "nombre": "Cartera Hermes - Estándar"},
]
TALLERES = [{"codigo": "TAL-0001", "nombre": "Taller A (ejemplo)"}, {"codigo": "TAL-0002", "nombre": "Taller B (ejemplo)"}]
LOTES = [  # newest first, as `servicios` returns them
    {"codigo": "LOT-0003", "taller": "TAL-0001", "taller_nombre": "Taller A (ejemplo)", "estado": "EN_CONFECCION",
     "fecha": date(2026, 10, 20),
     "items": [{"codigo": "LIT-0005", "producto": "PRD-0001", "producto_nombre": "Portafolio Simple Ch. - Estándar"}]},
    {"codigo": "LOT-0002", "taller": "TAL-0002", "taller_nombre": "Taller B (ejemplo)", "estado": "LISTA",
     "fecha": date(2026, 10, 1),
     "items": [{"codigo": "LIT-0003", "producto": "PRD-0001", "producto_nombre": "Portafolio Simple Ch. - Estándar"},
               {"codigo": "LIT-0004", "producto": "PRD-0002", "producto_nombre": "Cartera Bugatti - Carpincho"}]},
    {"codigo": "LOT-0001", "taller": "TAL-0001", "taller_nombre": "Taller A (ejemplo)", "estado": "CERRADA",
     "fecha": date(2026, 9, 5),
     "items": [{"codigo": "LIT-0001", "producto": "PRD-0003", "producto_nombre": "Cartera Hermes - Estándar"}]},
]
GASTOS = [
    {"codigo": "GF-0001", "concepto": "Sueldo Mariano (consumos y moldes)", "monto_ars_del_mes": D("1000000")},
    {"codigo": "GF-0007", "concepto": "Sueldo Gerardo (encargado de fábrica)", "monto_ars_del_mes": None},
    {"codigo": "GF-0008", "concepto": "Cargas sociales de los sueldos", "monto_ars_del_mes": None},
    {"codigo": "GF-0009", "concepto": "Cargas sociales de los alquileres", "monto_ars_del_mes": None},
]


@dataclass
class FuenteEnMemoria:
    """Reads only: there is no write method on purpose, so a resolver that tried to save would fail loudly."""

    dolar: D | None = D("1545")
    chequeo: dict | None = None
    materiales_: list = field(default_factory=lambda: [dict(m) for m in MATERIALES])
    llamadas: list = field(default_factory=list)

    def materiales(self):
        return self.materiales_

    def colores(self):
        return COLORES

    def productos(self):
        return PRODUCTOS

    def talleres(self):
        return TALLERES

    def lotes(self):
        return LOTES

    def gastos(self, periodo):
        if periodo is None:
            return "2026-10", GASTOS
        return (periodo, GASTOS) if periodo == "2026-10" else (periodo, [])

    def ultimo_dolar(self):
        return self.dolar

    def chequeo_de_precio(self, material, color, precio, moneda, fecha):
        self.llamadas.append((material, color, precio, moneda, fecha))
        return self.chequeo


def interpretacion(accion, **campos):
    return Interpretacion(accion=accion, **campos)
