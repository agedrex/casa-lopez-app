"""Load SYNTHETIC EXAMPLE data so the cost dashboard can be tried end to end (staging demos only).

    cd backend && DATABASE_URL=... .venv/bin/python scripts/cargar_ejemplo.py --entorno staging --confirmar [--hasta AAAA-MM] [--solo-mostrar]

It loads the 6 months ending at `--hasta` (default: this month): a dollar per month, price updates, fixed costs of the
factory and the store, one salary correction and, in the last month, two pending amounts, example products and 2 to 4 lots
per month. Everything goes through `backend.servicios` (so its validations apply) and every row carries the literal text
EJEMPLO in its note, which is also how a second run recognizes what already exists and creates nothing.

Nothing is ever deleted or updated in place here (the project forbids it). The planning part (`planificar`) is a pure
function of (last month, today, people, workshops), so it is tested without a database.
"""

import argparse
import os
import re
import sys
from calendar import monthrange
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend import servicios
from backend.database import DatabaseConfigurationError, create_database_engine, get_database_url
from backend.models import Color, GastoPeriodo, OrdenFabricacion, PrecioMaterial, Producto, TipoCambio

MARCA = "EJEMPLO"
MESES = 6
PERIODO = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
# Month the seeded prices and dollar come from (migration 0004). SUPUESTO: validar. The example series are anchored on
# the seed values (dollar 1545, cuero 24 USD, tela 4053, flex 10000) so that the first example price after the seed
# continues the series instead of jumping.
MES_BASE = 2026 * 12 + 8  # 2026-09
DOLAR_BASE = Decimal("1545")
PCT_DOLAR = (Decimal("2"), Decimal("3"), Decimal("4"))  # monthly rise, by month index % 3 (2 % to 4 %)
# material, currency, price unit, price at MES_BASE, update every n months, rise in % per update, rounding step
REGLAS_DE_PRECIOS = (
    ("MAT-CU01", "USD", "m2", Decimal("24"), 1, Decimal("4.5"), Decimal("0.5")),
    ("MAT-FO02", "ARS", "m2", Decimal("4053"), 2, Decimal("5"), Decimal("50")),
    ("MAT-FL01", "ARS", "m2", Decimal("10000"), 3, Decimal("8"), Decimal("100")),
)
COLOR_VIEJO = "Rojo"
# The only price of its color: it is never updated, so "Qué está viejo" has something to show.
PRECIO_VIEJO = ("MAT-CU02", COLOR_VIEJO, "USD", "m2", Decimal("82"))
# model, leather, color, who makes it, name, sewing per unit at a workshop (ARS). The models are seeded (MOD-nnnn).
PRODUCTOS = (
    ("MOD-0001", "MAT-CU01", None, "EXTERNA", "Portafolio simple chico", Decimal("12000")),
    ("MOD-0011", "MAT-CU01", None, "INTERNA", "Cartera Peter chica", Decimal("8000")),
    ("MOD-0012", "MAT-CU01", None, "EXTERNA", "Cartera Peter Jenny", Decimal("12000")),
    ("MOD-0024", "MAT-CU01", None, "INTERNA", "Billetera dama", Decimal("6000")),
    ("MOD-0024", "MAT-CU02", COLOR_VIEJO, "INTERNA", "Billetera dama carpincho rojo", Decimal("6000")),
    ("MOD-0005", "MAT-CU01", None, "EXTERNA", "Necesaire Elio", Decimal("16000")),
    ("MOD-0013", "MAT-CU01", None, "INTERNA", "Portarretratos chico", Decimal("8000")),
    ("MOD-0016", "MAT-CU01", None, "INTERNA", "Portavalores", Decimal("8000")),
)
SUELDOS_FABRICA = {"CONSUMO_MOLDES": 1_200_000, "CORTE": 1_100_000, "CONFECCION": 1_150_000, "ENCARGADO": 1_500_000}
SUELDO_VENDEDOR = 900_000
LUZ_Y_GAS = {1: 150, 2: 160, 3: 150, 4: 170, 5: 210, 6: 250, 7: 260, 8: 240, 9: 200, 10: 170, 11: 150, 12: 150}  # thousands
# A lot's path; `OFFSETS` are the days after shipping at which each state is reached.
CAMINO = ("EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA", "CERRADA")
OFFSETS = (1, 2, 4, 7, 9)
DIAS_DE_ENVIO = (2, 6, 11, 16)


# --- Plan (pure) ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ColorPlan:
    clave: str
    nombre: str
    marca: str


@dataclass(frozen=True)
class DolarPlan:
    clave: str
    periodo: str
    fecha: date
    valor: Decimal
    marca: str


@dataclass(frozen=True)
class PrecioPlan:
    clave: str
    periodo: str
    material: str
    color: str | None
    precio: Decimal
    moneda: str
    unidad: str
    fecha: date
    marca: str


@dataclass(frozen=True)
class ProductoPlan:
    clave: str
    modelo: str
    cuero: str
    color: str | None
    confecciona: str
    nombre: str
    tarifa: Decimal  # sewing per unit at a workshop, ARS
    alta: date
    marca: str


@dataclass(frozen=True)
class GastoPlan:
    clave: str
    periodo: str
    concepto: str
    lado: str
    categoria: str
    persona: str | None
    monto: Decimal | None
    marca: str


@dataclass(frozen=True)
class CorreccionPlan:
    clave: str
    periodo: str
    clave_gasto: str
    monto: Decimal
    marca: str


@dataclass(frozen=True)
class RenglonPlan:
    producto: str  # key of a ProductoPlan
    cantidad: Decimal
    cotizado: Decimal | None
    pagado: Decimal | None


@dataclass(frozen=True)
class LotePlan:
    clave: str
    periodo: str
    donde: str
    taller: str | None
    envio: date
    entrega: date | None
    pasos: tuple[tuple[str, date], ...]  # states after PLANIFICADA, with their dates
    renglones: tuple[RenglonPlan, ...]
    marca: str


@dataclass(frozen=True)
class Plan:
    meses: list[str]
    colores: list[ColorPlan]
    dolares: list[DolarPlan]
    precios: list[PrecioPlan]
    productos: list[ProductoPlan]
    gastos: list[GastoPlan]
    correcciones: list[CorreccionPlan]
    lotes: list[LotePlan]

    def filas(self):
        for grupo in (self.colores, self.dolares, self.precios, self.productos, self.gastos, self.correcciones, self.lotes):
            yield from grupo


def _indice(periodo: str) -> int:
    return int(periodo[:4]) * 12 + int(periodo[5:7]) - 1


def _redondear(valor: Decimal, paso: Decimal) -> Decimal:
    return (valor / paso).quantize(Decimal(1), ROUND_HALF_UP) * paso


def _fecha(periodo: str, dia: int, hoy: date) -> date:
    """Day `dia` of the month, never past the end of it nor, in the current month, past today."""
    ano, mes = int(periodo[:4]), int(periodo[5:7])
    tope = monthrange(ano, mes)[1]
    if periodo == servicios.mes_de(hoy):
        tope = min(tope, hoy.day)
    return date(ano, mes, min(dia, tope))


def _dolar_del_mes(indice: int) -> Decimal:
    valor = DOLAR_BASE
    for k in range(MES_BASE + 1, indice + 1):
        valor *= 1 + PCT_DOLAR[k % 3] / 100
    for _ in range(indice, MES_BASE):
        valor /= Decimal("1.03")
    return _redondear(valor, Decimal(5))


def _precio_de_regla(regla, indice: int) -> Decimal | None:
    """The price of a series in a month, or None if the series is not updated that month (or it is the seed's month)."""
    _, _, _, base, cada, pct, paso = regla
    distancia = indice - MES_BASE
    if distancia == 0 or distancia % cada:
        return None
    return _redondear(base * (1 + pct / 100) ** (distancia // cada), paso)


def _planificar_gastos(periodo: str, ultimo: bool, personas: list[dict]) -> list[GastoPlan]:
    mes, indice = int(periodo[5:7]), _indice(periodo)
    distancia = indice - MES_BASE
    escalon = (distancia + 3) // 3  # rents step up every three months
    def sueldo(base: int) -> Decimal:
        return _redondear(Decimal(base) * (1 + Decimal("0.02") * distancia), Decimal(10_000))

    filas = [
        ("alquiler-fabrica", "Alquiler de la fábrica", "FABRICA", "ALQUILER", None, Decimal(850_000 + 50_000 * escalon)),
        ("luz-gas", "Luz y gas de la fábrica", "FABRICA", "SERVICIOS", None, Decimal(LUZ_Y_GAS[mes] * 1000)),
        ("mantenimiento", "Mantenimiento de máquinas", "FABRICA", "OTROS", None, Decimal(60_000 + 10_000 * (indice % 3))),
    ]
    activas = [p for p in personas if p.get("activo", True)]
    for persona in activas:
        if persona["rol"] in SUELDOS_FABRICA:
            filas.append((f"sueldo-{persona['codigo']}", f"Sueldo {persona['nombre']}", "FABRICA", "SUELDOS",
                          persona["codigo"], sueldo(SUELDOS_FABRICA[persona["rol"]])))
    filas.append(("alquiler-local", "Alquiler del local", "TIENDA", "ALQUILER", None, Decimal(700_000 + 40_000 * escalon)))
    vendedor = next((p for p in activas if p["rol"] == "VENTAS"), None)
    if vendedor:
        filas.append((f"sueldo-{vendedor['codigo']}", f"Sueldo {vendedor['nombre']}", "TIENDA", "SUELDOS",
                      vendedor["codigo"], sueldo(SUELDO_VENDEDOR)))
    pendientes = {"luz-gas", "mantenimiento"} if ultimo else set()  # the last month still waits for two bills
    return [
        GastoPlan(f"gasto {periodo} {clave}", periodo, concepto, lado, categoria, persona,
                  None if clave in pendientes else monto, f"{MARCA} gasto {periodo} {clave}")
        for clave, concepto, lado, categoria, persona, monto in filas
    ]


def _planificar_lotes(
    periodo: str, hoy: date, talleres: list[str], productos: list[ProductoPlan],
) -> list[LotePlan]:
    indice = _indice(periodo)
    actual = periodo == servicios.mes_de(hoy)
    lotes = []
    for j in range(3 + (indice % 3 == 0)):  # 3 lots, 4 every third month
        externo = bool(talleres) and (indice + j) % 2 == 1
        envio = _fecha(periodo, DIAS_DE_ENVIO[j], hoy)
        if periodo > servicios.mes_de(hoy):
            meta = 0  # a future month: planned only
        elif actual:
            meta = (3, 2, 1, 4)[j % 4]  # in progress: how many steps of CAMINO are done; never closed this month
        else:
            meta = len(CAMINO)
        pasos = tuple((estado, min(envio + timedelta(days=dias), hoy)) for estado, dias in zip(CAMINO[:meta], OFFSETS))
        entrega = pasos[-1][1] if meta == len(CAMINO) else None
        elegidos = []
        for k in range(1 + (indice + 2 * j) % 3):
            posicion = (indice * 3 + j * 2 + k * 5) % len(productos)
            while productos[posicion] in elegidos:
                posicion = (posicion + 1) % len(productos)
            elegidos.append(productos[posicion])
        renglones = []
        for k, producto in enumerate(elegidos):
            cantidad = Decimal(12 + (indice * 7 + j * 11 + k * 13) % 29)  # 12 to 40 units
            cotizado = pagado = None
            if externo:
                cotizado = _redondear(producto.tarifa * (1 + Decimal("0.02") * (indice - MES_BASE)) * Decimal("1.1"), Decimal(500))
                if entrega is not None:
                    pagado = cotizado - Decimal(500) * (1 + (indice + j + k) % 2)
            renglones.append(RenglonPlan(producto.clave, cantidad, cotizado, pagado))
        lotes.append(LotePlan(
            f"lote {periodo} {j + 1}", periodo, "EXTERNA" if externo else "INTERNA",
            talleres[(indice + j) % len(talleres)] if externo else None, envio, entrega, pasos, tuple(renglones),
            f"{MARCA} lote {periodo} #{j + 1}"))
    return lotes


def planificar(hasta: str, hoy: date, personas: list[dict], talleres: list[str]) -> Plan:
    """Everything the loader would create for the 6 months ending at `hasta`; no clock, no database."""
    if not PERIODO.fullmatch(hasta):
        raise ValueError("El mes tiene que tener el formato AAAA-MM.")
    meses = list(reversed(servicios.ultimos_meses(hasta, MESES)))
    colores = [ColorPlan("color rojo", COLOR_VIEJO, f"{MARCA} color")]
    dolares = [DolarPlan(f"dolar {m}", m, _fecha(m, 3, hoy), _dolar_del_mes(_indice(m)), f"{MARCA} dólar {m}") for m in meses]
    precios = []
    for m in meses:
        for regla in REGLAS_DE_PRECIOS:
            precio = _precio_de_regla(regla, _indice(m))
            if precio is not None:
                precios.append(PrecioPlan(f"precio {m} {regla[0]}", m, regla[0], None, precio, regla[1], regla[2],
                                          _fecha(m, 2, hoy), f"{MARCA} precio {m} {regla[0]}"))
    material, color, moneda, unidad, valor = PRECIO_VIEJO
    precios.append(PrecioPlan(f"precio {meses[0]} {material} {color}", meses[0], material, color, valor, moneda, unidad,
                              _fecha(meses[0], 2, hoy), f"{MARCA} precio {meses[0]} {material} {color}"))
    productos = [ProductoPlan(f"producto {n}", modelo, cuero, color, confecciona, nombre, tarifa, _fecha(meses[0], 1, hoy),
                              f"{MARCA} producto {n}")
                 for n, (modelo, cuero, color, confecciona, nombre, tarifa) in enumerate(PRODUCTOS, 1)]
    gastos = [g for m in meses for g in _planificar_gastos(m, m == meses[-1], personas)]
    correcciones = []
    mes_corregido = meses[2]  # a past month
    sueldos = [g for g in gastos if g.periodo == mes_corregido and g.categoria == "SUELDOS" and g.lado == "FABRICA"]
    if sueldos:
        original = sueldos[-1]  # the last factory salary of the month (the manager's in the seed)
        correcciones.append(CorreccionPlan(
            f"correccion {mes_corregido}", mes_corregido, original.clave,
            _redondear(original.monto * Decimal("1.1"), Decimal(10_000)), f"{MARCA} corrección {mes_corregido} (aumento)"))
    lotes = [lote for m in meses for lote in _planificar_lotes(m, hoy, talleres, productos)]
    return Plan(meses, colores, dolares, precios, productos, gastos, correcciones, lotes)


# --- Loading ----------------------------------------------------------------------------------------------------

@dataclass
class Resumen:
    plan: Plan
    escribio: bool
    creados: Counter
    omitidos: Counter
    avisos: list[str]

    @property
    def total_creado(self) -> int:
        return sum(self.creados.values())


def _marcados(session: Session, columna_codigo, columna_nota) -> dict[str, str]:
    """{note: code} of the rows that carry the EJEMPLO marker: the only way the loader recognizes its own rows."""
    return {nota: codigo for codigo, nota in session.execute(
        select(columna_codigo, columna_nota).where(columna_nota.like(f"{MARCA}%"))).all()}


def cargar_ejemplo(session: Session, hasta: str, hoy: date, escribir: bool = True) -> Resumen:
    """Create what the plan lists and the database does not have yet; with `escribir=False` only count it."""
    personas = servicios.listar_personas(session)
    talleres = [t["codigo"] for t in servicios.listar_talleres(session) if t["activo"]]
    plan = planificar(hasta, hoy, personas, talleres)
    resumen = Resumen(plan, escribir, Counter(), Counter(), [])
    creados, omitidos = resumen.creados, resumen.omitidos

    def crear(tipo: str, accion) -> None:
        if escribir:
            accion()
        creados[tipo] += 1

    def omitir(tipo: str, motivo: str | None = None) -> None:
        omitidos[tipo] += 1
        if motivo and motivo not in resumen.avisos:
            resumen.avisos.append(motivo)

    existentes = _marcados(session, Color.codigo, Color.nota)
    for color in plan.colores:
        if color.marca in existentes:
            omitir("colores")
        elif session.scalar(select(Color.id).where(Color.nombre == color.nombre)) is not None:
            omitir("colores", f"El color {color.nombre} ya existe sin la marca {MARCA}: no se vuelve a crear.")
        else:
            crear("colores", lambda c=color: servicios.crear_color(session, nombre=c.nombre, nota=c.marca))

    existentes = _marcados(session, TipoCambio.id, TipoCambio.nota)
    for dolar in plan.dolares:
        if dolar.marca in existentes:
            omitir("dólares")
            continue
        try:
            crear("dólares", lambda d=dolar: servicios.crear_dolar(
                session, fecha=d.fecha, ars_por_usd=d.valor, fuente="MANUAL", tipo="VENDEDOR", nota=d.marca))
        except servicios.Conflicto:
            omitir("dólares", f"Ya había un dólar con la misma fecha y fuente; no se carga el de {dolar.periodo}.")

    existentes = _marcados(session, PrecioMaterial.codigo, PrecioMaterial.nota_fuente)
    for precio in plan.precios:
        if precio.marca in existentes:
            omitir("precios")
            continue
        try:
            crear("precios", lambda p=precio: servicios.crear_precio(
                session, material=p.material, color=p.color, proveedor=None, precio=p.precio, moneda=p.moneda,
                unidad_del_precio=p.unidad, iva_incluido=False, vigente_desde=p.fecha, nota_fuente=p.marca))
        except servicios.Conflicto:
            omitir("precios", f"Ya había un precio de {precio.material} para esa fecha; no se carga el de {precio.periodo}.")

    productos = _marcados(session, Producto.codigo, Producto.nota)
    for producto in plan.productos:
        if producto.marca in productos:
            omitir("productos")
            continue

        def nuevo_producto(p=producto) -> None:
            ficha = servicios.crear_producto(
                session, modelo=p.modelo, cuero=p.cuero, color=p.color, quien_lo_confecciona=p.confecciona,
                fecha_de_alta=p.alta, nombre_propio=p.nombre, es_kit=False, nota=p.marca)
            productos[p.marca] = ficha["codigo"]

        crear("productos", nuevo_producto)

    # A month that already has fixed costs of its own (the seeded 2026-10, a copied month) is never added to: the new
    # rows would be summed with the real ones.
    ajenos = set(session.scalars(select(GastoPeriodo.periodo).where(
        GastoPeriodo.nota_fuente.is_(None) | ~GastoPeriodo.nota_fuente.like(f"{MARCA}%"))))
    existentes = _marcados(session, GastoPeriodo.codigo, GastoPeriodo.nota_fuente)
    nuevos = set()  # marks created in this run (a simulation creates nothing, but a correction needs its row to exist)
    for gasto in plan.gastos:
        if gasto.marca in existentes:
            omitir("gastos fijos")
        elif gasto.periodo in ajenos:
            omitir("gastos fijos", f"El mes {gasto.periodo} ya tiene costos fijos propios: no se le agregan los de ejemplo.")
        else:
            crear("gastos fijos", lambda g=gasto: servicios.crear_gasto(
                session, periodo=g.periodo, concepto=g.concepto, fabrica_o_tienda=g.lado, categoria=g.categoria,
                persona=g.persona, monto_ars_del_mes=g.monto, ficticio=False, nota_fuente=g.marca))
            nuevos.add(gasto.marca)
    existentes = _marcados(session, GastoPeriodo.codigo, GastoPeriodo.nota_fuente)
    for correccion in plan.correcciones:
        original = next(g for g in plan.gastos if g.clave == correccion.clave_gasto)
        if correccion.marca in existentes:
            omitir("correcciones")
        elif original.marca not in existentes and original.marca not in nuevos:
            omitir("correcciones", f"No hay un gasto de ejemplo en {correccion.periodo} para corregir.")
        else:
            try:
                crear("correcciones", lambda c=correccion, k=existentes.get(original.marca): servicios.corregir_gasto(
                    session, k, c.monto, nota=c.marca, ficticio=False))
            except servicios.Conflicto:
                omitir("correcciones", f"El gasto de ejemplo de {correccion.periodo} ya fue corregido por otra persona.")

    codigo_de = {p.clave: productos.get(p.marca) for p in plan.productos}
    lotes = _marcados(session, OrdenFabricacion.codigo, OrdenFabricacion.nota)
    for lote in plan.lotes:
        codigo = lotes.get(lote.marca)
        estado = "PLANIFICADA"
        if codigo is None:
            if escribir:
                items = [{"producto": codigo_de[r.producto], "cantidad": r.cantidad,
                          "taller_precio_cotizado_por_unidad_ars": r.cotizado, "taller_precio_pagado_por_unidad_ars": None,
                          "nota": f"{MARCA} renglón"} for r in lote.renglones]
                codigo = servicios.crear_orden(
                    session, donde_se_hace=lote.donde, taller=lote.taller, persona=None, fecha_de_envio=lote.envio,
                    fecha_de_entrega=None, estado=estado, nota=lote.marca, items=items)["codigo"]
            creados["lotes"] += 1
            creados["renglones de lote"] += len(lote.renglones)
        else:
            omitir("lotes")
            estado = servicios.detalle_orden(session, codigo)["estado"]  # a run that stopped halfway continues from here
        camino = ["PLANIFICADA", *(nombre for nombre, _ in lote.pasos)]
        if estado not in camino:
            omitir("lotes", f"El lote {codigo} está en un estado fuera del camino previsto: no se avanza.")
            continue
        for nombre, fecha in lote.pasos[camino.index(estado):]:
            if escribir:
                servicios.registrar_estado(session, codigo, estado=nombre, fecha=fecha, quien=None,
                                           fecha_de_entrega=lote.entrega if nombre == "CERRADA" else None)
            creados["cambios de estado"] += 1
        if lote.entrega is None:
            continue
        # What the workshop charged arrives once the lot is delivered.
        if codigo is None:  # simulation of a lot that does not exist yet
            faltan = [r for r in lote.renglones if r.pagado is not None]
            creados["precios pagados"] += len(faltan)
            continue
        for item, renglon in zip(servicios.detalle_orden(session, codigo)["items"], lote.renglones):
            if renglon.pagado is not None and item["pagado"] is None:
                if escribir:
                    servicios.registrar_precios_item(session, codigo, item["codigo"], cotizado=None, pagado=renglon.pagado)
                creados["precios pagados"] += 1
    return resumen


# --- Command line -----------------------------------------------------------------------------------------------

def describir_base(url) -> str:
    """host:port/name of a database URL; user and password are never part of it."""
    url = make_url(url)
    return f"{url.host}{f':{url.port}' if url.port else ''}/{url.database}"


def rechazar(mensaje: str) -> int:
    print(mensaje, file=sys.stderr)
    return 2


def main(argv=None, hoy: date | None = None) -> int:
    parser = argparse.ArgumentParser(description="Carga datos de EJEMPLO (ficticios) para probar el panel de costos.")
    parser.add_argument("--entorno", help="Tiene que ser 'staging'.")
    parser.add_argument("--confirmar", action="store_true", help="Confirma que querés escribir datos de ejemplo.")
    parser.add_argument("--hasta", help="Último mes a cargar (AAAA-MM). Por defecto, el mes actual.")
    parser.add_argument("--solo-mostrar", action="store_true", help="Muestra qué se crearía sin escribir nada.")
    opciones = parser.parse_args(argv)
    if opciones.entorno != "staging" or not opciones.confirmar:
        return rechazar("No se cargó nada: este script escribe datos de ejemplo y necesita los dos avisos juntos, "
                        "--entorno staging y --confirmar.")
    entorno = os.environ.get("RAILWAY_ENVIRONMENT_NAME")
    if entorno is not None and entorno != "staging":
        return rechazar("No se cargó nada: el entorno de Railway no es staging.")  # the value itself is never echoed
    hoy = hoy or date.today()
    hasta = opciones.hasta or servicios.mes_de(hoy)
    if not PERIODO.fullmatch(hasta):
        return rechazar("No se cargó nada: el mes de --hasta tiene que tener el formato AAAA-MM.")
    try:
        destino = describir_base(get_database_url())
    except DatabaseConfigurationError:
        print("No se pudo leer DATABASE_URL: hace falta una URL de PostgreSQL válida.", file=sys.stderr)
        return 1
    print(f"Base de datos: {destino}")
    print("Modo: solo mostrar (no se escribe nada)" if opciones.solo_mostrar else "Modo: se escribirán datos de EJEMPLO")
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            resumen = cargar_ejemplo(session, hasta, hoy, escribir=not opciones.solo_mostrar)
    except (servicios.DatosInvalidos, servicios.Conflicto, servicios.NoEncontrado) as error:
        print(f"Se frenó la carga: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # driver errors can carry connection details: only the class is shown
        print(f"Se frenó la carga por un error inesperado ({type(error).__name__}).", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    imprimir(resumen)
    return 0


def imprimir(resumen: Resumen) -> None:
    print(f"\nMeses cubiertos: {resumen.plan.meses[0]} a {resumen.plan.meses[-1]}")
    print("Filas que se crearían:" if not resumen.escribio else "Filas creadas:")
    for tipo, cantidad in resumen.creados.items():
        print(f"  {tipo}: {cantidad}")
    if not resumen.creados:
        print("  ninguna (todo estaba cargado)")
    if resumen.omitidos:
        print("Ya existían o se salteó: " + ", ".join(f"{tipo} {cantidad}" for tipo, cantidad in resumen.omitidos.items()))
    for aviso in resumen.avisos:
        print(f"Aviso: {aviso}")
    print(f"Todo lo creado lleva la marca {MARCA} en su nota.")


if __name__ == "__main__":
    raise SystemExit(main())
