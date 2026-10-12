# Morfeo IA — Marco Multi-Agente de Formulación de Propuestas de Investigación

<p align="center">
  <img src="https://raw.githubusercontent.com/LIAUNAL/propuestasmorfeo-ia/main/logos/logo_labIA_readme.png" alt="Logo Laboratorio de IA - UNAL" width="300">
  <br>
  <strong>Laboratorio de Inteligencia Artificial — Universidad Nacional de Colombia Sede Manizales</strong>
  <br>
  <em>Orquestación agéntica, formulación metodológica rigurosa y generación de propuestas científicas en LaTeX y Word</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/propuestasmorfeo-ia/"><img src="https://img.shields.io/pypi/v/propuestasmorfeo-ia.svg?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/propuestasmorfeo-ia/"><img src="https://img.shields.io/pypi/pyversions/propuestasmorfeo-ia.svg" alt="Python versions"></a>
  <a href="https://github.com/LIAUNAL/propuestasmorfeo-ia/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-green.svg" alt="License: Apache 2.0"></a>
  <a href="https://github.com/LIAUNAL/propuestasmorfeo-ia"><img src="https://img.shields.io/badge/LIA-UNAL_Manizales-black.svg" alt="LIA UNAL"></a>
</p>

---

**Morfeo IA** (`propuestasmorfeo-ia`) es un entorno de trabajo agéntico diseñado para redactar, estructurar y auditar propuestas completas de investigación y desarrollo tecnológico en Inteligencia Artificial. Produce documentos formales en **español** bajo formato LaTeX nativo (con exportación determinista a Word/DOCX), estructurados en 16 secciones metodológicas con coherencia matemática, lógica y presupuestal.

El sistema coordina un equipo de **11 subagentes especializados** guiados por compuertas de revisión (*gates* G0.5 a G7), auditoría cruzada de coherencia, generación determinista de diagramas TikZ y una capa de grafos de conocimiento dual conectada mediante el servidor MCP `codegraph`.

---

## Índice

1. [Instalación](#instalación)
2. [Inicio Rápido](#inicio-rápido)
3. [Comandos del CLI (`morfeo`)](#comandos-del-cli-morfeo)
4. [Tablero de Control Web (`morfeo ui`)](#tablero-de-control-web-morfeo-ui)
5. [Ecosistema de Agentes Especializados](#ecosistema-de-agentes-especializados)
6. [Flujo del Pipeline y Compuertas de Revisión](#flujo-del-pipeline-y-compuertas-de-revisión)
7. [Capa de Grafos de Conocimiento (Codebase-Memory)](#capa-de-grafos-de-conocimiento-codebase-memory)
8. [Bucle Determinista de Diagramas TikZ](#bucle-determinista-de-diagramas-tikz)
9. [Criterios de Estilo y Prosa Natural](#criterios-de-estilo-y-prosa-natural)
10. [Runtimes Soportados](#runtimes-soportados)
11. [Pruebas Automatizadas](#pruebas-automatizadas)

---

## Instalación

Morfeo se distribuye como paquete de Python instalable vía `pip` o `pipx`. El CLI base no impone dependencias externas obligatorias para mantener una huella ligera (~2 MB).

```bash
# Instalación recomendada en entorno aislado
pipx install propuestasmorfeo-ia

# O instalación directa con pip
pip install propuestasmorfeo-ia
```

Si deseas soporte extendido opcional para FastAPI y Uvicorn en el panel de control web:

```bash
pip install "propuestasmorfeo-ia[ui]"
```

*(El comando `morfeo ui` funciona de forma nativa con el servidor multihilo de la biblioteca estándar de Python sin requerir paquetes adicionales).*

---

## Inicio Rápido

Para iniciar un nuevo proyecto de propuesta en una carpeta independiente:

```bash
# 1. Crear el espacio de trabajo de la propuesta
morfeo init ~/propuestas/salud-mental-ia --title "Sistema de Alertas Tempranas en Salud Mental"

# 2. Entrar al proyecto creado
cd ~/propuestas/salud-mental-ia

# 3. Lanzar el panel de seguimiento visual en el navegador
morfeo ui

# 4. Inspeccionar el estado del proyecto desde la terminal
morfeo status
```

Dentro del directorio inicializado puedes ejecutar los comandos del asistente en Claude Code (`/propuesta-init`, `/propuesta-analizar`, `/propuesta-continuar`) o el pipeline de tu runtime preferido.

---

## Comandos del CLI (`morfeo`)

| Comando | Descripción |
|---|---|
| `morfeo init <dir> [--title] [--preset] [--tools]` | Inicializa un workspace autocontenido con los 67 activos base del marco. |
| `morfeo status [dir] [--json]` | Inspecciona la corrida activa, fases completadas, compuertas aprobadas y estado del PDF. |
| `morfeo ui [dir] [--port 8765] [--no-open]` | Despliega el Command Center web interactivo en tiempo real. |
| `morfeo compile [dir] [--docx] [--run <id>]` | Compila el proyecto LaTeX a PDF (`build.sh`) o exporta a Word (`--docx`). |
| `morfeo upgrade [dir] [--force]` | Actualiza plantillas y scripts del marco preservando insumos y propuestas existentes. |
| `morfeo audit [dir] [--json]` | Verifica la integridad criptográfica (SHA-256) de los archivos frente al manifiesto. |

> **Nota de compatibilidad:** El comando `marco` se mantiene disponible como alias idéntico de `morfeo`.

---

## Tablero de Control Web (`morfeo ui`)

El comando `morfeo ui` lanza un panel de control interactivo en el navegador (`http://localhost:8765`):

- **Pipeline y Compuertas:** Monitoreo en vivo de las 13 fases y el estado de aprobación de los 8 *gates* (G0.5, G1, G2, G3, G4, G5, G5.5, G6.4, G6.5, G7).
- **Telemetría de Uso:** Desglose del consumo acumulado de tokens, tool-uses y duración por fase a partir del registro del framework.
- **Grafos de Conocimiento:** Visores embebidos interactivos para explorar el grafo de literatura científica (`papers-graph`) y el mapa de relaciones del vault Obsidian (`vault-graph`).
- **Visor PDF Integrado:** Previsualización del documento LaTeX compilado con descarga directa.

---

## Ecosistema de Agentes Especializados

El marco cuenta con **11 subagentes especializados** con roles no solapados:

| Agente | Modelo sugerido | Responsabilidad |
|---|---|---|
| `coordinador-propuesta` | Sonnet | Referencia canónica del pipeline y ensamble final de `main.tex`. |
| `investigador` | Opus | Definición del árbol de problemas (§3), hipótesis (§5), objetivos (§6, §7) y marco conceptual (§8). |
| `redactor` | Opus | Prosa narrativa (§2, §9, §10, §11, §14, §15, front-matter y consideraciones éticas). |
| `grant-flow-auditor` | Sonnet | Auditoría micro-estilística de cadencia, voz activa y eliminación de fricción léxica. |
| `insumos-observador` | Sonnet | Ingesta y estructuración de insumos del usuario (PDFs, papers, TDRs, convocatorias). |
| `bibliografo-propuesta` | Sonnet | Construcción del estado del arte (§4) y bibliografía en BibTeX (§16, ≥50 refs APA). |
| `revisor` | Sonnet | Validación formal en cada puerta de revisión (*gate* PASS/FAIL). |
| `presupuestador` | Sonnet | Desglose financiero (§13): tabla de rubros, cofinanciación y aritmética exacta. |
| `disenador-tikz` | Sonnet | Autoría de la especificación JSON de los diagramas (nunca escribe LaTeX directo). |
| `revisor-figuras` | Sonnet | Juicio visual (escala, legibilidad, armonía) sobre el render PNG de las figuras. |
| `tikz-optimizer` | Sonnet | Corrección asistida de especificaciones JSON cuando falla la compilación o la auditoría. |

---

## Flujo del Pipeline y Compuertas de Revisión

El ciclo de formulación se divide en unidades metodológicas estrictas:

```text
Fase 0    Ingesta de insumos y clasificación TDR / borrador
  │
  ├── [GATE G0.5] Aprobación de tabla de secciones ajustada al TDR
  │
Fase 1    Árbol de problemas (§3) y pregunta de investigación
  ├── Bucle TikZ: figura arbol_problemas (render determinista)
  └── [GATE G1] Veredicto Revisor
  │
Fase 2    Estado del arte (§4, ≥30 refs Q1/Q2) e hipótesis (§5)
  ├── Bucle TikZ: figura estado_arte
  └── [GATE G2] Veredicto Revisor
  │
Fase 3    Justificación y pertinencia (§2, TRL 6/7 explícito)
  └── [GATE G3] Veredicto Revisor
  │
Fase 4    Objetivo general (§6) y 3 específicos (§7) — mapeo 1:1 con subproblemas
  └── [GATE G4] Veredicto Revisor
  │
Fase 5    Marco conceptual (§8) y equipo de trabajo (§9, roles derivados de §7)
  └── [GATE G5] Veredicto Revisor
  │
Fase 5.5  Metodología articulada (§10)
  ├── Bucle TikZ: figura metodologico
  └── [GATE G5.5] Veredicto Revisor
  │
Fase 6    Resultados esperados (§11) y consideraciones éticas (§12)
Fase 6.4  Presupuesto financiero (§13)
  └── [GATE G6.4] Veredicto Revisor
  │
Fase 6.45 Cronograma de actividades (§14, Gantt) y productos (§15)
Fase 6.5  Front-matter (Resumen, Resumen ejecutivo, Palabras clave)
  └── [GATE G6.5] Veredicto Revisor
  │
Fase 7    Auditoría cruzada final y ensamble de main.tex
  └── [GATE G7] Aprobación final y compilación PDF/DOCX
```

### Diagramas de Arquitectura y Flujo

- **Diagrama Interactivo (Archify):** Consulta [`docs/diagrams/morfeo-pipeline-flow.html`](docs/diagrams/morfeo-pipeline-flow.html) para explorar los componentes, dependencias cruzadas y artefactos en un visor SVG/HTML offline.
- **Diagrama de Flujo (Mermaid/SVG):** Visualiza la secuencia completa en [`docs/pipeline-flow.svg`](docs/pipeline-flow.svg) o revisa las notas de diseño en [`docs/pipeline-flow.md`](docs/pipeline-flow.md).

---

## Capa de Grafos de Conocimiento (Codebase-Memory)

Morfeo integra la capa de grafo mediante el servidor MCP `codegraph` (`@colbymchenry/codegraph`), gestionando dos corpus por corrida:

1. **`<run-id>-papers`:** Indexa el repositorio de literatura científica recolectada en `artefactos/scoping/papers/`, extrayendo clusters conceptuales y relaciones temáticas en `grafos/papers-graph-report.md`.
2. **`<run-id>-vault`:** Indexa el espejo Markdown compatible con Obsidian en `artefactos/vault/`, evaluando la conectividad de ideas entre secciones e insumos en `grafos/vault-graph-report.md`.

El script `scripts/graph_html.py` genera un gemelo visual interactivo en HTML para cada grafo (`grafos/<corpus>-graph.html`), permitiendo inspeccionar la red conceptual tanto en local como desde el visor del panel de control web.

---

## Bucle Determinista de Diagramas TikZ

Los diagramas (árbol de problemas, mapa del estado del arte y diagrama metodológico) no se codifican a mano en LaTeX. La geometría se genera mediante un compilador determinista:

```bash
python3 scripts/figura.py <name> --spec specs/<name>.spec.json
```

1. **Diseñador-TikZ** redacta únicamente la especificación en formato JSON (`specs/<name>.spec.json`).
2. `render_tikz.py` calcula anchos óptimos, equiespaciado de columnas, anclas y aplica la paleta institucional (UNAL, LabIA, GCPDS).
3. `compile_tikz.py` compila la figura y ejecuta el autofix determinista ante advertencias de `Overfull \hbox`.
4. `audit_tikz.py` valida mecánicamente 17 criterios técnicos (incluyendo legibilidad y dimensiones físicas).
5. **Revisor-Figuras** emite juicio visual exclusivamente sobre escala, armonía y centrado a partir del render PNG pregenerado.

---

## Criterios de Estilo y Prosa Natural

Toda la prosa generada en español pasa obligatoriamente por las directrices de dos metodologías integradas:

- **`estilo-natural-es`:** Garantiza cadencia variada, predominio de voz activa, transiciones fluidas y eliminación de fórmulas mecánicas habituales en modelos de lenguaje, manteniendo fidelidad estricta a datos, citas y cifras.
- **`depuracion-redundancias-es`:** Audita que cada párrafo introduzca un avance conceptual genuino, eliminando reiteraciones léxicas o argumentativas dentro de una misma sección.

---

## Runtimes Soportados

El marco admite ejecución multi-runtime:

- **Claude Code (Canónico):** Definición principal en `.claude/agents/` y `.claude/commands/`.
- **Google Antigravity:** Port generado en `.agent/workflows/` y `.agent/skills/`.
- **OpenCode:** Port generado en `.opencode/agents/` y `.opencode/commands/`.
- **Pi:** Port generado en `.pi/agents/` y `.pi/prompts/`.

Para sincronizar y validar los puertos secundarios ante cualquier modificación de los archivos base:

```bash
python3 scripts/gen-antigravity.py
python3 scripts/gen-opencode.py --check
python3 scripts/gen-pi.py --check
```

---

## Pruebas Automatizadas

El proyecto cuenta con una suite integral de pruebas unitarias y de integración que verifican la integridad del CLI, la compilación de diagramas y la coherencia del manifiesto:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

---

## Licencia

Distribuido bajo la licencia [Apache 2.0](LICENSE). Desarrollado por el **Laboratorio de Inteligencia Artificial de la Universidad Nacional de Colombia Sede Manizales**.
