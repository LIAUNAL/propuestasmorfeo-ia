# Workflow: propuesta

> Inicia el pipeline multi-agente de redacción de una propuesta de investigación en IA a partir de la idea del usuario y sus insumos.

El usuario quiere redactar una propuesta de investigación en IA siguiendo el
marco multi-agente descrito en `AGENTS.md` y en la referencia canónica del
pipeline, `.agent/skills/coordinador-propuesta/SKILL.md`. **Tú, el asistente
primario, eres el dispatcher real** de este pipeline: `coordinador-propuesta`
es documentación de referencia, no un subagente activo, porque los subagentes
de Antigravity se orquestan vía plataforma (definiendo o invocando subagentes que cargan las skills de `.agent/skills/`)
para despachar cada fase al subagente correspondiente en `.agent/skills/`.

Entrada del usuario:

$ARGUMENTS

## Raíz de corrida (`RUN_ROOT`) — lee esto antes de escribir cualquier archivo

Todos los artefactos de una corrida viven en **una sola carpeta de proyecto**,
`proposals/<run-id>/`, repartidos en exactamente **cuatro subcarpetas**. Nada
queda suelto en la raíz de la corrida salvo `_run.md`, que describe la carpeta
misma.

| Subcarpeta | Qué contiene | Quién escribe ahí |
|---|---|---|
| `insumos/` | Insumos del usuario: TDR, papers, propuestas base, documentos de referencia. | El usuario. El pipeline solo lee. |
| `artefactos/` | Todo lo que el pipeline genera y **no** es fuente LaTeX: `estado_propuesta.md`, `insumos.md`, `guia_ajustada_TDR.md`, `pipeline/` (log de fases/compuertas), `scoping/papers/` (corpus), `vault/` (espejo Obsidian). | El dispatcher y los subagentes. |
| `grafos/` | Reportes de `codebase-memory`: `papers-graph-report.md`, `vault-graph-report.md` y sus snapshots. | Solo el dispatcher. |
| `redaccion/` | El proyecto LaTeX: `main.tex`, `sections/`, `refs.bib`, `main.pdf`, `main.docx`, más el tooling de build (`build.sh`, `scripts/`, `logos/`, `templates/`). | Los subagentes que escriben secciones. |

En TODO este documento, cualquier ruta que empiece por `insumos/`, `artefactos/`,
`grafos/` o `redaccion/` se resuelve **dentro de `RUN_ROOT`**, no en la raíz
del repo. Las únicas rutas literalmente relativas a la raíz son las del
framework: `.claude/`, `scripts/`, `guiaProyectosIA_Agente.md`, `AGENTS.md`,
`plantilla/` y `proposals/` (esta última contiene las corridas, su registro
local y el puntero de corrida activa, y no se versiona). Ninguno de los cuatro
nombres de subcarpeta colisiona con un directorio del repo, así que una ruta de
corrida nunca es ambigua.

Resolución de `RUN_ROOT`, en este orden exacto:

1. Si existe `proposals/.current-run`, `RUN_ROOT` = `proposals/<contenido
   de ese archivo>/`. Es el caso normal, y lo escribe `/propuesta-init`.
2. Si no existe, **DETENTE** antes de escribir nada: pídele al usuario que
   corra `/propuesta-init <idea>` (o corre tú mismo
   `scripts/init-run.sh <run-id> "<idea>"` tras resolver el run-id como
   describe la Fase 0) y solo después continúa con la Fase 0. Nunca improvises
   una carpeta de corrida a mano ni escribas artefactos en la raíz del repo.

Cuando una llamada MCP de `codebase-memory` pide un `repo_path` absoluto,
`<RUN_ROOT>` es la ruta absoluta de esa carpeta (p. ej.
`/ruta/al/repo/proposals/2026-09-siun-alianzas`), y los dos corpus son
`<RUN_ROOT>/artefactos/scoping/papers` y `<RUN_ROOT>/artefactos/vault`. Los
nombres de índice se derivan del mismo run-id: `<run-id>-papers` y
`<run-id>-vault`.

## Roster de subagentes (`.agent/skills/`)

`insumos-observador`, `investigador`, `redactor`, `bibliografo-propuesta`,
`disenador-tikz`, `tikz-optimizer`, `revisor-figuras`, `revisor`,
`presupuestador`, `grant-flow-auditor`. (No existen `orquestador`, `observador`
ni `bibliotecario`: usa siempre estos 10 nombres reales. `coordinador-propuesta`
existe como documento de referencia del pipeline, no como subagente despachable.)

## Cómo usar `codebase-memory` (MCP `codegraph`)

Este pipeline mantiene vistas de grafo sobre sus propios artefactos (el
corpus de papers de scoping y el mirror Obsidian del vault) con
**codebase-memory** — el servidor MCP `codegraph` declarado en `.mcp.json`
(`codegraph serve --mcp`). No hay binario que invocar por Bash ni API key
que pedir: son llamadas a herramientas MCP. Si en algún punto de esta
corrida sientes la tentación de pedirle al usuario una API key para indexar,
es una señal de que estás inventando un flujo que no existe: detente y usa
las herramientas MCP de abajo.

Herramientas que usa el DISPATCHER (nunca un subagente: `revisor` solo tiene
Read/Grep/Glob, sin acceso MCP):

| Herramienta | Para qué |
|---|---|
| `index_repository(repo_path, name, mode)` | Construye o **actualiza** el índice de un corpus. Es incremental: volver a llamarla sobre el mismo `name` reindexa lo que cambió. No existe `--update` ni `--force`. |
| `get_architecture(project, aspects)` | Vista agregada: `clusters` (comunidades temáticas), `hotspots` (nodos centrales), `boundaries`, `structure`, `file_tree`. |
| `search_graph(project, ...)` / `query_graph(project, query)` | Consulta por patrón de nombre, o Cypher de solo lectura para cruces multi-salto. |
| `index_status(project)` / `check_index_coverage(project, paths)` | Frescura del índice y huecos de cobertura. Un resultado limpio significa "sin hueco registrado", nunca "cobertura probada". |
| `delete_project(project)` | Descarta un índice obsoleto (p. ej. cuando una iteración de G1a reemplaza los 5 papers del corpus semilla). |

Reglas duras:

- **Siempre `repo_path` absoluto al directorio del corpus**, nunca la raíz
  del repo. `codebase-memory` respeta `.gitignore`, y todo el contenido de
  una corrida está gitignoreado: indexado desde la raíz, el corpus aparece
  como `not_indexed` con `reason: "gitignore"`. Indexado con el corpus
  **como raíz propia** (`<RUN_ROOT>/artefactos/vault`,
  `<RUN_ROOT>/artefactos/scoping/papers`), el `.gitignore` del repo padre no
  aplica y los archivos sí entran. Las negaciones (`!ruta`) en `.cbmignore`
  **no** revierten una regla de `.gitignore`, así que el corpus-como-raíz es
  la única mecánica válida.
- **Ruido excluido con `.cbmignore`** dentro del corpus (esto sí funciona):
  `artefactos/vault/.cbmignore` excluye `.obsidian/`; `artefactos/scoping/.cbmignore`
  excluye los reportes derivados.
- **Nombres de proyecto estables por corrida**: `<run-id>-papers` para el
  corpus de scoping y `<run-id>-vault` para el mirror Obsidian. Son dos
  índices distintos y nunca se mezclan.
- **La vista HTML la genera el marco, no `codebase-memory`.**
  `codebase-memory` no exporta un grafo navegable. La capa HTML la produce
  `scripts/graph_html.py` a partir de un JSON que el DISPATCHER escribe junto
  al reporte Markdown (ver "Reporte de grafo" abajo). El Markdown sigue siendo
  el artefacto citable en las compuertas; el HTML es su gemelo visual
  autocontenido (sin CDN, abre sin red). Se generan siempre los dos.
- **No hay edges de `[[wikilink]]`.** `codebase-memory` modela carpetas,
  archivos y secciones (encabezados Markdown), no enlaces entre notas. Los
  `[[wikilinks]]` rotos se detectan de forma determinista con `Grep`, no se
  infieren del grafo.

### Reporte de grafo

Tras cada indexado, el DISPATCHER escribe un reporte Markdown con
exactamente estas tres secciones, derivadas de las llamadas MCP:

```markdown
# Reporte de grafo — <corpus> (<run-id>)
Índice: <project> · <N> nodos / <M> edges · frescura: <index_status>
## Nodos centrales
<hotspots y grado, de get_architecture / query_graph>
## Comunidades temáticas
<clusters de get_architecture, con los archivos de cada cluster>
## Preguntas sugeridas
<3-5 preguntas que el DISPATCHER deriva de los dos bloques anteriores>
```

Rutas fijas del reporte: `grafos/papers-graph-report.md` (corpus de
papers) y `grafos/vault-graph-report.md` (mirror del vault).
Ambos son artefactos de corrida, gitignoreados, nunca se commitean.

**Gemelo HTML (obligatorio, paso del DISPATCHER).** Junto con el Markdown, el
DISPATCHER escribe el dato del grafo y renderiza su vista navegable:

1. Escribe `grafos/<corpus>-graph.json` (p. ej. `papers-graph.json`,
   `vault-graph.json`) con este contrato: `corpus`, `run_id`, `title`,
   `generated_at`, `index` (`project`, `nodes`, `edges`, `freshness`),
   `central_nodes` (`note`, `items[]`), `communities` (`note`, `clusters[]`),
   `questions[]`, `nodes[]` (`id`, `label`, `type`, `group`) y `edges[]`
   (`source`, `target`, `type`). Los campos `note` se renderizan verbatim:
   sirven para declarar con honestidad una sección degenerada en vez de
   dejarla muda. El `group` de un nodo es libre y puede reflejar una
   agrupación que NO viene del grafo (p. ej. las subsecciones SOTA del
   bibliógrafo) — el HTML la colorea y la rotula como tal.
2. Ejecuta `scripts/graph_html.py grafos/<corpus>-graph.json`, que escribe
   `grafos/<corpus>-graph.html`: autocontenido, sin CDN, abre sin red, y
   determinista (misma entrada, mismo HTML).
3. Se generan siempre los dos archivos, también al refrescar el índice del
   vault.

**Techo de utilidad del grafo (hallazgo verificado, no lo ignores).** En un
corpus de documentos (p. ej. abstracts en Markdown) `codebase-memory` produce un
grafo **estructural, no semántico**: sin aristas entre documentos, sin hotspots
y sin clusters, de forma **invariante al tamaño del corpus** (verificado a 5 y a
50 papers: los nodos y aristas escalan linealmente y las comunidades detectadas
siguen siendo cero). Tampoco fusiona encabezados homónimos entre archivos. La
vista HTML hace visible esa estructura y su degeneración, pero **no la inventa**;
la agrupación temática real proviene del sub-paso `grouping` del bibliógrafo, y
el reporte y el HTML deben declararlo en sus campos `note` en vez de simular que
existen comunidades.

### Refresh del índice del vault (procedimiento único)

Cada vez que una fase de abajo dice "aplica el procedimiento de Refresh del
índice del vault", el DISPATCHER hace exactamente esto:

1. `index_repository(repo_path="<RUN_ROOT>/artefactos/vault", name="<run-id>-vault",
   mode="fast")` — incremental, sin borrar nada.
2. `get_architecture(project="<run-id>-vault",
   aspects=["clusters","hotspots","boundaries"])`.
3. `Grep` sobre `artefactos/vault/` con el patrón `\[\[([^\]]+)\]\]` y contrasta cada
   destino contra los archivos existentes de `artefactos/vault/secciones/` y
   `artefactos/vault/insumos/`: cada destino sin archivo es un `[[wikilink]]` roto.
4. Reescribe `grafos/vault-graph-report.md` con las tres
   secciones del formato de arriba, más una línea por `[[wikilink]]` roto.

## Instrucciones de inicio

1. Si no hay insumos (PDFs/papers/enlaces) en el mensaje ni en `insumos/`,
   pídelos al usuario antes de avanzar. Los archivos fuente se guardan en
   `insumos/`. Si los hay, despacha con `Task` al subagente
   `insumos-observador` (Fase 0) para clasificar (TDR / draft-base /
   background), extraer el TDR si aplica, y estructurar el contexto en
   `artefactos/insumos.md`. Ver el bloque "Fase 0" del pipeline abajo para el
   flujo completo de clasificación, gate de ambigüedad y decisión de ruta.
2. Crea/mantén un registro de estado del documento en
   `artefactos/estado_propuesta.md` con: sección actual, artefactos clave
   (pregunta de investigación, subproblemas, objetivos, hipótesis) y estado de
   cada gate. En esta misma Fase 0 asegúrate también de que existan
   `artefactos/vault/secciones/` y `artefactos/vault/insumos/` (créalos si faltan) — el mirror
   Obsidian de la propuesta (ver "Vault mirror" en `coordinador-propuesta.md`).
   Más adelante (a partir de G1b, ver bloque "Fase 1b" abajo), el dispatcher
   indexa `artefactos/vault/` con `codebase-memory` bajo el nombre de proyecto
   `<run-id>-vault` y escribe el reporte derivado en
   `grafos/vault-graph-report.md` — artefacto de corrida,
   gitignoreado, nunca se commitea, igual que
   `grafos/papers-graph-report.md` de la Fase 1a/1b (son dos índices
   completamente distintos, sobre corpus y reportes distintos).
3. Avanza fase por fase según el pipeline de `coordinador-propuesta.md`
   (resumido abajo). Tras cada gate, presenta al usuario: (a) resumen de lo
   producido, (b) veredicto del `revisor` (o `revisor-figuras` en los bucles
   de figura de las Fases 1, 2 y 5.5), (c) petición de aprobación explícita,
   (d) Costo/tiempo: `<tokens_total>` tokens, `<tool_uses>` tool-calls,
   `<duration_ms>` — o `no medible directamente` (ver "Telemetría de uso por
   fase" abajo para el detalle de cómo se calculan estos valores).
   **NO avances sin aprobación.**
4. Recuerda: toda la salida del documento es en español; los archivos van en
   `redaccion/sections/*.tex` y `redaccion/refs.bib`; ensambla `redaccion/main.tex`
   al final (Fase 7). También existen `artefactos/vault/secciones/*.md` y
   `artefactos/vault/insumos/*.md`: un mirror visual en Markdown (Obsidian) mantenido por
   los propios agentes que escriben secciones (`insumos-observador`,
   `investigador`, `redactor`, `bibliografo-propuesta`, `presupuestador`) al
   escribir su `.tex` o `.bib` correspondiente — tú no lo regeneras aparte.
5. Consulta `guiaProyectosIA_Agente.md` para las instrucciones párrafo a
   párrafo de cada sección antes de despachar cualquier fase.

## Grafo de coherencia del vault (asesor, NO bloqueante)

A partir de la aprobación de G1b, el DISPATCHER mantiene un índice de ideas
sobre `artefactos/vault/` con `codebase-memory` y lo inyecta como evidencia asesora en
cada `Task → revisor` de las Fases 1-5 y 7 (ver los pasos "[NUEVO]" dentro de
cada fase, abajo). Este índice es DISTINTO del de la Fase 1a/1b (que indexa
`artefactos/scoping/papers/`, el corpus de papers de scoping, bajo el proyecto
`<run-id>-papers`, y reporta en `grafos/papers-graph-report.md`): el índice
de esta sección es el proyecto `<run-id>-vault`, cubre el mirror Obsidian
(`artefactos/vault/secciones/` + `artefactos/vault/insumos/`) y reporta en
`grafos/vault-graph-report.md`. Nunca lo indexa `revisor` (solo
tiene Read/Grep/Glob, sin acceso MCP) — siempre lo dispara el dispatcher, con
el procedimiento "Refresh del índice del vault" definido arriba.

Formato exacto del bloque que el dispatcher inyecta inline en el prompt de
`Task → revisor` (el mismo tag `ASESOR-GRAFO` que usa `revisor.md` en su
HALLAZGOS debe leerse contra este bloque):

```
EVIDENCIA DE GRAFO (asesora, NO bloqueante) — grafos/vault-graph-report.md
Dependencias duras (guia_ajustada_TDR "Nota de trazabilidad"): §3↔§7, §3↔§6, §5↔§6, §10↔§8.
- Presentes: <referencias cruzadas halladas entre notas del vault>
- Ausentes/huérfanas: <p. ej. SP3 sin objetivo enlazado>
- Nodos centrales / comunidades temáticas: <extracto del reporte de grafo>
- [[wikilinks]] rotos: <destinos sin archivo, del chequeo determinista con Grep>
Es pista; tu checklist manual sigue siendo la autoridad del veredicto.
```

Nota de renumeración: el 4º par (antes `§5.3↔§2.1`, Enfoques teóricos ↔
subproblemas) ya no existe como sección propia — `§5.3 Enfoques teóricos` fue
eliminada y su función (nombrar el enfoque/algoritmo por subproblema con
causa-efecto explícito) quedó absorbida en Metodología (§10), punto 1
(Métodos, del desarrollo por objetivo), que referencia el marco conceptual
(§8); de ahí el par `§10↔§8`.

Si el reporte de grafo revela un `[[wikilink]]` roto, una contradicción, o una idea
huérfana frente a uno de los 4 pares de trazabilidad de arriba, el
dispatcher además agrega una fila a `## Hallazgos de coherencia (grafo)` en
`artefactos/estado_propuesta.md` (crea la sección la primera vez que se usa),
con fase, archivo, y tipo de problema. Este hallazgo NUNCA por sí solo hace
que `revisor` cambie su VEREDICTO a FAIL.

## Instrucciones del revisor sobre el PDF (`artefactos/pipeline/instrucciones_revisor_pdf.md`)

El panel de anotaciones del tablero (`morfeo ui`) deja instrucciones cuando el
operador marca un pasaje del PDF con **Comentario**. Un comentario no reescribe
prosa: se registra como instrucción pendiente en
`artefactos/pipeline/instrucciones_revisor_pdf.md`, con la página, el texto ancla
y el archivo de la sección cuando se pudo ubicar. El manuscrito no cambia.

El panel tiene además un campo **Reemplazar por**, y ese sí cambia el manuscrito
en el acto. Cuando el operador lo llena, la marca deja de ser un aviso y pasa a
ser un reemplazo determinista: al pulsar **Ejecutar cambios** el pasaje anclado se
sustituye por ese texto literal en la sección correspondiente y el PDF se
recompila, sin modelo de por medio. Dos validaciones lo gobiernan: el ancla tiene
que ubicarse, o el reemplazo falla con un mensaje claro y no toca nada; y un
reemplazo vacío solo borra si el operador lo confirma, porque sin confirmar se
queda como comentario y viaja a la cola. El registro guarda la métrica del
reemplazo junto a las demás, y una corrida que no cambió la fuente no declara
recompilación.

El panel muestra cuántas instrucciones están pendientes y dice que no cambian
nada hasta que alguien las consuma. Esa cola era invisible, y su invisibilidad es
lo que hacía parecer roto el botón.

Antes de cerrar la siguiente unidad del pipeline, el DISPATCHER lee ese archivo.
Si tiene entradas sin marcar:

1. Las entrega al `redactor`, que las aplica sobre la sección correspondiente.
2. Pasa el resultado por `grant-flow-auditor`, que pule la cadencia sin mover
   cifras, citas ni estructura.
3. Marca cada casilla como aplicada y anota el veredicto de la compuerta.

Dos reglas que no se negocian. Una instrucción sin ejecutar no se recupera de
ningún otro sitio, así que el archivo se anexa y nunca se reescribe desde cero.
Y una instrucción cuyo ancla no se pudo ubicar se ejecuta igual, buscando el
pasaje por su texto. Las marcas **Tachar** y **Humanizar** sí modifican el
manuscrito en el acto y no pasan por este archivo.

## Registro de pipeline (`artefactos/pipeline/`, distinto de los índices de papers y vault)

Un TERCER registro, independiente de los dos índices, documenta la estructura del
pipeline mismo (fases/compuertas/agentes/artefactos), no el corpus de
papers ni el mirror Obsidian. Corpus y CWD dedicados: `artefactos/pipeline/`
— NUNCA corre desde la raíz del repo.

Corpus: el DISPATCHER escribe/actualiza un archivo `artefactos/pipeline/<NN>-<fase>.md`
por cada evento de fase (p. ej. `00-fase0.md`, `10-fase1a.md`,
`11-fase1b.md`, `20-fase1.md`, ...), más un `artefactos/pipeline/_estado.md`
compacto que espeja la tabla de compuertas en cada actualización (mantiene
el corpus autocontenido bajo el único CWD `artefactos/pipeline/`, ya que
`estado_propuesta.md` vive un nivel arriba). Plantilla mínima por evento:

```markdown
---
fase: <id>
agentes: [<subagente(s)>]
gate: <Gx | none>
veredicto: <PASS | FAIL | pending | n/a>
fecha: <YYYY-MM-DD>
tokens_total: <N | no medible directamente>
tool_uses: <N | no medible directamente>
duration_ms: <N | no medible directamente>
---
# Fase <id> — <nombre>
## Entradas
- <artefacto/sección consumida>
## Salidas
- <sección/artefacto producido>  [[<nota-vault-o-sección>]]
## Dependencias
- <fase previa de la que depende>
## Desglose por despacho (suma = totales del frontmatter)
| # | Agente | MODE/Etiqueta | Tokens | Tool-uses | Duración (ms) |
|---|--------|---------------|--------|-----------|---------------|
| 1 | insumos-observador | — | 12345 | 8 | 45000 |
```

`artefactos/pipeline/_estado.md` mantiene el mismo set de columnas en cada
actualización — encabezado exacto:

```
| Fase | Gate | Veredicto | Fecha | Tokens | Tool-uses | Duración |
```

Cada fila corresponde a un evento de fase; los valores de las 3 columnas
nuevas (`Tokens`, `Tool-uses`, `Duración`) son los mismos totales
acumulados por fase descritos más abajo en "Telemetría de uso por fase" —
nunca se recalculan aparte.

Cuándo actualiza: en CADA transición de compuerta (los mismos puntos donde
el dispatcher voltea `gate_status`, ver "Reglas de gate (obligatorias)"
abajo) — ver el bloque `[NUEVO] DISPATCHER: pipeline-graph` dentro de cada
fase/compuerta. Mecánica: el DISPATCHER únicamente escribe/actualiza el
archivo de evento `.md` y `artefactos/pipeline/_estado.md` — `artefactos/pipeline/`
NO se indexa con `codebase-memory` (no aporta valor consumido; el overhead se
descarta). Nunca lo hace
`revisor` (solo Read/Grep/Glob) — siempre lo hace el dispatcher.

## Telemetría de uso por fase

Tras cada llamado delegado (Task/Agent) que retorna dentro de una fase, lee
el bloque `<usage>` al final de su resultado (`subagent_tokens: N`,
`tool_uses: N`, `duration_ms: N`). ANTES de sumarlo al acumulador de la fase,
agrega una fila a `## Desglose por despacho` del evento de esta fase (ver
plantilla en "Registro de pipeline" arriba) con el ordinal `#` del despacho, el
nombre del agente despachado, su `MODE/Etiqueta`, y los mismos 3 campos
numéricos ya leídos de `<usage>` — reutilizados tal cual, sin ninguna nueva
lectura ni parseo del resultado. Recién después de escribir esa fila, súmalo
al acumulador de esta fase. El acumulador arranca en 0 al iniciar la fase y
acumula TODOS los despachos de la fase, incluidos los re-despachos por FAIL
y los bucles de figura, hasta el cierre de compuerta.

Regla de etiquetado de `## Desglose por despacho`: `#` es un ordinal
monótono de despacho por fase — nunca se reinicia dentro de la misma fase y
avanza también con los re-despachos por FAIL o los reintentos del bucle de
figuras (nunca se salta ni se reutiliza un número; cada despacho, incluido
un re-despacho, ocupa su propia fila). `MODE/Etiqueta` lleva el rol del
despacho dentro de cualquier bucle en curso más el contador de intentos
compartido con el resto del pipeline — p. ej. `tikz-optimizer intento 2/4`,
`MODE=deliverable` — o `—` cuando el agente no tiene MODE ni contador de
intentos aplicable en ese despacho. En el bucle de figuras el contador es por
diagrama: el despacho inicial de `disenador-tikz` (autor de la spec) es el
intento 1, y cada re-despacho a `tikz-optimizer` suma uno más, así que la fila
lleva p. ej. `disenador-tikz árbol de problemas intento 1/4` o
`tikz-optimizer árbol de problemas intento 2/4`. `revisor-figuras` lleva el
MISMO número de intento de la iteración que audita (p. ej. `revisor-figuras
árbol de problemas intento 2/4`), porque comparte el contador único por
diagrama (ver "Bucle de figuras (canónico)"). El paso determinista
`python3 scripts/figura.py` NO es un despacho delegado: es trabajo inline del
dispatcher y no aporta al acumulador de la fase.

Regla de sentinel por despacho: si un despacho puntual retorna sin bloque
`<usage>`, su fila en `## Desglose por despacho` escribe el literal
`no medible directamente` en sus 3 celdas numéricas (Tokens, Tool-uses,
Duración (ms)) — nunca un valor estimado o inferido. La regla de
sentinel/parcial a NIVEL DE FASE (ver debajo: sentinel en los 3 campos si
TODOS los despachos de la fase carecen de `<usage>`, o el sufijo
`(parcial: K/M sin usage)` si solo ALGUNOS carecen de él) queda sin cambios;
la suma de las filas de despacho que sí traen `<usage>` debe seguir
igualando exactamente el total (íntegro o parcial) que se registra a nivel
de fase.

Suma `subagent_tokens`, `tool_uses` y `duration_ms` de todos los despachos
de la fase; `duration_ms` es tiempo de cómputo agregado, no reloj de pared
(no se mide solapamiento entre despachos).

Si la fase no despachó ningún llamado delegado (trabajo puramente inline del
dispatcher, sin ningún despacho — a la fecha ninguna fase del pipeline cae
en este caso, pero la regla debe cubrir cualquier fase futura que sí lo
haga), registra los tres campos (`tokens_total`, `tool_uses`, `duration_ms`) con el
literal `no medible directamente` — nunca un número estimado o inferido. El
trabajo inline vía MCP/Bash (indexado con `codebase-memory`, build de PDF,
pixelshot, cálculo de
run-id, escrituras de pipeline-graph) no está delegado y no aporta a este
acumulador; su costo simplemente no se cuenta, nunca se estima.

Si un llamado delegado retorna sin bloque `<usage>`, su aporte es
desconocido y nunca se fabrica. Si TODOS los llamados delegados de la fase
carecen de `<usage>`, el registro de la fase es el sentinel
`no medible directamente` en los tres campos. Si SOLO ALGUNOS carecen de él,
suma los que sí lo traen y agrega el sufijo `(parcial: K/M sin usage)`
(K = llamados con `<usage>`, M = llamados totales de la fase), para que el
número nunca se presente como completo sin serlo.

Estos totales por fase (numéricos, sentinel, o con sufijo parcial) son los
que se escriben en el frontmatter del evento (`tokens_total`, `tool_uses`,
`duration_ms`), en las 3 columnas nuevas de `_estado.md`, y en el punto (d)
del cierre de compuerta — ver las referencias en cada bloque
`[NUEVO] DISPATCHER: pipeline-graph` de cada fase abajo.

## Formato exacto — inyección de guide_fingerprint hacia insumos-observador

Antes de despachar `Task → insumos-observador` (Fase 0, ver "FINGERPRINT DE
GUÍA BASE" en el bloque "Fase 0" abajo), el DISPATCHER calcula el
fingerprint de la guía BASE y lo inyecta inline en el prompt de esa Task,
como bloque separado que el subagente lee en su propio paso 0 ("Fingerprint
de la guía vigente" en `insumos-observador.md`) ANTES de calcular nada por
su cuenta. Formato exacto — mismo valor que consume el campo
`guide_fingerprint` del payload cacheado (Decisión A / dominio
`insumo-extraction-cache`): 12 hex de sha256, SIEMPRE sobre
`guiaProyectosIA_Agente.md` (nunca sobre una guía ajustada al TDR — en la
Fase 0 esa guía todavía no existe, se genera recién en la Fase 0.5):

```
guide_fingerprint: <12 hex de shasum -a 256 guiaProyectosIA_Agente.md | cut -c1-12>
```

Este es el mismo formato/fórmula que el fallback ya existente de
`insumos-observador.md`, así que no hay divergencia posible entre el valor
inyectado y el autocalculado. Si el dispatcher no logra calcular o inyectar
este bloque por cualquier motivo, simplemente lo omite — el fallback de
`insumos-observador.md` cubre ese caso y la corrida nunca se bloquea.

Nota de reuso: este valor se calcula temprano (Fase 0) porque es solo un
hash de archivo — no depende de haber leído ni troceado la guía. La
PRE-CARGA DE FRAGMENTOS DE GUÍA (inicio de la Fase 1a, más abajo) reutiliza
este mismo valor cuando corresponde, en vez de recalcularlo; ver ese bloque
para las condiciones exactas de reuso vs. recálculo.

## Pipeline (dispatch con `Task` fase por fase)

```
Fase 0  ──→ RESOLUCIÓN DE RUN-ID (identidad de la corrida): si
        `proposals/.current-run` ya existe, el run-id YA está resuelto (lo
        fijó `/propuesta-init`): léelo de ahí, confirma que
        `proposals/<run-id>/_run.md` tiene `estado: activa`, y salta directo
        al bloque siguiente sin re-derivar nada. Si no existe, resuelve el
        run-id de esta corrida y crea su carpeta con
        `scripts/init-run.sh <run-id> "<idea breve>"` (nunca a mano). Esquema
        `<YYYY-MM>-<slug>` (p. ej. `2026-07-siun-alianzas`). `<YYYY-MM>` sale
        de la fecha del sistema. `<slug>` = 2-4 palabras clave en
        kebab-case, en minúsculas, sin tildes/ñ (ASCII-folded), derivadas de
        la idea en `$ARGUMENTS` descartando stopwords. Override: si
        `$ARGUMENTS` empieza con `run-id=<valor>` o `--run-id <valor>`,
        valida `<valor>` contra `[a-z0-9-]+` y úsalo tal cual (el resto de
        `$ARGUMENTS` es la idea); si no hay override, usa el slug
        auto-derivado. Escribe el run-id resuelto en
        `artefactos/estado_propuesta.md` ("## Identidad de la corrida
        (run-id)": `run_id`, `slug_source` [auto|user], `idea`, `creada`
        [YYYY-MM-DD], `estado` [activa]) y agrega una fila a
        `proposals/registry.md`, el registro LOCAL de corridas (no se
        versiona). `scripts/init-run.sh` ya lo crea con su encabezado y agrega
        la fila al hacer `/propuesta-init`, así que acá normalmente solo
        verificás que la fila exista.
        ──→ GUARDIA DE CORRIDA ACTIVA: lee el `_run.md` de la corrida
        apuntada por `proposals/.current-run`. Si su `estado` es `activa` y
        NO es la corrida que estás arrancando, DETENTE y exige confirmación
        explícita — sin importar si todas sus compuertas están cerradas o no:
        "Existe la corrida activa `<run-id>` (última compuerta `<Gx>`).
        ¿Cerrarla como `archivada` y seguir con `<run-id-nuevo>`? (sí/no)".
        Solo "sí" continúa; "no" ofrece reanudar/revisar esa corrida en vez
        de iniciar una nueva.
        ──→ CIERRE DE LA CORRIDA PREVIA (tras "sí" arriba): con una
        subcarpeta por corrida, cerrar una corrida NO copia ni borra nada —
        su `main.pdf`/`main.docx` y todos sus artefactos ya están a salvo en
        `proposals/<run-id-previo>/`, que **es** el archivo. Son cuatro pasos:
          1. En `proposals/<run-id-previo>/_run.md`: `estado: archivada` y
             `cerrada: <YYYY-MM-DD>`.
          2. En `proposals/registry.md`: misma fila a `archivada`, con
             `cerrada` y `archivo` (ruta local `proposals/<run-id-previo>/`,
             nunca una URL de GitHub).
          3. Descarta sus índices de `codebase-memory` para no dejar índices
             huérfanos: `delete_project("<run-id-previo>-papers")` y
             `delete_project("<run-id-previo>-vault")`.
          4. NO hay commit en este paso: `proposals/` entero está
             gitignored, registro incluido, así que cerrar una corrida no
             produce ningún cambio versionado. Nunca uses `git add -f` para
             meter contenido de una corrida en git; si algo bajo `proposals/`
             apareciera trackeado, es un bug a corregir en `.gitignore`.
        Nunca vacíes ni "reinicies" la carpeta de la corrida previa: la
        corrida nueva nace en su propia carpeta vía `/propuesta-init`.
        ──→ SIN CORRIDA PREVIA: si no existe una corrida anterior, omite
        GUARDIA DE CORRIDA ACTIVA y CIERRE DE LA CORRIDA PREVIA por
        completo; continúa directo con el resto de la Fase 0.
        ──→ FINGERPRINT DE GUÍA BASE (liviano, antes de despachar
        insumos-observador): calcula
        `guide_fingerprint = shasum -a 256 guiaProyectosIA_Agente.md | cut -c1-12`
        (12 hex, SIEMPRE sobre la guía BASE — no la ajustada al TDR, que
        todavía no existe en este punto de la corrida) y consérvalo en la
        sesión activa del dispatcher para el resto de la corrida. Es solo un
        hash de archivo, no requiere trocear nada, por eso se calcula acá,
        antes de que exista la guía aplicable ajustada de la Fase 0.5 (ver
        "Formato exacto — inyección de guide_fingerprint hacia
        insumos-observador" arriba para el formato exacto que se inyecta).
        Task → insumos-observador → ingerir insumos (PDFs, papers, links, prompt)
        y clasificarlos (TDR / draft-base / background, ver
        `insumos-observador.md`); si hay TDR, extraer sus secciones + tabla
        de criterios ponderados. El dispatcher inyecta inline en este prompt
        el bloque `guide_fingerprint: <valor>` calculado arriba.
        ──→ GATE DE AMBIGÜEDAD: si insumos-observador marca uno o más
        archivos como AMBIGUA (para TDR y/o draft-base), DETENTE y pregunta
        al usuario para confirmar/corregir. Si TDR y draft-base están
        ambiguos a la vez, combina ambas dudas en UNA sola pregunta.
        ──→ RAMA TDR: si hay un TDR confirmado (auto o por el usuario),
        calcula la tabla de prioridad por sección (regla ALTA = tercil
        superior por puntaje de criterios ponderados del TDR, empates en el
        límite del tercil se incluyen como ALTA; crosswalk:
        calidad/innovación→§6/§7 (objetivos), §4/§5/§8 (estado del
        arte/hipótesis/marco conceptual), §10 (metodología); formación→§15;
        impacto territorial/ODS→§2; articulación→§2/§15) y escríbela en
        `artefactos/estado_propuesta.md` ("Prioridad por sección"). Si no hay
        TDR, omite este paso por completo.
        ──→ RAMA DRAFT: si hay draft-base confirmado → ruta DRAFT-EXISTS.
        Si no, pregunta explícitamente "¿existe un borrador previo?" antes
        de concluir NO-DRAFT; el usuario puede nombrar un archivo para pasar
        a DRAFT-EXISTS.
        ──→ Escribe la decisión de ruta (DRAFT-EXISTS | NO-DRAFT, archivo
        TDR, archivo draft-base y quién confirmó cada uno) en
        `artefactos/estado_propuesta.md` ("Clasificación y ruta (Fase 0)").
        ──→ CORROBORACIÓN DE SECCIONES (solo si hay TDR): lee de insumos.md
        "Secciones obligatorias declaradas por el TDR" y registra en
        estado_propuesta.md ("Clasificación y ruta") los 3 campos nuevos (TDR
        especifica secciones, Fuente, Evidencia).
Fase 0.5 [COMPUERTA G0.5] Solo aplica si el campo "Archivo TDR" de la tabla
        "Clasificación y ruta (Fase 0)" quedó con un valor no vacío
        (confirmado auto o resuelto vía el gate de ambigüedad — ambos
        cuentan). Si no hay TDR, omite esta fase por completo: la guía
        aplicable sigue siendo `guiaProyectosIA_Agente.md` sin cambios y el
        dispatcher continúa directo a la Fase 1a.
        ──→ [BLOQUEO DURO — corroboración de secciones] Verifica "TDR
        especifica sus propias secciones":
          - Sí (TDR mismo o `doc-secciones` que aporta la lista) → continúa
            al opt-in; el investigador usará esa lista como estructura
            obligatoria.
          - No y SIN `doc-secciones` con la lista → DETENTE: no opt-in, no
            despacho al investigador; G0.5 NO puede pasar. Muestra el
            mensaje de bloqueo (abajo), registra G0.5 = BLOQUEADA. Exits:
            (a) el usuario aporta el documento → re-corrobora y continúa;
            (b) el usuario opta EXPLÍCITAMENTE por no ajustar → base guide,
            G0.5 = OMITIDA-POR-USUARIO.
          - Si el gate de ambigüedad de la Fase 0 sigue pendiente, combina
            ambas peticiones en UN solo mensaje (misma lógica de combinación
            existente).

        > **Fase 0.5 en pausa — falta el documento de secciones obligatorias.**
        > El TDR clasificado (`<archivo TDR>`) **no enumera explícitamente** la
        > estructura/secciones que la propuesta debe contener; solo trae una tabla de
        > criterios de evaluación ponderados. Para ajustar la guía a la estructura
        > realmente exigida (y no solo a los pesos de los criterios) necesito el
        > documento que liste las secciones obligatorias de la propuesta.
        > Por favor aporta ese documento (un archivo de "secciones"/"estructura" de la
        > propuesta, PDF o .docx) en `insumos/` y confírmame el nombre. Hasta
        > entonces la compuerta **G0.5 queda BLOQUEADA**: no puedo generar
        > `guia_ajustada_TDR.md` por la vía ajustada al TDR.
        > Alternativa explícita: si no existe tal documento y prefieres seguir con la
        > guía base (`guiaProyectosIA_Agente.md`) sin ajuste al TDR, dímelo y lo
        > registro como G0.5 = OMITIDA-POR-USUARIO (no genero una guía "a medias" desde
        > solo los criterios).

        ──→ OPT-IN G0.5 (concepto nuevo y separado del campo
        "Confirmaciones de usuario" de la Fase 0, que solo cubre el gate de
        ambigüedad): pregunta una sola vez, explícitamente, "Se detectó un
        TDR (<archivo>). ¿Genero una guía ajustada al TDR antes de la
        búsqueda de literatura? (sí/no)".
          - "no" → guía aplicable = `guiaProyectosIA_Agente.md` (sin
            cambios); registra G0.5 = OMITIDA-POR-USUARIO en
            `artefactos/estado_propuesta.md` ("Compuertas tempranas (G0.5,
            G1a)").
          - "sí" → Task → investigador → genera
            `artefactos/guia_ajustada_TDR.md` a partir de
            `guiaProyectosIA_Agente.md` (entrada de solo lectura — el
            archivo base NUNCA se modifica), ajustando
            secciones/alcance/requisitos según la tabla de criterios
            ponderados ya extraída en `artefactos/insumos.md` ("Extracción
            del TDR"). El archivo generado DEBE incluir la "Tabla de
            secciones definitivas" con el formato exacto que exige
            `investigador.md` ("Generación de la guía ajustada") — es un
            requisito de forma del entregable, no opcional.
        ──→ GATE G0.5: presenta `artefactos/guia_ajustada_TDR.md` al usuario
        para aprobación explícita. La presentación de este gate NO es un
        resumen en prosa: el dispatcher copia la "Tabla de secciones
        definitivas" completa (todas las filas, sin resumir ni truncar) tal
        cual quedó en `artefactos/guia_ajustada_TDR.md` y la renderiza como
        tabla Markdown directamente en el mensaje de chat al usuario — la
        misma tabla debe ya existir en el `.md` (no se genera una versión
        distinta para consola). La aprobación/petición de cambios del
        usuario se resuelve sobre esa tabla específica (fila por fila si
        aplica), no sobre el documento en general.
          - Aprobada → guía aplicable = `artefactos/guia_ajustada_TDR.md`;
            registra G0.5 = APROBADA (quién/fecha) en
            `artefactos/estado_propuesta.md`.
          - Cambios solicitados → vuelve a despachar la misma Task al
            `investigador` con las correcciones exactas del usuario (p. ej.
            "renombrar §X", "fusionar §Y con §Z", "mover el bloque de
            divulgación a §15"), regenera la tabla completa (no un parche
            fila a fila hecho por el dispatcher) y repite el gate completo
            (tabla renderizada de nuevo en consola). NO avances sin
            aprobación explícita.
        En ambos desenlaces finales (OMITIDA-POR-USUARIO o APROBADA), el
        dispatcher continúa con la Fase 1a, que consume la "guía aplicable"
        resuelta aquí (ver bloque "Fase 1a" a continuación).
Fase 1a [COMPUERTA COMBINADA G1a] Scoping temprano: se ejecuta siempre,
        haya o no TDR — la "guía aplicable" resuelta en la Fase 0/Fase 0.5
        (base o ajustada) solo determina el parámetro (b) de la búsqueda del
        bibliógrafo en el paso (a) siguiente, no si esta fase corre.
        ──→ PRE-CARGA DE FRAGMENTOS DE GUÍA (una sola lectura completa por
        corrida, antes del paso (a) siguiente): el DISPATCHER (no un
        subagente) lee la guía aplicable UNA vez con un único `Read`
        completo (`guide = artefactos/guia_ajustada_TDR.md` si G0.5 =
        APROBADA, si no `guiaProyectosIA_Agente.md`) y retiene el contenido
        verbatim en su propia memoria de sesión — SIN `grep`/`rg`, SIN
        llamadas `Read` adicionales con `offset`/`limit`, SIN aritmética de
        líneas. El cableado Task por Task de este contenido (qué fragmento
        se inyecta en cada despacho) es un cambio posterior (PR3 de esta
        cadena); acá solo se define QUÉ queda disponible en memoria y CÓMO
        identificarlo cuando haga falta — el bloque FALLBACK que sigue ya
        forma parte del contrato que ese cableado posterior debe respetar,
        aunque en este PR todavía no haya ninguna Task que lo dispare.

        A partir de esa única lectura, identificá por tu propio criterio de
        lectura (no por regex ciego, así evitás falsos positivos de `### `
        dentro de un bloque de código delimitado por tres backticks, p. ej.
        un ejemplo dentro de "Convenciones técnicas de LaTeX") los bloques
        siguientes, cada uno delimitado desde su encabezado/marcador hasta
        el inicio del siguiente:
          - **Directrices Generales**: el bloque bajo
            `**Directrices Generales:**` hasta el `---` que lo cierra.
          - **Secciones numeradas** (`### N. <título>`): una por cada
            sección de la guía. En `guia_ajustada_TDR.md` el título y/o la
            numeración pueden diferir de la guía base (`investigador.md`,
            "Generación de la guía ajustada", puede renombrar/fusionar/
            reordenar secciones) — identificá cada bloque por su contenido y
            posición real en ESTA guía, nunca asumas que coincide con la
            guía base.
          - **Preliminares** (`### Resumen`, `### Resumen ejecutivo`,
            `### Palabras clave`) y **Convenciones técnicas de LaTeX**.
          - Fingerprint de esta guía: si `$guide` es la guía BASE (siempre
            el caso en corridas NO-TDR, y también en corridas TDR con G0.5 =
            OMITIDA-POR-USUARIO), REUTILIZA el `guide_fingerprint` YA
            calculado en la Fase 0 antes de despachar `insumos-observador`
            (ver "Formato exacto — inyección de guide_fingerprint..."
            arriba) en vez de recalcularlo. Si `$guide` es la guía AJUSTADA,
            es un archivo distinto: calculá `shasum -a 256 "$guide" | cut
            -c1-12` sobre este archivo, solo para uso interno de esta
            precarga (p. ej. etiquetar advertencias de fallback) — nunca
            reemplaza ni se reinyecta como el `guide_fingerprint` de
            `insumos-observador`, que siempre referencia la guía BASE, sin
            excepción.
        ──→ FALLBACK DE IDENTIFICACIÓN INSEGURA: si para una sección
        puntual que una Task necesita no podés identificar con confianza el
        bloque correspondiente (marcador/encabezado ausente, renombrado de
        forma irreconocible, formato de numeración distinto al esperado, o
        cualquier otra ambigüedad — p. ej. una guía ajustada al TDR sin el
        constraint de forma `### N. <título>`), NO adivines ni inventes
        contenido: para ESA Task puntual, inyectá la guía completa (`$guide`)
        en vez del fragmento, con un comentario
        `<!-- ADVERTENCIA: sección §N no identificada con confianza en
        <guide>; se inyecta la guía completa como fallback seguro -->`
        dentro del bloque inyectado, y agregá una advertencia visible (no
        bloqueante) en la sesión con el dispatcher señalando qué sección
        faltó y en qué Task se aplicó el fallback. Esto nunca detiene la
        corrida.
        ──→ FORMATO EXACTO DE INYECCIÓN (`## FRAGMENTO DE GUÍA`): a partir de
        acá, cuando una fase indica "inyecta el fragmento de §N" en el
        prompt de una `Task`, el bloque tiene esta forma exacta (mismo
        estilo que `ASESOR-GRAFO`/`guide_fingerprint` arriba):

        ```
        ## FRAGMENTO DE GUÍA (§N — <título de la sección>[, §M — <título>...])

        <Directrices Generales, verbatim, siempre presente>

        ---

        <contenido verbatim de §N>
        [<contenido verbatim de §M> si la Task necesita más de una sección —
         p. ej. un gate de revisor que audita dos secciones a la vez]

        [<Convenciones técnicas de LaTeX, verbatim — SOLO si la Task
         REDACTA un archivo .tex>]
        ```

        Reglas: Directrices Generales va SIEMPRE, sin excepción. Las
        secciones listadas en el título del bloque son las que esa Task
        posee/audita (ver el mapeo fase→sección de cada bloque de Fase
        abajo) — incluye, cuando corresponda, secciones de fases anteriores
        que el gate necesita para validar una dependencia cruzada (p. ej.
        el gate de Fase 4 necesita §3 además de §5-§7 para el mapeo
        subproblema↔objetivo), no solo las producidas en la fase actual. El
        bloque de Convenciones técnicas de LaTeX se agrega SOLO para Tasks
        que REDACTAN un `.tex` real: `investigador`/`redactor` (siempre) y
        `bibliografo-propuesta` SOLO para su Task de §4 (autora
        `04_estado_arte.tex`, ver Fase 2 abajo) — nunca para su Task de §16
        (autora únicamente `refs.bib`; el wrapper `16_bibliografia.tex` lo
        arma el dispatcher en Fase 7, no bibliografo-propuesta) ni para
        MODE=explore/MODE=scope (no autoran archivo). Los gates de
        `revisor` auditan contenido/coherencia, no sintaxis LaTeX
        (`revisor.md` no referencia esas convenciones en su checklist), así
        que nunca lo reciben, ni siquiera cuando el gate lee un `.tex`
        existente (p. ej. Fase 6.4 lee `13_presupuesto.tex` para el
        recomputo aritmético, pero no necesita las convenciones de forma).
        Orden cuando coexisten con `EVIDENCIA DE GRAFO` en el mismo prompt
        de gate: `EVIDENCIA DE GRAFO` primero, `## FRAGMENTO DE GUÍA`
        después (mismo orden en que ambos bloques se describen en cada
        bloque de Fase de este documento). Si
        el FALLBACK DE IDENTIFICACIÓN INSEGURA se activó para alguna de las
        secciones pedidas, el bloque completo se reemplaza por la guía
        íntegra (`$guide`) con el comentario de advertencia ya descrito, en
        vez de intentar mezclar fragmento parcial con guía completa.
        (a) Task → bibliografo-propuesta MODE=scope → exactamente 5 papers
        Q1/Q2 publicados en los últimos 2 años, abstract-only, que calcen
        con (i) el prompt original del usuario a `/propuesta` y (ii) la guía
        aplicable (`artefactos/guia_ajustada_TDR.md` si G0.5 = APROBADA, si no
        `guiaProyectosIA_Agente.md`). Ver `bibliografo-propuesta.md`,
        "MODE=scope", para el contrato completo (herramientas, esquema de
        salida `artefactos/scoping/papers/paper-{1..5}.md`, prohibición de
        leer cualquier borrador existente).
        (b) El DISPATCHER (no el subagente) indexa el corpus con
        `codebase-memory`, de forma aislada. Mecánica exacta:
          1. `index_repository(repo_path="<RUN_ROOT>/artefactos/scoping/papers",
             name="<run-id>-papers", mode="full")` — `repo_path` absoluto al
             directorio del corpus, NUNCA la raíz del repo (ver "Reglas
             duras" en "Cómo usar `codebase-memory`"); `mode="full"` porque
             la agrupación temática de la Fase 1b necesita la capa semántica.
          2. `get_architecture(project="<run-id>-papers",
             aspects=["clusters","hotspots","boundaries","file_tree"])`.
          3. Escribe `grafos/papers-graph-report.md` con las tres secciones
             del formato de "Reporte de grafo" (Nodos centrales, Comunidades
             temáticas, Preguntas sugeridas).
        Si una iteración previa de G1a dejó un índice con papers distintos,
        `delete_project("<run-id>-papers")` antes de reindexar, para que el
        índice no mezcle papers descartados con los nuevos.
        (c) Task → investigador (rama de entrada temprana — ver
        `investigador.md`, "Entrada temprana (Fase 1a)") → 3 subproblemas
        tempranos, cada uno con (1) el gap, (2) de qué abstract(s)
        (`paper-N`) proviene, (3) un cruce de una línea contra el TDR/guía.
        Antes de despachar esta Task, el dispatcher arma el bloque `##
        FRAGMENTO DE GUÍA` (formato exacto en "FORMATO EXACTO DE INYECCIÓN"
        arriba) con Directrices Generales + §3 (Descripción del problema) +
        §4 (Estado del arte) y lo inyecta inline al inicio del prompt de
        esta Task.
        ──→ COMPUERTA COMBINADA G1a: presenta juntos, en una sola solicitud
        de aprobación:
          1. Los 5 papers + parámetros de búsqueda (query, filtro de
             cuartil, rango de años, hits por herramienta).
          2. El grafo: la ruta del reporte
             `grafos/papers-graph-report.md` y su gemelo visual navegable
             `grafos/papers-graph.html` (abribles por el usuario; el HTML es
             autocontenido y abre sin red) + sus 3 secciones:
             Nodos centrales, Comunidades temáticas, Preguntas sugeridas.
             Si el grafo salió degenerado (sin nodos centrales ni
             comunidades), dilo explícitamente: no presentes un grafo vacío
             como si fuera un resultado.
          3. Los 3 subproblemas tempranos, cada uno con su gap y su
             `paper-N` de origen.
        Reglas de iteración por componente (NO es un rechazo en bloque):
          - Cambio solo a los PAPERS → re-despacha MODE=scope con el ajuste
            solicitado → regenera los 5 abstracts → RECONSTRUYE el grafo
            (repite el paso (b)) → re-ejecuta la entrada temprana del
            investigador (repite el paso (c)) → vuelve a presentar G1a.
          - Cambio solo al GRAFO (reetiquetar/reagrupar) → re-deriva
            únicamente `get_architecture` + el reporte, sin reindexar ni
            cambiar el corpus (el índice no cambia); los papers y los
            subproblemas quedan intactos; vuelve a presentar G1a. El
            auto-cascade a los subproblemas es explícitamente NO, salvo que
            el usuario lo pida (default adoptado).
          - Cambio solo a los SUBPROBLEMAS → re-despacha la entrada temprana
            del investigador con el feedback exacto del usuario; mismos 5
            papers y mismo grafo; vuelve a presentar G1a.
        Regla de faltante G1a: si el bibliógrafo reporta menos de 5 papers
        Q1/Q2 ≤2 años, el dispatcher NO debe sustituir ni relajar filtros en
        silencio — preséntale al usuario, en vivo, estas opciones:
          (a) ampliar la ventana de años,
          (b) relajar el cuartil (aceptar solo Q2 o un venue top nombrado),
          (c) ampliar/reformular los términos de búsqueda,
          (d) continuar con menos de 5,
          (e) aceptar un paper específico que el usuario nombre.
        Aplica la opción elegida y vuelve a presentar dentro de G1a.
        ──→ Al aprobar G1a: escribe los 3 subproblemas aprobados + G1a =
        APROBADA en `artefactos/estado_propuesta.md` ("Compuertas tempranas
        (G0.5, G1a)" → sub-tabla "G1a — Scoping temprano": 5 papers,
        parámetros de búsqueda, ruta del grafo + extracto del reporte, los 3
        subproblemas tempranos con su gap/`paper-N`, y Estado G1a).
        ──→ [NUEVO] DISPATCHER: pipeline-graph (primera inicialización):
        escribe `artefactos/pipeline/00-fase0.md` + `10-fase1a.md` (evento de
        esta compuerta) y `artefactos/pipeline/_estado.md`. Fase 0 no tiene
        compuerta propia, así que su fila/evento se escribe recién acá, en
        la primera transición de compuerta de la corrida (G1a): cada archivo
        de evento lleva los campos de uso acumulados de SU PROPIA fase
        (`00-fase0.md` con el acumulador de la Fase 0 — el único despacho
        delegado de esa fase es `Task → insumos-observador`, más
        re-despachos si el GATE DE AMBIGÜEDAD repite el paso — y
        `10-fase1a.md` con el acumulador, independiente, de la Fase 1a),
        nunca un valor combinado; ídem las dos filas correspondientes en
        `_estado.md` (ver "Telemetría de uso por fase").
Fase 1b [COMPUERTA COMBINADA G1b] Expansión de corpus SOTA: se ejecuta
        siempre que la Fase 1a cerró con G1a = APROBADA (ver
        `artefactos/estado_propuesta.md`, sub-tabla "G1a — Scoping temprano");
        si G1a no corrió o no cerró en APROBADA, omite esta fase por
        completo y continúa directo a la Fase 1.
        (a) Task → bibliografo-propuesta MODE=sota, sub-paso **corpus** →
        expande el corpus semilla de 5 papers de G1a a 30-40 papers
        abstract-only (`paper-6.md`..`paper-N.md`, dedup por DOI/título
        contra el corpus semilla, `paper-1..5.md` byte-inalterados). Ver
        `bibliografo-propuesta.md`, "MODE=sota" → sub-paso "corpus", para el
        contrato completo (herramientas, esquema de salida, Regla de
        faltante).
        (b) El DISPATCHER (no el subagente) actualiza el índice sobre el
        corpus ampliado, de forma incremental (NUNCA `delete_project` en esta
        fase, a diferencia de la re-iteración del paso (b) de la Fase 1a).
        Mecánica exacta:
          1. `cp grafos/papers-graph-report.md grafos/papers-graph-report-g1a-snapshot.md`
             (snapshot del reporte de G1a sobre el corpus semilla, antes de
             tocar nada; esta copia queda fija para siempre, NUNCA se
             regenera, sirve de referencia/diff frente al corpus ampliado).
          2. `index_repository(repo_path="<RUN_ROOT>/artefactos/scoping/papers",
             name="<run-id>-papers", mode="full")` — mismo `name` que en la
             Fase 1a, así que reindexa incrementalmente: `paper-1..5.md` no
             cambiaron y solo entra el trabajo nuevo de `paper-6..N.md`.
          3. `get_architecture(project="<run-id>-papers",
             aspects=["clusters","hotspots","boundaries","file_tree"])` y
             reescribe `grafos/papers-graph-report.md` sobre el corpus
             ampliado.
        El reporte vigente sigue en `grafos/papers-graph-report.md` (ahora
        refleja el corpus ampliado); `graph-report-g1a-snapshot.md` queda fijo
        como la foto de G1a.
        (c) Task → bibliografo-propuesta MODE=sota, sub-paso **grouping**
        (solo después de que el paso (b) complete) → propone 3-5
        subsecciones SOTA como tabla de mapeo paper → subsección →
        SP1/SP2/SP3.
        ──→ COMPUERTA COMBINADA G1b: presenta juntos, en una sola solicitud
        de aprobación:
          1. El corpus ampliado: conteo final de papers y parámetros de
             búsqueda (query, filtro de cuartil, rango de años, hits por
             herramienta) del sub-paso corpus.
          2. El grafo actualizado: la ruta del reporte
             `grafos/papers-graph-report.md` y su gemelo visual navegable
             `grafos/papers-graph.html` + sus 3 secciones (Nodos
             centrales, Comunidades temáticas, Preguntas sugeridas) sobre el
             corpus ampliado. Recuerda que el reporte y su HTML ya traen el
             snapshot inmutable de G1a como referencia de diff.
          3. La tabla de mapeo de 3-5 subsecciones SOTA (paper → subsección
             → SP1/SP2/SP3).
        Reglas de iteración por componente (NO es un rechazo en bloque):
          - Cambio solo al CORPUS → re-despacha el sub-paso corpus con el
            ajuste solicitado (repite el paso (a)) → re-ejecuta la
            actualización incremental del índice (repite el paso (b)) →
            re-deriva la tabla de subsecciones (repite el paso (c) — el
            sub-paso grouping SIEMPRE se re-ejecuta cuando cambia el
            corpus, no es opcional ni un caso de scope creep) → vuelve a
            presentar G1b.
          - Cambio solo a la AGRUPACIÓN (subsecciones) → re-ejecuta
            únicamente el sub-paso grouping (paso (c)) con el feedback
            exacto del usuario; el corpus y el índice quedan intactos;
            vuelve a presentar G1b.
        Regla de faltante G1b: si el bibliógrafo reporta menos de 30 papers
        Q1/Q2 dentro de la ventana de recencia aplicable, el dispatcher NO
        debe sustituir ni relajar filtros en silencio — preséntale al
        usuario, en vivo, el mismo menú de la Regla de faltante G1a, ahora
        al piso de 30:
          (a) ampliar la ventana de años,
          (b) relajar el cuartil (aceptar solo Q2 o un venue top nombrado),
          (c) ampliar/reformular los términos de búsqueda,
          (d) continuar con menos de 30,
          (e) aceptar un paper específico que el usuario nombre.
        Aplica la opción elegida y vuelve a presentar dentro de G1b.
        ──→ Al aprobar G1b: Task → bibliografo-propuesta MODE=sota, sub-paso
        **WRITE-REFS** → escribe `redaccion/refs.bib` en una sola pasada
        cubriendo el corpus completo (prohibido antes de esta aprobación).
        Luego escribe el corpus aprobado + la tabla de subsecciones + G1b =
        APROBADA en `artefactos/estado_propuesta.md` ("Compuertas tempranas
        (G0.5, G1a)" → sub-tabla "G1b — Corpus y subsecciones SOTA": conteo
        de papers, parámetros de búsqueda, ruta del grafo actualizado +
        extracto del reporte, tabla de mapeo de subsecciones, y Estado
        G1b).
        ──→ [NUEVO] DISPATCHER: papers-graph refresh (post-WRITE-REFS):
        guardia — ejecuta este bloque solo si `redaccion/refs.bib` cambió en
        este sub-paso (WRITE-REFS lo acaba de escribir). Mecánica:
        `index_repository(repo_path="<RUN_ROOT>/artefactos/scoping/papers",
        name="<run-id>-papers", mode="full")` (incremental, mismo `name`) y
        reescribe `grafos/papers-graph-report.md`.
        ──→ [NUEVO] DISPATCHER: pipeline-graph: escribe
        `artefactos/pipeline/11-fase1b.md` (evento de esta compuerta) y
        actualiza `artefactos/pipeline/_estado.md`, incluye además los campos
        de uso acumulados de la fase (ver "Telemetría de uso por fase").
        ──→ [NUEVO] Índice de ideas del vault — baseline (primera vez):
        inmediatamente después de lo anterior, en esta misma transición de
        aprobación final de G1b (NO en cada iteración del bucle de G1b), el
        DISPATCHER construye el índice baseline del vault. Este índice es
        DISTINTO del del paso (b) de esta misma Fase 1b (que actualiza el
        índice del corpus de papers de scoping, `<run-id>-papers`): este cubre
        el mirror Obsidian (`artefactos/vault/secciones/` + `artefactos/vault/insumos/`), no el
        corpus de papers, y es un proyecto aparte. Ver "Grafo de coherencia
        del vault" arriba para el detalle completo del mecanismo asesor.
        Mecánica exacta:
          1. `index_repository(repo_path="<RUN_ROOT>/artefactos/vault",
             name="<run-id>-vault", mode="full")` — `repo_path` absoluto al
             vault, NUNCA la raíz del repo; `mode="full"` solo en este
             baseline (los refresh por gate usan `mode="fast"`). Baseline: en
             este punto `artefactos/vault/insumos/` ya tiene notas de insumos de la Fase
             0; `artefactos/vault/secciones/` aún no tiene notas de sección, porque las
             Fases 1-7 no han corrido todavía.
          2. `get_architecture(project="<run-id>-vault",
             aspects=["clusters","hotspots","boundaries"])` + el chequeo
             determinista de `[[wikilinks]]` con `Grep` (pasos 2-3 de "Refresh
             del índice del vault").
          3. Escribe `grafos/vault-graph-report.md` — artefacto de
             corrida, gitignoreado, nunca se commitea.
Fase 1  (en AMBAS rutas) Task → bibliografo-propuesta MODE=explore → mapa de
        literatura de amplitud (≥5 obras, devuelto inline al dispatcher, sin
        archivo de salida), despachado ANTES del investigador. Antes de
        despachar esta Task, el dispatcher arma el bloque `## FRAGMENTO DE
        GUÍA` (formato exacto en "FORMATO EXACTO DE INYECCIÓN" arriba) con
        Directrices Generales + §4 (Estado del arte) y lo inyecta inline al
        inicio del prompt de esta Task.
        Task → investigador → §3 descripción del problema (subproblemas +
        pregunta de investigación). Inyecta inline en el prompt de esta Task el mapa de MODE=explore y,
        si existe, el bloque "PRIORIDAD TDR" de la Fase 0. El dispatcher
        arma además, antes de despachar esta Task, el bloque `## FRAGMENTO
        DE GUÍA` con Directrices Generales + §3 (Descripción del problema) +
        Convenciones técnicas de LaTeX, y lo inyecta inline al inicio del
        mismo prompt.
        Si la Fase 1a corrió y su gate cerró con G1a = APROBADA (ver
        `artefactos/estado_propuesta.md`, sub-tabla "G1a — Scoping temprano"),
        inyecta ADEMÁS, inline, el bloque "SUBPROBLEMAS TEMPRANOS APROBADOS
        (G1a)" con los 3 subproblemas tempranos y su justificación
        gap↔`paper-N`. Si la Fase 1a no corrió (o no cerró en APROBADA),
        omite por completo este bloque adicional: el despacho de esta Task
        es entonces idéntico al de hoy.
        Si además la Fase 1b corrió y su gate cerró con G1b = APROBADA (ver
        `artefactos/estado_propuesta.md`, sub-tabla "G1b — Corpus y
        subsecciones SOTA"), inyecta ADEMÁS, inline, el bloque "CORPUS Y
        SUBSECCIONES APROBADAS (G1b)" con el conteo del corpus ampliado y la
        tabla de mapeo de subsecciones; si la Fase 1b no corrió (o no cerró
        en APROBADA), omite este bloque adicional y el despacho sigue el
        comportamiento previo al cambio.
        ──→ luego bucle de figura `<name>` = `arbol_problemas`,
        procedimiento canónico completo en "Bucle de figuras (canónico)".
        Contenido autorizado: el bloque del Investigador (9 causas en 3
        grupos, tronco, 4 ramas, copa). La copa NUNCA se conecta con las
        raíces.
        `artefactos/vault/secciones/03_descripcion_problema.md` cambió en esta fase
        (recién escrita/actualizada por `investigador`); si no cambió,
        reutiliza el reporte de grafo existente sin
        re-indexar. Si hubo cambios: aplica el procedimiento de "Refresh
        del índice del vault" (arriba) y lee
        `grafos/vault-graph-report.md`; arma e inyecta inline
        el bloque `EVIDENCIA DE GRAFO` (formato en "Grafo de coherencia del
        vault" arriba) en el prompt de la Task → revisor de este gate; si
        hay hallazgo de coherencia, agrégalo a `## Hallazgos de coherencia
        (grafo)` en `artefactos/estado_propuesta.md`. Antes de despachar la
        Task de este gate, el dispatcher arma además el bloque `##
        FRAGMENTO DE GUÍA` con Directrices Generales + §3 (Descripción del
        problema) y lo inyecta inline al inicio del prompt.
        ──→ GATE Task → revisor (con bloque EVIDENCIA DE GRAFO inline) ──→ usuario. NO avances sin aprobación.
        ──→ [NUEVO] DISPATCHER: pipeline-graph: escribe
        `artefactos/pipeline/20-fase1.md` (evento de esta compuerta) y
        actualiza `artefactos/pipeline/_estado.md`, incluye además los campos
        de uso acumulados de la fase (ver "Telemetría de uso por fase").
Fase 2  Task → bibliografo-propuesta → §4 estado del arte.
        Además del texto de §4 (3-5 subsecciones), esta Task produce, como
        bloque comentado al final de `04_estado_arte.tex`, el contenido del
        diagrama de estado del arte (clusters, papers, relaciones, frase
        roja por cluster) — ver `bibliografo-propuesta.md` constraint 11.
        Antes de despachar esta Task, el dispatcher arma el
        bloque `## FRAGMENTO DE GUÍA` con Directrices Generales + §4 (Estado
        del arte) + Convenciones técnicas de LaTeX y lo inyecta inline al
        inicio del prompt.
        Task → investigador → §5 hipótesis, despachada DESPUÉS de que §4
        complete (§5 consume la síntesis de cierre de §4; corrección
        puramente documental de esta nota — el dispatcher ya secuencia
        §4→§5 hoy, sin cambio de comportamiento). Antes de despachar esta
        Task, el dispatcher arma el bloque `## FRAGMENTO DE GUÍA` con
        Directrices Generales + §5 (Hipótesis) + Convenciones técnicas de
        LaTeX y lo inyecta inline al inicio del prompt.
        ──→ luego bucle de figura `<name>` = `estado_arte` (o `estado_arte_a`
        y `estado_arte_b` si el mapa no cabe en A4 a tamaño natural: ver "Tamaño
        de página de las figuras"), solo después de
        que la Task de §4 complete (necesita el bloque comentado con el
        contenido del diagrama), procedimiento canónico completo en
        "Bucle de figuras (canónico)". Contenido autorizado: el bloque
        comentado al final de 04_estado_arte.tex (clusters, papers,
        relaciones, frase roja por cluster).
        `artefactos/vault/secciones/04_estado_arte.md` o `artefactos/vault/secciones/05_hipotesis.md`
        cambiaron en esta fase; si no cambiaron, reutiliza el reporte de grafo existente sin
        re-indexar. Si hubo cambios: aplica el procedimiento de "Refresh
        del índice del vault" (arriba) y lee
        `grafos/vault-graph-report.md`; arma e inyecta inline el bloque `EVIDENCIA DE
        GRAFO` en el prompt de la Task → revisor de este gate; si hay
        hallazgo, agrégalo a `## Hallazgos de coherencia (grafo)` en
        `artefactos/estado_propuesta.md`. Antes de despachar la Task de este
        gate, el dispatcher arma además el bloque `## FRAGMENTO DE GUÍA` con
        Directrices Generales + §4 (Estado del arte) + §5 (Hipótesis) y lo
        inyecta inline al inicio del prompt.
        ──→ GATE Task → revisor (con bloque EVIDENCIA DE GRAFO inline) ──→ usuario. NO avances sin aprobación.
        ──→ [NUEVO] DISPATCHER: pipeline-graph: escribe
        `artefactos/pipeline/30-fase2.md` (evento de esta compuerta) y
        actualiza `artefactos/pipeline/_estado.md`, incluye además los campos
        de uso acumulados de la fase (ver "Telemetría de uso por fase").
Fase 3  Task → redactor → §2 justificación y pertinencia. Antes de despachar
        esta Task, el dispatcher arma el bloque `## FRAGMENTO DE GUÍA` con
        Directrices Generales + §2 (Justificación y pertinencia) +
        Convenciones técnicas de LaTeX y lo inyecta inline al inicio del
        prompt.
        ──→ [NUEVO] DISPATCHER: guardia — re-indexa el vault solo si
        `artefactos/vault/secciones/02_justificacion.md` cambió en esta fase; si no
        cambió, reutiliza el reporte de grafo existente sin
        re-indexar. Si hubo cambios: aplica el procedimiento de "Refresh
        del índice del vault" (arriba) y lee
        `grafos/vault-graph-report.md`; arma e inyecta
        inline el bloque `EVIDENCIA DE GRAFO` en el prompt de la Task →
        revisor de este gate; si hay hallazgo, agrégalo a `## Hallazgos de
        coherencia (grafo)` en `artefactos/estado_propuesta.md`. Antes de
        despachar la Task de este gate, el dispatcher arma además el bloque
        `## FRAGMENTO DE GUÍA` con Directrices Generales + §2 (Justificación
        y pertinencia) y lo inyecta inline al inicio del prompt.
        ──→ GATE Task → revisor (con bloque EVIDENCIA DE GRAFO inline) ──→ usuario. NO avances sin aprobación.
        ──→ [NUEVO] DISPATCHER: pipeline-graph: escribe
        `artefactos/pipeline/40-fase3.md` (evento de esta compuerta) y
        actualiza `artefactos/pipeline/_estado.md`, incluye además los campos
        de uso acumulados de la fase (ver "Telemetría de uso por fase").
Fase 4  Task → investigador → §6 objetivo general + §7 objetivos específicos.
        Antes de despachar esta Task, el dispatcher arma el bloque `##
        FRAGMENTO DE GUÍA` con Directrices Generales + §6 (Objetivo
        general) + §7 (Objetivos específicos) + Convenciones técnicas de
        LaTeX y lo inyecta inline al inicio del prompt.
        ──→ [NUEVO] DISPATCHER: guardia — re-indexa el vault solo si
        `artefactos/vault/secciones/06_objetivo_general.md` o
        `artefactos/vault/secciones/07_objetivos_especificos.md` cambiaron en esta
        fase; si no cambiaron, reutiliza el reporte de grafo existente sin
        re-indexar. Si hubo cambios: aplica el procedimiento de "Refresh
        del índice del vault" (arriba) y lee
        `grafos/vault-graph-report.md`; arma e inyecta inline el bloque `EVIDENCIA DE
        GRAFO` en el prompt de la Task → revisor de este gate; si hay
        hallazgo, agrégalo a `## Hallazgos de coherencia (grafo)` en
        `artefactos/estado_propuesta.md`. Antes de despachar la Task de este
        gate, el dispatcher arma además el bloque `## FRAGMENTO DE GUÍA` con
        Directrices Generales + §3 (Descripción del problema) + §5
        (Hipótesis) + §6 (Objetivo general) + §7 (Objetivos específicos) —
        §3 es necesaria acá porque el gate audita el mapeo subproblema↔
        objetivo específico 1:1 contra el texto normativo de §3, no solo
        contra la memoria de la fase anterior — y lo inyecta inline al
        inicio del prompt.
        ──→ GATE Task → revisor (valida mapeo subproblema↔objetivo específico
        1:1; valida también hipótesis (§5, ya aprobada en la Fase 2)
        ↔objetivo general, con bloque EVIDENCIA DE GRAFO inline) ──→ usuario.
        NO avances sin aprobación.
        ──→ [NUEVO] DISPATCHER: pipeline-graph: escribe
        `artefactos/pipeline/50-fase4.md` (evento de esta compuerta) y
        actualiza `artefactos/pipeline/_estado.md`, incluye además los campos
        de uso acumulados de la fase (ver "Telemetría de uso por fase").
Fase 5  Task → investigador → §8 marco conceptual (en paralelo; 3-5
        subsecciones, título claro por concepto — ver `investigador.md`
        constraint 10). Antes de
        despachar esta Task, el dispatcher arma el bloque `## FRAGMENTO DE
        GUÍA` con Directrices Generales + §8 (Marco conceptual) +
        Convenciones técnicas de LaTeX y lo inyecta inline al inicio del
        prompt.
        Task → redactor → §9 equipo de trabajo (deriva roles de §7 objetivos
        específicos; nunca de la metodología). Antes de despachar esta Task,
        el dispatcher arma el bloque `## FRAGMENTO DE GUÍA` con Directrices
        Generales + §9 (Equipo de trabajo) + Convenciones técnicas de LaTeX
        y lo inyecta inline al inicio del prompt.
        Estas dos Tasks (§8 y §9) se despachan como llamadas independientes
        en el MISMO turno/bloque de herramientas del dispatcher — no en
        turnos secuenciales — ya que §9 deriva solo de §7 (ya aprobada en la
        Fase 4) y §8 no depende de §9.
        ──→ [NUEVO] DISPATCHER: guardia — re-indexa el vault solo si
        `artefactos/vault/secciones/08_marco_conceptual.md` o
        `artefactos/vault/secciones/09_equipo_trabajo.md` cambiaron en esta fase; si no
        cambiaron, reutiliza el reporte de grafo existente sin
        re-indexar. Si hubo cambios: aplica el procedimiento de "Refresh
        del índice del vault" (arriba) y lee
        `grafos/vault-graph-report.md`; arma e inyecta
        inline el bloque `EVIDENCIA DE GRAFO` en el prompt de la Task →
        revisor de este gate; si hay hallazgo, agrégalo a `## Hallazgos de
        coherencia (grafo)` en `artefactos/estado_propuesta.md`. Antes de
        despachar la Task de este gate, el dispatcher arma además el bloque
        `## FRAGMENTO DE GUÍA` con Directrices Generales + §3 (Descripción
        del problema) + §7 (Objetivos específicos) + §8 (Marco conceptual) +
        §9 (Equipo de trabajo) — §3 y §7 son necesarias acá porque el gate
        audita §8↔§3 (marco conceptual↔limitaciones del problema) y
        §9↔§7 (equipo de trabajo deriva de los objetivos específicos), no
        solo las dos secciones producidas en esta misma fase — y lo inyecta
        inline al inicio del prompt.
        ──→ GATE Task → revisor (con bloque EVIDENCIA DE GRAFO inline) ──→ usuario. NO avances sin aprobación.
        ──→ [NUEVO] DISPATCHER PDF-en-compuerta: ensambla/compila
        `redaccion/main.tex` → `redaccion/main.pdf` (ver "Reglas de gate
        (obligatorias)") antes de presentar el veredicto al usuario.
        ──→ [NUEVO] DISPATCHER: pipeline-graph: escribe
        `artefactos/pipeline/60-fase5.md` (evento de esta compuerta) y
        actualiza `artefactos/pipeline/_estado.md`, incluye además los campos
        de uso acumulados de la fase (ver "Telemetría de uso por fase").
Fase 5.5 [NUEVO] Task → redactor → §10 metodología (compuerta propia,
        separada de la Fase 5). Antes de despachar esta Task, el dispatcher
        arma el bloque `## FRAGMENTO DE GUÍA` con Directrices Generales +
        §10 (Metodología) + Convenciones técnicas de LaTeX y lo inyecta
        inline al inicio del prompt. Luego bucle de figura `<name>` =
        `metodologico`, procedimiento canónico completo en "Bucle de
        figuras (canónico)". El diagrama NUNCA incluye personal
        responsable dentro de sus bloques (ver `disenador-tikz.md`).
        `artefactos/vault/secciones/10_metodologia.md` cambió en esta fase; si no
        cambió, reutiliza el reporte de grafo existente sin
        re-indexar. Si hubo cambios: aplica el procedimiento de "Refresh
        del índice del vault" (arriba) y lee
        `grafos/vault-graph-report.md`; arma e inyecta
        inline el bloque `EVIDENCIA DE GRAFO` en el prompt de la Task →
        revisor de este gate (nota: distinto del bucle de figuras arriba,
        que usa `revisor-figuras`, no `revisor`, y no recibe evidencia de
        grafo); si hay hallazgo, agrégalo a `## Hallazgos de coherencia
        (grafo)` en `artefactos/estado_propuesta.md`. Antes de despachar la
        Task de este gate, el dispatcher arma además el bloque `##
        FRAGMENTO DE GUÍA` con Directrices Generales + §7 (Objetivos
        específicos) + §8 (Marco conceptual) + §9 (Equipo de trabajo) + §10
        (Metodología) — §7/§8/§9 son necesarias acá porque el gate audita
        §10↔§7 (metodología deriva de los objetivos específicos) y
        §10↔§8/§9 (sustento conceptual y responsables coherentes) — y lo
        inyecta inline al inicio del prompt.
        ──→ GATE Task → revisor (con bloque EVIDENCIA DE GRAFO inline) ──→ usuario. NO avances sin aprobación.
        ──→ [NUEVO] DISPATCHER PDF-en-compuerta: ensambla/compila
        `redaccion/main.tex` → `redaccion/main.pdf` antes de presentar el
        veredicto al usuario.
        ──→ [NUEVO] DISPATCHER: pipeline-graph: escribe
        `artefactos/pipeline/65-fase5_5.md` (evento de esta compuerta) y
        actualiza `artefactos/pipeline/_estado.md`, incluye además los campos
        de uso acumulados de la fase (ver "Telemetría de uso por fase").
Fase 6  Task → redactor → §11 resultados esperados (sin gate propio; §11 y
        §12 se auditan juntas en la Fase 7 junto con el resto del
        documento, igual que antes). Antes de despachar esta
        Task, el dispatcher arma el bloque `## FRAGMENTO DE GUÍA` con
        Directrices Generales + §11 (Resultados esperados) + Convenciones
        técnicas de LaTeX y lo inyecta inline al inicio del prompt.
        Task → redactor → §12 consideraciones éticas (ídem, sin gate
        propio). Antes de despachar esta Task, el dispatcher arma el bloque
        `## FRAGMENTO DE GUÍA` con Directrices Generales + §12
        (Consideraciones éticas) + Convenciones técnicas de LaTeX y lo
        inyecta inline al inicio del prompt.
Fase 6.4 [COMPUERTA INTERACTIVA G-Presupuesto] Presupuesto (interactivo).
        Precondición: §10, §11 y §12 ya aprobadas/producidas (el presupuesto
        justifica cada ítem contra la metodología, §10). El Cronograma (§14)
        todavía NO existe en este punto del pipeline —se redacta después,
        en la Fase 6.45— así que la verificación cruzada
        Presupuesto↔Cronograma queda diferida a la auditoría final de la
        Fase 7 (referencia hacia adelante válida, ver "Reglas de
        dependencia"). DEBE cerrar ANTES de la Fase 6.45 y de la Fase 6.5
        (el front-matter sintetiza §1–§16 ya aprobadas).
        ──→ RESOLUCIÓN DE MODO: si `artefactos/insumos.md` (o
        `guia_ajustada_TDR.md`) trae un bloque `## Marco presupuestal (TDR)`
        con tope no vacío → MODE=tdr; si trae el sentinel `sin datos
        presupuestales en TDR` o no hay bloque → MODE=base.
        (a) Task → presupuestador (MODE=tdr | MODE=base) → primer borrador de
        `redaccion/sections/13_presupuesto.tex` + su mirror de vault, con el
        self-audit aritmético ya aplicado; cada monto/cantidad no derivable de
        un insumo va marcado `[supuesto]`.
        ──→ BUCLE INTERACTIVO (sin tope de rondas; termina SOLO con
        aprobación explícita del usuario):
          1. El DISPATCHER presenta al usuario: (i) la tabla renderizada
             (ítem/cantidad/valor unitario/valor total/justificación,
             subtotales por rubro y total general); (ii) la lista de ítems
             marcados `[supuesto]`; (iii) en MODE=tdr, tope, cofinanciación
             aplicable, duración y el margen restante frente al tope.
          2. El usuario responde por línea (agregar/quitar/editar ítems,
             cantidades, valores unitarios, rubros, justificaciones) o aprueba.
          3. Si hay feedback → Task → presupuestador con las correcciones
             EXACTAS del usuario → regenera la tabla + re-corre el self-audit →
             el DISPATCHER resume los DELTAS respecto de la ronda anterior (qué
             filas/valores cambiaron y el nuevo total) y vuelve al paso 1.
             NUNCA auto-apruebes ni asumas conformidad por silencio.
          4. Si el usuario aprueba explícitamente → sale del bucle.
        ──→ [NUEVO] DISPATCHER: guardia — re-indexa el vault solo si
        `artefactos/vault/secciones/13_presupuesto.md` cambió en esta fase (o en la
        ronda interactiva más reciente); si no cambió, reutiliza el reporte de grafo existente sin
        re-indexar. Si hubo cambios: aplica el procedimiento de "Refresh
        del índice del vault" (arriba) y lee
        `grafos/vault-graph-report.md`; arma e inyecta inline
        el bloque `EVIDENCIA DE GRAFO` en el prompt de la Task → revisor de
        este gate; si hay hallazgo, agrégalo a `## Hallazgos de coherencia
        (grafo)` en `artefactos/estado_propuesta.md`. Antes de despachar la
        Task de este gate, el dispatcher arma además el bloque `##
        FRAGMENTO DE GUÍA` con Directrices Generales + §10 (Metodología) +
        §13 (Presupuesto) — §10 es necesaria acá porque el checklist de
        `revisor.md` exige que cada justificación de línea de presupuesto
        nombre un elemento real de §10 — y lo inyecta inline al inicio del
        prompt.
        ──→ GATE Task → revisor (con bloque EVIDENCIA DE GRAFO inline; aplica
        el criterio de Presupuesto del checklist de `revisor.md`: recomputo
        aritmético independiente, tope/cofinanciación, justificación→§10
        (Metodología; el cruce contra §14 Cronograma se valida recién en la
        Fase 7), membresía de rubro) ──→ usuario. NO avances sin aprobación.
        ──→ Al aprobar: el DISPATCHER voltea `gate_status` a `pass` en
        `artefactos/vault/secciones/13_presupuesto.md` y registra la fila de la fase en
        `artefactos/estado_propuesta.md` (tabla "Presupuesto (Fase 6.4)": modo
        [tdr|base], tope [valor+moneda o "n/a (base)"], total general, margen
        frente al tope, cofinanciación/split aplicable + cumplimiento, número
        de rondas interactivas, supuestos `[supuesto]` confirmados por el
        usuario, estado del gate G-Presupuesto [APROBADA (quién/fecha) |
        pending]).
        ──→ [NUEVO] DISPATCHER: pipeline-graph: escribe
        `artefactos/pipeline/65-fase6_4.md` (evento de esta compuerta, misma
        plantilla mínima descrita arriba en "Registro de pipeline") y actualiza
        `artefactos/pipeline/_estado.md`, incluye además los campos de uso
        acumulados de la fase (ver "Telemetría de uso por fase").
Fase 6.45 Task → redactor → §14 cronograma de actividades (Gantt) (sin gate
        propio; §14, §15 y §16 se auditan juntas en la Fase 7, mismo patrón
        que la Fase 6). Antes de despachar esta Task, el dispatcher arma el
        bloque `## FRAGMENTO DE GUÍA` con Directrices Generales + §14
        (Cronograma de actividades) + Convenciones técnicas de LaTeX y lo
        inyecta inline al inicio del prompt.
        Task → redactor → §15 productos esperados (ídem, sin gate propio).
        Antes de despachar esta Task, el dispatcher arma el bloque
        `## FRAGMENTO DE GUÍA` con Directrices Generales + §15 (Productos
        esperados) + Convenciones técnicas de LaTeX y lo inyecta inline al
        inicio del prompt.
        Task → bibliografo-propuesta → §16 bibliografía (BibTeX,
        consolidación final MODE=deliverable §4+§16, cubre todas las
        referencias citadas a lo largo del documento; ídem, sin gate
        propio). Antes de despachar esta Task, el dispatcher arma el bloque
        `## FRAGMENTO DE GUÍA` con Directrices Generales + §16
        (Bibliografía) y lo inyecta inline al inicio del prompt.
        ──→ [NUEVO] DISPATCHER: papers-graph refresh: guardia — ejecuta este
        bloque solo si `redaccion/refs.bib` cambió en esta fase (la
        consolidación MODE=deliverable lo acaba de extender). Mecánica:
        `index_repository(repo_path="<RUN_ROOT>/artefactos/scoping/papers",
        name="<run-id>-papers", mode="full")` (incremental, mismo `name`) y
        reescribe `grafos/papers-graph-report.md`.
Fase 6.46 Task → redactor → §17 Estrategia de articulación con comunidades y
        actores territoriales (redaccion/sections/17_articulacion_comunidades.tex)
        y §18 Estrategia de acceso, mediación, divulgación y apropiación social
        del conocimiento (redaccion/sections/18_apropiacion_social.tex). Son las
        dos secciones NUEVAS que el apartado o) y p) del TDR §8.3 exigen y que
        la guía base no contempla: sirven directamente al criterio de 20 pts de
        integración del equipo con comunidades y al de enfoque territorial, y §18
        ancla los 3 productos de tipo C de §15 con responsable y momento de
        entrega en §14. Por eso esta unidad va DESPUÉS de la Fase 6.45 —§14 y
        §15 tienen que existir— y ANTES de la Fase 6.5, porque el front-matter
        sintetiza el documento completo, §17 y §18 incluidos. Mismo mirror de
        vault que el resto de secciones del redactor.
        Antes de despachar cada Task, el dispatcher arma el bloque
        `## FRAGMENTO DE GUÍA` con Directrices Generales + §17 (o §18) +
        Convenciones técnicas de LaTeX y lo inyecta inline al inicio del prompt.
        ──→ [NUEVO] DISPATCHER: vault-graph refresh: guardia — ejecuta este
        bloque solo si en esta fase se crearon o editaron secciones del vault.
        Mecánica: `index_repository(repo_path="<RUN_ROOT>/artefactos/vault",
        name="<run-id>-vault", mode="fast")` (incremental, mismo `name`) y
        reescribe `grafos/vault-graph.{md,json,html}`.
        ──→ GATE Task → revisor (valida §17 y §18 contra la guía; verifica que
        §18 ancle los 3 productos de tipo C de §15 y que §17 declare actores,
        mecanismos, responsables y momentos) ──→ usuario. NO avances sin aprobación.
Fase 6.5 Task → redactor → secciones preliminares (front-matter), como
        síntesis del documento completo (§2–§18 ya aprobadas): Resumen
        (redaccion/sections/00_resumen.tex, máx. 400 palabras), Resumen
        ejecutivo (redaccion/sections/00_resumen_ejecutivo.tex, exactamente 5
        párrafos), Palabras clave (redaccion/sections/00_palabras_clave.tex,
        5 palabras). El título (12 a 15 palabras) e identificación institucional
        van exclusivamente en el bloque de encabezado/portada de `main.tex`
        (regla de unicidad: ninguna otra sección lo repite). En `main.tex` NO se
        incluye una sección numerada de cuerpo ni párrafos narrativos para §1 Título e
        identificación: el documento avanza del encabezado al front-matter, y
        tras este se aplica `\setcounter{section}{1}` para que el cuerpo inicie
        directamente en `\input{sections/02_justificacion}` (§2). Mismo mirror de
        vault que el resto de secciones del redactor. Antes de despachar esta Task,
        el dispatcher arma el bloque `## FRAGMENTO DE GUÍA` con Directrices Generales
        + §Resumen + §Resumen ejecutivo + §Palabras clave + Convenciones técnicas de
        LaTeX y lo inyecta inline al inicio del prompt.
        Antes de despachar la Task de este gate, el dispatcher arma el
        bloque `## FRAGMENTO DE GUÍA` con Directrices Generales + §Resumen +
        §Resumen ejecutivo + §Palabras clave y lo inyecta inline al inicio
        del prompt.
        ──→ GATE Task → revisor (valida las 3 preliminares contra la guía) ──→ usuario. NO avances sin aprobación.
        ──→ [NUEVO] DISPATCHER: pipeline-graph: escribe
        `artefactos/pipeline/70-fase6.md` (cubre Fase 6 + Fase 6.45 + Fase 6.46
        + Fase 6.5, evento de esta compuerta) y actualiza
        `artefactos/pipeline/_estado.md`,
        incluye además los campos de uso acumulados de la fase (ver
        "Telemetría de uso por fase").
Fase 7  ──→ [NUEVO] DISPATCHER: aplica el procedimiento de "Refresh del índice
        del vault" sobre el vault completo (todas las secciones ya escritas),
        con `mode="full"` en vez de `"fast"` — es la última auditoría, conviene
        la capa semántica completa; lee
        `grafos/vault-graph-report.md`; arma e inyecta
        inline el bloque `EVIDENCIA DE GRAFO` en el prompt de la Task →
        revisor de la auditoría final; si hay hallazgo, agrégalo a `##
        Hallazgos de coherencia (grafo)` en `artefactos/estado_propuesta.md`.
        Task → revisor → auditoría final (con bloque EVIDENCIA DE GRAFO inline;
        incluye AHORA la verificación cruzada Presupuesto (§13) ↔ Cronograma
        de actividades (§14) diferida desde la Fase 6.4, ya que ambas
        secciones existen recién en este punto) ──→ usuario. NO avances sin
        aprobación.
        ──→ [NUEVO] DISPATCHER: pipeline-graph: escribe
        `artefactos/pipeline/80-fase7.md` (evento de la auditoría final) y
        actualiza `artefactos/pipeline/_estado.md`, incluye además los campos
        de uso acumulados de la fase (ver "Telemetría de uso por fase").
        ──→ [NUEVO] DISPATCHER: resumen de costo/tiempo de la corrida
        completa — lee directamente las filas ya acumuladas de
        `artefactos/pipeline/_estado.md` (sin recomputar nada) y presenta una
        tabla `Fase | Tokens | Tool-uses | Duración`, una fila por cada fase
        de `_estado.md` (ninguna fase omitida), más una fila `TOTAL` que
        suma solo las filas numéricas (las filas con el sentinel
        `no medible directamente` quedan excluidas de la suma).
        Tú (el asistente primario) ensamblas `redaccion/main.tex` una vez aprobado.
        Los 3 archivos `00_*.tex` (Resumen → Resumen ejecutivo → Palabras
        clave, en ese orden) DEBEN incluirse antes del contenido de §2,
        maquetados con `\section*{}`. Tras el front-matter se incluye
        `\setcounter{section}{1}` para que el cuerpo inicie en el número 2.
        En `main.tex` NUNCA se incluye una sección numerada de cuerpo ni párrafos
        narrativos de §1 Título e identificación (el título y la identificación
        se compilan exclusivamente en el bloque de encabezado de portada).
        Orden del cuerpo (`\input{sections/...}`, 16 secciones en este orden exacto):
        `02_justificacion`,
        `03_descripcion_problema` (con `diag_arbol_problemas`),
        `04_estado_arte` (con `diag_estado_arte`), `05_hipotesis`, `06_objetivo_general`,
        `07_objetivos_especificos`, `08_marco_conceptual`,
        `09_equipo_trabajo`, `10_metodologia` (con `diag_metodologico`),
        `11_resultados_esperados`, `12_consideraciones_eticas`,
        `13_presupuesto`, `14_cronograma_actividades`,
        `15_productos_esperados`, y por último el bloque de bibliografía
        (`16_bibliografia` + `\bibliographystyle{apalike}` +
        `\bibliography{refs}`, §16). Nota de reordenamiento: `13_presupuesto`
        va ANTES de `14_cronograma_actividades` en el cuerpo ensamblado,
        aunque ambas secciones referencian las mismas fases de la
        Metodología (§10) — es la posición mandada por
        `guiaProyectosIA_Agente.md`, no un error de orden.
        Tras ensamblar y compilar `redaccion/main.pdf` (`redaccion/build.sh`),
        genera también la versión Word con `./build.sh --docx` desde
        `redaccion/`: produce `redaccion/main.docx` con los 3 diagramas
        rasterizados como imágenes y §13 Presupuesto como tabla editable (el
        sombreado de §13 no se conserva; el Gantt de §14 Cronograma de
        actividades queda como imagen). Es un paso mecánico
        post-compilación que corres tú (asistente primario), no un agente.
        `build.sh` ahora falla con `exit 1` si LaTeX reportó errores reales
        (`^!` en `main.log`) durante el ensamblado del PDF; si eso ocurre,
        tratá la falla como un STOP explícito: mostrale al usuario el mensaje
        de error tal cual lo emite `build.sh` y NO continúes a
        `./build.sh --docx` ni des por cerrada la Fase 7/compuerta hasta que
        el usuario corrija el error o apruebe explícitamente seguir igual.
        [NUEVO] Como último paso de la Fase 7, ya con `main.pdf` ensamblado,
        corres una pasada de QA visual asesora: `pixelshot redaccion/main.pdf
        -o redaccion/pixelshot-out/` y revisas los tiles renderizados en busca
        de posición del logo (encabezado UNAL, pie GCPDS/LabIA), desbordes de
        tablas/Gantt, figuras TikZ rotas o ilegibles, y coherencia general de
        maquetación. Es un paso mecánico que corres tú (asistente primario),
        no un agente ni un Task nuevo — sin ronda interactiva adicional. Si
        detectas un hallazgo, agrega una fila a `## Hallazgos de QA visual
        (pixelshot)` en `artefactos/estado_propuesta.md` (crea la sección la
        primera vez que se usa), con página, tipo
        (logo/desborde/TikZ-roto/otro) y detalle. Este hallazgo es puramente
        asesor: NUNCA altera el VEREDICTO PASS/FAIL de la auditoría de
        `revisor` (ya emitido antes de este paso) ni bloquea el
        ensamblado/build/cierre de la Fase 7. Si `pixelshot` no está
        disponible o falla (dependencia faltante, error de Playwright/CDP,
        timeout), registra una fila "QA visual no disponible en esta corrida:
        `<razón>`" en la misma sección y continúa — la Fase 7 se da por
        completa igual.
```

## Bucle de figuras (canónico)

**Un solo procedimiento**, referenciado por las Fases 1 (árbol de problemas),
2 (mapa de estado del arte) y 5.5 (diagrama metodológico). No lo reimplementes
en cada fase.

La geometría de las tres figuras es **determinista**: no la dibuja un modelo.
`scripts/render_tikz.py` construye `diag_<name>.tex` desde una spec JSON
compacta (anchos que caben el token más largo, columnas equiespaciadas, anclas
reales en cada extremo, paleta y tamaños canónicos), `compile_tikz.py` lo
compila a PNG + SVG + preview, y `audit_tikz.py` responde los criterios
mecánicos. Medido en la corrida `2026-09-tept-depresion-ia-portable`: el bucle
anterior costaba **~28,8 min por figura** (tres despachos y tres fallos de
`disenador-tikz` sin reporte) y este cuesta **menos de 1 s** en el caso limpio y
~2,5 s en el peor caso de autofix.

```
1. Task -> disenador-tikz
   escribe `redaccion/specs/<name>.spec.json` (NO escribe LaTeX).
   Inyecta inline el contenido autorizado: el bloque del Investigador para el
   árbol, el bloque comentado al final de 04_estado_arte.tex para el mapa, y
   §10 para el metodológico.

2. DISPATCHER (inline, determinista -- nunca delegado):
   python3 scripts/figura.py <name> --spec specs/<name>.spec.json
   Salida: `FIGURA PASS: <name> (<t>s, <k> compilacion(es), presupuesto 180s OK)`
   o `FIGURA FAIL` + la lista de chequeos fallidos.

3. Segun la salida de figura.py:
   - `FIGURA PASS`                          -> continua al paso 4.
   - `spec invalida: ...`                   -> Task -> tikz-optimizer con el mensaje verbatim
   - `FIGURA FAIL` con fallo de auditoria   -> Task -> tikz-optimizer
   - `autofix no convergio` / `COMPILE FAILED` -> Task -> tikz-optimizer con el
     log `redaccion/sections/figuras/log_<name>.txt`
   Cualquier re-despacho a `tikz-optimizer` cuenta como un intento mas
   (paso 5) y vuelve al paso 2.

4. Contador de intentos: POR DIAGRAMA y POR CORRIDA (nunca global, nunca
   persiste entre corridas). Cuenta SOLO fallos deterministas (spec invalida,
   autofix que no converge, compile, auditoria): son los unicos que el
   dispatcher puede resolver sin criterio humano. El despacho inicial de
   `disenador-tikz` es el intento 1; cada re-despacho a `tikz-optimizer` suma
   uno mas. Tope = 4 intentos por diagrama (1 inicial + 3 remediaciones). Al
   llegar al 4.o fallo el dispatcher DETIENE el bucle -- no despacha un 5.o
   intento -- y escala al usuario con: (1) nombre del diagrama y su fase/§,
   (2) intentos usados vs. tope ("4/4 intentos"), (3) el mensaje de
   `figura.py` verbatim, (4) pedido explicito de guia al usuario. Nunca
   reintenta en silencio mas alla del tope ni abandona en silencio; no avanza a
   la siguiente fase sin la guia del usuario.

5. Task -> revisor-figuras (UNA sola vez por figura, FUERA del bucle)
   El bucle cierra con el PASS determinista del paso 3; recien ahi se pide el
   veredicto visual. Es la unica llamada a modelo de todo el bucle de figuras y
   esta acotada a proposito:

   - Una llamada por figura. Nunca se re-despacha dentro del bucle, asi que no
     se multiplica por los intentos. La version anterior lo metia dentro: hasta
     4 llamadas visuales por diagrama, y una de ellas midio 4,2 min
     (`artefactos/pipeline/30-fase2.md`, despacho #7).
   - Inyecta el reporte de auditoria completo (los chequeos mecanicos ya
     resueltos) y la RUTA EXACTA del unico archivo a leer:
     `redaccion/sections/figuras/fig_<name>-preview.png`. El preview esta
     limitado a 1400 px de lado mayor justamente para acotar la entrada.
   - Pidele SOLO los 4 criterios visuales. Los criterios mecanicos ya estan
     resueltos y no se re-evaluan.
   - PASS -> el diagrama esta listo.
   - FAIL -> NO reabre el bucle ni suma intentos. Corre UNA remediacion
     acotada: Task -> tikz-optimizer con las `CORRECCIONES` verbatim, un
     re-render y una re-verdicto. Si esa segunda verdicto tambien es FAIL, el
     dispatcher se detiene y escala al usuario. Nunca hay una tercera.
   - Si la Task vuelve sin reporte o supera 240 s de reloj, NO la re-despaches:
     registra el PASS determinista, deja el veredicto visual como
     `no obtenido` en el evento de la fase y dilo explicitamente al usuario.
     El estado por defecto ante un fallo del revisor visual es "no verificado",
     nunca "verificado".

   Regla de presupuesto: el presupuesto de 180 s de `figura.py` cubre el bucle
   DETERMINISTA. El veredicto visual se mide aparte (bloque `<usage>` del
   despacho, columna `Duracion` del `## Desglose por despacho`) y, sumado al
   determinista, no debe superar 240 s por figura. Un diagrama que lo exceda se
   reporta como degradado en el evento de la fase.
```

Presupuesto de reloj: `figura.py` sale con codigo distinto de cero si el bucle
completo supera `--budget-s` (180 s por defecto). Un diagrama que exceda los 3
minutos es un fallo del pipeline, no un caso a tolerar.

### Tamano de pagina de las figuras

`figura.py` **reporta siempre** el tamano fisico de la figura en cm (el raster de
200 DPI son 78,74 px/cm) y solo lo **exige** con `--page-fit WxH`. La plantilla
A4 de `main.tex` usa `margin=2.4cm`, asi que el presupuesto real de una figura
que deba entrar a tamano natural es `--page-fit 16.2x24`.

Regla: un diagrama entra a **tamano natural** o la corrida lo justifica por
escrito. Escalar con `\resizebox` no es gratis: en la corrida
`2026-09-tept-depresion-ia-portable` el mapa de 25 papers media 17,0 x 31,3 cm y
`main.tex` lo imprimia al ~74 %, de modo que los tamanos auditados se veian a
~9 pt reales.

Cuando un diagrama **no cabe** y no puede caber sin recortar contenido, la
salida es **partirlo en dos figuras** con nombres `<base>_a`, `<base>_b`, cada
una con su propia spec y su propia entrada en `main.tex`. Es lo que se hizo con
el mapa de estado del arte: 5 clusters x 5 papers son ~28,5 cm de alto a
cualquier tamano legible, asi que se entrego como `estado_arte_a` (grupos 1-3,
15,5 x 12,6 cm) y `estado_arte_b` (grupos 4-5 + cierre, 9,5 x 15,6 cm). El
dispatcher debe (a) partir el bloque de contenido autorizado entre las dos
specs, (b) correr el bucle de figuras una vez por cada una, y (c) pedir al
ensamblador de `main.tex` las dos entradas `\begin{figure}` con dos captions y
dos `\label`, y actualizar en §4 la referencia cruzada a ambas.

Nota de artefactos: `specs/<name>.spec.json` es la **unica fuente autoral** del
diagrama; `sections/diag_<name>.tex` es salida generada y **nunca se edita a
mano** (el siguiente render la sobrescribe). `specs/<name>.overrides.json`
guarda los anchos que el autofix determinista midio; si un nodo se acorta, la
entrada obsoleta debe borrarse para que el render vuelva a medir.

## Reglas de dependencia (haz que `revisor` las valide en cada gate)

- 3 subproblemas (§3) ↔ 3 objetivos específicos (§7), mapeo 1:1.
- Pregunta de investigación (cierre §3) ↔ objetivo general (§6).
- Hipótesis (§5) ↔ objetivo general (§6).
- Metodología (§10) ↔ objetivos específicos (§7), marco conceptual (§8) y
  equipo de trabajo (§9), cadena de valor. El punto 1 (Métodos) del
  desarrollo por objetivo de Metodología nombra el enfoque/algoritmo por
  subproblema con razonamiento causa-efecto explícito referenciando el marco
  conceptual (§8) — función que antes cubría el desaparecido §5.3 Enfoques
  teóricos.
- Metodología (§10) ↔ resultados esperados (§11) y productos esperados
  (§15): el punto 5 (Resultado conceptual esperado) y el punto 6
  (Producto(s) esperado(s)) del desarrollo por objetivo de Metodología son el
  insumo que §11/§15 consolidan y formalizan por fase.
- Equipo de trabajo (§9) deriva sus roles de los objetivos específicos (§7);
  nunca de la Metodología (§10).
- Cronograma de actividades (§14) ↔ fases de la Metodología (§10).
- Resultados esperados (§11) ↔ productos entregados en hitos del cronograma
  (§14) — referencia hacia adelante en el pipeline (§11 se redacta en la
  Fase 6, antes de que §14 exista en la Fase 6.45); se verifica en firme en
  la auditoría final de la Fase 7.
- Presupuesto (§13) ↔ Metodología (§10) y Cronograma (§14) — misma
  referencia hacia adelante, verificada en firme en la Fase 7.
- TRL 6 o 7 debe ser explícito en pertinencia (§2) y resultados esperados
  (§11); **nunca** se nombra en objetivo general (§6) ni en objetivos
  específicos (§7).

## Reglas de clasificación y ambigüedad

- Confirmación obligatoria ante ambigüedad: si `insumos-observador` marca un
  archivo como AMBIGUA para TDR y/o draft-base, el dispatcher DEBE detenerse
  y pedir confirmación al usuario antes de continuar (no autoresolver).
- El draft-base nunca es la única fuente: cuando existe, se complementa —no
  se reemplaza— con el mapa de MODE=explore y el resto de insumos de
  background.
- Sin bypass del gate: ambas rutas (DRAFT-EXISTS y NO-DRAFT) convergen en el
  mismo gate investigador→revisor→usuario existente; ninguna rama lo omite.
- Garantía retrocompatible: si no hay TDR ni archivos candidatos a
  draft-base (todo es background), la clasificación no agrega preguntas de
  confirmación adicionales. El pre-step de `bibliografo-propuesta`
  (MODE=explore) en la Fase 1 sigue siendo obligatorio para ambas rutas,
  incluida esta — no se omite ni se bypassea el gate.

## Reglas de gate (obligatorias)

- Tras cada gate, presenta el veredicto PASS/FAIL del revisor correspondiente
  y espera aprobación explícita del usuario antes de despachar la siguiente
  fase. **Tras cada gate, NO avances sin aprobación.**
- **Mantené el bloque `## Control de ejecución`** en
  `artefactos/estado_propuesta.md` en CADA transición de unidad, con el
  formato y los campos que define `.agent/workflows/_propuesta-steps.md`
  (fuente única): `mode`, `next_step`, `next_command`, `last_completed`,
  `intake_complete`, más `idea`/`idea_source`. En este comando `mode: auto`,
  y `next_step` apunta a la unidad siguiente de la tabla de pasos. No es
  opcional: `/propuesta-continuar` lee exactamente ese `next_step` para saber
  qué sigue, así que una corrida arrancada con `/propuesta` queda reanudable
  por pasos solo si el bloque está al día. Al terminar la Fase 7,
  `next_step: done` y `next_command: (none)`.
- **Auditoría de prosa antes del gate (`grant-flow-auditor`).** Cuando la
  unidad produjo o editó secciones narrativas (`redactor` o `investigador`),
  despachá `grant-flow-auditor` sobre esas secciones ANTES del `revisor`:
  audita micro-estilo (cadencia, voz activa, transiciones, fricción para el
  evaluador), no cumplimiento. Esa auditoría incluye, como paso propio, el
  pulido de prosa en español que define la skill `estilo-natural-es`
  (desmecanizar enumeraciones y
  aperturas formulaicas, variar longitud de frase y conectores, regla 70/30
  de vocabulario, con fidelidad byte a byte de cifras, fechas y citas). Pasale
  al subagente la ruta exacta de esa skill en el prompt de despacho, y exigile
  que devuelva su bloque de verificación (patrones detectados, tabla de
  cambios, invariantes y puntuación de naturalidad y fidelidad). El `revisor`
  sigue siendo la autoridad del veredicto PASS/FAIL; el auditor no lo
  reemplaza ni lo bloquea. No aplica a unidades sin prosa nueva (bucles de
  figura, presupuesto, bibliografía).
- En FAIL, vuelve a despachar con `Task` al agente responsable de la sección
  con las correcciones exactas del revisor, y repite el gate.
- No reescribas contenido de sección tú mismo; ese trabajo es de los
  subagentes especialistas.
- Tras el veredicto PASS de cada gate, actualiza tú (el dispatcher) el campo
  `gate_status` de `pending` a `pass` en el frontmatter de la(s) nota(s)
  `artefactos/vault/secciones/*.md` correspondientes a esa fase — el `revisor` solo tiene
  herramientas de lectura (Read/Grep/Glob) y no puede escribir archivos, así
  que esta responsabilidad es tuya, igual que ya lo es para
  `artefactos/estado_propuesta.md`. En FAIL, deja `gate_status` en `pending` (o
  cámbialo a `fail` si el re-despacho vuelve a fallar) hasta que el
  re-despacho apruebe.
- **PDF en cada compuerta de aprobación de usuario; DOCX solo al final
  (regla permanente).** En TODA compuerta que requiera aprobación explícita
  del usuario (cualquier "GATE Task → revisor... → usuario" o compuerta
  interactiva equivalente como G-Presupuesto, en cualquier fase del
  pipeline, no solo Fase 7), el dispatcher ensambla y compila un PDF ANTES
  de presentar el veredicto, para que la aprobación se dé sobre un documento
  real, no solo sobre fragmentos `.tex` o un resumen de texto. Mecánica:
  genera/actualiza `redaccion/main.tex` incluyendo el bloque de título en la portada,
  luego `\input{sections/00_frontmatter}`, luego `\setcounter{section}{1}`, y luego
  `\input{}` únicamente de las secciones que YA existen en disco en `redaccion/sections/`
  en ese punto de la corrida (mismo orden documentado en la Fase 7, "Orden del cuerpo" —
  nunca stubs ni placeholders de secciones no escritas todavía; nunca incluir
  `01_titulo_identificacion` ni párrafos de sección 1 en el cuerpo de `main.tex`), luego
  ejecuta `./build.sh` (nunca `./build.sh --docx` en estas compuertas
  intermedias) para producir `redaccion/main.pdf`. Comparte con el usuario la
  ruta del PDF junto con el veredicto del revisor (usa `pixelshot` si quieres
  dar un resumen visual además de la ruta). El `.docx` NUNCA se genera en
  estas compuertas intermedias — se produce UNA sola vez, en la Fase 7
  final, tras la aprobación del documento completo (`./build.sh --docx`, ver
  Fase 7).

Comienza ahora confirmando la idea del usuario y listando los insumos
detectados, luego arranca la Fase 0 despachando `insumos-observador` con
`Task`.
