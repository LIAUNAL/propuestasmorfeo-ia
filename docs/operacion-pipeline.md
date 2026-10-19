# Operación del pipeline

Material que necesita solo quien despacha el pipeline (el asistente primario
o el runtime que haga ese papel). Salió de `AGENTS.md` porque ese archivo se
carga en cada llamada a un subagente, y este contenido no le sirve a ninguno.
Las reglas globales, el roster y las skills siguen en `AGENTS.md`.

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
18 secciones con gates sigue `/propuesta` o el
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
