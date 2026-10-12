#!/usr/bin/env python3
"""Hook de Claude Code que registra en la Fábrica el run de cada subagente que termina.

Satisface REQ-EJECUCION-004 de FRD-EJECUCION, componente "hook registrar_run" de
BP-EJECUCION-AGENTES-TOKENS-TIEMPO-WORK (WO-33).

Es un script de la biblioteca estándar de Python 3.11+, sin dependencias externas (no requiere
`pip install`): corre en la máquina de cualquiera del equipo, invocado por Claude Code vía el hook
`SubagentStop` (con `SessionEnd` como fallback), no por la app.

Cómo se instala: ver `skills/agedrex-factory/execution/registrar-runs.md`.

Contrato duro (AC-EJECUCION-004.3): este script NUNCA puede interrumpir ni hacer fallar la sesión
de Claude Code. Pase lo que pase —Fábrica caída, token vencido, transcript ilegible, JSON corrupto—
`main()` no propaga la excepción, no escribe nada en stdout y el proceso siempre termina con
`sys.exit(0)`. Cada desenlace deja una línea en `~/.claude/factory-runs.log` (override:
`FACTORY_RUNS_LOG`) para poder mirarlo después.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Detección del WO, en este orden estricto (ver detectar_wo): un `WO-\d+` suelto NO alcanza — las
# reglas de la casa que abren el prompt de todo ejecutor mencionan `WO-83` como ejemplo
# (Referencias legibles (`WO-83`, `FRD-X`, `F3`, `E1`)...), así que un patrón que tomara el primer
# `WO-\d+` del mensaje le atribuiría todo run a WO-83.
#
# 1) Marcador explícito `[wo: WO-N]` en cualquier parte del texto — el orquestador lo pone siempre
#    (documentado en skills/agedrex-factory/execution/registrar-runs.md).
WO_MARKER_PATTERN = re.compile(r"\[wo:\s*WO-(\d+)\]", re.IGNORECASE)
# 2) Si no hay marcador, la mención explícita de ejecución (sin esto, un WO citado de pasada en
#    las reglas de la casa no cuenta).
WO_MENTION_PATTERN = re.compile(r"(?:Ejecutá|ejecución de|ejecutor de)\s+(WO-\d+)", re.IGNORECASE)

# Claves de tokens que trae un `usage` de Claude Code. No siempre vienen las cuatro.
CAMPOS_USAGE = {
    "tokens_input": "input_tokens",
    "tokens_output": "output_tokens",
    "tokens_cache_read": "cache_read_input_tokens",
    "tokens_cache_creation": "cache_creation_input_tokens",
}


# --------------------------------------------------------------------------------------
# Funciones puras: reciben datos, devuelven datos. Nada de I/O acá (son las que se testean).
# --------------------------------------------------------------------------------------


def leer_transcript(path: Path) -> list[dict]:
    """Lee un `.jsonl` línea por línea. Una línea que no parsea se saltea sin abortar el resto."""
    eventos: list[dict] = []
    with path.open("r", encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea:
                continue
            try:
                evento = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if isinstance(evento, dict):
                eventos.append(evento)
    return eventos


def _texto_de_contenido(content: object) -> str:
    """`message.content` puede ser un string o una lista de bloques `{"type": "text", "text": …}`."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        partes = []
        for bloque in content:
            if isinstance(bloque, dict) and bloque.get("type") == "text":
                partes.append(str(bloque.get("text", "")))
        return "\n".join(partes)
    return ""


def detectar_wo(eventos: list[dict]) -> str | None:
    """El WO sale del PRIMER mensaje `user` del transcript, y solo de ese, en este orden:

    1. El marcador explícito `[wo: WO-N]` en cualquier parte del texto.
    2. Si no hay marcador, la mención `Ejecutá/ejecución de/ejecutor de WO-N`.
    3. Si tampoco, `None` — nunca se adivina con el primer `WO-\\d+` suelto que aparezca (las
       reglas de la casa del prompt del ejecutor mencionan `WO-83` como ejemplo, y eso daría un
       falso positivo real).
    """
    for evento in eventos:
        if evento.get("type") != "user":
            continue
        mensaje = evento.get("message") or {}
        texto = _texto_de_contenido(mensaje.get("content"))
        marcador = WO_MARKER_PATTERN.search(texto)
        if marcador:
            return f"WO-{marcador.group(1)}"
        mencion = WO_MENTION_PATTERN.search(texto)
        if mencion:
            return mencion.group(1).upper()
        return None
    return None


def rol_de(agent_type: str | None) -> str:
    """`wo-reviewer*` → reviewer; `wo-executor*` → executor; cualquier otra cosa → other."""
    if agent_type and agent_type.startswith("wo-reviewer"):
        return "reviewer"
    if agent_type and agent_type.startswith("wo-executor"):
        return "executor"
    return "other"


def _parsear_timestamp(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


def resumir_uso(eventos: list[dict]) -> dict:
    """Suma el uso de un transcript deduplicando por `message.id`.

    Una misma respuesta aparece repartida en varias líneas `assistant` con el mismo `message.id`
    y un `usage` que va creciendo hasta el valor final: hay que quedarse con la ÚLTIMA línea de
    cada id y sumar esas, nunca sumar todas las líneas (multiplica los números).
    """
    ultimo_por_id: dict[str, dict] = {}
    orden_ids: list[str] = []
    ultimo_modelo: str | None = None
    timestamps: list[str] = []

    for evento in eventos:
        timestamp = evento.get("timestamp")
        if timestamp:
            timestamps.append(timestamp)

        if evento.get("type") != "assistant":
            continue
        mensaje = evento.get("message") or {}
        message_id = mensaje.get("id")
        if message_id is None:
            continue

        if message_id not in ultimo_por_id:
            orden_ids.append(message_id)
        ultimo_por_id[message_id] = mensaje
        if mensaje.get("model"):
            ultimo_modelo = mensaje["model"]

    totales = dict.fromkeys(CAMPOS_USAGE, 0)
    for message_id in orden_ids:
        usage = ultimo_por_id[message_id].get("usage") or {}
        for campo_propio, campo_usage in CAMPOS_USAGE.items():
            totales[campo_propio] += usage.get(campo_usage, 0)

    if timestamps:
        inicio, fin = timestamps[0], timestamps[-1]
        duracion = (_parsear_timestamp(fin) - _parsear_timestamp(inicio)).total_seconds()
    else:
        inicio = fin = None
        duracion = 0.0

    return {
        **totales,
        "duration_seconds": round(max(duracion, 0.0), 2),
        "model": ultimo_modelo,
        "started_at": inicio,
        "ended_at": fin,
    }


def armar_payload(
    resumen: dict,
    *,
    role: str,
    agent_type: str | None,
    agent_id: str | None,
    session_id: str | None,
) -> dict:
    """El cuerpo del POST a `.../runs`. `source` fijo en "hook": así se distingue de dónde salió."""
    return {
        "source": "hook",
        "role": role,
        "tokens_input": resumen["tokens_input"],
        "tokens_output": resumen["tokens_output"],
        "tokens_cache_read": resumen["tokens_cache_read"],
        "tokens_cache_creation": resumen["tokens_cache_creation"],
        "duration_seconds": resumen["duration_seconds"],
        "model": resumen.get("model"),
        "agent_type": agent_type,
        "agent_id": agent_id,
        "session_id": session_id,
        "started_at": resumen.get("started_at"),
        "ended_at": resumen.get("ended_at"),
    }


# --------------------------------------------------------------------------------------
# I/O: disco, red, entorno. Todo lo que puede fallar por motivos ajenos al parseo.
# --------------------------------------------------------------------------------------


def resolver_transcript_subagente(payload: dict) -> Path | None:
    """Ubica el `.jsonl` del subagente a partir del `agent_id` del payload.

    `transcript_path` en `SubagentStop` apunta al `.jsonl` de la sesión PADRE
    (`~/.claude/projects/<slug>/<session_id>.jsonl`); el transcript del subagente vive en
    `~/.claude/projects/<slug>/<session_id>/subagents/agent-<agentId>.jsonl`.

    Sin `agent_id` en el payload NO se adivina cuál archivo es: la carpeta `subagents/` puede
    tener el `.jsonl` de VARIOS subagentes corriendo en paralelo, y el más reciente por `mtime` no
    tiene por qué ser el de este WO — puede ser el de otro (falso positivo real, visto en
    producción). El llamador (`main`) decide no registrar el run cuando falta `agent_id`, antes
    de llegar acá.
    """
    transcript_path = payload.get("transcript_path")
    agent_id = payload.get("agent_id")
    if not transcript_path or not agent_id:
        return None

    transcript = Path(transcript_path).expanduser()
    session_id = payload.get("session_id") or transcript.stem
    subagents_dir = transcript.parent / session_id / "subagents"

    candidato = subagents_dir / f"agent-{agent_id}.jsonl"
    if candidato.exists():
        return candidato
    return None


def obtener_proyecto(payload: dict) -> str | None:
    """`FACTORY_PROJECT` del entorno; si no está, el slug de `.factory.json` en el `cwd` del hook."""
    proyecto = os.environ.get("FACTORY_PROJECT")
    if proyecto:
        return proyecto

    cwd = payload.get("cwd")
    if not cwd:
        return None
    config_path = Path(cwd).expanduser() / ".factory.json"
    if not config_path.exists():
        return None
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    slug = config.get("project")
    return str(slug) if slug else None


def enviar_run(url: str, proyecto: str, wo: str, token: str, cuerpo: dict) -> tuple[bool, str]:
    endpoint = f"{url.rstrip('/')}/api/v1/p/{proyecto}/work-orders/{wo}/runs"
    datos = json.dumps(cuerpo).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=datos,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as respuesta:
            return True, f"HTTP {respuesta.status}"
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", "replace")[:300]
        return False, f"HTTP {exc.code}: {detalle}"
    except urllib.error.URLError as exc:
        return False, f"no se pudo conectar: {exc.reason}"
    except Exception as exc:  # cualquier otra cosa de la red tampoco puede tirar la sesión
        return False, f"error inesperado en el POST: {exc!r}"


def _ruta_log() -> Path:
    override = os.environ.get("FACTORY_RUNS_LOG")
    return Path(override).expanduser() if override else Path.home() / ".claude" / "factory-runs.log"


def registrar_log(mensaje: str) -> None:
    """Deja constancia en el log. Si ni esto se puede escribir, se traga el error: nunca romper."""
    try:
        ruta = _ruta_log()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with ruta.open("a", encoding="utf-8") as archivo:
            archivo.write(f"{timestamp} {mensaje}\n")
    except Exception:
        pass


def main() -> None:
    try:
        crudo = sys.stdin.read()
        try:
            payload = json.loads(crudo) if crudo.strip() else {}
        except json.JSONDecodeError:
            registrar_log("SKIP el payload del hook no es JSON válido")
            return
        if not isinstance(payload, dict):
            registrar_log("SKIP el payload del hook no es un objeto")
            return

        if not payload.get("agent_id"):
            # Sin agent_id no hay con qué armar la ruta del transcript del subagente, y no se
            # adivina: adivinar (el `agent-*.jsonl` más reciente por mtime) puede atribuirle el
            # run a OTRO work order si hay varios subagentes en paralelo.
            registrar_log("SKIP sin agent_id: no se registra")
            return

        transcript = resolver_transcript_subagente(payload)
        if transcript is None:
            registrar_log("SKIP no se encontró el transcript del subagente")
            return

        try:
            eventos = leer_transcript(transcript)
        except OSError as exc:
            registrar_log(f"ERROR no se pudo leer el transcript {transcript}: {exc}")
            return

        wo = detectar_wo(eventos)
        if wo is None:
            registrar_log(f"SKIP sin WO detectable en {transcript}")
            return

        agent_type = payload.get("agent_type")
        role = rol_de(agent_type)
        resumen = resumir_uso(eventos)
        cuerpo = armar_payload(
            resumen,
            role=role,
            agent_type=agent_type,
            agent_id=payload.get("agent_id"),
            session_id=payload.get("session_id"),
        )

        proyecto = obtener_proyecto(payload)
        if proyecto is None:
            registrar_log(f"SKIP sin FACTORY_PROJECT ni .factory.json para {wo}")
            return

        url = os.environ.get("FACTORY_URL")
        token = os.environ.get("FACTORY_TOKEN")
        if not url or not token:
            registrar_log(f"SKIP falta FACTORY_URL o FACTORY_TOKEN para {wo}")
            return

        tokens_total = resumen["tokens_input"] + resumen["tokens_output"]
        ok, detalle = enviar_run(url, proyecto, wo, token, cuerpo)
        if ok:
            registrar_log(
                f"OK {wo} role={role} tokens_total={tokens_total} "
                f"duration_seconds={resumen['duration_seconds']} ({detalle})"
            )
        else:
            registrar_log(f"ERROR {wo} role={role}: {detalle}")
    except Exception as exc:  # el contrato duro: esto nunca puede tirar la sesión
        registrar_log(f"ERROR inesperado en el hook: {exc!r}")


if __name__ == "__main__":
    main()
    sys.exit(0)
