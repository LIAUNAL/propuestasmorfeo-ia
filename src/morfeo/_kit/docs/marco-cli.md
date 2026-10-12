# Referencia del CLI `marco`

CLI de proyecto portable para el framework `marco-propuestas-ia`.
Comandos: `init`, `guide`, `status`, `upgrade`.

---

## 1. Instalación

El CLI `marco` se instala con **pipx** desde la raíz del repositorio
`marco-propuestas-ia/`:

```bash
# Editable (recomendado)
pipx install -e .
```

```bash
# No editable (requiere MARCO_KIT_ROOT — ver §6)
pipx install .
```

**¿Por qué editable es lo recomendado?** `marco_cli.py` resuelve la
ubicación del kit (agentes, comandos, guía, generadores) mediante
`Path(__file__).resolve().parent.parent`. Con `pipx install -e .`, el
archivo `marco_cli.py` se queda en el repositorio clonado y esa
resolución encuentra el kit sin configuración adicional. Con `pipx install .`,
el archivo se copia dentro del venv de pipx y la resolución falla a menos
que se defina `MARCO_KIT_ROOT`.

Verificar la instalación:

```bash
which marco          # → ~/.local/bin/marco
marco --help         # lista comandos y flags
```

Si `marco` no se encuentra después de la instalación, ejecutar
`pipx ensurepath` y reiniciar la terminal.

---

## 2. Comandos

### 2.1 `marco init` — Crear un proyecto portable

```
marco init <dir> [--title TITLE] [--tools TOOLS] [--lang CODE] [--model-preset NAME]
```

Crea una carpeta de proyecto autocontenida en `<dir>` con el kit completo
de agentes, comandos, guía, esqueleto LaTeX en `plantilla/`, mirror
`artefactos/vault/`, `DECISIONS.md`, `journal/`, `.marco/` (version + manifest + config)
y la configuración de idioma y modelo.

| Flag | Valor por defecto | Descripción |
|------|-------------------|-------------|
| `<dir>` | (obligatorio) | Ruta del directorio destino (se crea si no existe) |
| `--title` | `None` | Título opcional de la propuesta; se escribe en el `README.md` del proyecto |
| `--tools` | `claude,opencode,pi,antigravity` | Lista separada por comas de los runtimes a instalar (ver §5) |
| `--lang` | `es` (o prompt interactivo) | Código BCP-47 del idioma de la propuesta. En TTY sin flag, muestra un menú interactivo |
| `--model-preset` | `claude` (o prompt interactivo) | Nombre del preset de modelos. En TTY sin flag, muestra un menú interactivo. Presets válidos: `claude`, `gpt`, `opencode-go` |

**Comportamiento:**

1. Crea `<dir>` si no existe.
2. Resuelve `--lang` y `--model-preset`: si el flag está presente lo usa;
   si no y el stdin es una TTY, presenta un menú interactivo numerado; en
   non-TTY sin flag usa los valores por defecto.
3. Valida el preset antes de toda escritura a disco; si es inválido, sale
   con error listando los presets válidos.
4. Copia los archivos del kit listados en `kit-manifest.json` desde la fuente
   (monorepo o `MARCO_KIT_ROOT`).
5. Escribe `.marco/version`, `.marco/manifest.json` con checksums SHA-256,
   y `.marco/config.json` con `language`, `model_preset`, `agent_models`,
   `created_at` y `updated_at`.
6. **No** crea contenido de corrida en la raíz del proyecto: las corridas las
   crea `scripts/init-run.sh` (vía `/propuesta-init`) en `proposals/<run-id>/`
   con sus cuatro subcarpetas, y las zonas de depósito las siembra
   `/propuesta-insumos` dentro del `insumos/` de esa corrida. `drop_zones` y
   `vault_subdirs` siguen en el manifest porque esos comandos los consumen.
7. Si no existe, siembra `idea.md` en la raíz del proyecto con la plantilla de idea
   en el idioma configurado.
10. Si no existe, siembra `DECISIONS.md` con la plantilla de registro de
    decisiones en el idioma configurado.
11. Crea `journal/` con un `README.md` en el idioma configurado.
12. Escribe un `README.md` descriptivo del proyecto con la línea de
    configuración (idioma + preset).
13. Aplica el preset de modelos a los archivos `.claude/agents/*.md` (reescribe
    la línea `model:` en el frontmatter) y a `AGENTS.md` (regla #1 de idioma).
14. Si `--tools` incluye `opencode`, ejecuta `gen-opencode.py --root <dir>`.
15. Si `--tools` incluye `pi`, ejecuta `gen-pi.py --root <dir>`.

**Idempotencia:** si `<dir>` ya existe y contiene `DECISIONS.md` o
`idea.md`, esos archivos **no se sobrescriben** (solo se
siembran si faltan). Los archivos del kit se refrescan siempre.

**Ejemplos:**

```bash
marco init ~/propuestas/mi-propuesta
marco init ~/propuestas/mi-propuesta --title "IA para salud global"
marco init /tmp/p1 --tools claude
marco init /tmp/p2 --tools claude,opencode
marco init /tmp/p3 --title "Demo" --tools claude,pi
marco init /tmp/p4 --lang en --model-preset gpt
marco init /tmp/p5 --lang en --model-preset opencode-go --tools claude
```

**Códigos de salida:**

| Código | Significado |
|--------|-------------|
| 0 | Proyecto creado correctamente |
| 1 | Error: manifest no encontrado, argumento inválido, etc. |

---

### 2.2 `marco upgrade` — Refrescar el kit y reconfigurar herramientas

```
marco upgrade [<dir>] [--tools TOOLS]
```

Refresca los archivos del kit en un proyecto portable existente y permite actualizar opcionalmente la lista de herramientas/runtimes instalados.
Nunca toca el contenido del operador.

| Flag | Valor por defecto | Descripción |
|------|-------------------|-------------|
| `<dir>` | `.` (directorio actual) | Ruta del directorio del proyecto portable |
| `--tools` | `None` (conserva configuradas) | Lista separada por comas de runtimes a habilitar (`claude`, `opencode`, `pi`, `antigravity`) |

**Comportamiento:**

1. Verifica la existencia del proyecto leyendo `.marco/manifest.json` en `<dir>` (sale con error si no es un proyecto válido).
2. Lee `kit-manifest.json` de la fuente del kit.
3. Para cada ruta en `kit_paths`, si **no** coincide con algún patrón de `preserve_paths`, copia el archivo desde la fuente al proyecto.
4. Si se especifica `--tools`, actualiza la lista de herramientas en `.marco/config.json`.
5. Re-ejecuta los generadores para todas las herramientas activas configuradas (`gen-opencode.py`, `gen-pi.py`, `gen-antigravity.py`).
6. Actualiza `.marco/version` y `.marco/manifest.json` con los nuevos checksums y la versión anterior.

**Preserve-list** (nunca se modifican): `insumos/**`,
`redaccion/sections/**`, `redaccion/main.tex`, `redaccion/refs.bib`,
`proposals/**` (corridas, registro local y puntero),
`vault/**`, `DECISIONS.md`, `journal/**`.

**Idempotente:** ejecutar `upgrade` dos veces seguidas sin cambios en el
kit deja el árbol exactamente igual y termina com código 0.

**Ejemplos:**

```bash
marco upgrade
marco upgrade ~/propuestas/mi-propuesta
marco upgrade --tools claude,antigravity,opencode
```

**Códigos de salida:**

| Código | Significado |
|--------|-------------|
| 0 | Kit actualizado correctamente |
| 1 | Error: proyecto no encontrado, manifest faltante, etc. |

---

### 2.3 `marco status` — Estado del proyecto

```
marco status [<dir>]
```

Imprime un resumen del estado actual de un proyecto portable.

**Comportamiento:**

1. Lee `.marco/version` y muestra la versión del kit.
2. Si existe `artefactos/estado_propuesta.md`, extrae e imprime los campos
   del bloque de control (`mode`, `next_step`, `next_command`,
   `last_completed`, `intake_complete`).
3. Muestra las últimas 30 líneas de `DECISIONS.md`.
4. Muestra las primeras 20 líneas de la entrada más reciente de `journal/`.
5. Si no existe `.marco/version`, imprime una advertencia clara y termina
   con código 1 — no intenta leer los archivos de estado.

**Ejemplos:**

```bash
marco status ~/propuestas/mi-propuesta
marco status .
```

```bash
# Fuera de un proyecto portable:
$ marco status /tmp/no-marco
warning: /tmp/no-marco is not a portable marco project (no .marco/version)
```

**Códigos de salida:**

| Código | Significado |
|--------|-------------|
| 0 | Estado leído correctamente |
| 1 | El directorio no es un proyecto portable (sin `.marco/version`) |

---

### 2.4 `marco guide` — Guía interactiva de onboarding

```
marco guide [<dir>]
```

Muestra una guía interactiva y el estado paso a paso del proyecto, junto con la recomendación del próximo comando a ejecutar según `artefactos/estado_propuesta.md`.

**Comportamiento:**

1. Verifica la existencia de `.marco/version` en `<dir>`.
2. Muestra un resumen del estado del proyecto (`estado_propuesta.md`, las últimas entradas de `DECISIONS.md` y `journal/`).
3. Recomienda explícitamente la acción o slash command a ejecutar a continuación (`/propuesta-analizar`, `/propuesta-continuar`, etc.).

**Ejemplos:**

```bash
marco guide ~/propuestas/mi-propuesta
marco guide .
```

---

### 2.5 `marco --list-presets` — Listar presets de modelos

```
marco --list-presets
```

Lista en consola todos los presets de modelos incorporados (`claude`, `gpt`, `opencode-go`) y su alineación de modelos por cada uno de los 10 agentes.

---

## 3. Layout producido por `marco init`

```
<dir>/
├── .marco/
│   ├── version                      # Versión del kit (ej. 0.1.0)
│   ├── manifest.json                # Manifiesto: versión, checksums SHA-256, fecha
│   └── config.json                  # Configuración: idioma, preset de modelos, agent_models
├── .claude/
│   ├── agents/                      # 10 agentes (canónicos, editables a mano)
│   └── commands/                    # 7 comandos /propuesta-*
├── .opencode/                       # SÓLO si --tools incluye opencode (generado)
│   ├── agents/
│   └── commands/
├── .pi/                             # SÓLO si --tools incluye pi (generado)
│   ├── prompts/
│   ├── references/agents/
│   └── skills/marco-propuestas/
├── insumos/
│   ├── tdr/                         # Drop zone: términos de referencia
│   ├── draft/                       # Drop zone: borradores previos
├── plantilla/                       # Esqueleto LaTeX versionado (copiado a redaccion/)
│   ├── build.sh                     # Script de compilación LaTeX/DOCX
│   ├── scripts/
│   │   ├── compile_tikz.py          # Compilación de diagramas TikZ
│   │   ├── prep_docx.py             # Preparación para exportar a DOCX
│   │   └── split_latex_section.py   # Shim del splitter (skill de usuario)
│   ├── logos/                       # Logos institucionales (LabIA, UNAL, GCPDS)
│   └── templates/
│       ├── README.md
│       └── reference.docx           # Plantilla pandoc para DOCX
├── scripts/
│   ├── init-run.sh                  # Crea proposals/<run-id>/ (4 subcarpetas)
│   ├── marco_cli.py                 # Este CLI
│   └── apa.csl                      # Estilo APA para el export a Word
├── proposals/                       # Corridas — lo crea init-run.sh, nada versionado
│   ├── registry.md                  #   Registro local de corridas
│   ├── .current-run                 #   Puntero a la corrida activa
│   └── <run-id>/                    #   insumos/ artefactos/ grafos/ redaccion/
├── idea.md                          # Nota de idea (sembrada si no existe)
├── DECISIONS.md                     # Registro en vivo de decisiones
├── journal/
│   └── README.md                    # Convención de entradas append-only
├── AGENTS.md                        # Playbook del marco multi-agente
├── guiaProyectosIA_Agente.md        # Guía autoritativa sección por sección
├── README.md                        # README del proyecto portable
├── requirements.txt                 # Dependencias Python
├── .gitignore
└── .mcp.json                        # Configuración de MCP servers
```

**No se pre-pueblan:** `redaccion/main.tex`, `redaccion/refs.bib`,
`redaccion/sections/*.tex` — esos los genera el pipeline `/propuesta-*`
durante la corrida.

> **Nota sobre estructura y desambiguación:**
> - **`plantilla/` vs `proposals/`**: `plantilla/` es el esqueleto LaTeX versionado, y es lo único que `init-run.sh` copia al `redaccion/` de cada corrida. `proposals/` contiene las corridas en sí (`proposals/<run-id>/` con `insumos/`, `artefactos/`, `grafos/`, `redaccion/`), el registro local y el puntero de corrida activa; nada de eso se versiona.
> - **`scripts/` vs `redaccion/scripts/`**: `scripts/` (en la raíz) contiene el tooling del repositorio/CLI (`marco_cli.py`, `init-run.sh`, y los generadores de runtime `gen-opencode.py`, `gen-pi.py` y `gen-antigravity.py`); `redaccion/scripts/` contiene scripts exclusivos de compilación y post-procesamiento LaTeX/TikZ/DOCX (`compile_tikz.py`, `prep_docx.py`).

---

## 4. Manifest y contrato de instalación

El archivo `scripts/kit-manifest.json` es la fuente de verdad del kit.
Usa formato JSON (no YAML) para mantener `marco_cli.py` libre de
dependencias externas.

### Estructura del manifest

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `version` | string | Versión del kit (actual: `0.2.0`). Se incrementa independientemente del framework de propuestas. |
| `kit_paths` | string[] | Lista plana de archivos que constituyen el kit (incluye scripts del CLI `scripts/marco_cli.py` y estilo CSL APA `scripts/apa.csl`). Cada entrada es una ruta relativa desde la raíz de la fuente del kit. |
| `preserve_paths` | string[] | 10 patrones glob que `marco upgrade` NUNCA debe tocar. |
| `drop_zones` | string[] | 5 subdirectorios que se crean bajo `insumos/`: `tdr`, `draft`, `background`, `doc-secciones`, `ideas`. |
| `vault_subdirs` | string[] | 2 subdirectorios que se crean bajo `artefactos/vault/`: `insumos`, `secciones`. |

### Regla de instalación

**Un archivo no listado en `kit_paths` NO DEBE aparecer en el destino.**
Si un mantenedor agrega un archivo al repositorio pero olvida listarlo en
`kit-manifest.json`, ni `marco init` ni `marco upgrade` lo instalarán.
Esta restricción es deliberada: el manifest es la lista autoritativa.

### Checksums

`marco init` calcula un hash SHA-256 por cada archivo copiado y lo
registra en `.marco/manifest.json` bajo la clave `files`, como una lista
de objetos `{"path": "...", "sha256": "..."}`.

`marco upgrade` recalcula los checksums de los archivos del kit
actualizados y escribe un nuevo `.marco/manifest.json` con los valores
frescos, la versión anterior (`previous_version`) y la marca de tiempo
(`updated_at`).

---

## 5. `--tools` flag

El flag `--tools` acepta una lista separada por comas de runtimes a
instalar en el proyecto portable.

| Valor | Efecto |
|-------|--------|
| `claude` | El directorio `.claude/` (agentes + comandos) **siempre se copia**, pues es la fuente de verdad (SSOT). No ejecuta ningún generador. |
| `opencode` | Además de `.claude/`, ejecuta `python3 scripts/gen-opencode.py --root <dir>` para generar `.opencode/`. |
| `pi` | Además de `.claude/`, ejecuta `python3 scripts/gen-pi.py --root <dir>` para generar `.pi/`. |
| `antigravity` | Además de `.claude/`, ejecuta `python3 scripts/gen-antigravity.py --root <dir>` para generar `.agent/`. |

**Valor por defecto (al momento de esta escritura):** `claude,opencode,pi,antigravity`.

**Cómo omitir un runtime:**

```bash
marco init /tmp/p1 --tools claude              # solo kit, sin generated runtimes
marco init /tmp/p2 --tools claude,opencode     # skip pi y antigravity
marco init /tmp/p3 --tools claude,pi           # skip opencode y antigravity
marco init /tmp/p4 --tools claude,antigravity  # solo claude y antigravity
```

`marco upgrade` detecta automáticamente qué runtimes están presentes en el
proyecto (por la existencia de `.opencode/`, `.pi/` y `.agent/`) y regenera los
que existen — no requiere `--tools` en `upgrade` salvo que se deseen habilitar nuevos runtimes.

---

## 6. Variables de entorno

### `MARCO_KIT_ROOT`

Valor por defecto: `Path(__file__).resolve().parent.parent` — es decir,
el directorio que contiene `scripts/marco_cli.py` es `scripts/` y su padre
es la raíz del repositorio `marco-propuestas-ia/`.

Cuándo definir `MARCO_KIT_ROOT`:

- **Instalación no editable** (`pipx install .`): el CLI se copia al venv
  de pipx y `__file__` ya no apunta al repositorio. Hay que exportar la
  variable para que encuentre el kit.
- **Fuente de kit personalizada**: si se quiere usar un directorio distinto
  como origen del kit (por ejemplo, una rama clonada en otra ruta).
- **CI / automatización**: cuando el script se ejecuta desde un contexto
  donde la resolución relativa no funciona.

Ejemplo:

```bash
export MARCO_KIT_ROOT=/home/usuario/marco-propuestas-ia
marco init /tmp/p1 --title "Mi propuesta"
```

---

## 7. Flujo operativo completo

### Creación y primer uso

```bash
# 1. Crear el proyecto portable
marco init ~/propuestas/mi-propuesta --title "Título del proyecto"

# 2. Copiar insumos (TDR, borradores, papers)
cp /ruta/TDR.pdf ~/propuestas/mi-propuesta/insumos/tdr/
$EDITOR ~/propuestas/mi-propuesta/idea.md

# 3. Abrir el runtime con CWD = la carpeta del proyecto
cd ~/propuestas/mi-propuesta
#   Claude Code: claude
#   OpenCode:    opencode .
#   pi:          pi .

# 4. Usar los slash commands del pipeline
# /propuesta-init    → crea y activa proposals/<run-id>/ (4 subcarpetas)
# /propuesta-insumos  → zonas de depósito dentro del insumos/ de la corrida
# /propuesta-analizar → intake + clasificación
# /propuesta-continuar → una unidad del pipeline (stepped, recomendado)
# /propuesta    → pipeline completo en una sesión
```

### Copia y reubicación

```bash
# Copiar el proyecto completo a otra máquina
cp -a ~/propuestas/mi-propuesta /otra/maquina/

# En la otra máquina, abrir el runtime con CWD = la nueva ubicación
cd /otra/maquina/mi-propuesta
#  → mismo redaccion/sections/, DECISIONS.md, journal/, estado_propuesta
#  → sin reescritura de rutas ni reinstalación del kit
```

### Actualización del kit

```bash
# Después de cambios en el monorepo (agentes, comandos, guía)
cd /ruta/al/monorepo
git pull

# Refrescar el kit en el proyecto portable (sin tocar contenido del operador)
marco upgrade ~/propuestas/mi-propuesta
```

---

## 8. Generadores

Los generadores `gen-opencode.py`, `gen-pi.py` y `gen-antigravity.py` transforman la fuente de
verdad (`.claude/`) en los runtimes secundarios.

### Uso manual (para mantenedores del kit)

```bash
# Desde la raíz del monorepo
python3 scripts/gen-opencode.py              # escribe .opencode/
python3 scripts/gen-opencode.py --check      # drift lint, no escribe
python3 scripts/gen-opencode.py --root <dir> # genera en un directorio distinto

python3 scripts/gen-pi.py                    # escribe .pi/
python3 scripts/gen-pi.py --check            # drift lint, no escribe
python3 scripts/gen-pi.py --root <dir>       # genera en un directorio distinto

python3 scripts/gen-antigravity.py           # escribe .agent/ (workflows + skills)
python3 scripts/gen-antigravity.py --check   # drift lint, no escribe
python3 scripts/gen-antigravity.py --root <dir> # genera en un directorio distinto
```

### Flag `--root`

El flag `--root <dir>` indica al generador que use `<dir>` como raíz
(tanto para leer `.claude/` como para escribir `.opencode/`, `.pi/` o `.agent/`).
Es **retrocompatible**: sin `--root`, el generador usa
`Path(__file__).resolve().parent.parent` (comportamiento histórico).

`marco init` y `marco upgrade` invocan estos generadores automáticamente
con `--root <dir>` cuando el runtime correspondiente está incluido en
`--tools`. El uso manual es necesario solo cuando se editan los archivos
fuente de `.claude/` directamente.

### `--check` (drift lint)

El modo `--check` ejecuta todo el proceso de generación en memoria y
compara con los archivos existentes en disco. Si el output generado
difiere del actual, o si encuentra patrones de Claude que no están
mapeados en las reglas de sustitución, termina con código 3 sin escribir
nada en disco.

**Códigos de salida de los generadores:**

| Código | Significado |
|--------|-------------|
| 0 | OK |
| 1 | Uso incorrecto |
| 2 | Fuente/rules faltante |
| 3 | Drift encontrado (`--check`) |

---

## 9. Notas de implementación

- **Librería estándar solamente:** `marco_cli.py` usa exclusivamente
  módulos de la stdlib de Python (`argparse`, `hashlib`, `json`, `os`,
  `shutil`, `subprocess`, `pathlib`, `fnmatch`). No requiere dependencias
  externas.
- **Formato JSON (no YAML):** el manifest es JSON para mantener el CLI
  libre de dependencias. La pregunta de diseño YAML vs JSON se resolvió a
  favor de JSON.
- **Flag `--root` retrocompatible:** los generadores `gen-opencode.py` y
  `gen-pi.py` aceptan `--root <dir>`. Sin el flag, usan el directorio
  del script (comportamiento histórico). Esto permite que `marco init` y
  `marco upgrade` apunten los generadores al proyecto portable sin romper
  el uso directo desde el monorepo.
- **`init` idempotente:** si el directorio destino ya existe, `init` no
  sobrescribe `DECISIONS.md` ni `idea.md`. Los archivos del
  kit se refrescan siempre.
- **`upgrade` idempotente:** ejecutar `upgrade` dos veces seguidas sin
  cambios en el kit deja el árbol exactamente igual y termina con código 0.

---

## 11. Idioma y preset de modelos

`marco init` acepta los flags `--lang` y `--model-preset` para configurar
el idioma de la propuesta y el lineup de modelos por agente. Ambos se
almacenan en `.marco/config.json` y persisten a través de `marco upgrade`.

### `--lang <code>`

Código BCP-47 del idioma en que los agentes deben redactar la propuesta.
Valor por defecto: `es` (español).

- La tabla de traducción incorporada cubre `es` y `en` para las plantillas
  de operador (`insumos/ideas/idea.md`, `DECISIONS.md`, `journal/README.md`).
- Códigos no cubiertos (p. ej. `fr`, `de`, `pt-BR`) se almacenan
  **literalmente** en `.marco/config.json` y se usan en la regla #1 de
  `AGENTS.md`, pero las plantillas se renderizan en español (fallback).
- El código se inyecta en la regla #1 de `AGENTS.md` reemplazando
  "español" por el código configurado. Para `es` es un no-op.

### `--model-preset <name>`

Nombre del preset de modelos por agente. Define qué modelo usa cada uno
de los 10 agentes del marco. Tres presets incorporados:

| Agente | `claude` (default) | `gpt` | `opencode-go` |
|--------|-------------------|-------|---------------|
| `investigador` | `opus` | `gpt-5.6-sol` | `opencode-go/glm-5.2` |
| `redactor` | `opus` | `gpt-5.6-sol` | `opencode-go/glm-5.2` |
| `bibliografo-propuesta` | `sonnet` | `gpt-5.6-terra` | `opencode-go/glm-5.2` |
| `revisor` | `sonnet` | `gpt-5.6-terra` | `opencode-go/glm-5.2` |
| `presupuestador` | `sonnet` | `gpt-5.6-terra` | `opencode-go/glm-5.2` |
| `insumos-observador` | `sonnet` | `gpt-5.6-terra` | `opencode-go/glm-5.2` |
| `disenador-tikz` | `sonnet` | `gpt-5.6-terra` | `opencode-go/glm-5.2` |
| `tikz-optimizer` | `sonnet` | `gpt-5.6-terra` | `opencode-go/glm-5.2` |
| `revisor-figuras` | `sonnet` | `gpt-5.6-terra` | `opencode-go/glm-5.2` |
| `coordinador-propuesta` | `sonnet` | `gpt-5.6-terra` | `opencode-go/glm-5.2` |

Ver la lista completa desde el CLI:

```bash
marco --list-presets
```

### Prompt interactivo en TTY

Cuando se omite `--lang` o `--model-preset` y el stdin es una terminal
(TTY), `marco init` presenta un menú numerado y lee una línea:

```text
Select proposal language:
  1. es (default)
  2. en
Enter number (or press Enter for default):
```

- Enter vacío → se aplica el valor por defecto.
- Número inválido → se vuelve a mostrar el menú.
- En non-TTY (CI, `</dev/null`, flag presente) el prompt se omite y se
  usan los valores por defecto o los flags. Nunca bloquea.

### Esquema de `.marco/config.json`

```json
{
  "language": "es",
  "model_preset": "claude",
  "agent_models": {
    "investigador": "opus",
    "redactor": "opus",
    "bibliografo-propuesta": "sonnet",
    "revisor": "sonnet",
    "presupuestador": "sonnet",
    "insumos-observador": "sonnet",
    "disenador-tikz": "sonnet",
    "tikz-optimizer": "sonnet",
    "revisor-figuras": "sonnet",
    "coordinador-propuesta": "sonnet"
  },
  "created_at": "2026-07-19T12:00:00+00:00",
  "updated_at": "2026-07-19T12:00:00+00:00"
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `language` | string | Código BCP-47 del idioma de la propuesta. Se almacena literalmente. |
| `model_preset` | string | Nombre del preset base (`claude`, `gpt`, o `opencode-go`). Se conserva para auditoría. |
| `agent_models` | dict | Mapa resuelto de 10 agentes a modelo. Es lo que los generadores consumen realmente. |
| `created_at` | string (ISO-8601) | Marca de tiempo de creación del proyecto. |
| `updated_at` | string (ISO-8601) | Marca de tiempo de la última modificación (igual a `created_at` en init). |

`agent_models` es el campo autoritativo: los operadores avanzados pueden
editar un modelo específico directamente en este archivo (sin crear un
nuevo preset) y luego ejecutar `marco upgrade` para propagar el cambio a
los tres runtimes (`.claude/`, `.opencode/`, `.pi/`).

### Comportamiento en `marco upgrade`

`marco upgrade` lee `.marco/config.json` si existe. Después de refrescar
los archivos del kit:

1. Re-aplica `agent_models` a los archivos `.claude/agents/*.md` (copia
   local, no el SSOT del monorepo).
2. Re-escribe la regla #1 de `AGENTS.md` con el código de idioma.
3. Si hay agentes en el kit que no están en `agent_models`, los agrega
   desde el preset con una advertencia.
4. Vuelve a ejecutar `gen-opencode.py` y `gen-pi.py` para que los runtimes
   generados reflejen la configuración.

Si `.marco/config.json` no existe, `upgrade` se comporta como antes
(retrocompatibilidad).

---

## 12. Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|----------------|----------|
| `marco: command not found` | pipx no está en el PATH, o no se instaló el CLI | Ejecutar `pipx install -e .` desde la raíz de `marco-propuestas-ia/`; luego `pipx ensurepath` y reiniciar la terminal. |
| `module not found: marco_cli` | pipx se ejecutó desde un subdirectorio; `package-dir = {"" = "scripts"}` de `pyproject.toml` no se aplicó | Ejecutar `pipx install -e .` desde la raíz del repositorio (`marco-propuestas-ia/`), no desde `scripts/` ni otro subdirectorio. |
| `kit source missing: <path>` | `MARCO_KIT_ROOT` no está definido y la instalación no es editable (el CLI no puede resolver la ruta del kit) | Usar `pipx install -e .` (recomendado), o exportar `MARCO_KIT_ROOT=/ruta/a/marco-propuestas-ia`. |
| `error: kit manifest not found: ...` | El manifest `scripts/kit-manifest.json` no existe en la fuente del kit | Verificar que la fuente del kit (monorepo o `MARCO_KIT_ROOT`) contenga `scripts/kit-manifest.json`. |
| `warning: ... is not a portable marco project (no .marco/version)` | `marco status` se ejecutó en un directorio que no es un proyecto portable | Ejecutar primero `marco init <dir>` para crear el proyecto. |
| `error: unknown model preset '<name>'` | El preset indicado en `--model-preset` no es válido | Usar uno de: `claude`, `gpt`, `opencode-go`. Ver `marco --list-presets`. |
| `DRIFT: ... unmapped pattern ".claude/"` en generadores | Un archivo de comando contiene una referencia a `.claude/` que no está cubierta por las reglas de sustitución | Agregar una regla en `gen-opencode.rules.json` / `gen-pi.rules.json` con `applies_to: [<archivo>.md]`. |

---

## 13. Pruebas Automatizadas

El framework incluye una suite de pruebas end-to-end (`tests/test_e2e_framework.py`) escrita con `unittest`. Verifica la integridad del manifest, la creación y actualización de proyectos portables, el funcionamiento de los generadores y las opciones de compilación del `build.sh`:

---

## 14. Herramientas de Compilación y Conversión a Word

El framework incluye scripts dedicados para la compilación LaTeX/DOCX y conversión de formato:

### `redaccion/build.sh`

Script principal de compilación del documento PDF / DOCX de la propuesta.

```bash
cd proposal
./build.sh [pdf|docx|all]
```

### `redaccion/scripts/compile_tikz.py`

Compila autónomamente los diagramas TikZ a PDF/PNG y realiza detección determinista de desbordamiento horizontal (`Overfull \hbox`), reportando el conteo exacto de ocurrencias para el optimizador visual.

### `redaccion/scripts/prep_docx.py`

Prepara las secciones LaTeX para conversión a Microsoft Word mediante Pandoc, aplicando transformaciones de citas, tablas e imágenes.

### `scripts/convert_to_word.py`

Script CLI independiente para convertir directamente la propuesta LaTeX completa a formato DOCX.

```bash
python3 scripts/convert_to_word.py [--root <dir>] [--output <file.docx>]
```


