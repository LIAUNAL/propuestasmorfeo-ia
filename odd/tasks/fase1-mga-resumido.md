# Fase 1 reorder and MGA resumido tab

Objective: reorder the early pipeline (1a scoping, 1b trees, 1c SOTA corpus, 1 MGA resumido + §3) for base and SGR flows, and add an "MGA resumido" dashboard tab before "Secciones".
Branch: `feat/fase1-mga-resumido`. Delivery: ask-on-risk. Runner: `uv run python -m unittest discover tests -p "test_*.py"` and `npm test`.

## Specs

- S1. Unit order for both flows (verbatim):
  "Fase 0: intake e insumos (igual que flujo base)
  G0.5: Guia al tdr (igual que flujo base)
  Fase 1a: Scouping y subproblemas (igual que flujo base)
  Fase 1b: Arbol de problemas y arbol de objetivos -> debes generar el arbol de problemas y objetivos según las reglas generales para sgr en ambos tipos de proyectos
  Fase 1c: Corpus SOTA y semilla bibliográfica
  Fase 1: MGA resumido"
  Scope: "Actualiza el flujo de las fases para flujos base de proyectos morfeo y para flujos proyectos sgr (actualiza flujo general y fases Pipeline del tablero"
- S2. Fase 1b writes both trees (problem and objective) with the MGA rules, in both flows. The objective tree is no longer first written in Fase 4.
- S3. Fase 1 produces the MGA resumido artifact and then derives §3 from it, under gate G1 (user decision L2).
- S4. Dashboard tab: "construye una pestaña antes de secciones, que se llama MGA resumido". It renders the MGA resumido artifact.
- S5. MGA resumido content, verbatim:
  "# Plantemiento del problema

  Parrafo 1:  ##Problema central: copiar problema central del arbol de problemas, textual pasalo
  Parrafo 2: ## Contexto general de la problemática:
  Introduce el problema desde el sector de aplicación, contextualizando desafíos operativos, económicos o sociales, describir mejor el problema central, delimitar la ubicacion (departamentos o regiones). Luego, a forma de concluding declarar las causas directas del arbol de problemas.

  Parrafo 3: expande la causa raiz 1.  Para proyecto de IA aplicada busca relacionar la causa raiz 1 con levantamiento de datos sensores, bateria de pruebas, levantamiento de informacion,y construccion de base de datos (no hay infrastructura, se requieren especialistas, apoyo comunidades para levantamiento de datos), calidad de datos, descentralizados.

  Parrafo 4: expande la causa raiz 2. Para proyecto de IA aplicada busca relacionar la causa raiz 2 con la necesidad de plataforma interoperable que se alimente de datos en causa 1, con buena conectividad, accessible, buena interaccion con el usario y con la necesidad de desarrollar modelos de ia generativa y predictiva, agentes de ia, proceso de datos, multimodal, baratos, desplegables, muchas variables,  etc

  Parrafo 5  expande la causa raiz 3  la cual debe estar alineada con la Apropiacion social y transferencia de la tecnologia (pocos estudios, no en colombia), barrera con las comunidades, que lo apropien, que tenga impacto en ellos.

  Nota: los lineamientos del parrafo 3 a 5 deben estar relacionados con la guía para construir el arbol de problemas.

  ## Magnitud del problema:

  encontrar cifras que sustenten cada causas raiz.  para generar indicador de linea base. Explora cual debe ser indicador base según el arbol de problemas y la descripción de las causas, busca el instigador mas flexible y cómodo de cuantificar. Para proyectos de ia aplicada trata de alinearlo con la plataforma, como indicador base. Construye de 2 a 3 párrafos que expandan este idea.

  Crea una tabla con los indicadores que se sacan de la magnitud del problema, y resaltar el que buscamos obtener en el proyecto."
  Assumption: "causa raiz N" means direct cause N of the problem tree (the three subproblems).

## Tasks

- [x] T1 (S1, S2, S3) pipeline units, gates, status, prompts (propuesta.md, steps, continuar, agents), docs — route inline — 74ab934, 768cf7f (general flow diagram)
- [x] T2 (S4, S5) MGA resumido artifact contract, backend route, dashboard tab, tests — route inline — e05caf0

## Log

- L1 (2026-10-20) user request: pasted block quoted in S1–S5 ("Actualiza el flujo de las fases para flujos base de proyectos morfeo y para flujos proyectos sgr ...").
- L2 (2026-10-20) decision on §3: "Fase 1 hace ambos (Recomendado)" — Fase 1 writes the MGA resumido and then derives §3 from it, same gate G1.
- L3 Route: inline (no writer trigger: tasks share prompt files). Explorer mapping delegated (mapping trigger: >5 lookups across core, dashboard, commands, agents, docs, tests).
- L4 T1: RED 4 failures in tests/test_pipeline_units.py (16 units, 15 gates, chain fase1a→fase1b→fase1c→fase1); GREEN after units/steps edit. G1b now names the trees gate, G1c the SOTA corpus. Ports and kit regenerated, --check clean. Archify diagram re-pinned to 74ab934 and re-rendered with a new lane, check reports no failures.
- L5 T2: RED 4/4 in tests/js/mga.tab.test.mjs; GREEN after adding the `mga` tab (`loadMgaResumido`, reads `/api/artifact?file=artefactos/mga_resumido.md`, existing renderMarkdown; no backend change). Trees tab order test now expects «MGA resumido» after it. Suites: Python 339 OK, JS 73 OK.
- L6 Review: full branch exceeded the budget (lens_context_budget_exceeded); user chose "Tramos de código (Recomendado)". Slice code (8 files) and slice prompts (7 files) reviewed in detached worktrees with readability+reliability, both approved and acknowledged. Fixed afterwards: MGA tab tells 404 from other errors, Fase 1 injects the objective tree too, G1b records its sub-table, compatibility note for runs that recorded the corpus as G1b, and the investigador may update trunk.magnitude in Fase 1 (re-approval). Gate-id reuse stays as advisory.
- L7 (2026-10-20) user: "revisa que el logo de morfeo en cada proyecto al levantar el tablero se vea en el tablero ui arriba a la izquierda y en la pestaña respectiva del navegador. por ejemplo para el que estmaos probando de regalias sale el logo de smith no el de morfeo". Evidence: the server sends Morfeo's bytes; PaperSmith (Smith logo) runs on 127.0.0.1 with the same /favicon.ico and /favicon.png paths, and Morfeo cached them for 24 h. Fix eafcee1: ?app=morfeo cache key on icons and logo, no-cache on brand assets; tests/test_dashboard_branding.py (RED 2 → GREEN).
