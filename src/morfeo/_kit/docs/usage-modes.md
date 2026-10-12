# Cómo usar el marco (modos, pipeline y CLI)

Guía de operador para **usar el marco de punta a punta**: modos de trabajo
(TDR / borrador), arranque del pipeline multi-agente (stepped o auto), y
**herramientas de shell** del repo (build LaTeX/DOCX, generador OpenCode,
helpers).

**Slash commands del pipeline** (Claude Code, OpenCode o pi, sesión
**interactiva**):

| Comando | Rol |
|---------|-----|
| `/propuesta-init` | Crea drop zones bajo `insumos/` |
| `/propuesta-analizar` | Intake + clasificación; para **antes** de scoping |
| `/propuesta-continuar` | **Una** unidad del pipeline; imprime el siguiente comando |
| `/propuesta` | Pipeline completo en una sesión (gates en la misma sesión) |
| `/propuesta-limpiar` | Archiva corrida activa y resetea workspace |

**No hay** un binario CLI que reemplace esas slash commands ni un run
**sin gates** (unattended). No confundir `/propuesta-continuar` con
`/opsx-continue` (OpenSpec en otro workflow).

Runtimes soportados: **Claude Code** (canónico, `.claude/`), **OpenCode**
(secundario generado, `.opencode/`), **pi** (secundario generado, `.pi/`
vía `python3 scripts/gen-pi.py`), y **Google Antigravity** (secundario generado,
`.agent/` vía `python3 scripts/gen-antigravity.py`). **Codex** no está soportado.

Diagrama de fases: [`pipeline-flow.md`](./pipeline-flow.md).

---

## 0. Flujo recomendado (stepped)

```text
/propuesta-init [slug]          # tdr/ draft/ background/ doc-secciones/ ideas/
# copiá TDR / borrador / papers; completá ideas/idea.md (o pasá la idea en args)
/propuesta-analizar [idea]      # intake; idea desde args o ideas/; imprime next command
/propuesta-continuar            # repetir hasta next_step=done
cd proposal && ./build.sh
```

Tras cada unidad, el dispatcher imprime el **siguiente** slash command
(normalmente otra vez `/propuesta-continuar`).

**Alternativa (una sesión):** `/propuesta <idea>` —
mismo pipeline, se detiene solo en gates de aprobación (no en cada frontera
de unidad).

---

## 1. Idea central: modos de propuesta

| Modo | Qué pones en `insumos/` | Qué hace el pipeline |
|------|--------------------------|----------------------|
| **Scratch** | Opcional: TDR, papers, `doc-secciones` | Escribe la propuesta completa desde la idea |
| **Improve-from-draft** | Borrador PDF/DOCX (`draft-base`) ± papers | Siembra el encuadre temprano (§3) desde el borrador y **reescribe** las 16 secciones |
| **Both** | TDR + borrador + papers | TDR gobierna estructura/presupuesto/prioridad; el borrador siembra ciencia; el resto del pipeline corre completo |

**Semántica honesta de “continuar / mejorar”:** un borrador en `insumos/` se
clasifica como `draft-base`. Eso **no** reanuda una corrida a medias ni parchea
`redaccion/sections/*.tex` existentes. Siembra el trabajo del `investigador` y
luego el pipeline **reescribe** la propuesta bajo la guía aplicable (base o
ajustada al TDR).

---

## 2. Cómo se usa la herramienta (paso a paso)

### 2.1 Requisitos mínimos

Antes de la primera corrida (detalle en `REQUIREMENTS.md` y `README.md`):

1. **Runtime interactivo:** Claude Code, OpenCode y/o pi configurado.
2. **MCP** del proyecto (`.mcp.json`): literatura (OpenAlex, Crossref, Semantic
   Scholar, PubMed, arXiv, Context7, Consensus) + `engram` si usas caché de
   extracciones.
3. **Python 3.11+** (recomendado 3.12) con venv e `pip install -r requirements.txt`
   para codebase-memory / PDF / DOCX helpers.
4. **LaTeX:** `pdflatex`, `bibtex`, `latexmk` en PATH (para PDF).
5. **DOCX export (opcional):** `pandoc`, `pdftoppm`.

```bash
cd marco-propuestas-ia
python3 -m venv .venv          # o pyenv 3.12.x
source .venv/bin/activate
pip install -r requirements.txt
```

### 2.2 Preparar insumos (`insumos/`)

Copia los archivos de la corrida en `insumos/` (gitignored; solo disco local).
Opcional: `/propuesta-init` crea drop zones etiquetadas (también bajo
`insumos/<slug>/`).

| Tipo de archivo | Label / carpeta | Rol |
|-----------------|-----------------|-----|
| Términos de referencia / bases / convocatoria | `TDR` / `tdr/` | Tope, cofinanciación, duración, rubros, criterios, secciones |
| Propuesta previa o en curso (PDF/DOCX) | `draft-base` / `draft/` | Semilla de contenido (no merge de LaTeX) |
| Papers, datos, notas de apoyo | `background` / `background/` | Contexto; no compite con TDR/draft |
| Lista explícita de secciones obligatorias | `doc-secciones` / `doc-secciones/` | Desbloquea G0.5 si el TDR no enumera secciones |
| Notas de idea / concepto para el grant | `idea-seed` / `ideas/` | Semilla científica; se **adapta** al TDR (no lo reemplaza) |

```bash
# Plano (sigue válido)
cp /ruta/TDR-convocatoria.pdf insumos/
cp /ruta/propuesta-previa.pdf insumos/   # opcional

# O con drop zones
# /propuesta-init mi-convocatoria
cp /ruta/TDR.pdf insumos/mi-convocatoria/tdr/
cp /ruta/borrador.pdf insumos/mi-convocatoria/draft/
# editá insumos/mi-convocatoria/ideas/idea.md  (template sembrado por init)
```

Nombres claros ayudan a la clasificación (p. ej. `TDR-MinCiencias-2026.pdf`).
`insumos-observador` escanea `insumos/` **en recursivo**.

**Resolución de la idea de investigación** (analizar / auto):

1. Texto usable en el comando (`$ARGUMENTS`) — gana si está presente  
2. Si no: contenido usable en `ideas/idea.md` (u otros `idea-seed` bajo `ideas/`)  
3. Si no: el dispatcher pregunta  

Template vacío o solo placeholders de init **no** cuenta como idea. Con TDR +
idea: la idea se alinea a la convocatoria; no se ignora el TDR.

**Cómo el agente “lee” PDF/DOCX:** no hay un CLI de conversión obligatorio.
`insumos-observador` extrae texto con **pymupdf4llm/markdownify** (PDF),
**markitdown** (DOCX, PPTX, XLSX; con fallback a `textutil`/`unzip`), y opcionalmente **pixelshot** + visión para tablas
malformadas; el resultado estructurado queda en `artefactos/insumos.md`.

### 2.3 Arrancar el pipeline (slash commands)

Abre Claude Code, OpenCode o pi en la raíz de `marco-propuestas-ia` (sesión
**interactiva**; en pi confiá el proyecto para cargar `.pi/`).

**Stepped (recomendado):**

```text
/propuesta-init
# completá ideas/idea.md y/o:
/propuesta-analizar Sistema de IA para ...
# o solo: /propuesta-analizar   (si ideas/idea.md ya tiene contenido)
/propuesta-continuar
# ... repetir hasta done ...
```

**Auto (una sesión):**

```text
/propuesta <idea de investigación en español>
```

Argumentos opcionales de run-id (analizar / auto):

```text
/propuesta-analizar run-id=2026-07-mi-proyecto Sistema de IA para ...
/propuesta --run-id 2026-07-mi-proyecto Sistema de IA para ...
```

Sin override, el run-id se auto-deriva como `<YYYY-MM>-<slug>` desde la idea.

**Archivar / reset:**

```text
/propuesta-limpiar
```

Archiva la corrida activa a `proposals/<run-id>/` (solo disco local) y resetea
la corrida como `archivada` sin tocar su contenido (incluye control `next_step`), con
confirmación explícita.

### 2.4 Qué hace el dispatcher

1. Resuelve el run-id y escribe `artefactos/estado_propuesta.md`.
2. Si hay corrida `activa` incompleta → **guardia de colisión** (archivar o
   no iniciar una nueva).
3. Aplica la **INTAKE CHECKLIST (Fase 0)** (solo ítems no resueltos).
4. Despacha `insumos-observador` sobre `insumos/`.
5. Confirma clasificaciones AMBIGUA con el usuario (nunca auto-resuelve).
6. Si hay TDR → extracción a `artefactos/insumos.md` + rama de prioridad.
7. Si hay draft-base → ruta **DRAFT-EXISTS**; si no → pregunta por borrador y
   puede quedar **NO-DRAFT**.
8. Si hay TDR → Fase 0.5 (G0.5): opt-in a `artefactos/guia_ajustada_TDR.md`.
9. Continúa Fases 1a…7 con gates de aprobación (papers, problema, SOTA,
   objetivos, metodología, presupuesto, auditoría final).
10. Fase 7 ensambla `redaccion/main.tex` y pide compilar PDF (y DOCX al final).

### 2.5 Checklist de intake (qué te preguntará)

Solo se pregunta lo que aún no esté resuelto por el mensaje o por `insumos/`:

1. Idea de investigación  
2. Intención de modo: `scratch` | `improve-from-draft` | `both`  
3. Identidad del archivo TDR (si hay candidatos o AMBIGUA)  
4. Identidad del draft-base (si hay candidatos, AMBIGUA, o afirmas tener borrador)  
5. G0.5: ¿ajustar la guía al TDR? (solo con TDR confirmado)  
6. Duración / tope si el TDR no los trae (cuando hagan falta)  
7. Identidades del equipo para §9 (nunca se inventan)

Labels canónicos: `TDR`, `draft-base`, `background`, `doc-secciones`
(ver `.claude/agents/insumos-observador.md`).

### 2.6 Camino A — Scratch (desde idea, opcional TDR)

1. Pon en `insumos/` el TDR (si existe) y papers de apoyo.
2. Ejecuta `/propuesta <idea>` (o `/propuesta-analizar` en flujo stepped).
3. Confirma clasificación del TDR si el agente marca AMBIGUA.
4. En G0.5 (solo con TDR): decide si generar guía ajustada al TDR.
   - Si el TDR **no** lista secciones obligatorias y no hay `doc-secciones`,
     G0.5 puede quedar bloqueada: aporta un `doc-secciones` o continúa con la
     guía base (`G0.5 = OMITIDA-POR-USUARIO`).
5. Aprueba gates de papers, problema, objetivos, metodología, presupuesto, etc.
6. Compila con `redaccion/build.sh` (ver §3).

Sin TDR: se omite G0.5; rige `guiaProyectosIA_Agente.md`. Presupuesto en
MODE=base si no hay marco presupuestal en TDR.

### 2.7 Camino B — Improve-from-draft (borrador existente)

1. Pon el borrador (PDF o DOCX) en `insumos/`.
2. Opcional: TDR + papers en el mismo directorio.
3. Ejecuta `/propuesta <idea>` (o `/propuesta-analizar` en flujo stepped).
4. Confirma `draft-base` si hace falta; si no hay candidato, responde a
   “¿existe un borrador previo?” nombrando el archivo.
5. El `investigador` usa el draft como **semilla primaria** de subproblemas /
   pregunta (§3), complementada por exploración bibliográfica (MODE=explore
   sigue siendo obligatoria).
6. El resto de secciones se **redactan de nuevo** en `redaccion/sections/` bajo
   la guía aplicable; no se “continúa” el PDF página a página.

Con TDR + draft (modo **both**): el TDR manda en estructura, topes y
prioridad de secciones; el draft siembra el encuadre científico.

### 2.8 Dos propuestas distintas (separación de contexto)

Solo hay **una** corrida activa a la vez, la que apunta `proposals/.current-run`.

| Qué | Cómo se separa |
|-----|----------------|
| Contenido de la propuesta | `run-id` + archivo en `proposals/<run-id>/` al archivar |
| Insumos | `insumos/` es **compartido** — limpia/reemplaza archivos entre corridas |
| Caché Engram de extracciones | Por **hash de contenido** del archivo, no por run-id |
| Memoria del chat del runtime | Nueva sesión recomendada al cambiar de propuesta |

Flujo típico A → B:

```text
1. /propuesta run-id=...-proyecto-a <idea A>   # termina o pausa
2. /propuesta-limpiar                          # cierra A (su carpeta queda intacta)
3. Reemplaza insumos/ con insumos de B
4. Nueva sesión de chat (recomendado)
5. /propuesta run-id=...-proyecto-b <idea B>
```

### 2.9 Referencias bibliográficas (existencia y corrección)

Resumen operativo (detalle en agentes `bibliografo-propuesta` y `revisor`):

1. Búsqueda en MCP reales (Consensus, OpenAlex, Semantic Scholar, etc.).
2. Ficha local `artefactos/scoping/papers/paper-N.md` (DOI, Q1/Q2, metadata).
3. Verificación de existencia (Crossref DOI / OpenAlex / S2) **antes** de
   escribir `redaccion/refs.bib`; si no resuelve → se descarta.
4. Un solo escritor de `refs.bib`: `bibliografo-propuesta`.
5. Prosa con `\citet{}` / `\citep{}` (APA author-year, natbib).
6. `revisor`: no-orphan (cada cite key → paper note) + pisos de calidad.
7. `./build.sh` → BibTeX detecta claves faltantes en el log.

---

## 3. CLI y herramientas de shell del repo

El marco **no** expone un CLI único tipo `marco-propuestas run`. Lo que sí hay
son **scripts de shell/Python** para build, portabilidad de agentes y helpers
de figuras. El pipeline multi-agente se lanza solo con **slash commands**.

### 3.1 Mapa de entrypoints

| Superficie | Qué es | Cuándo usarla |
|------------|--------|----------------|
| `/propuesta-init` | Slash | Drop zones en `insumos/` |
| `/propuesta-analizar` | Slash | Intake only; imprime siguiente comando |
| `/propuesta-continuar` | Slash | Una unidad del pipeline (stepped) |
| `/propuesta` | Slash | Pipeline completo en una sesión |
| `/propuesta-limpiar` | Slash | Archivar corrida activa y resetear workspace |
| `redaccion/build.sh` | Bash CLI | Compilar PDF / exportar DOCX / watch / clean |
| `python3 scripts/gen-opencode.py` | Python CLI | Regenerar `.opencode/` desde `.claude/` |
| `redaccion/scripts/compile_tikz.py` | Python helper | Compilar diagramas TikZ → PNG/SVG (lo usan agentes) |
| `redaccion/scripts/prep_docx.py` | Python helper | Preparar árbol LaTeX seguro para pandoc DOCX |

### 3.2 `redaccion/build.sh` — compilar la propuesta

Requisitos en PATH: `pdflatex`, `bibtex`, `latexmk`. Para `--docx`: también
`pandoc` y `pdftoppm`.

`redaccion/main.tex` **no** está en git: lo genera la Fase 7 de `/propuesta`.
Compila solo cuando ese archivo (y `sections/`, `refs.bib`) existen.

```bash
cd proposal

./build.sh              # compilación normal (latexmk → main.pdf)
./build.sh --clean      # limpia auxiliares y recompila
./build.sh --clean-only # solo limpia, no compila
./build.sh --manual     # pdflatex → bibtex → pdflatex × 2
./build.sh --watch      # recompila al detectar cambios
./build.sh --docx       # exporta main.docx vía pandoc (requiere main.pdf previo)
./build.sh --help       # ayuda
```

Flujo típico post-Fase 7:

```bash
cd proposal
./build.sh
./build.sh --docx
# salidas: main.pdf, main.docx
```

Notas:

- Estilo de citas: **natbib + apalike** (autor-año), no IEEE numérico.
- `--docx` rasteriza diagramas TikZ/pgfgantt a PNG vía `prep_docx.py` y llama
  a pandoc; algunos estilos (p. ej. sombreado de tablas) pueden no preservarse.

### 3.3 Generadores de harness (OpenCode y pi)

Fuente de verdad de agentes/comandos: **`.claude/`**.  
`.opencode/` y `.pi/` se **generan**; no se editan a mano.

```bash
# desde la raíz de marco-propuestas-ia
python3 scripts/gen-opencode.py          # escribe .opencode/
python3 scripts/gen-opencode.py --check
python3 scripts/gen-pi.py                # escribe .pi/prompts + references + skill
python3 scripts/gen-pi.py --check
```

| Exit code | Significado |
|-----------|-------------|
| 0 | OK |
| 1 | Uso incorrecto |
| 2 | Fuente/rules faltante |
| 3 | Drift encontrado (`--check`) |

- OpenCode rules: `scripts/gen-opencode.rules.json`
- pi rules: `scripts/gen-pi.rules.json` (prompts = slash `/propuesta-*`;
  subagentes despachables en `.pi/agents/`)

**pi:** abrí el repo en `pi`, confiá el proyecto para cargar `.pi/`, usá los
mismos nombres de comando. No hay subagentes anidados: el primario lee las
role cards. Gates = sesión interactiva (no `pi -p` de punta a punta).

Tras editar `.claude/agents/*` o `.claude/commands/*`:

```bash
python3 scripts/gen-opencode.py
python3 scripts/gen-pi.py
```

### 3.4 Helpers Python de build (uso normal vía agentes / build.sh)

Suelen invocarlos el pipeline o `build.sh`; puedes llamarlos a mano para
depurar:

```bash
# Compilar un diagrama TikZ (requiere pdflatex, pdftoppm, pdftocairo)
python3 redaccion/scripts/compile_tikz.py
# (lee diagramas bajo redaccion/sections/; ver cabecera del archivo)

# Preparar staging docx-safe antes de pandoc
python3 redaccion/scripts/prep_docx.py --stage /tmp/docx-stage
```

### 3.5 Python del entorno (codebase-memory y deps)

No es el entrypoint del pipeline, pero es la CLI del stack de grafo/PDF:

```bash
source .venv/bin/activate
codebase-memory --help
# codebase-memory se usa en fases de scoping/vault vía el dispatcher, no en lugar de /propuesta
```

### 3.6 Lo que **no** es un CLI de este marco

| Expectativa | Realidad |
|-------------|----------|
| `marco run --tdr file.pdf` | No existe; usa `insumos/` + slash commands |
| Pipeline sin gates (unattended) | No soportado; siempre hay aprobación humana en gates |
| `opencode run /propuesta ...` headless con gates | Gates requieren sesión interactiva |
| CLI Codex | Fuera de alcance |
| Un solo binario que haga agentes + PDF | Separado: slash commands (agentes) + `build.sh` (PDF/DOCX) |
| Reanudar a medias `redaccion/sections/*.tex` | No; draft-base = semilla + reescritura completa |

### 3.7 Proyecto portable (`marco init`)

El flujo descrito en las secciones anteriores (trabajar en la raíz del
monorepo) queda como **demo / dev kit workspace**. Para corridas reales,
el entrypoint recomendado es `marco init`, que crea una carpeta de
proyecto autocontenida, copiable y relocalizable.

**Problema:** el monorepo singleton no es copiable-relocalizable. Las
carpetas por corrida bajo `proposals/<run-id>/` guardan LaTeX parcial
pero **no** incluyen los insumos originales (`insumos/`) ni un registro
de decisiones. Mover una propuesta a otra máquina requiere reconstruir el
contexto manualmente.

**Nuevo flujo:**

```bash
marco init ~/propuestas/global-health-wellbeing-ai \
  --title "Global Health and Wellbeing in an Era of Transformative AI"
cp RFP.pdf ~/propuestas/global-health-wellbeing-ai/insumos/tdr/
$EDITOR ~/propuestas/global-health-wellbeing-ai/insumos/ideas/idea.md
cd ~/propuestas/global-health-wellbeing-ai
# abrir Claude Code / OpenCode / pi EN esa carpeta
# /propuesta-init  → re-siembra drop zones (no recrea proyecto)
# /propuesta-analizar …
```

**Contrato de portabilidad:** copiá toda la carpeta a otra máquina,
`cd` a ella y reanudá — mismo `estado_propuesta`, secciones, decisiones,
journal. Sin reescritura de rutas ni reinstalación del kit.

**`DECISIONS.md`** (en vivo): el operador y el dispatcher lo editan
durante las gates. Contiene decisiones, aclaraciones, acuerdos hacer/no
hacer y preguntas abiertas.

**`journal/`** (append-only): un archivo por evento material con nombre
`YYYYMMDD-HHMM-<evento>.md`. MVP: se siembra vacío con un
`journal/README.md` de convención; la escritura automatizada desde las
gates es fase 2.

**`marco upgrade <dir>`:** refresca solo el kit (agentes, comandos, guía,
generadores). Nunca toca `insumos/`, `redaccion/sections/`,
`DECISIONS.md`, `journal/` ni ningún contenido del operador.

**`marco status <dir>`:** imprime el estado desde
`artefactos/estado_propuesta.md` más las últimas entradas de `DECISIONS.md`
y `journal/`. Si no hay `.marco/`, advierte que no es un proyecto
portable.

**`--tools` flag:** por defecto `claude,opencode,pi`. Controla qué
runtimes se instalan. `MARCO_KIT_ROOT` puede definirse para usar una
fuente de kit distinta del monorepo actual.

**Instalación del CLI:**

```bash
# Desde la raíz de marco-propuestas-ia/
pipx install -e .           # editable (recomendado)
# which marco → ~/.local/bin/marco
```

Con `pipx install -e .`, la resolución del kit usa `__file__` y encuentra
el repositorio automáticamente. Para instalaciones no editables, definí
`MARCO_KIT_ROOT=/ruta/a/marco-propuestas-ia`. Detalle completo en
[`docs/marco-cli.md`](marco-cli.md).

**Nota:** el monorepo sigue siendo la fuente del kit (`.claude/` SSOT,
generadores, guía) y un workspace de desarrollo/demo, pero **ya no es
el runtime raíz para corridas de producción**.

Para el detalle completo de flags, entorno, manifest y flujo del CLI, ver
[`docs/marco-cli.md`](marco-cli.md).

---

## 4. Fuera de alcance (no prometido)

| Tema | Estado |
|------|--------|
| **Codex** u otro runtime distinto de Claude Code / OpenCode / pi | No soportado |
| CLI/API que reemplace `/propuesta` | No existe; entrypoint = slash command |
| Ingestión de árbol LaTeX multi-archivo como draft-base | No; usa PDF/DOCX en `insumos/` |
| Reanudación mid-run de `redaccion/sections/*.tex` (saltar a la última gate) | No implementada; “reanudar” en la guardia de colisión no es un protocolo completo |
| Configuración de idioma/branding | Por defecto español + LabIA/UNAL |

---

## 5. Referencias

- Auto (cuerpo del pipeline): `.claude/commands/propuesta.md`
- Stepped: `propuesta-init.md`, `propuesta-analizar.md`, `propuesta-continuar.md`
- Tabla de unidades: `.claude/commands/_propuesta-steps.md`
- Limpieza: `.claude/commands/propuesta-limpiar.md`
- Espejos generados: `.opencode/commands/`, `.pi/prompts/`, `.agent/workflows/` — regenerar con
  `python3 scripts/gen-opencode.py`, `python3 scripts/gen-pi.py`, `python3 scripts/gen-antigravity.py`
- Clasificación de insumos: `.claude/agents/insumos-observador.md`
- Bibliografía: `.claude/agents/bibliografo-propuesta.md`, `revisor.md`
- Playbook: `AGENTS.md`
- Dependencias: `REQUIREMENTS.md`, `requirements.txt`
- Flujo visual: [`pipeline-flow.md`](./pipeline-flow.md)
- Build: `redaccion/build.sh`
