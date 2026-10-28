"""Voice module (T7): from what the model EXTRACTED to a PROPOSAL a person can confirm. Nothing here writes.

`proponer` receives the closed `Interpretacion` (an action and raw mentions) and RESOLVES it with deterministic code:
mentions against the catalog (normalizing accents and case, matching whole words; no trigram, no model), numbers written
the Argentine way, dates against today's date. The result is a `PropuestaOut`: the resolved fields, the candidates when a
mention is ambiguous (up to five, with code and name), what is missing, warnings, the endpoint to call and the body for
it. The body is built with the SAME Pydantic models the write endpoints use (`api.PrecioIn`, `DolarIn`, ...), so it is
exactly what they accept, and it is `None` while anything is missing or ambiguous: nothing is ever guessed.

The model never computes money, never picks a code and never decides; every rule that protects the data (non-quotable
materials, append-only prices, 409 / 422) stays in the existing write endpoints, which the front calls with the person's
own session after an explicit "Confirmar".

SUPUESTO: validar. Everything marked so below is a convention of this module, not a rule confirmed by Gerardo.
"""

import re
import threading
import time
import unicodedata
from collections import deque
from collections.abc import Callable
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from backend import servicios
from backend.voz_llm import ACCIONES, Interpretacion

NOTA_DE_ORIGEN = "Carga por voz (confirmada por una persona)"
MAX_CANDIDATOS = 5
LIMITE_POR_MINUTO = 20  # SUPUESTO: validar. Per user and per process; the real quota depends on the model plan.
VENTANA_DEL_LIMITE = 60.0

# Words that carry no meaning when matching a mention against names ("el cuero de la tienda").
PALABRAS_VACIAS = frozenset({"de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "y", "e", "o", "en",
                             "al", "con", "por", "para", "que", "lo", "mi", "su"})
# What may stand next to a number without making it ambiguous ("USD 26", "$ 14.000", "26 dólares por m2").
RESIDUO_DE_NUMERO = frozenset({"usd", "u", "s", "us", "uss", "ars", "peso", "pesos", "dolar", "dolares", "m2", "x", "por",
                               "el", "la", "metro", "metros", "cuadrado", "cuadrados", "unidad", "unidades"})
_NUMERO = re.compile(r"(?<![0-9.,])[0-9][0-9.,]*")
_MILES = re.compile(r"[0-9]{1,3}(\.[0-9]{3})+")
_LOTE_DICHO = re.compile(r"(?:^| )lot(?:e)? ?0*([0-9]+)(?: |$)")


# --- Response models ---------------------------------------------------------------------------------------------

class CandidatoOut(BaseModel):
    """One option offered to the person. `codigo` is the value to send (for a color it is the color's name)."""

    codigo: str
    nombre: str


class CampoOut(BaseModel):
    valor: str
    texto: str | None = None


class PropuestaOut(BaseModel):
    accion: Literal[*ACCIONES]
    resumen: str
    campos_resueltos: dict[str, CampoOut]
    candidatos: dict[str, list[CandidatoOut]]
    faltantes: list[str]
    avisos: list[str]
    endpoint_destino: str | None
    payload_propuesto: dict | None


# --- Where the catalog comes from ----------------------------------------------------------------------------------

class FuenteVoz(Protocol):
    """Read-only view of the data the resolver needs. Same dict shapes as `servicios`. No write method on purpose."""

    def materiales(self) -> list[dict]: ...  # codigo, nombre, nombre_corto, etapa, unidad_de_consumo, cotizable
    def colores(self) -> list[dict]: ...  # codigo, nombre
    def productos(self) -> list[dict]: ...  # codigo, nombre
    def talleres(self) -> list[dict]: ...  # codigo, nombre
    def lotes(self) -> list[dict]: ...  # newest first: codigo, taller, taller_nombre, estado, fecha, items[{codigo, producto, producto_nombre}]
    def gastos(self, periodo: str | None) -> tuple[str | None, list[dict]]: ...  # (period used, [codigo, concepto, monto_ars_del_mes])
    def ultimo_dolar(self) -> Decimal | None: ...
    def chequeo_de_precio(self, material: str, color: str | None, precio: Decimal, moneda: str, fecha: date) -> dict | None: ...


class FuenteSQL:
    """`FuenteVoz` over the services (the same loaders the screens use). Reads only."""

    def __init__(self, session: Session):
        self._session = session

    def materiales(self):
        return servicios.listar_materiales(self._session)

    def colores(self):
        return servicios.listar_colores(self._session)

    def productos(self):
        return servicios.productos_para_voz(self._session)

    def talleres(self):
        return servicios.listar_talleres(self._session)

    def lotes(self):
        return servicios.lotes_para_voz(self._session)

    def gastos(self, periodo):
        try:
            costos = servicios.costos_fijos(self._session, periodo)
        except servicios.DatosInvalidos:  # no current period configured
            return None, []
        return costos["periodo"], [
            {"codigo": g["codigo"], "concepto": g["concepto"], "monto_ars_del_mes": g["monto_ars_del_mes"]}
            for g in costos["gastos"]]

    def ultimo_dolar(self):
        filas = servicios.listar_dolar(self._session)  # newest first
        return filas[0]["ars_por_usd"] if filas else None

    def chequeo_de_precio(self, material, color, precio, moneda, fecha):
        try:
            return servicios.chequear_precio(self._session, material, color, precio, moneda, fecha)
        except servicios.DatosInvalidos:
            return None  # the write endpoint will say what is wrong


# --- Rate limit ---------------------------------------------------------------------------------------------------

class LimitadorPorUsuario:
    """Sliding window per user, in memory (lost on restart; each replica counts on its own). SUPUESTO: validar."""

    def __init__(self, maximo: int = LIMITE_POR_MINUTO, ventana: float = VENTANA_DEL_LIMITE,
                 reloj: Callable[[], float] = time.monotonic):
        self.maximo = maximo
        self.ventana = ventana
        self._reloj = reloj
        self._registros: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def permitir(self, usuario: str) -> bool:
        ahora = self._reloj()
        limite = ahora - self.ventana
        with self._lock:
            for clave in [k for k, marcas in self._registros.items() if not marcas or marcas[-1] <= limite]:
                del self._registros[clave]
            marcas = self._registros.setdefault(usuario, deque())
            while marcas and marcas[0] <= limite:
                marcas.popleft()
            if len(marcas) >= self.maximo:
                return False
            marcas.append(ahora)
            return True


# --- Text helpers --------------------------------------------------------------------------------------------------

def normalizar(texto: str) -> str:
    """Lower case, no accents, letters and digits only, single spaces: `Marrón-Claro` -> `marron claro`."""
    sin_tildes = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", sin_tildes.lower()).strip()


def _raiz(palabra: str) -> str:
    return palabra[:-1] if len(palabra) > 3 and palabra.endswith("s") else palabra


def _palabras(texto: str) -> list[str]:
    return [_raiz(p) for p in normalizar(texto).split() if p not in PALABRAS_VACIAS]


def parse_numero(texto: str | None) -> tuple[Decimal | None, str | None]:
    """Reads ONE plain number written the Argentine way; (None, None) when it is not exactly that.

    `26`, `26,5`, `26.5`, `1.480`, `1.480,50`, `$ 14.000`, `USD 26`. Words ("mil", "un millón"), signs, two numbers or any
    other text beside the number are refused: nothing is multiplied or interpreted. SUPUESTO: validar. A dot followed by
    exactly three digits (`1.480`) is read as a thousands separator, as Argentines write it; the second item of the pair
    is a warning that says so, because `1.480` could also be 1.48.
    """
    if not texto:
        return None, None
    limpio = texto.strip()
    if "-" in limpio:
        return None, None
    corridas = list(_NUMERO.finditer(limpio))
    if len(corridas) != 1:
        return None, None
    corrida = corridas[0]
    residuo = limpio[:corrida.start()] + " " + limpio[corrida.end():]
    if "." in residuo or "," in residuo or not set(normalizar(residuo).split()) <= RESIDUO_DE_NUMERO:
        return None, None
    numero = corrida.group().rstrip(".,")
    if re.search(r"[.,]{2}", numero):
        return None, None
    aviso = None
    if "." in numero and "," in numero:
        entero, _, decimales = numero.rpartition(",")
        if numero.rfind(",") < numero.rfind(".") or not _MILES.fullmatch(entero) or not decimales.isdigit():
            return None, None
        valor = entero.replace(".", "") + "." + decimales
    elif "," in numero:
        if numero.count(",") > 1:
            return None, None
        valor = numero.replace(",", ".")
    elif "." in numero:
        if _MILES.fullmatch(numero):
            valor = numero.replace(".", "")
            aviso = f"Leí «{numero}» como {valor} (el punto separa miles). Si era un decimal, corregilo."
        elif numero.count(".") == 1:
            valor = numero
        else:
            return None, None
    else:
        valor = numero
    try:
        return Decimal(valor), aviso
    except InvalidOperation:
        return None, None


def _fecha_dicha(texto: str, fecha: date) -> bool:
    """Whether the sentence itself writes this date (2026-12-01, 01/12/2026, 1-12-2026): a future date must be explicit."""
    iso = fecha.isoformat()
    if re.search(rf"(?<![0-9]){re.escape(iso)}(?![0-9])", texto):
        return True
    return bool(re.search(rf"(?<![0-9])0*{fecha.day}[/.\-]0*{fecha.month}[/.\-]{fecha.year}(?![0-9])", texto))


# --- Resolver ---------------------------------------------------------------------------------------------------------

def _coincidencias(mencion: str, items: list[dict], codigo: str, nombres: tuple[str, ...], extras: tuple[str, ...] = ()) -> list[dict]:
    """The items a mention can mean, best first: a code written in it, else the whole mention equal to a name, else every
    word of the mention found in the item (a word may be a prefix: `carpin` finds `carpincho`)."""
    normalizada = normalizar(mencion)
    if not normalizada:
        return []
    por_codigo = [i for i in items if f" {normalizar(i[codigo])} " in f" {normalizada} "]
    if por_codigo:
        return por_codigo
    iguales = [i for i in items if normalizada in {normalizar(i[n]) for n in (codigo, *nombres) if i.get(n)}]
    if iguales:
        return iguales
    palabras = _palabras(mencion)
    if not palabras:
        return []
    puntuados = []
    for orden, item in enumerate(items):
        del_item = [_raiz(p) for n in (codigo, *nombres, *extras) if item.get(n) for p in normalizar(item[n]).split()]
        puntaje = 0
        for palabra in palabras:
            if palabra in del_item:
                puntaje += 2
            elif len(palabra) >= 3 and any(p.startswith(palabra) for p in del_item):
                puntaje += 1
            else:
                break
        else:
            puntuados.append((-puntaje, len(del_item), orden, item))
    return [item for *_, item in sorted(puntuados, key=lambda p: p[:3])]


class _Borrador:
    """What a proposal accumulates while its fields are resolved."""

    def __init__(self, texto: str, hoy: date, fuente: FuenteVoz):
        self.texto, self.hoy, self.fuente = texto, hoy, fuente
        self.campos: dict[str, CampoOut] = {}
        self.candidatos: dict[str, list[CandidatoOut]] = {}
        self.faltantes: list[str] = []
        self.avisos: list[str] = []

    def falta(self, campo: str, aviso: str | None = None) -> None:
        if campo not in self.faltantes:
            self.faltantes.append(campo)
        if aviso and aviso not in self.avisos:
            self.avisos.append(aviso)

    def aviso(self, aviso: str) -> None:
        if aviso not in self.avisos:
            self.avisos.append(aviso)

    def resuelto(self, campo: str, valor: str, texto: str | None = None) -> None:
        self.campos[campo] = CampoOut(valor=valor, texto=texto or valor)

    def ofrecer(self, campo: str, candidatos: list[tuple[str, str]], aviso: str) -> None:
        self.candidatos[campo] = [CandidatoOut(codigo=c, nombre=n) for c, n in candidatos[:MAX_CANDIDATOS]]
        self.falta(campo, aviso)

    # -- one mention against a catalog ------------------------------------------------------------------------------

    def elegir(self, campo: str, mencion: str | None, items: list[dict], *, codigo: str, nombres: tuple[str, ...],
               nombre_de: Callable[[dict], str], extras: tuple[str, ...] = (), que: str = "",
               ofrecible: Callable[[dict], bool] | None = None) -> dict | None:
        """The one item a mention means, or None after recording why (missing / unknown / ambiguous with candidates)."""
        if not mencion:
            self.falta(campo)
            return None
        encontrados = _coincidencias(mencion, items, codigo, nombres, extras)
        if not encontrados:
            self.falta(campo, f"No encontré {que or campo} «{mencion}».")
            return None
        if len(encontrados) > 1:
            opciones = [i for i in encontrados if ofrecible is None or ofrecible(i)]
            if not opciones:
                self.falta(campo, f"Lo que coincide con «{mencion}» no se puede usar: está bloqueado.")
                return None
            self.ofrecer(campo, [(i[codigo], nombre_de(i)) for i in opciones],
                         f"«{mencion}» puede ser más de uno ({len(encontrados)}): elegí cuál.")
            return None
        return encontrados[0]

    def material(self, mencion: str | None) -> dict | None:
        elegido = self.elegir("material", mencion, self.fuente.materiales(), codigo="codigo", nombres=("nombre", "nombre_corto"),
                              nombre_de=_nombre_de_material, extras=("etapa",), que="el material",
                              ofrecible=lambda m: m["cotizable"])  # a blocked material is never offered as a choice
        if elegido is None:
            return None
        if not elegido["cotizable"]:
            self.falta("material", f"El material {elegido['codigo']} no es cotizable: está bloqueado hasta definir su unidad.")
            return None
        self.resuelto("material", elegido["codigo"], _nombre_de_material(elegido))
        return elegido

    def color(self, mencion: str | None) -> str | None:
        """Optional: no mention is fine, a mention that does not resolve is asked about."""
        if not mencion:
            return None
        colores = self.fuente.colores()
        elegido = self.elegir("color", mencion, colores, codigo="nombre", nombres=(), nombre_de=lambda c: c["nombre"], que="el color")
        if elegido is None:
            return None
        self.resuelto("color", elegido["nombre"])
        return elegido["nombre"]

    def numero(self, campo: str, texto: str | None, modelo: type[BaseModel], campo_del_modelo: str) -> Decimal | None:
        valor, aviso = parse_numero(texto)
        if valor is None:
            self.falta(campo, f"No pude leer «{texto}» como un número." if texto else None)
            return None
        informacion = modelo.model_fields[campo_del_modelo]
        try:  # the very constraints of the write endpoint's field (sign, digits, decimals)
            tipo = Annotated[informacion.annotation, *informacion.metadata] if informacion.metadata else informacion.annotation
            TypeAdapter(tipo).validate_python(valor)
        except ValidationError:
            self.falta(campo, f"El valor «{texto}» no es válido para este dato (negativo, cero o con demasiados dígitos).")
            return None
        if aviso:
            self.aviso(aviso)
        self.resuelto(campo, format(valor, "f"))
        return valor

    def fecha(self, campo: str, fecha: date | None) -> date | None:
        """Past or today: fine. Missing: today, said out loud. Future: refused unless the sentence writes that date."""
        if fecha is None:
            self.aviso(f"No dijiste la fecha: propongo hoy ({self.hoy.isoformat()}).")
            return self.hoy
        if fecha > self.hoy:
            if not _fecha_dicha(self.texto, fecha):
                self.falta(campo, f"La fecha {fecha.isoformat()} es futura: decila completa si es a propósito, o corregila.")
                return None
            self.aviso(f"La fecha {fecha.isoformat()} es futura: confirmá que es correcta.")
        self.resuelto(campo, fecha.isoformat())
        return fecha


def _nombre_de_material(material: dict) -> str:
    return f"{material.get('nombre_corto') or material['nombre']} ({material['codigo']})"


def _propuesta(accion: str, borrador: _Borrador, resumen: str, endpoint: str | None = None, payload: dict | None = None) -> PropuestaOut:
    completa = not borrador.faltantes and endpoint is not None and payload is not None
    return PropuestaOut(
        accion=accion, resumen=resumen, campos_resueltos=borrador.campos, candidatos=borrador.candidatos,
        faltantes=borrador.faltantes, avisos=borrador.avisos,
        endpoint_destino=endpoint if completa else None, payload_propuesto=payload if completa else None)


def _texto_de(borrador: _Borrador, campo: str) -> str:
    resuelto = borrador.campos.get(campo)
    return (resuelto.texto or resuelto.valor) if resuelto else "…"


def _armar(modelo: type[BaseModel], borrador: _Borrador, datos: dict, *, sin_nulos: bool = False) -> dict | None:
    """The body, built by the endpoint's own model. A failure here is reported, never hidden."""
    try:
        return modelo(**datos).model_dump(mode="json", exclude_none=sin_nulos)
    except ValidationError as error:
        for detalle in error.errors():
            borrador.falta(str(detalle["loc"][0]) if detalle["loc"] else "datos", "Los datos no son válidos para cargarlos.")
        return None


# --- Actions -----------------------------------------------------------------------------------------------------------

def _cargar_precio(i: Interpretacion, b: _Borrador) -> PropuestaOut:
    from backend.api import PrecioIn

    material = b.material(i.material)
    if material:
        b.resuelto("unidad_del_precio", material["unidad_de_consumo"])  # SUPUESTO: validar. Price per consumption unit.
    color = b.color(i.color)
    precio = b.numero("precio", i.numero, PrecioIn, "precio")
    if i.moneda is None:
        b.falta("moneda")
    else:
        b.resuelto("moneda", i.moneda)
    fecha = b.fecha("vigente_desde", i.fecha)
    payload = None
    if not b.faltantes and material and precio is not None and fecha:
        unidad = material["unidad_de_consumo"]
        chequeo = b.fuente.chequeo_de_precio(material["codigo"], color, precio, i.moneda, fecha)
        if chequeo and chequeo.get("salto_grande"):
            b.aviso(f"El precio varía {chequeo['variacion_pct']} % respecto del anterior ({chequeo['anterior']}). "
                    "Si es un error de tipeo, corregilo antes de confirmar.")
        payload = _armar(PrecioIn, b, {
            "material": material["codigo"], "color": color, "proveedor": None, "precio": precio, "moneda": i.moneda,
            "unidad_del_precio": unidad, "iva_incluido": False, "vigente_desde": fecha, "nota_fuente": NOTA_DE_ORIGEN})
    resumen = (f"Entendí esto: cargar el precio de {_texto_de(b, 'material')}"
               f"{' en color ' + color if color else ''}: {i.moneda or '…'} {format(precio, 'f') if precio is not None else '…'}"
               f" por {b.campos['unidad_del_precio'].valor if 'unidad_del_precio' in b.campos else 'unidad'},"
               f" desde el {fecha.isoformat() if fecha else '…'}.")
    return _propuesta("cargar_precio", b, resumen, "/precios", payload)


def _cargar_dolar(i: Interpretacion, b: _Borrador) -> PropuestaOut:
    from backend.api import DolarIn

    valor = b.numero("ars_por_usd", i.numero, DolarIn, "ars_por_usd")
    if i.tipo_dolar is None:
        b.falta("tipo")
    else:
        b.resuelto("tipo", i.tipo_dolar)
    fecha = b.fecha("fecha", i.fecha)
    payload = None
    if not b.faltantes and valor is not None and fecha:
        anterior = b.fuente.ultimo_dolar()
        variacion, salto = servicios.variacion_de_precio(anterior, valor)
        if salto:
            b.aviso(f"El dólar varía {variacion} % respecto del último cargado ({format(anterior, 'f')}). "
                    "Si es un error de tipeo, corregilo antes de confirmar.")
        payload = _armar(DolarIn, b, {"fecha": fecha, "ars_por_usd": valor, "fuente": "MANUAL", "tipo": i.tipo_dolar,
                                      "nota": NOTA_DE_ORIGEN})
    resumen = (f"Entendí esto: cargar el dólar {(i.tipo_dolar or '…').lower()} a ARS "
               f"{format(valor, 'f') if valor is not None else '…'} con fecha {fecha.isoformat() if fecha else '…'}.")
    return _propuesta("cargar_dolar", b, resumen, "/dolar", payload)


def _agregar_extra(i: Interpretacion, b: _Borrador) -> PropuestaOut:
    from backend.api import ExtraIn

    producto = b.elegir("producto", i.producto, b.fuente.productos(), codigo="codigo", nombres=("nombre",),
                        nombre_de=lambda p: p["nombre"], que="el producto")
    if producto:
        b.resuelto("producto", producto["codigo"], f"{producto['nombre']} ({producto['codigo']})")
    material = b.material(i.material)
    color = b.color(i.color)
    consumo = b.numero("consumo_neto_por_unidad", i.numero, ExtraIn, "consumo_neto_por_unidad")
    endpoint = payload = None
    if not b.faltantes and producto and material and consumo is not None:
        endpoint = f"/productos/{producto['codigo']}/extras"
        payload = _armar(ExtraIn, b, {"material": material["codigo"], "color": color,
                                      "consumo_neto_por_unidad": consumo, "nota": NOTA_DE_ORIGEN})
    resumen = (f"Entendí esto: agregar a {_texto_de(b, 'producto')} una línea extra de {_texto_de(b, 'material')}"
               f"{' en color ' + color if color else ''}, consumo {format(consumo, 'f') if consumo is not None else '…'}.")
    return _propuesta("agregar_extra", b, resumen, endpoint, payload)


def _lote_dicho(mencion: str, lotes: list[dict]) -> dict | None:
    """`LOT-0003`, `lote 3`, `lot 0003`: a lot is named by its code or its number."""
    normalizada = normalizar(mencion)
    for lote in lotes:
        if f" {normalizar(lote['codigo'])} " in f" {normalizada} ":
            return lote
    dicho = _LOTE_DICHO.search(normalizada)
    if dicho:
        buscado = f"LOT-{int(dicho.group(1)):04d}"
        return next((lote for lote in lotes if lote["codigo"] == buscado), None)
    return None


def _registrar_precio_taller(i: Interpretacion, b: _Borrador) -> PropuestaOut:
    from backend.api import PreciosItemIn

    lotes = b.fuente.lotes()
    productos = b.fuente.productos() if i.producto else []
    codigos_de_producto: set[str] | None = None
    if i.producto:
        coincidentes = _coincidencias(i.producto, productos, "codigo", ("nombre",))
        codigos_de_producto = {p["codigo"] for p in coincidentes}
        if not coincidentes:
            b.falta("producto", f"No encontré el producto «{i.producto}».")

    lote = None
    if i.lote:
        lote = _lote_dicho(i.lote, lotes)
        if lote is None:
            b.falta("lote", f"No encontré el lote «{i.lote}».")
    elif i.taller or i.producto:
        pool = lotes
        if i.taller:
            talleres = _coincidencias(i.taller, b.fuente.talleres(), "codigo", ("nombre",))
            if not talleres:
                b.falta("taller", f"No encontré el taller «{i.taller}».")
            codigos_de_taller = {t["codigo"] for t in talleres}
            pool = [lt for lt in pool if lt["taller"] in codigos_de_taller]
        if codigos_de_producto is not None:
            pool = [lt for lt in pool if any(it["producto"] in codigos_de_producto for it in lt["items"])]
        if "taller" in b.faltantes or "producto" in b.faltantes:
            pool = []
        if len(pool) == 1:
            lote = pool[0]
        elif len(pool) > 1:
            b.ofrecer("lote", [(lt["codigo"], _nombre_de_lote(lt)) for lt in pool],
                      f"Hay {len(pool)} lotes posibles: elegí cuál (muestro los más recientes).")
        else:
            b.falta("lote", None if b.faltantes else "No encontré un lote con esos datos.")
    else:
        b.falta("lote")

    item = None
    if lote:
        b.resuelto("lote", lote["codigo"], _nombre_de_lote(lote))
        items = lote["items"]
        if codigos_de_producto is not None:
            items = [it for it in items if it["producto"] in codigos_de_producto]
            if not items:
                b.falta("item", f"El lote {lote['codigo']} no tiene ese producto.")
        if "producto" in b.faltantes:
            items = []  # the product was not understood: do not pick a line for it
        if len(items) == 1:
            item = items[0]
            b.resuelto("item", item["codigo"], f"{item['producto_nombre']} ({item['producto']})")
        elif len(items) > 1:
            b.ofrecer("item", [(it["codigo"], f"{it['producto_nombre']} ({it['producto']})") for it in items],
                      f"El lote {lote['codigo']} tiene {len(items)} productos: elegí cuál.")
        elif "item" not in b.faltantes:
            b.falta("item", None if "producto" in b.faltantes else f"El lote {lote['codigo']} no tiene productos.")

    precio = b.numero("precio", i.numero, PreciosItemIn, "cotizado")
    if i.cotizado_o_pagado is None:
        b.falta("precio_de")
    else:
        b.resuelto("precio_de", i.cotizado_o_pagado)
    endpoint = payload = None
    if not b.faltantes and lote and item and precio is not None and i.cotizado_o_pagado:
        endpoint = f"/ordenes/{lote['codigo']}/items/{item['codigo']}/precios"
        payload = _armar(PreciosItemIn, b, {i.cotizado_o_pagado: precio}, sin_nulos=True)
    resumen = (f"Entendí esto: registrar el precio {i.cotizado_o_pagado or '…'} por unidad de ARS "
               f"{format(precio, 'f') if precio is not None else '…'} en {_texto_de(b, 'lote')}, renglón {_texto_de(b, 'item')}.")
    return _propuesta("registrar_precio_taller", b, resumen, endpoint, payload)


def _nombre_de_lote(lote: dict) -> str:
    partes = [lote["codigo"], lote.get("taller_nombre") or "en casa", lote["estado"]]
    if lote.get("fecha"):
        partes.append(lote["fecha"].isoformat())
    return " · ".join(partes)


def _cargar_monto_gasto(i: Interpretacion, b: _Borrador) -> PropuestaOut:
    from backend.api import MontoIn

    periodo, gastos = b.fuente.gastos(i.periodo)
    if periodo is None:
        b.falta("periodo", "No hay un período vigente configurado: decí el mes (AAAA-MM).")
    else:
        b.resuelto("periodo", periodo)
        if i.periodo is None:
            b.aviso(f"No dijiste el período: uso el vigente ({periodo}).")

    gasto = None
    if periodo is not None and not gastos:
        b.falta("gasto", f"No hay gastos cargados en el período {periodo}.")
    elif periodo is not None:
        if not i.concepto:
            b.falta("gasto")
        else:
            encontrados = _coincidencias(i.concepto, gastos, "codigo", ("concepto",))
            pendientes = [g for g in encontrados if g["monto_ars_del_mes"] is None]
            if not encontrados:
                b.falta("gasto", f"No encontré el gasto «{i.concepto}» en {periodo}.")
            elif not pendientes:
                b.falta("gasto", "El gasto " + ", ".join(g["codigo"] for g in encontrados[:MAX_CANDIDATOS])
                        + " ya tiene monto: para corregirlo cargá un gasto nuevo desde Costos fijos.")
            elif len(encontrados) > 1:
                b.ofrecer("gasto", [(g["codigo"], g["concepto"]) for g in pendientes],
                          f"«{i.concepto}» puede ser más de un gasto sin monto: elegí cuál.")
            else:
                gasto = pendientes[0]
                b.resuelto("gasto", gasto["codigo"], f"{gasto['concepto']} ({gasto['codigo']})")

    monto = None
    if i.moneda == "USD":
        b.falta("monto_ars_del_mes", "Los costos fijos se cargan en pesos: no convierto dólares.")
    else:
        monto = b.numero("monto_ars_del_mes", i.numero, MontoIn, "monto_ars_del_mes")
    endpoint = payload = None
    if not b.faltantes and gasto and monto is not None:
        endpoint = f"/costos-fijos/{gasto['codigo']}/monto"
        payload = _armar(MontoIn, b, {"monto_ars_del_mes": monto})
    resumen = (f"Entendí esto: cargar ARS {format(monto, 'f') if monto is not None else '…'} como monto de "
               f"{_texto_de(b, 'gasto')} ({periodo or '…'}).")
    return _propuesta("cargar_monto_gasto", b, resumen, endpoint, payload)


def _desconocida(i: Interpretacion, b: _Borrador) -> PropuestaOut:
    razon = i.razon or "No entendí el pedido."
    b.aviso(razon)
    return _propuesta("desconocida", b, f"No entendí el pedido: {razon}")


_ACCIONES = {
    "cargar_precio": _cargar_precio, "cargar_dolar": _cargar_dolar, "agregar_extra": _agregar_extra,
    "registrar_precio_taller": _registrar_precio_taller, "cargar_monto_gasto": _cargar_monto_gasto,
    "desconocida": _desconocida,
}


def proponer(interpretacion: Interpretacion, texto: str, hoy: date, fuente: FuenteVoz) -> PropuestaOut:
    """The proposal for one interpreted sentence. `texto` is only used to check that a future date was written out."""
    return _ACCIONES[interpretacion.accion](interpretacion, _Borrador(texto, hoy, fuente))
