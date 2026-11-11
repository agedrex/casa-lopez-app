"""Resale products: things Casa López buys ready-made and resells. No materials, stages or quotes.

The cost of a product is the unit cost of its latest purchase (latest `fecha`, then latest id); a new price is a new
purchase, nothing is edited or deleted. The cost of a purchase is `unidades × costo_unitario_ars`. The sale price is the
one typed in the latest purchase that has one; the margin is computed here, never by the front.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Categoria, CompraReventa, ProductoReventa
from backend.servicios import (
    Conflicto, DatosInvalidos, NoEncontrado, _insertar, _siguiente_numero, _texto_o_nada,
)

CENTAVOS = Decimal("0.01")


def _compras(session: Session, producto_id: int) -> list[CompraReventa]:
    """Newest first: latest `fecha`, then latest id."""
    return list(session.scalars(
        select(CompraReventa).where(CompraReventa.producto_reventa_id == producto_id)
        .order_by(CompraReventa.fecha.desc(), CompraReventa.id.desc())
    ))


def _compra_a_dict(c: CompraReventa) -> dict:
    margen, margen_pct = _margen(c.costo_unitario_ars, c.precio_venta_unitario_ars)
    return {
        "fecha": c.fecha, "unidades": c.unidades, "costo_unitario_ars": c.costo_unitario_ars,
        "costo_total_ars": c.unidades * c.costo_unitario_ars, "precio_venta_unitario_ars": c.precio_venta_unitario_ars,
        "margen_unitario_ars": margen, "margen_pct": margen_pct, "proveedor": c.proveedor, "nota": c.nota,
        "creado_por": c.creado_por, "creado_en": c.created_at,
    }


def _margen(costo: Decimal, precio: Decimal | None) -> tuple[Decimal | None, Decimal | None]:
    """Margin over the sale price (profit / price), as a fraction. None without a sale price."""
    if precio is None:
        return None, None
    ganancia = precio - costo
    return ganancia, (ganancia / precio).quantize(Decimal("0.0001"))


def _a_dict(p: ProductoReventa, categoria: str | None, compras: list[CompraReventa]) -> dict:
    ultima = compras[0] if compras else None
    con_precio = next((c for c in compras if c.precio_venta_unitario_ars is not None), None)
    costo = ultima.costo_unitario_ars if ultima else None
    precio = con_precio.precio_venta_unitario_ars if con_precio else None
    margen, margen_pct = _margen(costo, precio) if costo is not None else (None, None)
    return {
        "codigo": p.codigo, "nombre": p.nombre, "categoria": categoria, "proveedor": p.proveedor, "nota": p.nota,
        "activo": p.activo, "costo_unitario_ars": costo, "precio_venta_unitario_ars": precio,
        "margen_unitario_ars": margen, "margen_pct": margen_pct, "ultima_compra": ultima.fecha if ultima else None,
        "compras": len(compras), "unidades_compradas": sum((c.unidades for c in compras), Decimal(0)),
    }


def _categoria_nombre(session: Session, categoria_id: int | None) -> str | None:
    return session.scalar(select(Categoria.nombre).where(Categoria.id == categoria_id)) if categoria_id else None


def _por_codigo(session: Session, codigo: str) -> ProductoReventa:
    p = session.scalar(select(ProductoReventa).where(ProductoReventa.codigo == codigo))
    if p is None:
        raise NoEncontrado(f"No existe el producto de mercadería {codigo}.")
    return p


def listar(session: Session) -> list[dict]:
    resultado = []
    for p in session.scalars(select(ProductoReventa).order_by(ProductoReventa.id)):
        resultado.append(_a_dict(p, _categoria_nombre(session, p.categoria_id), _compras(session, p.id)))
    return resultado


def detalle(session: Session, codigo: str) -> dict:
    p = _por_codigo(session, codigo)
    compras = _compras(session, p.id)
    return {**_a_dict(p, _categoria_nombre(session, p.categoria_id), compras), "historial": [_compra_a_dict(c) for c in compras]}


def crear(
    session: Session, *, nombre: str, categoria: str | None, proveedor: str | None, nota: str | None,
) -> dict:
    nombre = nombre.strip()
    if not nombre:
        raise DatosInvalidos("Falta el nombre del producto.")
    categoria_id = None
    if categoria:
        categoria_id = session.scalar(select(Categoria.id).where(Categoria.nombre == categoria))
        if categoria_id is None:
            raise DatosInvalidos(f"No existe la categoría {categoria}.")
    fila = ProductoReventa(
        codigo=f"MER-{_siguiente_numero(session, ProductoReventa.codigo, 'MER'):04d}", nombre=nombre,
        categoria_id=categoria_id, proveedor=_texto_o_nada(proveedor), nota=_texto_o_nada(nota),
    )
    _insertar(session, fila, "Ya hay un producto de mercadería con ese nombre, o no se pudo asignar el código; intentá de nuevo.")
    session.commit()
    return detalle(session, fila.codigo)


def cambiar_activo(session: Session, codigo: str, activo: bool) -> dict:
    """Archiving hides nothing from the history and deletes nothing."""
    _por_codigo(session, codigo).activo = activo
    session.commit()
    return detalle(session, codigo)


def registrar_compra(
    session: Session, codigo: str, *, unidades: Decimal, costo_unitario_ars: Decimal,
    precio_venta_unitario_ars: Decimal | None = None, fecha: date | None = None, proveedor: str | None = None,
    nota: str | None = None, quien: str | None = None,
) -> dict:
    """Append one purchase. Never updates or deletes: a new cost is a new purchase."""
    if unidades is None or unidades <= 0:
        raise DatosInvalidos("Las unidades tienen que ser mayores que cero.")
    if costo_unitario_ars is None or costo_unitario_ars <= 0:
        raise DatosInvalidos("El costo por unidad tiene que ser mayor que cero.")
    if precio_venta_unitario_ars is not None and precio_venta_unitario_ars <= 0:
        raise DatosInvalidos("El precio de venta tiene que ser mayor que cero.")
    p = _por_codigo(session, codigo)
    fila = CompraReventa(
        producto_reventa_id=p.id, fecha=fecha or date.today(), unidades=unidades, costo_unitario_ars=costo_unitario_ars,
        precio_venta_unitario_ars=precio_venta_unitario_ars, proveedor=_texto_o_nada(proveedor) or p.proveedor,
        nota=_texto_o_nada(nota), creado_por=quien,
    )
    _insertar(session, fila, "No se pudo registrar la compra.")
    session.commit()
    return detalle(session, codigo)
