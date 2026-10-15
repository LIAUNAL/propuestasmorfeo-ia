# Tablero de fases, subfases y grafo del manuscrito

Exploración para rediseñar cómo el Command Center presenta las fases del pipeline,
el avance sobre el manuscrito y las relaciones internas del documento, y para
unificar el estilo visual de todos los grafos del marco con el de
`papersmith-ai`. La exploración y la propuesta no tocaron código; U1 se
implementó después con su propia prueba.

## Specs

S1. Pedido del operador, textual:

> realiza una exploracion para mejorar la interaccion del tablero con el usuario
> respecto a las fases y los avances en el manuscrito. la idea es que el usuario
> puede ir avanzando entre fases desde cli o desde el mismo tablero. revisa que
> fases y sus subfases deberian ser visibles en el flujo, y como vamos informando
> de los avances en las ejecuciones del flujo del proyecto, hasta ir construyendo
> cada parte de la redaccin del documento. ademas, en el flujo de seguimiento de
> fases, al dar clic, el usuario deberia poder ver de forma resumida que esta
> haciendo el flujo, que agentes o skills se estan levantando, que artefactos se
> van generando, y la version parcial del manuscritok, cuando sea viable. ademas,
> la parte de las subfases de redaccion deben ser mas claras en el flujo, y debe
> poder interactuar al dar clic en dichas subfases de las secciones del paper,
> bajo que pricipios se estna escribiendo, reglas y estructuras de los parrafos,
> relaciones con otras secciones, etc. para esa fase, construir un grafo, parecido
> al que hiciste de sota, con mismo tipo de visualicion, en el qeu se muetren las
> conecciones e ideas princpales del manuscrito, con secciones o parrafos
> relevantes entre si, buscando dar respueta a la novedad dle paper. Revisa los
> tools, herramientas y formas de visualización, la iluminación, el manejo 3d ,
> etc de los grafos en https://github.com/LIAUNAL/papersmith-ai, para que uses
> esos mismos estilos en todos las construcciones de grafo de este proyecto

S2. La entrega es una propuesta: no se implementa nada hasta que el operador elija
entre las decisiones de la última sección.

## Mapa: lo que existe y lo que el tablero muestra

`PHASES_INFO` tiene **13 entradas** (`dashboard/static/index.html:2075-2089`) con
forma `{id, name, agent, gate, desc, tools, outputs}`. La tabla real de unidades
(`.claude/commands/_propuesta-steps.md:31-49`) tiene **15**, más `fase0` y `g0_5`.

| Unidad real (`_propuesta-steps.md`) | Gate real | En el tablero |
|---|---|---|
| `fase0`, `g0_5` | G0.5 | Fase 0 |
| `fase1a` (scoping temprano, subproblemas) | G1a | **no existe** |
| `fase1b` (corpus SOTA, `refs.bib` semilla, vault) | G1b | **no existe** |
| `fase1` (§3 + auditor + figura + revisor) | G1 | Fase 1 |
| `fase2` (§4+§5) | G2 | Fase 2 |
| `fase3` (§2) | G3 | Fase 3 |
| `fase4` (§6–§7) | G4 | Fase 4 |
| `fase5` (§8+§9) | G5 | Fase 5 |
| `fase5_5` (§10) | G5.5 | Fase 5.5 |
| `fase6` (§11+§12) | **sin gate** | Fase 6, con `gate: "G6"` inventado |
| `fase6_4` (§13) | `G budget` | Fase 6.4, como `G6.4` |
| `fase6_45` (§14+§15+§16) | **sin gate** | Fase 6.45, con `G6.45` inventado |
| `fase6_46` (§17+§18) | `G comunidades` | Fase 6.46, como `G6.46` |
| `fase6_5` (front-matter) | `G front` | Fase 6.5, como `G6.5` |
| `fase7` (auditoría final y ensamble) | `G final` | Fase 7, como `G7` |

Cinco brechas concretas, todas verificadas:

1. **Faltan las dos subfases que producen los insumos del paper.** `fase1a` y
   `fase1b` tienen gate propio y su salida es el corpus, el `refs.bib` semilla y
   los subproblemas: el usuario no puede ver la fase que decide de qué va el
   documento.
2. **El paso de estilo no tiene unidad ni representación.** `grant-flow-auditor`
   aparece embebido en el campo `agent` ("investigador & grant-flow-auditor") de
   otras fases (`index.html:2075-2089`), y la auditoría de redundancias
   (`depuracion-redundancias-es`) no aparece en ninguna parte del tablero.
3. **Los tres bucles de figura no tienen estado.** Viven como texto dentro de
   `desc` ("bucle del árbol de problemas TikZ"); no se ve en qué intento va
   ninguno, aunque el presupuesto es de 4 por diagrama y el agotamiento escala al
   usuario.
4. **Los nombres de compuerta no coinciden.** La tabla de pasos dice `G budget`,
   `G comunidades`, `G front`, `G final`; `status.py` usa `G6.4, G6.46, G6.5, G7`
   y además **inventa** `G6` y `G6.45` para dos pasos que no tienen compuerta
   (`status.py:72,80` frente a `_propuesta-steps.md:39-43`). Dos pasos sin gate no
   pueden aprobarse ni bloquearse: quedan en un estado que el tablero no sabe
   pintar.
5. **El drawer no hace nada.** `openDrawer` (`index.html:2130-2178`) muestra gate,
   agente, descripción, herramientas y salidas, y **no tiene un solo botón**. No
   hay forma de avanzar una fase desde el tablero, y tampoco desde el CLI hay un
   botón equivalente salvo escribir `/propuesta-continuar`.

## Mapa: señales de avance que ya existen y nadie consume

- `get_project_status` devuelve `workspace, version, active_run, run_details,
  all_runs, sections, gates, telemetria, totals, artifacts, archify_flow_ready,
  decisions_exists, idea_exists` (`core/status.py:365-381`). El tablero ignora
  `total_citations`, `archify_flow_ready`, `decisions_exists`, `idea_exists` y los
  indicadores `papers_graph`/`vault_graph`.
- **El bloque de control de ejecución de `estado_propuesta.md` nunca se parsea**:
  `next_step`, `mode` e `intake_complete` están en disco y no llegan al tablero.
  Es la pieza que haría posible decir «la siguiente unidad es X» sin adivinar.
- `artifacts` lista **solo `artefactos/*.md` de primer nivel**
  (`list_artifacts_info`, `status.py:262-276`): se pierden `pipeline/`,
  `scoping/`, `vault/`, `kit/` y `anexos/`.
- El frontmatter de `artefactos/pipeline/NN-fase*.md` trae `fase, agentes, gate,
  veredicto, fecha, tokens_total, tool_uses, duration_ms` (`20-fase1.md:1-9`), más
  `## Entradas`, `## Salidas` y `## Dependencias`. Es más rico que la tabla de
  telemetría que el tablero construye a partir de `_estado.md`
  (`status.py:237-260`), y la lista de agentes por fase **no se muestra**.
- El espejo `artefactos/vault/secciones/NN_*.md` lleva frontmatter con
  `tex_source`, `fase` y `gate_status` (`03_descripcion_problema.md:2-4`), así que
  la relación sección ↔ fase existe legible por máquina.
- `sections` calcula `words`, `citations` y `has_figures` por sección, y el estado
  es una heurística de dos valores (`SEALED` si supera 50 palabras, `DRAFTING` si
  no; `status.py:133-135`). No hay estado intermedio entre «vacía» y «sellada».

## Mapa: lo que NO existe legible por máquina

Esto condiciona el grafo del manuscrito y conviene decirlo sin rodeos.

- **Los principios de escritura y las reglas de párrafo son prosa.**
  `guiaProyectosIA_Agente.md` los enuncia sección por sección en Markdown
  narrativo (`:40-382`); `guia_ajustada_TDR.md` lo mismo; `redactor.md` y
  `estilo-natural-es/SKILL.md` son texto. No hay campos estructurados.
- **Los cuatro pares de trazabilidad** (subproblemas↔objetivos específicos,
  pregunta↔objetivo general, hipótesis↔objetivo general, metodología↔objetivos)
  viven solo en prosa (`AGENTS.md` regla 5, criterios de compuerta de
  `_propuesta-steps.md`). Ningún JSON ni YAML los codifica.
- `redaccion/etiquetas.json` es un mapa de `cleveref` (`sec:*` → "la sección N"),
  no un grafo de relaciones.

Conclusión: **el grafo del manuscrito no se puede derivar del repositorio tal como
está.** O se autoriza y se audita contra el documento, o se construye antes una
fuente estructurada que hoy no existe.

## El estilo de grafo de `papersmith-ai`, extraído

| Pieza | Cómo está hecho | Evidencia |
|---|---|---|
| Escena | WebGL oscuro sobre `#0a0a10`, con `FogExp2` a `0.35/radio` para profundidad | `viewer.js:44,171` |
| Iluminación | **Sin luces ni sombras:** esferas `MeshBasicMaterial` con color por instancia, más halos de degradado radial blanco→transparente pintados en canvas | `viewer.js:180,55-70` |
| Nodos | `InstancedMesh` de esferas 20×14; sol r=22, planetas r=10; halos de 30 y 15 px | `viewer.js:47-52` |
| Color | Paleta semántica: 11 colores de slot y 7 de relación | `render_atlas.py:32-54` |
| Aristas | Órbitas en `LineBasicMaterial` (`0x2a3350`, op. 0.55); lazos de familia en `LineDashedMaterial` (`0x9b7ede`, dash 40 / gap 28, op. 0.6, sin `depthWrite`) | `viewer.js:213,268` |
| Etiquetas | Sprites de canvas con tamaño constante en pantalla, op. 0.85, con sombra | `viewer.js:75-100` |
| Selección | Raycaster de 14 px, lo no elegido baja a 0.16, doble clic acerca, `OrbitControls` que se detiene al arrastrar | `viewer.js:45,286,374-390` |
| Determinismo | Cielo de estrellas con LCG propio, nunca `Math.random` | `viewer.js:99-104` |
| Distribución | Espiral de ángulo áureo, radios orbitales por profundidad (0/90/170/250), lifts por familia y miembro, inclinación máx. 0.9 | `render_atlas.py:56-64` |
| Empaque | HTML autocontenido, **sin CDN y sin `<script src>`**, bundle three.js + OrbitControls vendorizado (564 KB), build reproducible y aviso de terceros | `odd/tasks/atlas-3d-threejs.md` |

El tablero de `papersmith-ai` añade el resto: un solo sistema de tokens, dos
temas, **ningún color literal fuera de los bloques de tema**, elevación con
resplandor, anillo de recorte, oposición de *tracking* y de radios, sostenido por
`styles.test.ts` y Playwright (`odd/tasks/dashboard-archify-restyle.md`).

**Y una brecha ya presente en este proyecto:** `scripts/graph_html.py:132-133`
declara *Three.js from robust CDN with internal fallback* y carga solo el CDN; el
fallback **no existe**. Los dos grafos generados de la corrida dependen de
`cdnjs.cloudflare.com` (una ocurrencia en `papers-graph.html` y otra en
`vault-graph.html`). Sin red no se dibujan. Adoptar el contrato de `papersmith-ai`
no es cosmético: cierra ese defecto.

## Propuesta

### 1. Una sola fuente de verdad para el modelo de fases

Hoy el mismo modelo está escrito tres veces: `PHASES_INFO` en el tablero,
`CANONICAL_GATES` en `status.py:45-59`, y la tabla de `_propuesta-steps.md`. Las
tres se contradicen en los nombres de compuerta y en el número de unidades. Se
propone que la tabla de pasos sea la fuente y que `status.py` la lea, con las
unidades, su gate real, sus secciones de salida y sus agentes. `PHASES_INFO` pasa a
ser dato derivado, no constante duplicada. Dos pasos sin gate se declaran sin gate,
no con un gate inventado.

### 2. Hacer visibles las subfases, en dos niveles

- **Fases**: las 15 unidades reales, incluidas `fase1a` y `fase1b`, con su gate
  propio y su salida.
- **Subfases de redacción**: dentro de cada unidad, la cadena que la compone
  (agente redactor → `grant-flow-auditor` → bucle de figura si aplica → `revisor`
  → gate). El paso de estilo deja de ser un sufijo en el campo `agent` y pasa a ser
  un eslabón visible con su propio estado, igual que la auditoría de redundancias.

### 3. Estado por unidad, con lo que ya está en disco

Tres estados, no dos: **pendiente**, **en curso** y **cerrada**, más **bloqueada**
cuando el gate devolvió FAIL. La fuente es el frontmatter de
`artefactos/pipeline/NN-fase*.md` (que ya trae veredicto y agentes) más la tabla de
`_estado.md`, y la sección ↔ fase sale del frontmatter del vault.

Para el estado **en curso** hace falta un latido que hoy no existe: el
`NN-fase*.md` se escribe por evento, no al arrancar. La pieza mínima es que el
dispatcher escriba `artefactos/pipeline/_en_curso.json` con `{fase, agentes,
skill, artefacto_esperado, inicio}` al abrir la unidad y lo borre al cerrarla. Sin
eso, «qué agentes se están levantando» solo se puede mostrar después, nunca
mientras ocurre.

### 4. El clic: qué debería mostrar el drawer

| Bloque | Contenido | De dónde sale |
|---|---|---|
| Qué está haciendo | Nombre de la unidad y su descripción operativa | Tabla de pasos |
| Agentes y skills | Lista de subagentes y skills que levanta, con el que está activo en negrita | `agentes` del frontmatter + `_en_curso.json` |
| Artefactos que va dejando | Archivos de `## Salidas` que ya existen, con su tamaño y su hora | `## Salidas` + disco |
| Manuscrito parcial | Secciones de esa unidad con conteo de palabras, y el PDF más reciente con fecha y páginas | `sections` + `run_details` |
| Costo | Tokens, tool-uses y duración de esa unidad | Frontmatter y `_estado.md` |
| Siguiente paso | La unidad que sigue y el comando exacto para avanzarla | `next_step` de `estado_propuesta.md` |

La «versión parcial del manuscrito, cuando sea viable» tiene una respuesta honesta:
el PDF solo existe cuando `build.sh` ha corrido. Lo que sí es siempre viable es el
mapa de secciones con su conteo y la fecha del último PDF. Si se quiere un parcial
por unidad, hay que guardar una copia en
`artefactos/pipeline/snapshots/<unidad>.pdf`, y eso es una decisión de peso en disco.

### 5. Avanzar desde el CLI o desde el tablero

El tablero es un servidor HTTP de la biblioteca estándar. Para **ejecutar** una
unidad tendría que lanzar un subproceso con el CLI de un agente, lo que trae
credenciales, sesión viva y consentimiento al proceso del tablero. Además las
compuertas están diseñadas para parar y esperar a una persona: un avance automático
las contradice.

Tres caminos, en orden de riesgo creciente:

- **A. Sugerir.** El drawer muestra la unidad siguiente y el comando exacto
  (`/propuesta-continuar`), con un botón que lo copia al portapapeles. Cero riesgo,
  cero credenciales. Es lo que se puede hacer ya.
- **B. Encolar.** El tablero escribe la intención en
  `artefactos/pipeline/_solicitud.json` y la sesión de agente la lee al siguiente
  turno. El avance sigue siendo del agente, pero la decisión nace en el tablero.
- **C. Lanzar.** El tablero invoca el CLI del agente. Requiere credenciales en el
  proceso, un modo de sesión no interactivo y renunciar a las compuertas humanas.

### 6. El grafo del manuscrito

Sin fuente estructurada, el grafo tiene que **autorizarse y auditarse**, no
derivarse. La forma que mejor encaja con lo que el marco ya hace con las figuras
TikZ: el modelo escribe solo una **spec JSON**, un renderizador determinista
calcula la geometría, y una auditoría mecánica verifica que lo dibujado
corresponde a lo declarado.

Piezas:

1. `redaccion/specs/manuscrito.spec.json`: nodos por sección y por idea, aristas
   tipadas (`responde-a`, `depende-de`, `evidencia-de`, `contradice`, `cierra`), y
   para cada nodo el ancla textual (la etiqueta `sec:*` de `etiquetas.json`) y la
   sección de la que sale. La firma semántica reutiliza la paleta de relaciones de
   `papersmith-ai`.
2. Renderizador determinista con el estilo adoptado: mismo empaquetado
   autocontenido, misma paleta por rol, mismas aristas y halos, mismo determinismo.
3. Auditoría mecánica: toda arista debe apuntar a un nodo existente, toda sección
   citada debe existir en `sections/`, y el grafo debe cubrir los cuatro pares de
   trazabilidad. Los pares que hoy solo viven en prosa entran aquí como
   restricción verificable, que es la única forma de que dejen de ser una promesa.
4. Quién lo escribe: `investigador` propone el grafo de ideas y relaciones,
   `redactor` ancla cada nodo a su párrafo y `revisor` audita que el grafo
   responda a la novedad declarada en §6 y §11.

### 7. Unificar el estilo de todos los grafos

Cuatro construcciones quedan bajo el mismo contrato: `papers-graph.html` y
`vault-graph.html` (hoy con CDN y sin fallback), el Atlas del tablero y el grafo
nuevo del manuscrito. El contrato: HTML autocontenido sin red, paleta semántica
única, mismo modelo de iluminación sin luces, mismas aristas y halos, mismo
determinismo, y los tokens de color del tablero en un solo bloque de tema.

## Decisiones que hay que tomar antes de implementar

1. **Avance desde el tablero:** A (sugerir), B (encolar) o C (lanzar).
2. **Grafo del manuscrito:** spec autorizada y auditada (propuesta), o construir
   antes una fuente estructurada de principios y trazabilidad, que es trabajo de
   otra magnitud.
3. **3D frente a 2D para los grafos:** adoptar el bundle vendorizado
   (`papersmith-ai` usa 564 KB más OrbitControls) o conservar la vista 2D actual
   manteniendo la paleta y la iluminación del contrato 3D.
4. **Parciales del manuscrito:** mostrar el último PDF compilado, o guardar una
   copia por unidad en `artefactos/pipeline/snapshots/`.
5. **Latido `_en_curso.json`:** aceptar el cambio en el dispatcher, o renunciar a
   mostrar el progreso mientras ocurre.

## Unidades de trabajo propuestas

| # | Unidad | Depende de |
|---|---|---|
| U1 | Tabla de pasos como fuente única; `status.py` la lee y `PHASES_INFO` se deriva | — |
| U2 | Unidades reales y subfases de redacción visibles, con gate y sin gate | U1 |
| U3 | `_en_curso.json` en el dispatcher y estado «en curso» en el tablero | U1 |
| U4 | Drawer con agentes, artefactos, manuscrito parcial, costo y siguiente paso | U1, U2 |
| U5 | Avance según la decisión 1 | U4 |
| U6 | Contrato de estilo de grafos, sin CDN, aplicado a los dos grafos existentes | D3 |
| U7 | Spec y renderizador del grafo del manuscrito, con auditoría mecánica | U6, D2 |

## Log

L1 (2026-10-15, pedido original): la exploración completa, citada en S1.

L2 (2026-10-15, evidencia del mapa): subagente `gentle-ai-explore`; el handoff
completo está citado en las secciones de mapa. El estilo de los grafos se extrajo
del clon de `papersmith-ai` en la ruta temporal que dejó `fetch_content`.

L3 (2026-10-15, hallazgo propio durante la exploración): el fallback de three.js
que declara `scripts/graph_html.py:132` no existe. Es un defecto del marco, no de
la corrida, y lo arregla la unidad U6.

L4 (2026-10-15, U1 implementada): antes de empezar, la comprobación sobre los
artefactos mostró que la divergencia era peor de lo que decía el mapa. Cuatro
vocabularios distintos: la lista canónica de `status.py` (13 ids, **sin `G1a` ni
`G1b`**, con `G6` y `G6.45`); la tabla de pasos (12 compuertas más `G0.5`, con
nombres en prosa); el `_estado.md` de la corrida, que sí trae `G1a` y `G1b`; y el
frontmatter por unidad, con `none`, `G-Presupuesto`, `G front` y una vacía. El
`13/13` de la corrida era la coincidencia de dos treces distintos.

Se creó `src/morfeo/core/pipeline_units.py` como inventario único (16 unidades,
13 compuertas, alias de prosa y de artefacto, y las etiquetas sin compuerta
declaradas), `status.py` deriva de ahí su lista canónica y publica
`pipeline_units` en el sobre, y `tests/test_pipeline_units.py` ata el inventario a
la tabla de pasos para que una divergencia falle ahí. Once pruebas nuevas, 155 en
total. Verificación sobre la corrida: las compuertas canónicas pasan a ser
`G0.5, G1a, G1b, G1, G2, G3, G4, G5, G5.5, G6.4, G6.46, G6.5, G7`, todas PASS, sin
`G6` ni `G6.45`, y el total sigue siendo 13/13.

Queda pendiente U2 (que el tablero derive su flujo de `pipeline_units` y muestre
las subfases de redacción) y las demás unidades, que dependen de las cinco
decisiones abiertas.

L5 (2026-10-15, U2 implementada): la lista de fases del tablero pasa a derivarse
del sobre. Se eliminó la constante de trece entradas y **no se dejó respaldo
duplicado**: sin inventario, el flujo lo dice en lugar de mostrar una lista vieja
que parece correcta. El cajón de cada unidad muestra ahora la compuerta (o «sin
compuerta propia», con la nota de que la unidad se detiene igual una vez), los
agentes que levanta, las skills que aplica, las secciones del manuscrito con su
conteo de palabras y su estado, y la unidad siguiente. No hizo falta tocar
`getPhaseVerdict`: ya resolvía por id de compuerta y, para las unidades sin
compuerta, cae a la tabla de telemetría, que trae una fila por unidad.

Verificación en navegador sobre la corrida: **16 pasos en el flujo**, con `fase1a`
y `fase1b` presentes; tres unidades sin compuerta declaradas (`g0_5`, `fase6`,
`fase6_45`); **cero compuertas inventadas** en las tarjetas. El cajón de `fase1a`
muestra «GATE G1A: PASS», los agentes `bibliografo-propuesta` e `investigador` y
la unidad siguiente; el de `fase6` muestra «SIN COMPUERTA PROPIA» y explica que se
detiene igual una vez. Cuatro pruebas nuevas, 159 en total.
