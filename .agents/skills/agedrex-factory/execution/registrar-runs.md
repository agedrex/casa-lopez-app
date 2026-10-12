# Registrar runs: lo que costó ejecutar un work order

El plan dice "5 puntos". El run dice "un ejecutor Sonnet, 12 minutos, 300k tokens". Sin registrar el
segundo dato no hay forma de saber qué cuesta de verdad un work order, ni de calibrar las
estimaciones de puntos a futuro. Un run se guarda por `work_order_id`, con rol (`executor`,
`reviewer`, `orchestrator`, `suite`, `other`), tokens de entrada/salida/cache y duración — nada se
borra, se archiva.

## El hook automático

El paquete de la skill trae, en `hooks/registrar_run.py`, el hook que anota un run automáticamente
cuando termina un subagente de Claude Code. **Esa carpeta no es la fuente**: el hook tiene una sola
fuente real, `ops/hooks/registrar_run.py` en el repo de Agedrex Factory, y es el empaquetador de la
skill el que lo copia a `hooks/` al armar el zip — nunca se versiona una segunda copia acá adentro.

Se dispara en el evento `SubagentStop`, que trae en su payload `agent_id`, `agent_type`,
`session_id` y el `transcript_path` de la sesión **padre** (no del subagente). El transcript del
propio subagente vive en
`<directorio del transcript padre sin el .jsonl>/subagents/agent-<agent_id>.jsonl` — el hook
construye esa ruta a partir de `agent_id`. **Sin `agent_id` en el payload, el hook NO adivina**: no
toma el `agent-*.jsonl` más reciente por fecha de modificación de esa carpeta, porque con varios
subagentes corriendo en paralelo ese archivo bien puede ser el de OTRO work order (y sin `agent_id`
tampoco hay con qué deduplicar contra `uq_work_order_runs_agent`). En ese caso deja constancia en
`~/.claude/factory-runs.log` ("sin agent_id: no se registra") y no manda nada.

### Cómo detecta el WO

El hook lee el WO del **primer** mensaje `user` del transcript del subagente, en este orden:

1. El marcador explícito **`[wo: WO-N]`**, en cualquier parte del texto. El orquestador lo agrega
   siempre al armar el prompt de cada ejecutor — es la forma confiable de decirle al hook cuál es
   el WO, sin depender de que el texto lo mencione de una manera reconocible.
2. Si no hay marcador, la mención explícita `Ejecutá WO-N` / `ejecución de WO-N` / `ejecutor de
   WO-N`.
3. Si tampoco hay eso, el hook **no adivina** y no registra nada (logea "sin WO detectable").

Un `WO-\d+` suelto en cualquier otra parte del mensaje **no cuenta**: las reglas duras que abren el
prompt de todo ejecutor mencionan `WO-83` como ejemplo de referencia legible
(`Referencias legibles (WO-83, FRD-X, F3, E1)...`), y tomar el primer número que aparezca le
atribuiría el run entero a WO-83 en vez del WO real que se está ejecutando.

### Instalación

Fragmento para `~/.claude/settings.json` (o el `settings.json` del proyecto):

```json
{
  "hooks": {
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/agedrex-factory/hooks/registrar_run.py"
          }
        ]
      }
    ]
  }
}
```

Variables de entorno que necesita:

| Variable | Para qué |
|---|---|
| `FACTORY_URL` | Base de la API de la Fábrica contra la que registra el run. |
| `FACTORY_TOKEN` | Token personal (`fct_…`) con el que se autentica, igual que el MCP. |
| `FACTORY_PROJECT` | Slug del proyecto default cuando el WO no lo deja claro por sí solo. |

### Garantía: nunca bloquea

El hook **nunca** puede frenar ni romper una sesión de Claude Code. Si falla — red caída, token
vencido, WO que no existe, lo que sea — loguea el error en `~/.claude/factory-runs.log` y **sale con
código 0**. Un hook de registro de métricas no es motivo para que un agente se quede colgado o una
sesión se corte.

## Plan B: el hook no está instalado

Si el hook no está configurado (una máquina nueva, alguien que todavía no lo instaló), el run **no
se pierde silenciosamente**: quien orquesta lo registra a mano en cuanto ve la notificación de fin
de subagente, con los datos que esa notificación ya trae — tokens de entrada, salida, cache read,
cache creation, y duración.

`sf_run` (la tool del MCP para esto) llega recién con **WO-36** (ronda 2). Hasta que ese WO esté
desplegado, el camino Plan B es uno de estos dos:

1. Si el hook está instalado pero no se disparó por lo que sea, esperar a la próxima corrida o
   correrlo a mano (`python3 ~/.claude/skills/agedrex-factory/hooks/registrar_run.py` con el mismo
   payload de `SubagentStop` por stdin).
2. Si no hay hook ni `sf_run`, quien orquesta manda el mismo dato por REST directo, siguiendo el
   contrato de `POST /api/v1/p/{proyecto}/work-orders/{ref}/runs` con el rol que corresponda
   (normalmente `executor` para el subagente que acaba de terminar, `reviewer` para el delegate de
   revisión) y el payload (`role`, `tokens_input`, `tokens_output`, `tokens_cache_read`,
   `tokens_cache_creation`, `duration_seconds`, `model`, `agent_type`, `source: "manual"`, `note`) y
   un token — nunca por SQL directo contra la base.

**No se inventa un número.** Si la notificación no trae un dato, se manda lo que sí se sabe y se
deja `note` explicando qué falta — un run parcial es mejor información que un run inventado, y
muchísimo mejor que ningún run. En particular, `duration_seconds` es **opcional**: si no viene, el
servicio guarda `0` y agrega "sin duración informada" a `note` por su cuenta — no hace falta
mandarlo a mano, y nunca da 422 por faltar.
