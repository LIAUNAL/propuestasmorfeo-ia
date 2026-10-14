# Playbook: Marco de Redacción de Propuestas de Investigación en IA

Este playbook rige el comportamiento de todos los agentes del marco multi-agente
de redacción de propuestas.

**Runtime canónico: Claude Code.** El **asistente primario de Claude Code**
es el dispatcher real del pipeline: usa la herramienta `Task` para despachar
cada fase al subagente correspondiente definido en `.claude/agents/`.

**Slash commands:**

| Comando | Rol |
|---------|-----|
| `/propuesta-init` | Crea y activa la carpeta de la corrida (`proposals/<run-id>/`) |
| `/propuesta-insumos` | Zonas de depósito dentro de `insumos/` (incl. `ideas/`) |
| `/propuesta-analizar` | Intake (Fase 0 + G0.5); idea desde args o `ideas/`; para antes de scoping |
| `/propuesta-continuar` | Una unidad del pipeline (`next_step`); imprime el siguiente comando |
| `/propuesta` | Pipeline completo en una sesión (gates) |
| `/propuesta-limpiar` | Cierra la corrida activa |
| `/compilar-pdf` | Compila la corrida activa a PDF (`build.sh` en `redaccion/`) |
| `/compilar-docx` | Exporta la corrida activa a Word (`build.sh --docx` en `redaccion/`) |

Cuerpo del pipeline: `.claude/commands/propuesta.md`. Tabla de unidades y
control de ejecución: `.claude/commands/_propuesta-steps.md`. El archivo
`.claude/agents/coordinador-propuesta.md` es la **referencia canónica** del
pipeline y de las dependencias de despacho —no es un subagente activo, porque
los subagentes de Claude Code no pueden invocar a otros subagentes. El agente
**Revisor** valida en cada **puerta de revisión (gate)** antes de avanzar.

## Proyecto portable

Cuando el CWD contiene `.marco/version`, el runtime está dentro de un
proyecto portable creado con `marco init`. En ese modo:

- **`RUN_ROOT` se resuelve igual que en el repo** (ver regla 7): el proyecto
  portable trae su propio `plantilla/`, `scripts/init-run.sh` y `proposals/`,
  así que las corridas viven en `proposals/<run-id>/` con las mismas cuatro
  subcarpetas. Los agentes no necesitan reescritura de rutas.
- **`/propuesta-init`** crea la corrida ahí igual que en el repo, y
  **`/propuesta-insumos`** re-siembra las zonas de depósito dentro de
  `insumos/`. Usá `marco init` solo para crear el proyecto portable en sí.

Referencia completa del CLI (comandos, flags, entorno, manifest) en
[`docs/marco-cli.md`](docs/marco-cli.md).

## Reglas globales

1. **Idioma:** Los *system prompts* de los agentes están en inglés, pero toda
   la **salida del documento (propuesta) debe redactarse en español**.
2. **Insumos:** La propuesta se construye desde un prompt/idea del usuario más
   PDFs, papers, enlaces o información relevante que este aporte. Los archivos
   fuente (PDFs, papers, propuestas previas, documentos de referencia) se
   guardan en `insumos/` de la corrida (ver regla 7), planos o repartidos en
   zonas de depósito (`tdr/`, `draft/`, `background/`, `doc-secciones/`,
   `ideas/`) que `/propuesta-insumos` prepara. El agente
   **Insumos-Observador** los descubre de forma recursiva y extrae/estructura
   esos insumos en un contexto compartido (`idea-seed` para notas en `ideas/`).
3. **Enfoque:** Productos/servicios de IA con innovación investigativa,
   transferencia tecnológica clara, productos tangibles con **TRL 6 o 7**.
4. **Estructura:** Sigue rigurosamente las 16 secciones de la
   `guiaProyectosIA_Agente.md`. No omitas ni renumeres secciones. **Regla de no
   inclusión de §1 en el cuerpo de `main.tex`:** El título y la identificación
   institucional se compilan exclusivamente en el bloque de encabezado/portada
   (`\begin{center} ... \end{center}`) de `main.tex`. Nunca se incluye una
   sección numerada de cuerpo ni archivo `sections/01_titulo_identificacion.tex`;
   el cuerpo numerado arranca directamente tras el front-matter en §2 Justificación y
   pertinencia (`\setcounter{section}{1}`).
5. **Dependencias cruzadas y articulación institucional (obligatorias):**
   - Los 3 subproblemas (§3) ↔ 3 objetivos específicos (§7), mapeo 1:1.
   - La pregunta de investigación (cierre §3) ↔ objetivo general (§6).
   - La hipótesis (§5) ↔ objetivo general (§6).
   - Metodología (§10) ↔ objetivos específicos (§7), marco conceptual (§8) y
     equipo de trabajo (§9), cadena de valor. El punto 2 de Metodología nombra
     el enfoque/algoritmo por subproblema con razonamiento causa-efecto
     explícito referenciando el marco conceptual (§8) — función que antes
     cubría el desaparecido §5.3 Enfoques teóricos.
   - Equipo de trabajo (§9) deriva sus roles de los objetivos específicos
     (§7); nunca de la Metodología (§10).
   - Cronograma de actividades (§14) ↔ fases de la Metodología (§10).
   - Resultados esperados (§11) ↔ productos entregados en hitos del
     cronograma (§14).
   - Presupuesto (§13) ↔ Metodología (§10) y Cronograma (§14) —referencia
     hacia adelante válida, ya que Presupuesto se redacta antes que Cronograma
     en el pipeline pero ambos referencian las mismas fases de Metodología.
   - TRL 6 o 7 debe ser explícito en pertinencia (§2) y resultados esperados
     (§11); **nunca** se nombra en objetivo general (§6) ni en objetivos
     específicos (§7).
   - Alianza territorial y cohortes: La articulación interinstitucional entre la
     Universidad Nacional de Colombia Sede Manizales y la Universidad
     Tecnológica de Pereira (UTP) en el Eje Cafetero vincula una cohorte por
     conveniencia de 80 estudiantes (`EST-MZ-xxx` y `EST-PE-xxx`), con
     pruebas de campo y captura en ambos campus.
   - Tabla 4 de productos esperados (§15): Usa `\usepackage{xltabular}` y el
     entorno `xltabular` con encabezados de continuación para evitar
     desbordes de página (`Float too large`).
6. **Calidad bibliográfica:** ≥10 refs Q1/Q2 para §2 Justificación y
   pertinencia (mínimo 6 párrafos); ≥30 refs Q1/Q2 (≤3 años) para §4 Estado
   del arte; ≥50 refs totales para §16 Bibliografía; formato **APA
   author-year únicamente** (natbib+apalike, `\citet{}`/`\citep{}`) — el
   estilo numérico IEEE (`[1]`) está prohibido, conforme a
   `guiaProyectosIA_Agente.md` §16 Bibliografía. Sin tesis; preprints solo de
   labs/líderes reconocidos. En `16_bibliografia.tex`, se incluye `\clearpage`
   y `\renewcommand{\bibsection}{}` para suprimir el título redundante
   "Referencias" que `natbib` inserta por defecto.
7. **Carpeta de proyecto por corrida (`RUN_ROOT`):** cada corrida vive en
   **una sola carpeta**, `proposals/<run-id>/`, creada por `/propuesta-init`
   (que delega en `scripts/init-run.sh`, determinista e idempotente) y
   activada mediante el puntero `proposals/.current-run`. Dentro hay
   exactamente **cuatro subcarpetas**, y nada queda suelto en la raíz de la
   corrida salvo `_run.md`:

   | Subcarpeta | Contenido | La llena |
   |---|---|---|
   | `insumos/` | Insumos del usuario: TDR, papers, propuestas base, documentos de referencia | el usuario |
   | `artefactos/` | Lo generado que no es fuente LaTeX: `estado_propuesta.md`, `insumos.md`, `guia_ajustada_TDR.md`, `pipeline/`, `scoping/papers/`, `vault/` | el pipeline |
   | `grafos/` | Reportes de `codebase-memory`: `papers-graph-report.md`, `vault-graph-report.md` | el dispatcher |
   | `redaccion/` | El proyecto LaTeX: `main.tex`, `sections/`, `refs.bib`, `main.pdf`, `main.docx`, `build.sh`, `scripts/`, `logos/`, `templates/` | el pipeline |

   Toda ruta `insumos/...`, `artefactos/...`, `grafos/...` o `redaccion/...` que
   aparezca en este playbook, en los agentes o en el dispatcher se resuelve
   **dentro de `RUN_ROOT`**, nunca en la raíz del repo; las únicas rutas
   relativas a la raíz son las del framework (`.claude/`, `.opencode/`,
   `.pi/`, `scripts/`, `guiaProyectosIA_Agente.md`, `AGENTS.md`,
   `plantilla/`, `proposals/`). Ninguno de los cuatro nombres de subcarpeta
   colisiona con un directorio del repo, así que una ruta de corrida nunca es
   ambigua. Archivar una corrida es solo un cambio de estado en su `_run.md` y en el
   registro local `proposals/registry.md`: la carpeta ya **es** el archivo, no
   se copia ni se borra contenido. **Nada bajo `proposals/` se versiona**
   —corridas, registro y puntero incluidos—, así que ni crear ni cerrar una
   corrida produce cambios en git; `scripts/init-run.sh` recrea lo que falte,
   por lo que borrar `proposals/` es seguro. El esqueleto LaTeX versionado vive en `plantilla/` y es lo
   único que `init` copia a `redaccion/`; la raíz del repo nunca recibe
   artefactos de una corrida.
8. **Salida LaTeX:** Cada sección se escribe como archivo `.tex` en
   `redaccion/sections/`; referencias en `redaccion/refs.bib`; ensamblaje en
   `redaccion/main.tex`. El template `main.tex` incluye un footer con los
   logos institucionales (`redaccion/logos/`: LabIA, UNAL, GCPDS) vía
   `fancyhdr`; los agentes no deben eliminarlo. `redaccion/` es la **fuente de
   verdad** dentro de una corrida, pero **no está versionada**: `.tex`/`.bib`/`.pdf`/`.docx`
   y el resto del contenido de la corrida están en `.gitignore` (igual que
   las corridas archivadas bajo `proposals/<run-id>/`) — GitHub solo aloja el
   esqueleto del framework (agentes, comandos, scripts, plantillas), nunca
   el contenido de una propuesta específica. **Tipografía y jerarquía de tamaños de letra:**
   El documento base se compila en `11pt` (`\documentclass[11pt,a4paper]{article}`,
   un tamaño menor que el estándar de 12pt). Los títulos se configuran con dos tamaños menos:
   el título principal del proyecto en la portada/encabezado usa `\Large\bfseries`
   (reducido dos tamaños frente a los 20.7pt de `\LARGE`), las secciones de cuerpo (`\section`)
   usan `\large\bfseries` (12pt, dos tamaños menos frente a los 17.3pt de `\Large`) mediante
   `\usepackage{sectsty}` (`\sectionfont{\large\bfseries}`), las subsecciones (`\subsection`)
   usan `\normalsize\bfseries` (`\subsectionfont{\normalsize\bfseries}`) y las subsubsecciones
   (`\subsubsection`) usan `\normalsize\bfseries` (`\subsubsectionfont{\normalsize\bfseries}`).
9. **Espejo `artefactos/vault/`:** `artefactos/vault/secciones/` y
   `artefactos/vault/insumos/` son un espejo Markdown compatible con Obsidian,
   generado a partir de `redaccion/` para navegación y coherencia — **no** se
   versiona por separado ni se trata como fuente de verdad. Ante cualquier
   conflicto entre `artefactos/vault/` y `redaccion/`, `redaccion/` (LaTeX)
   manda.
10. **Grafo de conocimiento (`codebase-memory`):** la capa de grafo es el
   servidor MCP `codegraph` declarado en `.mcp.json` (`codegraph serve
   --mcp`), no una CLI ni una API key. El dispatcher mantiene dos índices por
   corrida — `<run-id>-papers` sobre `artefactos/scoping/papers` y
   `<run-id>-vault` sobre `artefactos/vault` — y escribe los reportes
   derivados en `grafos/papers-graph-report.md` y
   `grafos/vault-graph-report.md`. Dos restricciones verificadas
   fijan esa forma: `codegraph` respeta `.gitignore` (y todo el contenido de
   una corrida está gitignoreado), así que cada corpus se indexa **como raíz
   propia** con `repo_path` absoluto; y las negaciones `!ruta` de `.cbmignore`
   no revierten `.gitignore`, aunque `.cbmignore` sí sirve para excluir ruido
   dentro del corpus. `codebase-memory` no exporta HTML ni crea edges de
   `[[wikilink]]`: el artefacto **citable en las compuertas** es el reporte
   Markdown, los wikilinks rotos se detectan con `Grep`, y el **gemelo visual
   navegable** lo produce el marco con `scripts/graph_html.py` a partir de un
   JSON que escribe el dispatcher (`grafos/<corpus>-graph.html`). Detalle
   completo en "Cómo usar `codebase-memory`" de
   `.claude/commands/propuesta.md`.
11. **Captions de tablas y figuras:**
   - Todo caption (`\caption{...}` o `\caption[...]{...}`) debe ser **concreto, informativo y humanizado** aplicando estrictamente la skill `estilo-natural-es`.
   - Se prohíben las descripciones mecánicas o meta-visuales vacías (por ejemplo, evitar explicaciones como "las barras azules son las actividades y los rombos rojos los hitos" o "las raíces agrupan causas y el tronco el problema central"). En su lugar, el caption debe enunciar el contenido científico y metodológico real: el objeto del estudio, los grupos temáticos, la articulación con los objetivos específicos, las responsabilidades operativas o los mecanismos de transferencia con la comunidad de interés.
   - Prohibición estricta de rayas anglosajonas (` — `) o dobles guiones (`--`).
   - Se mantiene la sintaxis `\caption[Título corto]{Descripción concreta}` para figuras y `\caption{Descripción concreta}` para tablas, conservando siempre las etiquetas `\label{...}` intactas.
   - Esta regla rige para `redactor`, `disenador-tikz`, `revisor-figuras`, `presupuestador`, `coordinador-propuesta`, `grant-flow-auditor` y cualquier agente que proponga o audite tablas y figuras.
12. **Autonomía e independencia de herramientas de memoria externa (Engram):**
   - El marco, sus flujos de trabajo, las skills, las restricciones y los agentes son **100% autónomos y portables en disco** (`insumos/`, `artefactos/`, `redaccion/`, `specs/`).
   - Ninguna fase, comando, validación ni regla depende de forma obligatoria de Engram. Si Engram está instalado y configurado en el entorno local, puede utilizarse como acelerador opcional de caché o espejo pasivo; si no está disponible (en otros equipos, entornos sin Engram o al usar otros agentes CLI como Pi, OpenCode, Antigravity o Claude Code básico), el pipeline opera de manera completa, determinista y sin errores.

## Roster de agentes (`.claude/agents/`) y modelos por defecto

El marco tiene **11 agentes**, todos definidos en `.claude/agents/` (fuente de
verdad):

| Agente | Modelo por defecto | Rol |
|--------|--------------------|-----|
| `coordinador-propuesta` | sonnet | Referencia canónica del pipeline (no despachable como subagente activo) |
| `investigador` | opus | Subproblemas, pregunta, objetivos, hipótesis, marco conceptual |
| `redactor` | opus | Secciones narrativas (§2, §9–§12, §14–§15, §17–§18 y front-matter) |
| `grant-flow-auditor` | sonnet | Auditoría micro-estilística de prosa: cadencia, voz activa, transiciones y fricción en secciones, subsecciones o secciones modificadas; aplica la skill `estilo-natural-es` |
| `insumos-observador` | sonnet | Ingesta y estructuración de insumos del usuario |
| `bibliografo-propuesta` | sonnet | Bibliografía (§4, §16) |
| `revisor` | sonnet | Validación de coherencia/calidad en cada gate |
| `presupuestador` | sonnet | Presupuesto (§13): tabla de rubros + aritmética + cofinanciación |
| `disenador-tikz` | sonnet | Autoría de la **spec JSON** de los diagramas (nunca del LaTeX) |
| `revisor-figuras` | sonnet | Juicio visual (escala, centrado, armonía, etiquetas) sobre el preview PNG ya auditado |
| `tikz-optimizer` | sonnet | Corrección de la spec cuando la auditoría determinista falla |

No existen agentes llamados `orquestador`, `observador` (a secas) ni
`bibliotecario`; esos nombres no forman parte de este marco.

## Skills del marco (`.claude/skills/`)

Además de los agentes, el marco tiene **skills** (metodologías reutilizables
que un agente carga cuando la tarea lo pide), con la misma fuente de verdad
`.claude/` y el mismo régimen de ports generados:

| Skill | Para qué | La usa |
|-------|----------|--------|
| `estilo-natural-es` | Pulir y humanizar la prosa narrativa y científica en español (norma académica culta de Colombia): erradica 35 patrones de IA (aperturas cósmicas, gerundios de cierre, inflación de trascendencia, falsos rangos, regla de tres, monotonía de ritmo), prohíbe rayas anglosajonas (` — `) o dobles guiones (`--`), varía la cadencia oracional (burstiness) y aplica la regla 70/30 de vocabulario, con fidelidad estricta de cifras, fechas, presupuestos y citas BibTeX APA autor-año. No es una herramienta de evasión: no introduce errores tipográficos, imprecisión deliberada ni registro coloquial. | `grant-flow-auditor` (antes de cada `revisor`), `redactor`, `investigador` **y el asistente primario en toda prosa en español que redacte** |
| `depuracion-redundancias-es` | Auditar y eliminar redundancias conceptuales, léxicas y estructurales dentro de una misma sección, asegurando que cada párrafo aporte avance argumentativo y articulando la aplicación integral de `estilo-natural-es` (humanización y ritmo). | `grant-flow-auditor`, `redactor`, `investigador` y el asistente primario en revisiones integrales de texto |

La skill canónica vive en `.claude/skills/estilo-natural-es/SKILL.md` y de ahí
se porta de forma determinista: `.pi/skills/` (Pi) y `.agent/skills/`
(Antigravity) los genera `scripts/gen-pi.py` y `scripts/gen-antigravity.py`;
OpenCode la descubre directamente desde `.claude/skills/` (no se duplica en
`.opencode/skills/` para no provocar un aviso de nombre duplicado). Toda skill
nueva se agrega primero en `.claude/skills/`, luego a `scripts/kit-manifest.json`
y a los generadores, y se regeneran los ports con su `--check`.

### La skill `estilo-natural-es` es obligatoria en toda prosa en español

**Alcance.** Pasa por ella cualquier prosa en español que el marco produzca. Eso
incluye las secciones de la propuesta (§1–§18 y el front-matter) y también los
artefactos que el asistente primario redacta por su cuenta: `LEEME`, documentos
de `odd/tasks/`, guías, reportes y notas de corrida.

**Mecánica, según quién escriba.**

| Quién escribe | Cómo se aplica |
|---|---|
| `redactor` o `investigador` producen una sección | Redactan aplicando los principios de la skill; `grant-flow-auditor` audita y pule **antes** del `revisor`. El orden no es negociable: si el auditor edita después de un PASS, ese PASS queda invalidado y la revisión se repite sobre el texto final |
| El asistente primario redacta documentación en español | Aplica la skill **antes de escribir**. El texto sale ya pulido, en lugar de corregirse después |

**Qué queda fuera.** Entradas BibTeX, tablas de LaTeX, la tabla de presupuesto
(§13), el Gantt (§14), el código TikZ, las enumeraciones que la guía exige
(objetivos específicos, rubros, productos esperados) y todo texto en inglés. La
skill mejora la cadencia; no reescribe contenido, no inventa datos y no mueve una
cifra, una fecha ni una clave de cita.

**Invariantes de estilo del documento (obligatorios):**
- **Tipografía y jerarquía:** Compilado en `11pt` (`\documentclass[11pt,a4paper]{article}`). Títulos dos tamaños menos: título principal en encabezado `\Large\bfseries`, secciones de cuerpo `\large\bfseries`, subsecciones y subsubsecciones `\normalsize\bfseries`.
- **Logos institucionales:** En el pie de página mediante `fancyhdr` con los logos oficiales (`redaccion/logos/`: LabIA, UNAL, GCPDS).
- **Prohibición de rayas anglosajonas y dobles guiones:** Queda terminantemente prohibido el uso de `--` o ` — ` en la prosa narrativa. Los incisos se resuelven con comas, punto y coma o paréntesis.
- **Formato de citación:** APA autor-año natbib exclusivamente (`\citet{}`, `\citep{}`); el estilo numérico IEEE está prohibido.
- **Estructura fija:** Los párrafos requeridos por la guía (ej. los 6 de §2) y el mapeo 1:1 (3 subproblemas ↔ 3 objetivos específicos) son inalterables.

**Por qué la regla vive aquí y no solo en el pipeline.** Mientras fue un paso del
pipeline, cubría las secciones de la propuesta y dejaba fuera todo lo demás que
se escribe en español. Un `LEEME` o un documento de tareas sin pasar por la skill
tiene la misma textura mecánica que la skill existe para quitar.

## Flujo del pipeline (interactivo, con gates)

```
Paso previo  `/propuesta-init <idea>` → crea y activa `proposals/<run-id>/`
        (`RUN_ROOT`) con sus cuatro subcarpetas: insumos/ artefactos/ grafos/
        redaccion/. El usuario deja sus insumos en `insumos/`.
Fase 0  Insumos-Observador → ingerir insumos
Fase 1  Investigador → §3 descripción del problema + pregunta
        → Grant-Flow-Auditor (pule §3 con estilo-natural-es)
        → Bucle de figura `arbol_problemas` (procedimiento canónico único, ver
          "Bucle de figuras" abajo):
            Diseñador-TikZ (autor de `specs/arbol_problemas.spec.json`)
            → `python3 scripts/figura.py arbol_problemas` (determinista, ~1 s:
              render → compile → autofix de overflow → auditoría mecánica)
            → con `FIGURA PASS`, Revisor-Figuras audita SOLO los 4 criterios
              visuales sobre el preview PNG (PASS/FAIL)
            → en FAIL (spec, auditoría o visual), vuelve a Tikz-Optimizer, que
              corrige la SPEC (nunca el .tex); tope compartido de 4 intentos,
              con escalamiento explícito al usuario al agotarse
            → en PASS, continúa
        ──→ GATE Revisor ──→ user
Fase 2  Bibliografo-Propuesta → §4 estado del arte (paralelo)
        Investigador → §5 hipótesis
        → Grant-Flow-Auditor (pule §4 y §5 con estilo-natural-es)
        → Bucle de figura `<name>` = `estado_arte` (o `estado_arte_a` + `estado_arte_b`)
        ──→ GATE Revisor ──→ user
Fase 3  Redactor → §2 justificación y pertinencia
        → Grant-Flow-Auditor (pule §2 con estilo-natural-es)
        ──→ GATE Revisor ──→ user
Fase 4  Investigador → §6 objetivo general + §7 objetivos específicos
        → Grant-Flow-Auditor (pule §6 y §7 con estilo-natural-es)
        ──→ GATE Revisor (subproblema↔objetivo específico; valida también hipótesis↔objetivo general) ──→ user
Fase 5  Investigador → §8 marco conceptual (paralelo)
        Redactor → §9 equipo de trabajo (deriva roles de §7, nunca de Metodología)
        → Grant-Flow-Auditor (pule §8 y §9 con estilo-natural-es)
        ──→ GATE Revisor ──→ user
Fase 5.5 Redactor → §10 metodología
        → Grant-Flow-Auditor (pule §10 con estilo-natural-es)
        → Bucle de figura `<name>` = `metodologico`
        ──→ GATE Revisor ──→ user
Fase 6  Redactor → §11 resultados esperados; §12 consideraciones éticas
        → Grant-Flow-Auditor (pule §11 y §12 con estilo-natural-es) (sin gate propio)
Fase 6.4  Presupuestador → §13 presupuesto (interactivo) ──→ GATE Revisor ──→ user
Fase 6.45 Redactor → §14 cronograma de actividades (Gantt); §15 productos esperados (xltabular)
          Bibliografo-Propuesta → §16 bibliografía (BibTeX, con \renewcommand{\bibsection}{})
          → Grant-Flow-Auditor (pule §14 y §15 con estilo-natural-es) (sin gate propio)
Fase 6.46 Redactor → §17 articulación comunitaria; §18 apropiación social
          → Grant-Flow-Auditor (pule §17 y §18 con estilo-natural-es)
          ──→ GATE Revisor ──→ user
Fase 6.5  Redactor → front-matter (Resumen, Resumen ejecutivo, Palabras clave);
          el título e identificación van exclusivamente en el encabezado de `main.tex` (sin sección de cuerpo §1)
          → Grant-Flow-Auditor (pule front-matter con estilo-natural-es)
          ──→ GATE Revisor ──→ user
Fase 7  Revisor → auditoría final integral ──→ user;
        Coordinador-Propuesta → ensambla main.tex (con \setcounter{section}{1}, xltabular y bibliografía limpia)
```

En cada **GATE**, el asistente primario de Claude Code (siguiendo la
referencia de `coordinador-propuesta`) **detiene** el flujo y espera
aprobación del usuario antes de avanzar. El Revisor devuelve PASS/FAIL +
correcciones. Cada cierre de gate agrega además un punto de costo/tiempo
(tokens, tool-uses, duración) al resumen presentado al usuario, acumulado
por fase a partir del bloque `<usage>` de cada `Task` delegado — ver
"Telemetría de uso por fase" en `.claude/commands/propuesta.md` para el
detalle completo del cálculo y persistencia(`artefactos/pipeline/_estado.md`).

## Bucle de figuras (determinista)

Los tres diagramas (árbol de problemas §3, mapa de estado del arte §4, diagrama
metodológico §10) **no se dibujan a mano**. La geometría la calcula un script:
el modelo escribe solo la **spec JSON** con el contenido, y
`scripts/render_tikz.py` deriva de ahí `sections/diag_<name>.tex` con anchos que
caben el token más largo, columnas equiespaciadas, anclas reales en cada
extremo, la paleta institucional y los tamaños canónicos.

```bash
python3 scripts/figura.py <name> --spec specs/<name>.spec.json
```

Ese único comando hace render → compilación a PNG/SVG/preview → autofix
determinista de `Overfull \hbox` → auditoría mecánica, y sale con código
distinto de cero si supera su presupuesto de 180 s.

**El bucle es determinista y el veredicto visual queda fuera de él.** Un fallo
mecánico (spec inválida, autofix que no converge, compilación, auditoría) se
corrige con `tikz-optimizer`, que edita **la spec** —nunca el `.tex`, que es
salida generada y se sobrescribe en el siguiente render— y consume uno de los 4
intentos por diagrama. Cuando el bucle cierra con PASS, se pide **una sola vez**
el juicio que un script no puede dar (escala, centrado, armonía, etiquetas)
sobre `fig_<name>-preview.png`; un FAIL ahí no reabre el bucle: dispara una
remediación acotada y, si esa también falla, escala al usuario. Y si esa llamada
no devuelve reporte o supera 240 s, no se re-despacha: se registra el PASS
determinista y se deja constancia de que el veredicto visual **no se obtuvo**
(nunca se asume verificado).

Esto es deliberado: la auditoría mecánica cubre 17 criterios en milisegundos,
incluida una medición de legibilidad (el tamaño impreso del texto más pequeño) y
el tamaño físico de la figura, de modo que la única llamada a modelo del bucle
sea corta y acotada. En la corrida de referencia, un `revisor-figuras` que leía
el raster de 200 DPI y re-derivaba los criterios mecánicos tardó 4,2 min y
consumió 10 tool-uses.

El procedimiento completo y el contador de intentos (4 por diagrama, por
corrida) están definidos **una sola vez** en la sección "Bucle de figuras
(canónico)" de `.claude/commands/propuesta.md`; las Fases 1, 2 y 5.5 la
referencian. No reimplementes el bucle por fase.

Medido en la corrida `2026-09-tept-depresion-ia-portable`: el bucle anterior
costaba **~28,8 min por figura** (tres despachos de agente y tres fallos de
`disenador-tikz` sin reporte por agotar su presupuesto de salida razonando); el
actual cuesta **menos de 1 s** en el caso limpio y ~2,5 s en el peor caso de
autofix.

## Anexos administrativos de una convocatoria

Los anexos obligatorios (§8.6 del TDR y los propios de una alianza) se redactan
en **Markdown** en `artefactos/anexos/` —versionables, diffeables y revisables— y
de ahí se derivan los **PDF de radicación** con:

```bash
redaccion/scripts/anexos_a_pdf.sh <RUN_ROOT>/artefactos/anexos
```

El script (parte del kit, instalado por `marco init`) usa pandoc + xelatex y toma
tres decisiones deliberadas, todas porque el PDF es el documento que alguien firma:

- **Membrete de borrador en cada página.** Un anexo sin firmar y con datos por
  completar no puede parecerse al documento radicable.
- **Guillemets en lugar de los `⟨…⟩` del Markdown.** U+27E8/U+27E9 no existe en
  las fuentes instaladas y se imprimía como un cuadro vacío. El `.md` **no** se
  modifica: la sustitución ocurre en la copia temporal que consume pandoc.
- **Saltos de línea duros.** La prosa de una carta no envuelve (cada párrafo es
  una línea larga), pero la fecha, el destinatario y las líneas de firma sí usan
  un salto por línea; sin esa extensión pandoc los une en un párrafo corrido.

El §8.6 exige **máximo 2 MB por archivo**; el script avisa si alguno lo supera.
Antes de radicar hay que quitar de cada documento su sección interna de datos por
completar.

## Dispatch directo de agentes de propuesta

El **asistente primario de Claude Code** puede despachar directamente
cualquier subagente de propuesta para tareas puntuales —arreglar figuras,
revisar una sección, actualizar bibliografía, refinar objetivos— **sin pasar
por el pipeline completo de `coordinador-propuesta`**. El pipeline completo de
16 secciones con gates sigue `/propuesta` o el
flujo stepped `/propuesta-analizar` + `/propuesta-continuar`.

| Agente | Cuándo despacharlo directamente |
|--------|--------------------------------|
| `disenador-tikz` | Crear o rediseñar la spec JSON de un diagrama |
| `revisor-figuras` | Emitir juicio visual sobre una figura ya auditada (preview PNG) |
| `tikz-optimizer` | Corregir la spec de un diagrama cuyo `figura.py` falla |
| `investigador` | Definir/refinar subproblemas, pregunta, objetivos, hipótesis, marco conceptual |
| `redactor` | Redactar o revisar secciones narrativas (§2, §9–§12, §14–§15, §17–§18 y front-matter) |
| `revisor` | Validar coherencia y calidad de secciones ya redactadas |
| `grant-flow-auditor` | Auditar micro-estilo de prosa ya redactada (cadencia, voz activa, transiciones) y aplicar el pulido `estilo-natural-es` antes del `revisor` |
| `bibliografo-propuesta` | Construir o actualizar la bibliografía (§4, §16) |
| `insumos-observador` | Ingerir y estructurar insumos del usuario (PDFs, papers) |
| `presupuestador` | Construir o ajustar el presupuesto (§13): rubros, montos, cofinanciación |

Cuando despaches un agente de propuesta directamente, incluye en el prompt
todo el contexto necesario (sección asignada, artefactos clave, dependencias
cruzadas) ya que el agente no tiene el estado del pipeline que el
`coordinador-propuesta` mantiene.

## Guía completa de redacción

La guía autoritativa sección por sección (con instrucciones de párrafo a
párrafo, verbos rectores, parámetros de calidad y volumen bibliográfico) vive
en `guiaProyectosIA_Agente.md`. Todos los agentes consultan su sección
asignada — el dispatcher la lee una sola vez por corrida y le inyecta a cada
Task solo el fragmento correspondiente (`## FRAGMENTO DE GUÍA`, ver
`.claude/commands/propuesta.md`); ningún subagente relee el archivo completo
por su cuenta, salvo la auditoría final de Fase 7. Resumen de asignación:

| Sección | Agente responsable |
|---------|--------------------|
| Ingesta insumos | Insumos-Observador |
| §1 Título | Redactor |
| §2 Justificación y pertinencia | Redactor |
| §3 Descripción del problema + pregunta de investigación | Investigador |
| §4 Estado del arte | Bibliografo-Propuesta |
| §5 Hipótesis | Investigador |
| §6 Objetivo general | Investigador |
| §7 Objetivos específicos | Investigador |
| §8 Marco conceptual | Investigador |
| §9 Equipo de trabajo | Redactor |
| §10 Metodología | Redactor |
| Diagramas (spec JSON del árbol de problemas, mapa de estado del arte, diagrama metodológico) | Diseñador-TikZ |
| Auditoría visual de figuras (los 4 criterios que un script no puede dar) | Revisor-Figuras |
| Corrección de la spec de un diagrama cuando `figura.py` falla | Tikz-Optimizer |
| §11 Resultados esperados | Redactor |
| §12 Consideraciones éticas | Redactor |
| §13 Presupuesto | Presupuestador |
| §14 Cronograma de actividades | Redactor |
| §15 Productos esperados | Redactor |
| §16 Bibliografía | Bibliografo-Propuesta |
| Front-matter (Resumen, Resumen ejecutivo, Palabras clave) | Redactor |
| Revisión de coherencia y calidad | Revisor |
| Coordinación del pipeline de propuesta | Coordinador-Propuesta |

> **Runtime canónico:** Claude Code (`.claude/agents/` +
> `.claude/commands/`) es la **fuente de verdad** de este marco.
> El asistente primario de Claude Code despacha el pipeline completo vía
> `/propuesta`, o por unidades con el flujo por pasos
> (`/propuesta-analizar` → `/propuesta-continuar`), y puede además despachar
> directamente cualquier subagente de propuesta para tareas puntuales (ver
> sección "Dispatch directo" arriba).
> **OpenCode**, **Pi** y **Google Antigravity** son runtimes secundarios
> soportados, todos generados de forma determinista y zero-LLM desde las
> fuentes de Claude Code:
> - OpenCode: `scripts/gen-opencode.py` → `.opencode/agents/` + commands
> - Pi: `scripts/gen-pi.py` → `.pi/agents/` (subagentes despachables con
>   `subagent_run`; verificado con `subagent_list_agents`) + `.pi/prompts/`
> - Antigravity: `scripts/gen-antigravity.py` → `.agent/skills/` (skills de agentes y slash commands nativos) + `.agent/workflows/`
>
> `gen-opencode.py`, `gen-pi.py` y `gen-antigravity.py` aceptan `--check` (dry-run,
> exit≠ 0 si el puerto quedó desfasado o si hay drift).
> Los archivos `.claude/` siguen siendo la única fuente editada a mano; tras
> cambiar agentes o comandos, correr los generadores y su `--check`.
