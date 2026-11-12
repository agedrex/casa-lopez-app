"""Resale products: things Casa López buys ready-made and resells. No materials, stages or quotes.

The cost of a product is the unit cost of its latest purchase (latest `fecha`, then latest id); a new price is a new
purchase, nothing is edited or deleted. The cost of a purchase is `unidades × costo_unitario_ars`; a row without `unidades` is a price update typed in the
grid (no units arrived) and has no total. The sale price is the
one typed in the latest purchase that has one; the margin is computed here, never by the front.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import Categoria, CompraReventa, ProductoReventa
from backend.servicios import (
    MAX_FILAS_POR_LOTE, Conflicto, DatosInvalidos, NoEncontrado, _insertar, _siguiente_numero, _texto_o_nada,
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
        "costo_total_ars": None if c.unidades is None else c.unidades * c.costo_unitario_ars, "precio_venta_unitario_ars": c.precio_venta_unitario_ars,
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
        "compras": len([c for c in compras if c.unidades is not None]), "unidades_compradas": sum((c.unidades for c in compras if c.unidades is not None), Decimal(0)),
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


def _categoria_id(session: Session, categoria: str | None) -> int | None:
    if not categoria:
        return None
    categoria_id = session.scalar(select(Categoria.id).where(Categoria.nombre == categoria))
    if categoria_id is None:
        raise DatosInvalidos(f"No existe la categoría {categoria}.")
    return categoria_id


def _nuevo_producto(
    session: Session, *, nombre: str, categoria: str | None, proveedor: str | None, nota: str | None,
) -> ProductoReventa:
    """Insert the product row (flushed, not committed)."""
    nombre = nombre.strip()
    if not nombre:
        raise DatosInvalidos("Falta el nombre del producto.")
    fila = ProductoReventa(
        codigo=f"MER-{_siguiente_numero(session, ProductoReventa.codigo, 'MER'):04d}", nombre=nombre,
        categoria_id=_categoria_id(session, categoria), proveedor=_texto_o_nada(proveedor), nota=_texto_o_nada(nota),
    )
    _insertar(session, fila, "Ya hay un producto de mercadería con ese nombre, o no se pudo asignar el código; intentá de nuevo.")
    return fila


def crear(
    session: Session, *, nombre: str, categoria: str | None, proveedor: str | None, nota: str | None,
) -> dict:
    fila = _nuevo_producto(session, nombre=nombre, categoria=categoria, proveedor=proveedor, nota=nota)
    session.commit()
    return detalle(session, fila.codigo)


def cambiar_activo(session: Session, codigo: str, activo: bool) -> dict:
    """Archiving hides nothing from the history and deletes nothing."""
    _por_codigo(session, codigo).activo = activo
    session.commit()
    return detalle(session, codigo)


def _nueva_compra(
    session: Session, p: ProductoReventa, *, unidades: Decimal | None, costo_unitario_ars: Decimal,
    precio_venta_unitario_ars: Decimal | None, fecha: date | None, proveedor: str | None, nota: str | None,
    quien: str | None,
) -> None:
    """Insert one row (flushed, not committed). Without `unidades` it is a price update, not a purchase."""
    if unidades is not None and unidades <= 0:
        raise DatosInvalidos("Las unidades tienen que ser mayores que cero.")
    if costo_unitario_ars is None or costo_unitario_ars <= 0:
        raise DatosInvalidos("El costo por unidad tiene que ser mayor que cero.")
    if precio_venta_unitario_ars is not None and precio_venta_unitario_ars <= 0:
        raise DatosInvalidos("El precio de venta tiene que ser mayor que cero.")
    fila = CompraReventa(
        producto_reventa_id=p.id, fecha=fecha or date.today(), unidades=unidades, costo_unitario_ars=costo_unitario_ars,
        precio_venta_unitario_ars=precio_venta_unitario_ars, proveedor=_texto_o_nada(proveedor) or p.proveedor,
        nota=_texto_o_nada(nota), creado_por=quien,
    )
    _insertar(session, fila, "No se pudo registrar la compra.")


def registrar_compra(
    session: Session, codigo: str, *, unidades: Decimal | None = None, costo_unitario_ars: Decimal,
    precio_venta_unitario_ars: Decimal | None = None, fecha: date | None = None, proveedor: str | None = None,
    nota: str | None = None, quien: str | None = None,
) -> dict:
    """Append one row. Never updates or deletes: a new cost is a new row. Without units it is a price update."""
    if unidades is not None and unidades <= 0:
        raise DatosInvalidos("Las unidades tienen que ser mayores que cero.")
    if costo_unitario_ars is None or costo_unitario_ars <= 0:
        raise DatosInvalidos("El costo por unidad tiene que ser mayor que cero.")
    if precio_venta_unitario_ars is not None and precio_venta_unitario_ars <= 0:
        raise DatosInvalidos("El precio de venta tiene que ser mayor que cero.")
    p = _por_codigo(session, codigo)
    _nueva_compra(
        session, p, unidades=unidades, costo_unitario_ars=costo_unitario_ars,
        precio_venta_unitario_ars=precio_venta_unitario_ars, fecha=fecha, proveedor=proveedor, nota=nota, quien=quien)
    session.commit()
    return detalle(session, codigo)


def _positivo(valor: Decimal | None, que: str, donde: str) -> None:
    if valor is not None and valor <= 0:
        raise DatosInvalidos(f"{donde}: {que} tiene que ser mayor que cero.")


def _aplicar_cambio(session: Session, cambio: dict, quien: str | None) -> None:
    """One grid row. Name, category and supplier are edited in place; a new cost or sale price is a NEW row
    without units that repeats the other value, so the history keeps every price the product had."""
    p = _por_codigo(session, cambio["codigo"])
    donde = p.codigo
    # Every lookup comes BEFORE the first assignment: a query after `p.nombre = ...` would autoflush the new name
    # outside `_guardar` and a repeated name would surface as a raw IntegrityError (500) instead of a Conflicto.
    nombre = None
    if "nombre" in cambio:
        nombre = (cambio["nombre"] or "").strip()
        if not nombre:
            raise DatosInvalidos(f"{donde}: falta el nombre.")
    categoria_id = _categoria_id(session, cambio["categoria"]) if "categoria" in cambio else p.categoria_id
    if nombre is not None:
        p.nombre = nombre
    p.categoria_id = categoria_id
    if "proveedor" in cambio:
        p.proveedor = _texto_o_nada(cambio["proveedor"])
    if "nota" in cambio:
        p.nota = _texto_o_nada(cambio["nota"])
    if nombre is not None:
        _guardar(session, "Ya hay un producto de mercadería con ese nombre.")
    costo, precio = cambio.get("costo"), cambio.get("precio_venta")
    _positivo(costo, "el costo", donde)
    _positivo(precio, "el precio de venta", donde)
    if costo is None and precio is None:
        return
    compras = _compras(session, p.id)
    actual = _a_dict(p, None, compras)
    costo_final = costo if costo is not None else actual["costo_unitario_ars"]
    precio_final = precio if precio is not None else actual["precio_venta_unitario_ars"]
    if costo_final is None:
        raise DatosInvalidos(f"{donde}: cargá primero el costo de compra.")
    if costo_final == actual["costo_unitario_ars"] and precio_final == actual["precio_venta_unitario_ars"]:
        return
    # Not before the latest row: with a purchase dated in the future, today's row would never become "the latest".
    fecha = max(date.today(), compras[0].fecha) if compras else None
    _nueva_compra(
        session, p, unidades=None, costo_unitario_ars=costo_final, precio_venta_unitario_ars=precio_final, fecha=fecha,
        proveedor=None, nota=None, quien=quien)


def _guardar(session: Session, conflicto: str) -> None:
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError:
        raise Conflicto(conflicto) from None


def guardar_en_lote(session: Session, cambios: list[dict], nuevos: list[dict], *, quien: str | None = None) -> list[dict]:
    """Grid save, ONE transaction (all or nothing).

    `cambios`: {codigo, nombre?, categoria?, proveedor?, nota?, costo?, precio_venta?}. `nuevos`: {nombre, categoria?,
    proveedor?, nota?, costo?, precio_venta?, unidades?}; a new row with a cost also gets its first row of history
    (with `unidades` it is a real purchase). A sale price needs a cost.
    """
    if not cambios and not nuevos:
        raise DatosInvalidos("No hay cambios para guardar.")
    if len(cambios) + len(nuevos) > MAX_FILAS_POR_LOTE:
        raise DatosInvalidos(f"Son demasiadas filas de una vez (máximo {MAX_FILAS_POR_LOTE}).")
    codigos = [c["codigo"] for c in cambios]
    if len(set(codigos)) != len(codigos):
        raise DatosInvalidos("Hay un producto repetido en los cambios.")
    try:
        for cambio in cambios:
            _aplicar_cambio(session, cambio, quien)
        for index, nuevo in enumerate(nuevos, start=1):
            donde = f"Fila nueva {index}"
            costo, precio, unidades = nuevo.get("costo"), nuevo.get("precio_venta"), nuevo.get("unidades")
            _positivo(costo, "el costo", donde)
            _positivo(precio, "el precio de venta", donde)
            _positivo(unidades, "las unidades", donde)
            if costo is None and (precio is not None or unidades is not None):
                raise DatosInvalidos(f"{donde}: cargá el costo de compra.")
            fila = _nuevo_producto(
                session, nombre=nuevo.get("nombre") or "", categoria=nuevo.get("categoria"),
                proveedor=nuevo.get("proveedor"), nota=nuevo.get("nota"))
            if costo is not None:
                _nueva_compra(
                    session, fila, unidades=unidades, costo_unitario_ars=costo, precio_venta_unitario_ars=precio,
                    fecha=None, proveedor=None, nota=None, quien=quien)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return listar(session)
