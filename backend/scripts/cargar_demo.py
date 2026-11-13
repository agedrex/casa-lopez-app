"""Complete the staging DEMO with SYNTHETIC EXAMPLE data: suppliers, quotes, lots and consumption forms.

    cd backend && DATABASE_URL=... .venv/bin/python scripts/cargar_demo.py --entorno staging [--confirmar]

Run it AFTER `cargar_ejemplo.py` (it needs its example products, `EJEMPLO producto 1` to `8`, and the seeded workshops; what
it cannot find it skips and says so). Without `--confirmar` it only shows what it would create (dry run); with it, it writes.

What it loads, always through `backend.servicios`, `backend.proveedores` and `backend.formulario` (their validations apply, no
raw SQL):
  1. Five suppliers with 5 to 8 products each (unit, quantity of one presentation, reference price, currency, VAT, some with
     an older price row), linked to the seeded material when it matches; two supplier orders (`pedido_proveedor`).
  2. Saved quotes (`cotizacion`) of six example products at different dates, hence with different dollars, including an
     INICIAL and a RECOTIZACION of the same product. Two products stay without a quote on purpose.
  3. Four lots of the current moment (PLANIFICADA, EN_CORTE, EN_CONFECCION, LISTA) with several products and quantities.
  4. Five consumption forms: one NEW MODELO sent to the workshop to practice (ENVIADO), one COMPLETADO fully filled, one
     returned with a review comment (ENVIADO), one BORRADOR (admin only) and one VALIDADO.

Every row carries the literal text EJEMPLO in its note, which is also how a second run recognizes what already exists and
creates nothing. The only exception is the saved quote: `cotizacion` has no note, so it is recognized by (product, type)
and belongs to a product marked EJEMPLO; a product that already has a quote of that type is left alone. Nothing is deleted or updated in place; a supplier order is received "today" at
the price in force today of its material, so it does not move any cost.

WARNING: `recortar_staging.py` DELETES every consumption form (and trims the rest), so run this after it, not before.
The planning part (`planificar`) is a pure function of (today, workshops), tested without a database.
"""

import argparse
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend import formulario, proveedores, servicios
from backend.auth import ADMIN
from backend.database import DatabaseConfigurationError, create_database_engine, get_database_url
from backend.models import FormularioConsumo, OrdenFabricacion, PedidoProveedor, Producto, Proveedor, ProveedorProducto

MARCA = "EJEMPLO"
QUIEN = "cargar_demo"
ROLES = frozenset({ADMIN})
# A quote needs a dollar and a price of every material on its date; the seeded prices start here. SUPUESTO: validar.
FECHA_MINIMA_COTIZACION = date(2026, 9, 3)
CAMINO = ("EN_CORTE", "CORTADA", "EN_CONFECCION", "LISTA", "CERRADA")


def marca_de_producto(numero: int) -> str:
    """The note `cargar_ejemplo.py` gives to its n-th example product (the demo quotes and lots point to them)."""
    return f"{MARCA} producto {numero}"


# supplier: (key, explicit code or None, name, contact, phone, address, what it sells)
# PRV-0001 and PRV-0002 are the codes the seeded prices already name in `precio_material.proveedor` (the flex and the EVA).
PROVEEDORES = (
    ("1", "PRV-0001", "Espumas y Flex del Sur", "Marcela Quiroga", "011 5555-0101", "Av. Warnes 1200, CABA", "flex, cartón y entretelas"),
    ("2", "PRV-0002", "Goma Eva Industrial Pampa", "Ricardo Benítez", "011 5555-0102", "Ruta 8 km 52, Pilar", "goma EVA, cementos e hilos"),
    ("3", None, "Curtiembre del Plata", "Silvia Ferrari", "011 5555-0103", "Av. Mitre 3400, Avellaneda", "cueros"),
    ("4", None, "Textil Palermo", "Daniel Ocampo", "011 5555-0104", "Thames 1650, CABA", "telas, trencillas e hilos"),
    ("5", None, "Herrajes San Cristóbal", "Lucía Domínguez", "011 5555-0105", "Av. San Juan 2100, CABA", "herrajes"),
)
# supplier key -> products: (name, material or None, unit, quantity of a presentation or None, reference price, currency,
# price includes VAT, days ago it started, (older price, days ago it started) or None)
PRODUCTOS_DE_PROVEEDOR = {
    "1": (
        ("Flex 1 × 1,40 m × 0,8 mm (rollo)", "MAT-FL01", "m2", "1.4", "14000", "ARS", False, 75, ("12600", 160)),
        ("Cartón 1,5 mm (por m²)", "MAT-CA01", "m2", None, "12250", "ARS", False, 60, None),
        ("Friselina 1,50 m de ancho (rollo de 10 m)", None, "m", "10", "21500", "ARS", True, 40, None),
        ("Entretela termoadhesiva (por metro)", None, "m", None, "2800", "ARS", False, 55, ("2400", 140)),
        ("Cartulina 70 × 100 cm", None, "unidad", None, "950", "ARS", True, 30, None),
    ),
    "2": (
        ("Goma EVA 1 × 1,40 m × 2 mm (plancha)", "MAT-GE01", "m2", "1.4", "8200", "ARS", False, 75, ("7300", 180)),
        ("Goma EVA 1 × 1,40 m × 3 mm (plancha)", None, "m2", "1.4", "11800", "ARS", False, 75, None),
        ("Cemento de contacto (lata de 1 L)", None, "unidad", "1", "9800", "ARS", True, 35, ("8700", 120)),
        ("Cemento de contacto (lata de 4 L)", None, "unidad", "1", "36500", "ARS", True, 35, None),
        ("Hilo y cemento (juego)", "MAT-HC01", "juego", "1", "2.2", "USD", False, 50, ("2", 130)),
    ),
    "3": (
        ("Cuero vacuno anilina fina lisa, color arena", "MAT-CU01", "m2", None, "24", "USD", False, 50, ("22", 130)),
        ("Carpincho curtido", "MAT-CU02", "m2", None, "80", "USD", False, 50, None),
        ("Grano largo", "MAT-CU05", "m2", None, "34040", "ARS", False, 50, None),
        ("Vaca con pelo camuflada", "MAT-CU06", "m2", None, "35", "USD", False, 45, ("32", 100)),
        ("Potro / popurrí (por m²)", "MAT-FO01", "m2", None, "19", "USD", False, 45, None),
        ("Descarne vacuno (piel entera de unos 4 m²)", None, "m2", "4", "52", "USD", False, 30, None),
        ("Cuero vacuno cara plena napa (piel entera de unos 4,5 m²)", None, "m2", "4.5", "120", "USD", False, 20, None),
    ),
    "4": (
        ("Tela forrería Gross textil 1 × 1,50 (rollo)", "MAT-FO02", "m2", "1.5", "6080", "ARS", False, 60, ("5500", 150)),
        ("Tela forrería lisa negra 1 × 1,50 (rollo)", None, "m2", "1.5", "6400", "ARS", False, 60, None),
        ("Moiré para interiores (por metro)", None, "m", None, "3200", "ARS", True, 45, None),
        ("Trencilla de algodón 15 mm (rollo de 50 m)", None, "m", "50", "7900", "ARS", False, 40, None),
        ("Hilo de poliéster N° 40 (cono)", None, "unidad", "1", "3400", "ARS", True, 35, ("3000", 110)),
        ("Hilo de nylon encerado (cono)", None, "unidad", "1", "5200", "ARS", True, 35, None),
    ),
    "5": (
        ("Cierre N° 5 metálico", None, "unidad", None, "780", "ARS", True, 45, None),
        ("Cierre N° 3 plástico", None, "unidad", None, "420", "ARS", True, 45, None),
        ("Deslizador N° 5", None, "unidad", None, "350", "ARS", True, 45, ("300", 120)),
        ("Hebilla de 30 mm, níquel", None, "unidad", None, "1100", "ARS", True, 40, None),
        ("Mosquetón de 25 mm", None, "unidad", None, "1300", "ARS", True, 40, None),
        ("Remaches doble cabeza (caja de 1000)", None, "unidad", "1000", "9500", "ARS", False, 30, ("8200", 100)),
        ("Argolla de 10 mm (bolsa de 100)", None, "unidad", "100", "4800", "ARS", False, 30, None),
        ("Cadena bañada (por metro)", None, "m", None, "1.8", "USD", False, 25, None),
    ),
}
# supplier order: (key, supplier key, delivery note, [(material, presentations, presentation text, content of one in the
# unit of consumption)]). The price of a line is the one in force today of its material, read when loading.
PEDIDOS = (
    ("1", "1", "R-0001-00004512", (("MAT-FL01", "4", "rollo de 1 × 1,40 m", "1.4"),)),
    ("2", "4", "0003-00018877", (("MAT-FO02", "3", "rollo de 1 × 1,50 m", "1.5"),)),
)
# product number, type, days ago. Products 7 and 8 stay without a quote: their grid cost is the one of today.
COTIZACIONES = (
    (1, "INICIAL", 70), (1, "RECOTIZACION", 25), (2, "INICIAL", 62), (3, "INICIAL", 48), (3, "RECOTIZACION", 12),
    (4, "INICIAL", 34), (5, "INICIAL", 66), (5, "RECOTIZACION", 20), (6, "INICIAL", 8),
)
# Sewing per unit at a workshop (ARS) as asked by the workshop, by example product number.
TARIFAS = {1: Decimal("13000"), 2: Decimal("13000"), 3: Decimal("13500"), 4: Decimal("6500"), 5: Decimal("6800"),
           6: Decimal("17500"), 7: Decimal("9000"), 8: Decimal("9000")}
# lot: (key, where, workshop index, days ago it was sent, steps [(state, days ago)], [(product number, units)])
LOTES = (
    ("1", "EXTERNA", 0, 6, (("EN_CORTE", 5), ("CORTADA", 3), ("EN_CONFECCION", 1)), ((1, 24), (3, 18), (6, 30), (2, 12))),
    ("2", "INTERNA", None, 3, (("EN_CORTE", 2),), ((4, 20), (5, 10), (8, 16))),
    ("3", "EXTERNA", 1, 0, (), ((1, 15), (7, 25))),
    ("4", "EXTERNA", 2, 12, (("EN_CORTE", 11), ("CORTADA", 8), ("EN_CONFECCION", 6), ("LISTA", 1)), ((2, 22), (7, 14))),
)
# Quantities of the paper sheet by row name, for a medium article; each form scales them (SUPUESTO: validar las medidas).
MEDIDAS = {
    "CUERO": "0.42", "FORRO / TELA": "0.35", "FORRO / POTRO": "0", "GOMA EVA": "0.12", "FRISELINA": "0.30",
    "CARTÓN FIBRA": "0.08", "FLEX": "0.20", "CARTULINA": "0.05", "MOIRE": "0.10", "HS. DE TRABAJO": "3.5",
    "Y/O MANO DE OBRA TALLER": "0", "DESPERDICIO 30%": "0.13", "CORTE MANO DE OBRA": "0.5", "EMPAQUE": "1",
    "CIERRE N5": "1", "CIERRE N3": "0", "DESLIZADOR N5": "1", "DESLIZADOR N3": "0", "HEBILLA": "2", "MOSQUETÓN": "0",
    "MEDIA LUNA": "0", "ARGOLLA 10MM": "2", "IMÁN": "0", "TORNIQUETE": "0", "CADENA": "0.6", "REMACHES": "8",
    "SPAGUETTI": "0", "TRENCILLA": "0.8", "MANGUERA": "0", "OJALILLO": "4",
}
# form: (key, article, category, size or None, type, steps, filling, review comment, scale, note the workshop reads)
FORMULARIOS = (
    ("1", "Bandolera mini nueva", "Carteras y bandoleras", "CHICO", "MODELO", (), "ninguno", None, "1",
     "Modelo nuevo para practicar: medí cada pieza, completá la planilla y apretá Completar."),
    ("2", "Mochila urbana nueva", "Mochilas y morrales", "MEDIANO", "MODELO", ("llenar", "completar"), "completo", None, "1.6",
     "Planilla ya completada por el taller, a la espera de la revisión."),
    ("3", "Tarjetero slim nuevo", "Tarjeteros", "CHICO", "MODELO", ("llenar", "completar", "devolver"), "parcial",
     "Falta medir el forro y los herrajes: revisá la goma EVA y volvé a completar.", "0.3",
     "Planilla devuelta por el administrador con un comentario de revisión."),
    ("4", "Cinturón con hebilla nuevo", "Cinturones", None, "SUELTO", (), "ninguno", None, "1",
     "Borrador: todavía no se envió al taller."),
    ("5", "Billetera bifold nueva", "Billeteras", "CHICO", "MODELO", ("llenar", "completar", "validar"), "completo", None, "0.5",
     "Planilla validada: sus medidas ya están en el modelo."),
)


# --- Plan (pure) ------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductoDeProveedorPlan:
    clave: str
    proveedor: str
    nombre: str
    material: str | None
    unidad: str
    cantidad: Decimal | None
    precio: Decimal
    moneda: str
    iva_incluido: bool
    desde: date
    marca: str


@dataclass(frozen=True)
class ProveedorPlan:
    clave: str
    codigo: str | None
    nombre: str
    contacto: str
    telefono: str
    direccion: str
    marca: str
    productos: tuple[ProductoDeProveedorPlan, ...]


@dataclass(frozen=True)
class LineaDePedidoPlan:
    material: str
    cantidad: Decimal
    presentacion: str
    contenido: Decimal


@dataclass(frozen=True)
class PedidoPlan:
    clave: str
    proveedor: str
    remito: str
    fecha: date
    lineas: tuple[LineaDePedidoPlan, ...]
    marca: str


@dataclass(frozen=True)
class CotizacionPlan:
    clave: str
    producto: int  # number of the example product
    tipo: str
    fecha: date
    marca: str  # not stored (a quote has no note): the quote is recognized by (product, type, date)


@dataclass(frozen=True)
class RenglonPlan:
    producto: int
    cantidad: Decimal
    cotizado: Decimal | None


@dataclass(frozen=True)
class LotePlan:
    clave: str
    donde: str
    taller: str | None
    envio: date
    pasos: tuple[tuple[str, date], ...]  # states after PLANIFICADA, with their dates
    renglones: tuple[RenglonPlan, ...]
    marca: str


@dataclass(frozen=True)
class FormularioPlan:
    clave: str
    articulo: str
    categoria: str
    tamano: str | None
    tipo: str  # MODELO (a new model + its form already sent) or SUELTO (a loose BORRADOR)
    pasos: tuple[str, ...]  # after creation: llenar, completar, devolver, validar
    lineas: tuple[tuple[str, str, Decimal | None], ...]  # (section, name, quantity) the "llenar" step saves
    comentario: str | None
    marca: str


@dataclass(frozen=True)
class Plan:
    proveedores: list[ProveedorPlan]
    pedidos: list[PedidoPlan]
    cotizaciones: list[CotizacionPlan]
    lotes: list[LotePlan]
    formularios: list[FormularioPlan]

    def filas(self):
        for proveedor in self.proveedores:
            yield proveedor
            yield from proveedor.productos
        for grupo in (self.pedidos, self.cotizaciones, self.lotes, self.formularios):
            yield from grupo


def _lineas_llenas(llenado: str, escala: Decimal) -> tuple[tuple[str, str, Decimal | None], ...]:
    """The rows of the sheet with the quantities this form gets: all of them, only the first six, or none."""
    filas = []
    for fila in formulario.lineas_precargadas():
        valor = None
        if llenado == "completo" or (llenado == "parcial" and fila["seccion"] == "CONSUMO" and fila["orden"] <= 6):
            valor = (Decimal(MEDIDAS[fila["nombre"]]) * escala).quantize(Decimal("0.001"))
        filas.append((fila["seccion"], fila["nombre"], valor))
    return tuple(filas)


def planificar(hoy: date, talleres: list[str]) -> Plan:
    """Everything the loader would create; no clock, no database. `talleres` are the codes of the active workshops."""
    proveedores_plan = []
    for clave, codigo, nombre, contacto, telefono, direccion, _ in PROVEEDORES:
        productos = []
        for n, (producto, material, unidad, cantidad, precio, moneda, iva, dias, anterior) in enumerate(
                PRODUCTOS_DE_PROVEEDOR[clave], start=1):
            base = f"{MARCA} proveedor {clave} producto {n}"
            if anterior:
                productos.append(ProductoDeProveedorPlan(
                    f"proveedor {clave} producto {n} anterior", clave, producto, material, unidad,
                    Decimal(cantidad) if cantidad else None, Decimal(anterior[0]), moneda, iva,
                    hoy - timedelta(days=anterior[1]), f"{base} (precio anterior)"))
            productos.append(ProductoDeProveedorPlan(
                f"proveedor {clave} producto {n}", clave, producto, material, unidad,
                Decimal(cantidad) if cantidad else None, Decimal(precio), moneda, iva, hoy - timedelta(days=dias), base))
        proveedores_plan.append(ProveedorPlan(
            clave, codigo, nombre, contacto, telefono, direccion, f"{MARCA} proveedor {clave}", tuple(productos)))
    pedidos = [PedidoPlan(f"pedido {clave}", proveedor, remito, hoy,
                          tuple(LineaDePedidoPlan(m, Decimal(c), p, Decimal(k)) for m, c, p, k in lineas),
                          f"{MARCA} pedido {clave}")
               for clave, proveedor, remito, lineas in PEDIDOS]
    cotizaciones = [CotizacionPlan(f"cotización producto {n} {tipo}", n, tipo,
                                   max(hoy - timedelta(days=dias), FECHA_MINIMA_COTIZACION),
                                   f"{MARCA} cotización producto {n} {tipo}")
                    for n, tipo, dias in COTIZACIONES]
    lotes = []
    for clave, donde, indice, dias_envio, pasos, renglones in LOTES:
        externo = donde == "EXTERNA" and bool(talleres)
        lotes.append(LotePlan(
            f"lote {clave}", "EXTERNA" if externo else "INTERNA", talleres[indice % len(talleres)] if externo else None,
            hoy - timedelta(days=dias_envio), tuple((estado, hoy - timedelta(days=dias)) for estado, dias in pasos),
            tuple(RenglonPlan(n, Decimal(unidades), TARIFAS[n] if externo else None) for n, unidades in renglones),
            f"{MARCA} demo lote {clave}"))
    formularios = [FormularioPlan(
        clave, articulo, categoria, tamano, tipo, pasos, _lineas_llenas(llenado, Decimal(escala)), comentario,
        f"{MARCA} formulario {clave}: {nota}")
        for clave, articulo, categoria, tamano, tipo, pasos, llenado, comentario, escala, nota in FORMULARIOS]
    return Plan(proveedores_plan, pedidos, cotizaciones, lotes, formularios)


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


class _Carga:
    """What a loading step needs: the session, the counters and the two moves (create / skip)."""

    def __init__(self, session: Session, resumen: Resumen):
        self.session, self.resumen = session, resumen

    @property
    def escribir(self) -> bool:
        return self.resumen.escribio

    def crear(self, tipo: str, accion, cantidad: int = 1) -> None:
        """Run `accion` (only when writing) and count `cantidad` rows; if `accion` raises, nothing is counted."""
        if self.escribir:
            accion()
        self.resumen.creados[tipo] += cantidad

    def omitir(self, tipo: str, motivo: str | None = None, cantidad: int = 1) -> None:
        if cantidad:
            self.resumen.omitidos[tipo] += cantidad
        if motivo and motivo not in self.resumen.avisos:
            self.resumen.avisos.append(motivo)


def _marcados(session: Session, columna_codigo, columna_nota) -> dict[str, str]:
    """{note: code} of the rows that carry the EJEMPLO marker: the only way the loader recognizes its own rows."""
    return {nota: codigo for codigo, nota in session.execute(
        select(columna_codigo, columna_nota).where(columna_nota.like(f"{MARCA}%"))).all()}


def cargar_demo(session: Session, hoy: date, escribir: bool = True) -> Resumen:
    """Create what the plan lists and the database does not have yet; with `escribir=False` only count it."""
    talleres = [t["codigo"] for t in servicios.listar_talleres(session) if t["activo"]]
    plan = planificar(hoy, talleres)
    resumen = Resumen(plan, escribir, Counter(), Counter(), [])
    carga = _Carga(session, resumen)
    codigos_de_proveedor = _cargar_proveedores(carga, plan)
    _cargar_pedidos(carga, plan, hoy, codigos_de_proveedor)
    _cargar_formularios(carga, plan)
    productos = _marcados(session, Producto.codigo, Producto.nota)
    codigo_de = {n: productos.get(marca_de_producto(n)) for n in TARIFAS}
    if not any(codigo_de.values()):
        resumen.avisos.append(
            f"No hay productos {MARCA}: corré antes cargar_ejemplo.py. Se saltean las cotizaciones y los lotes.")
    else:
        _cargar_cotizaciones(carga, plan, codigo_de)
        _cargar_lotes(carga, plan, codigo_de)
    return resumen


# --- 1. Suppliers and their products -------------------------------------------------------------------------------

def _cargar_proveedores(carga: _Carga, plan: Plan) -> dict[str, str]:
    """Create the suppliers and, per supplier, the product rows it lacks (one atomic call). Returns {supplier key: code}."""
    session = carga.session
    existentes = _marcados(session, Proveedor.codigo, Proveedor.nota)
    productos = _marcados(session, ProveedorProducto.codigo, ProveedorProducto.nota)
    codigos: dict[str, str] = {}
    for proveedor in plan.proveedores:
        codigo = existentes.get(proveedor.marca)
        if codigo is not None:
            carga.omitir("proveedores")
        else:
            nuevo = []
            try:
                carga.crear("proveedores", lambda p=proveedor: nuevo.append(proveedores.create_supplier(
                    session, codigo=p.codigo, nombre=p.nombre, cuit=None, contacto=p.contacto, telefono=p.telefono,
                    direccion=p.direccion, nota=p.marca)["codigo"]))
            except (servicios.Conflicto, servicios.DatosInvalidos) as error:
                carga.omitir("proveedores", f"No se creó el proveedor {proveedor.nombre} ni sus productos: {error}")
                continue
            codigo = nuevo[0] if nuevo else None
        if codigo is not None:
            codigos[proveedor.clave] = codigo
        faltan = [p for p in proveedor.productos if p.marca not in productos]
        carga.omitir("productos de proveedor", cantidad=len(proveedor.productos) - len(faltan))
        if not faltan:
            continue
        # Oldest first, so the newest row of each product (the one in force) gets the highest code.
        faltan.sort(key=lambda p: (p.desde, p.clave))
        try:
            carga.crear("productos de proveedor", lambda c=codigo, f=faltan: proveedores.add_products(
                session, c, creado_por=QUIEN, productos=[
                    {"nombre": p.nombre, "material": p.material, "unidad": p.unidad, "cantidad": p.cantidad,
                     "precio_referencial": p.precio, "moneda": p.moneda, "iva_incluido": p.iva_incluido,
                     "vigente_desde": p.desde, "nota": p.marca} for p in f]), cantidad=len(faltan))
        except (servicios.Conflicto, servicios.DatosInvalidos) as error:
            carga.omitir("productos de proveedor", f"No se cargaron los productos de {proveedor.nombre}: {error}")
    return codigos


def _precio_de_hoy(session: Session, material: str, hoy: date) -> dict | None:
    """The price in force today for every colour of a material (the one a supplier order must not move)."""
    return next((p for p in servicios.listar_precios(session, material, hoy) if p["vigente"] and p["color"] is None), None)


def _cargar_pedidos(carga: _Carga, plan: Plan, hoy: date, codigos_de_proveedor: dict[str, str]) -> None:
    """Supplier orders received today at the price in force today of each material: they leave every cost as it was."""
    session = carga.session
    existentes = _marcados(session, PedidoProveedor.codigo, PedidoProveedor.nota)
    for pedido in plan.pedidos:
        if pedido.marca in existentes:
            carga.omitir("pedidos")
            continue
        proveedor = codigos_de_proveedor.get(pedido.proveedor)
        if proveedor is None and carga.escribir:
            carga.omitir("pedidos", f"No se cargó el pedido {pedido.clave}: falta su proveedor.")
            continue
        lineas = []
        for linea in pedido.lineas:
            precio = _precio_de_hoy(session, linea.material, hoy)
            if precio is None:
                break
            lineas.append({
                "material": linea.material, "cantidad_presentaciones": linea.cantidad, "presentacion": linea.presentacion,
                "contenido_por_presentacion": linea.contenido,
                "precio_por_presentacion": (precio["precio"] * linea.contenido).quantize(Decimal("0.0001")),
                "moneda": precio["moneda"], "iva_incluido": precio["iva_incluido"]})
        if len(lineas) < len(pedido.lineas):
            carga.omitir("pedidos", f"No se cargó el pedido {pedido.clave}: un material no tiene precio vigente hoy.")
            continue
        try:
            carga.crear("pedidos", lambda p=pedido, d=proveedor, l=lineas: proveedores.create_order(
                session, d, fecha_de_recepcion=p.fecha, remito=p.remito, documento_id=None, nota=p.marca, lineas=l,
                creado_por=QUIEN))
        except (servicios.Conflicto, servicios.DatosInvalidos) as error:
            carga.omitir("pedidos", f"No se cargó el pedido {pedido.clave}: {error}")


# --- 2. Saved quotes -------------------------------------------------------------------------------------------------

def _cargar_cotizaciones(carga: _Carga, plan: Plan, codigo_de: dict[int, str | None]) -> None:
    """A quote is skipped when its product already has one of that type (on any date): a run on another day creates nothing."""
    session = carga.session
    guardadas = {(q["producto"], q["tipo"]) for q in servicios.cotizaciones_guardadas(session)}
    for cotizacion in plan.cotizaciones:
        codigo = codigo_de.get(cotizacion.producto)
        if codigo is None:
            carga.omitir("cotizaciones", f"Falta el {marca_de_producto(cotizacion.producto)}: no se cotiza.")
        elif (codigo, cotizacion.tipo) in guardadas:
            carga.omitir("cotizaciones")
        else:
            try:
                carga.crear("cotizaciones", lambda c=codigo, q=cotizacion: servicios.guardar_cotizacion(
                    session, c, q.tipo, q.fecha))
            except servicios.Conflicto:
                carga.omitir("cotizaciones")
            except servicios.DatosInvalidos as error:  # incomplete: a price or the dollar is missing at that date
                carga.omitir("cotizaciones", f"No se guardó la cotización {cotizacion.tipo} de {codigo} del {cotizacion.fecha}: {error}")


# --- 3. Lots ---------------------------------------------------------------------------------------------------------

def _cargar_lotes(carga: _Carga, plan: Plan, codigo_de: dict[int, str | None]) -> None:
    session = carga.session
    lotes = _marcados(session, OrdenFabricacion.codigo, OrdenFabricacion.nota)
    for lote in plan.lotes:
        renglones = [r for r in lote.renglones if codigo_de.get(r.producto)]
        if len(renglones) < len(lote.renglones):
            carga.omitir("lotes", f"Al lote {lote.clave} le faltan productos {MARCA}: se carga con los que hay.", cantidad=0)
        codigo = lotes.get(lote.marca)
        estado = "PLANIFICADA"
        if codigo is None:
            if not renglones:
                carga.omitir("lotes", f"No se cargó el {lote.clave}: no hay productos {MARCA}.")
                continue
            nuevo = []
            carga.crear("lotes", lambda l=lote, r=renglones: nuevo.append(servicios.crear_orden(
                session, donde_se_hace=l.donde, taller=l.taller, persona=None, fecha_de_envio=l.envio,
                fecha_de_entrega=None, estado="PLANIFICADA", nota=l.marca,
                items=[{"producto": codigo_de[x.producto], "cantidad": x.cantidad,
                        "taller_precio_cotizado_por_unidad_ars": x.cotizado, "taller_precio_pagado_por_unidad_ars": None,
                        "nota": f"{MARCA} renglón"} for x in r])["codigo"]))
            carga.resumen.creados["renglones de lote"] += len(renglones)
            codigo = nuevo[0] if nuevo else None
        else:
            carga.omitir("lotes")
            estado = servicios.detalle_orden(session, codigo)["estado"]  # a run that stopped halfway continues from here
        camino = ["PLANIFICADA", *(nombre for nombre, _ in lote.pasos)]
        if estado not in camino:
            carga.omitir("lotes", f"El lote {codigo} está en un estado fuera del camino previsto: no se avanza.", cantidad=0)
            continue
        for nombre, fecha in lote.pasos[camino.index(estado):]:
            carga.crear("cambios de estado", lambda c=codigo, n=nombre, f=fecha: servicios.registrar_estado(
                session, c, estado=n, fecha=f, quien=None, fecha_de_entrega=None))


# --- 4. Consumption forms --------------------------------------------------------------------------------------------

def _hecho(paso: str, detalle: dict) -> bool:
    """Whether a step of a form already happened, judging by what the form looks like now."""
    if paso == "llenar":
        return any(linea["cantidad"] is not None for linea in detalle["lineas"])
    if paso == "completar":
        return detalle["estado"] in (formulario.COMPLETADO, formulario.VALIDADO) or detalle["comentario_revision"] is not None
    if paso == "devolver":
        return detalle["comentario_revision"] is not None
    return detalle["estado"] == formulario.VALIDADO  # validar


def _nuevo_formulario(session: Session, plan: FormularioPlan) -> str:
    """A MODELO form is a new model with its form already sent to the workshop; a SUELTO one is a loose BORRADOR."""
    if plan.tipo == "MODELO":
        return formulario.alta_rapida(
            session, nombre=plan.articulo, categoria=plan.categoria, tamano=plan.tamano, nota=plan.marca,
            quien=QUIEN)["formulario"]
    return formulario.crear_formulario(
        session, articulo=plan.articulo, taller=None, producto=None, nota=plan.marca, quien=QUIEN)["codigo"]


def _paso_de_formulario(session: Session, codigo: str, paso: str, plan: FormularioPlan) -> None:
    if paso == "llenar":
        actual = formulario.obtener_formulario(session, codigo, ROLES)
        formulario.guardar_formulario(
            session, codigo, articulo=actual["articulo"], nota=actual["nota"], roles=ROLES,
            lineas=[{"seccion": s, "nombre": n, "cantidad": c, "comentario": None} for s, n, c in plan.lineas])
    else:
        formulario.cambiar_estado(
            session, codigo, paso, roles=ROLES, quien=QUIEN, comentario=plan.comentario if paso == "devolver" else None)


def _cargar_formularios(carga: _Carga, plan: Plan) -> None:
    session = carga.session
    existentes = _marcados(session, FormularioConsumo.codigo, FormularioConsumo.nota)
    for f in plan.formularios:
        codigo = existentes.get(f.marca)
        if codigo is None:
            nuevo = []
            try:
                carga.crear("formularios", lambda p=f: nuevo.append(_nuevo_formulario(session, p)))
            except (servicios.Conflicto, servicios.DatosInvalidos) as error:
                carga.omitir("formularios", f"No se creó el formulario de {f.articulo}: {error}")
                continue
            codigo = nuevo[0] if nuevo else None
            pendientes = list(f.pasos)
        else:
            carga.omitir("formularios")
            detalle = formulario.obtener_formulario(session, codigo, ROLES)
            pendientes = [paso for paso in f.pasos if not _hecho(paso, detalle)]
        for paso in pendientes:
            try:
                carga.crear("pasos de formulario", lambda c=codigo, s=paso, p=f: _paso_de_formulario(session, c, s, p))
            except (servicios.Conflicto, servicios.DatosInvalidos, formulario.SinPermiso) as error:
                carga.omitir("formularios", f"El formulario {codigo} no avanzó ({paso}): {error}", cantidad=0)
                break


# --- Command line -----------------------------------------------------------------------------------------------

def describir_base(url) -> str:
    """host:port/name of a database URL; user and password are never part of it."""
    url = make_url(url)
    return f"{url.host}{f':{url.port}' if url.port else ''}/{url.database}"


def rechazar(mensaje: str) -> int:
    print(mensaje, file=sys.stderr)
    return 2


def correr(hoy: date, escribir: bool) -> Resumen:
    """Open the database named by DATABASE_URL, load (or only count) and close; nothing stays pending when not writing."""
    engine = create_database_engine()
    try:
        with Session(engine) as session:
            try:
                return cargar_demo(session, hoy, escribir=escribir)
            finally:
                if not escribir:
                    session.rollback()
    finally:
        engine.dispose()


def main(argv=None, hoy: date | None = None) -> int:
    parser = argparse.ArgumentParser(description="Completa la demo de staging con datos de EJEMPLO (ficticios).")
    parser.add_argument("--entorno", help="Tiene que ser 'staging'.")
    parser.add_argument("--confirmar", action="store_true",
                        help="Escribe los datos de ejemplo. Sin este aviso solo muestra qué se crearía y no escribe nada.")
    opciones = parser.parse_args(argv)
    if opciones.entorno != "staging":
        return rechazar("No se cargó nada: este script es solo para staging y necesita --entorno staging "
                        "(con --confirmar para escribir; sin él solo muestra qué se crearía).")
    entorno = os.environ.get("RAILWAY_ENVIRONMENT_NAME")
    if entorno is not None and entorno != "staging":
        return rechazar("No se cargó nada: el entorno de Railway no es staging.")  # the value itself is never echoed
    try:
        destino = describir_base(get_database_url())
    except DatabaseConfigurationError:
        print("No se pudo leer DATABASE_URL: hace falta una URL de PostgreSQL válida.", file=sys.stderr)
        return 1
    print(f"Base de datos: {destino}")
    print("Modo: se escribirán datos de EJEMPLO" if opciones.confirmar else "Modo: solo mostrar (sin --confirmar no se escribe nada)")
    try:
        resumen = correr(hoy or date.today(), escribir=opciones.confirmar)
    except (servicios.DatosInvalidos, servicios.Conflicto, servicios.NoEncontrado) as error:
        print(f"Se frenó la carga: {error}", file=sys.stderr)
        return 1
    except Exception as error:  # driver errors can carry connection details: only the class is shown
        print(f"Se frenó la carga por un error inesperado ({type(error).__name__}).", file=sys.stderr)
        return 1
    imprimir(resumen)
    return 0


def imprimir(resumen: Resumen) -> None:
    print("\nFilas que se crearían:" if not resumen.escribio else "\nFilas creadas:")
    for tipo, cantidad in resumen.creados.items():
        print(f"  {tipo}: {cantidad}")
    if not resumen.creados:
        print("  ninguna (todo estaba cargado)")
    if resumen.omitidos:
        print("Ya existían o se salteó: " + ", ".join(f"{tipo} {cantidad}" for tipo, cantidad in resumen.omitidos.items()))
    for aviso in resumen.avisos:
        print(f"Aviso: {aviso}")
    print(f"Todo lo creado lleva la marca {MARCA} en su nota (las cotizaciones, en el producto {MARCA} al que pertenecen).")


if __name__ == "__main__":
    raise SystemExit(main())
