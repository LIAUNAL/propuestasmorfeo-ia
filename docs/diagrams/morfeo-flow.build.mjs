/**
 * Source for `docs/diagrams/morfeo-pipeline-flow.html` and architecture flow.
 *
 * Regenerable via:
 *   node docs/diagrams/morfeo-flow.build.mjs
 * or:
 *   node docs/diagrams/morfeo-flow.build.mjs /tmp/morfeo-flow.json
 *   node ~/.claude/skills/archify/bin/archify.mjs render architecture \
 *     /tmp/morfeo-flow.json docs/diagrams/morfeo-pipeline-flow.html \
 *     --repo-root .
 */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const REPO = fileURLToPath(new URL('../../', import.meta.url)).replace(/\/$/, '');

const S = (p, line, end_line) => {
  const r = { path: p };
  if (line) r.line = line;
  if (end_line) r.end_line = end_line;
  return [r];
};

const agentMeta = (name) => {
  const p = `${REPO}/.claude/agents/${name}.md`;
  if (!fs.existsSync(p)) return { sub: 'agent', end: 10 };
  const lines = fs.readFileSync(p, 'utf8').trimEnd().split('\n');
  return { sub: 'subagente especializado', end: lines.length };
};

const A = (name) => S(`.claude/agents/${name}.md`, 1, agentMeta(name).end);
const K = (name) => S(`.claude/skills/${name}/SKILL.md`, 1, 30);

export const NODE_PURPOSES = {
  // 0 · Morfeo CLI & Workspace
  cliInit: {
    title: 'morfeo init',
    line1: 'Inicializa un espacio de trabajo reproducible y aislado para la corrida activa bajo proposals/<run-id>/.',
    line2: 'Despliega la estructura de cuatro subcarpetas e instala los activos base del marco de redacción.'
  },
  kitBundle: {
    title: 'morfeo._kit',
    line1: 'Empaqueta y distribuye plantillas LaTeX, bibliografía base y configuraciones de agentes.',
    line2: 'Garantiza reproducibilidad determinista e independencia total de dependencias externas.'
  },
  runRoot: {
    title: 'proposals/<run-id>/',
    line1: 'Directorio raíz autocontenido con carpetas insumos/, artefactos/, grafos/ y redaccion/.',
    line2: 'Aísla la ejecución de la propuesta evitando cualquier dispersión de archivos en el repositorio.'
  },
  cliStat: {
    title: 'morfeo status',
    line1: 'Audita el estado de avance, conteo de palabras y cumplimiento de compuertas de revisión.',
    line2: 'Genera el sobre estructurado de estado para inspección y control de calidad del pipeline.'
  },
  cliComp: {
    title: 'morfeo compile',
    line1: 'Ejecuta la compilación determinista del documento LaTeX a formato PDF y exportación Word.',
    line2: 'Valida referencias cruzadas, sintaxis BibTeX y renderizado de figuras vectoriales TikZ.'
  },

  // 1 · Ingesta & TDR (Fase 0)
  cmdAnalizar: {
    title: '/propuesta-analizar',
    line1: 'Inicia el protocolo de intake examinando la idea del usuario y documentos aportados.',
    line2: 'Estructura el checklist inicial de requerimientos antes de avanzar al scoping formal.'
  },
  insumosObs: {
    title: 'insumos-observador',
    line1: 'Extrae y clasifica recursivamente PDFs, papers y notas depositadas en la carpeta insumos/.',
    line2: 'Consolida la base documental estructurada compartida por los demás agentes del pipeline.'
  },
  insumosMd: {
    title: 'insumos.md',
    line1: 'Registro Markdown normalizado con el inventario, extractos y alcance de insumos.',
    line2: 'Opera como memoria documental de verdad para delimitar los alcances del proyecto.'
  },
  gate05: {
    title: 'GATE G0.5 (TDR)',
    line1: 'Compuerta formal de revisión de términos de referencia y alineación temática.',
    line2: 'Requiere visto bueno explícito del usuario para autorizar la transición a redacción.'
  },

  // 2 · Problema & TikZ (Fase 1)
  invProb: {
    title: 'investigador (Fase 1)',
    line1: 'Formula la descripción contextual del problema (§3) y la pregunta central de investigación.',
    line2: 'Delimita con precisión técnica los tres subproblemas fundamentales a resolver.'
  },
  tikzTree: {
    title: 'disenador-tikz (Árbol)',
    line1: 'Diseña la especificación JSON estructurada del árbol de problemas sin tocar LaTeX manual.',
    line2: 'Modela causas raíces, problema central y efectos para su compilación visual.'
  },
  figEngine: {
    title: 'figura.py',
    line1: 'Motor determinista de cálculo geométrico, renderizado y compilación de figuras TikZ.',
    line2: 'Audita criterios mecánicos de overflow, espaciado y tipografía de manera inmediata.'
  },
  revFig: {
    title: 'revisor-figuras',
    line1: 'Evalúa criterios visuales sobre el PNG generado: escala, legibilidad, centrado y balance.',
    line2: 'Emite dictamen PASS o transfiere incidencias al optimizador de especificaciones.'
  },
  gate1: {
    title: 'GATE G1 (Problema)',
    line1: 'Compuerta formal de validación de la descripción del problema y árbol de causas.',
    line2: 'Verifica la coherencia estricta entre la pregunta central y los tres subproblemas delimitados.'
  },

  // 3 · SOTA & Hipótesis (Fase 2)
  bibSota: {
    title: 'bibliografo-propuesta (SOTA)',
    line1: 'Construye el estado del arte (§4) respaldado con al menos 30 referencias Q1/Q2 recientes.',
    line2: 'Estructura la discusión comparativa en torno a los tres subproblemas del proyecto.'
  },
  invHip: {
    title: 'investigador (Hipótesis)',
    line1: 'Formula la hipótesis de investigación (§5) como una proposición técnica falsable.',
    line2: 'Conecta la solución metodológica propuesta con la pregunta central del proyecto.'
  },
  tikzSota: {
    title: 'disenador-tikz (SOTA)',
    line1: 'Diseña la especificación JSON del mapa conceptual o taxonómico del estado del arte.',
    line2: 'Visualiza clusters temáticos, brechas y frontera del conocimiento en formato vectorial.'
  },
  gate2: {
    title: 'GATE G2 (SOTA & Hipótesis)',
    line1: 'Compuerta formal que audita calidad bibliográfica Q1/Q2 y falsabilidad de la hipótesis.',
    line2: 'Exige aprobación antes de avanzar a la justificación técnica y territorial del proyecto.'
  },

  // 4 · Justificación & Objetivos (Fases 3 y 4)
  redJust: {
    title: 'redactor (Justificación)',
    line1: 'Redacta la justificación y pertinencia (§2) en seis párrafos rigurosos según la guía.',
    line2: 'Articula madurez tecnológica TRL 6 o 7, impacto socioeconómico y alineación con ODS.'
  },
  audJust: {
    title: 'grant-flow-auditor (Justificación)',
    line1: 'Audita micro-estilística, cadencia oracional, voz activa y transiciones narrativas.',
    line2: 'Erradica patrones mecánicos de IA aplicando la norma académica estilo-natural-es.'
  },
  gate3: {
    title: 'GATE G3 (Justificación)',
    line1: 'Compuerta formal que revisa la pertinencia territorial y solidez de la justificación.',
    line2: 'Valida el cumplimiento del estándar de seis párrafos y referencias de impacto.'
  },
  invObj: {
    title: 'investigador (Objetivos)',
    line1: 'Define el objetivo general (§6) y los tres objetivos específicos (§7) del proyecto.',
    line2: 'Establece un mapeo biyectivo 1:1 inalterable entre subproblemas y objetivos específicos.'
  },
  gate4: {
    title: 'GATE G4 (Objetivos)',
    line1: 'Compuerta crítica que audita la consistencia lógica entre subproblemas y objetivos.',
    line2: 'Verifica que ningún objetivo mencione explícitamente TRL y autoriza el marco conceptual.'
  },

  // 5 · Marco Conceptual & Equipo (Fase 5)
  invMarco: {
    title: 'investigador (Marco Conceptual)',
    line1: 'Elabora el marco conceptual (§8) definiendo constructos teóricos y matemáticos clave.',
    line2: 'Fundamenta los algoritmos y técnicas de IA que sustentan la metodología posterior.'
  },
  redEquipo: {
    title: 'redactor (Equipo de Trabajo)',
    line1: 'Estructura la sección de equipo de trabajo (§9) justificando cada perfil profesional.',
    line2: 'Deriva los roles exclusivamente de los objetivos específicos y nunca de la metodología.'
  },
  gate5: {
    title: 'GATE G5 (Marco & Equipo)',
    line1: 'Compuerta formal que valida suficiencia teórica y coherencia de perfiles del equipo.',
    line2: 'Garantiza que no existan roles huérfanos ni desacoplados de los objetivos del proyecto.'
  },

  // 6 · Metodología & Diagrama (Fase 5.5)
  redMet: {
    title: 'redactor (Metodología)',
    line1: 'Redacta la metodología (§10) detallando fases operativas, técnicas y validación experimental.',
    line2: 'Articula la cadena de valor con razonamiento causa-efecto ligado al marco conceptual.'
  },
  tikzMet: {
    title: 'disenador-tikz (Metodología)',
    line1: 'Elabora la especificación JSON del diagrama metodológico integral del proyecto.',
    line2: 'Ilustra flujo de datos, etapas de procesamiento y mecanismos de validación experimental.'
  },
  audMet: {
    title: 'grant-flow-auditor (Metodología)',
    line1: 'Pule la prosa metodológica asegurando precisión procedimental y cadencia natural.',
    line2: 'Verifica terminología técnica en español sin anglicismos espurios ni redundancias.'
  },
  gate55: {
    title: 'GATE G5.5 (Metodología)',
    line1: 'Compuerta mayor que certifica factibilidad técnica y claridad del flujo metodológico.',
    line2: 'Autoriza el avance hacia resultados, cronograma y estimación presupuestal.'
  },

  // 7 · Resultados, Presupuesto & Gantt (Fase 6)
  redRes: {
    title: 'redactor (Resultados & Ética)',
    line1: 'Redacta resultados esperados (§11) con métricas TRL y consideraciones éticas (§12).',
    line2: 'Detalla gobernanza de datos, consentimiento informado y gestión de riesgos éticos.'
  },
  presup: {
    title: 'presupuestador (Presupuesto)',
    line1: 'Modela la tabla de presupuesto (§13) con desglose de rubros y fuentes de financiación.',
    line2: 'Garantiza balance aritmético estricto y justificación atada a la metodología.'
  },
  gate64: {
    title: 'GATE G6.4 (Presupuesto)',
    line1: 'Compuerta formal interactiva que revisa topes, cofinanciación y costos unitarios.',
    line2: 'Exige verificación matemática exacta antes de redactar cronograma y entregables.'
  },
  redGantt: {
    title: 'redactor (Gantt & Entregables)',
    line1: 'Diseña el cronograma Gantt (§14) e inventario de productos esperados (§15).',
    line2: 'Mapea hitos temporales con fases metodológicas y entregables en tabla xltabular.'
  },
  bibBib: {
    title: 'bibliografo-propuesta (Bibliografía)',
    line1: 'Consolida la bibliografía general (§16) con al menos 50 referencias en formato APA autor-año.',
    line2: 'Verifica consistencia de claves BibTeX, suprime encabezados duplicados y limpia citas.'
  },

  // 8 · Front-Matter & Ensamble (Fases 6.5 y 7)
  redFront: {
    title: 'redactor (Front-Matter)',
    line1: 'Redacta resumen técnico, resumen ejecutivo, palabras clave e impacto estratégico.',
    line2: 'Ajusta el título en el encabezado de portada suprimiendo secciones de cuerpo §1.'
  },
  gate65: {
    title: 'GATE G6.5 (Front-Matter)',
    line1: 'Compuerta formal que revisa síntesis ejecutiva, fidelidad de palabras clave y portada.',
    line2: 'Autoriza la transición a la auditoría integral previa a la compilación final.'
  },
  revFinal: {
    title: 'revisor (Auditoría Integral)',
    line1: 'Ejecuta la auditoría global cruzada de dependencias, consistencia lógica y estilo.',
    line2: 'Evalúa cumplimiento estricto de las 18 secciones y directrices institucionales.'
  },
  gate7: {
    title: 'GATE G7 Final (Aprobación)',
    line1: 'Compuerta definitiva de aprobación formal de la propuesta completa de investigación.',
    line2: 'Requiere visto bueno final del usuario para emitir el documento final consolidado.'
  },
  coordEns: {
    title: 'coordinador-propuesta (Ensamble)',
    line1: 'Ensambla el documento maestro main.tex, compila PDF final y genera espejos Markdown.',
    line2: 'Sella la corrida registrando métricas de telemetría y entregables exportables.'
  },

  // 9 · Command Center & Grafos
  uiServer: {
    title: 'morfeo ui',
    line1: 'Servidor web del Command Center que orquesta seguimiento, telemetría y edición.',
    line2: 'Expone APIs REST para visualización de estado, grafos interactivos y control de corrida.'
  },
  cbmMcp: {
    title: 'codebase-memory MCP',
    line1: 'Servidor MCP codegraph que indexa corpus de literatura y notas del proyecto.',
    line2: 'Habilita navegación asociativa y generación de reportes estructurados de conocimiento.'
  },
  graphPapers: {
    title: 'papers-graph',
    line1: 'Grafo 3D interactivo celestial de artículos y estado del arte indexados.',
    line2: 'Mapea clusters de investigación, co-citaciones y relevancia metodológica de papers.'
  },
  graphVault: {
    title: 'vault-graph',
    line1: 'Visualizador 3D interactivo del espejo Markdown compatible con Obsidian.',
    line2: 'Inspecciona vínculos bidireccionales entre insumos, secciones y requerimientos TDR.'
  },
  pdfViewer: {
    title: 'PDF Previewer',
    line1: 'Visor PDF interactivo integrado con herramientas editoriales en tiempo real.',
    line2: 'Permite comentarios, tachado y humanización con recompilación eficiente y resaltado.'
  },

  // Transversal · Calidad & Telemetría
  skEstilo: {
    title: 'estilo-natural-es',
    line1: 'Metodología obligatoria para erradicar 35 patrones mecánicos de redacción de IA.',
    line2: 'Imprime cadencia humana, voz activa y fluidez según la norma culta colombiana.'
  },
  skDepur: {
    title: 'depuracion-redundancias',
    line1: 'Audita y elimina duplicidades conceptuales, léxicas y estructurales en cada sección.',
    line2: 'Garantiza avance argumentativo progresivo sin reiteraciones entre párrafos.'
  },
  guiaDoc: {
    title: 'guiaProyectosIA',
    line1: 'Directriz canónica rectora que estipula la estructura de 18 secciones del proyecto.',
    line2: 'Define reglas de dependencias cruzadas, formatos de tablas y estándares de calidad.'
  },
  telemetria: {
    title: 'telemetria_tokens',
    line1: 'Monitor de consumo de recursos que registra tokens, llamadas a herramientas y duración.',
    line2: 'Proporciona transparencia presupuestal y control de costos por fase del pipeline.'
  }
};

const n = (id, lane, col, type, label, sublabel, extra = {}) => ({
  id,
  lane,
  col,
  type,
  label,
  sublabel,
  width: Math.max(130, Math.ceil(label.length * 7 + 16), Math.ceil(sublabel.length * 5.5 + 20)),
  ...extra,
});

const nodes = [
  // Lane cli: 0 · CLI & Workspace
  n('cliInit', 'cli', 0, 'frontend', 'morfeo init', 'workspace por corrida', { sources: S('src/morfeo/cli.py', 1, 40) }),
  n('kitBundle', 'cli', 1, 'database', 'morfeo._kit', '67 activos base', { sources: S('src/morfeo/kit.py', 1, 35) }),
  n('runRoot', 'cli', 2, 'database', 'proposals/<run-id>/', '4 carpetas estructuradas', { sources: S('AGENTS.md', 60, 95) }),
  n('cliStat', 'cli', 3, 'messagebus', 'morfeo status', 'auditoria y estado', { sources: S('src/morfeo/core/status.py', 1, 45) }),
  n('cliComp', 'cli', 4, 'messagebus', 'morfeo compile', 'compilador build.sh', { sources: S('src/morfeo/core/compile.py', 1, 35) }),

  // Lane f0: 1 · Ingesta & TDR
  n('cmdAnalizar', 'f0', 0, 'frontend', '/propuesta-analizar', 'intake y checklist', { sources: S('.claude/commands/propuesta.md', 1, 40) }),
  n('insumosObs', 'f0', 1, 'backend', 'insumos-observador', 'ingesta de documentos', { sources: A('insumos-observador') }),
  n('insumosMd', 'f0', 2, 'database', 'insumos.md', 'corpus estructurado', { sources: S('AGENTS.md', 35, 55) }),
  n('gate05', 'f0', 3, 'security', 'GATE G0.5 (TDR)', 'tabla TDR aprobada', { sources: S('.claude/commands/propuesta.md', 100, 130) }),

  // Lane f1: 2 · Problema & TikZ
  n('invProb', 'f1', 0, 'backend', 'investigador (F1)', '§3 problema y pregunta', { sources: A('investigador') }),
  n('tikzTree', 'f1', 1, 'backend', 'disenador-tikz', 'spec arbol_problemas', { sources: A('disenador-tikz') }),
  n('figEngine', 'f1', 2, 'messagebus', 'figura.py', 'render y auditoria', { sources: S('plantilla/scripts/figura.py', 1, 50) }),
  n('revFig', 'f1', 3, 'backend', 'revisor-figuras', 'criterios visuales PNG', { sources: A('revisor-figuras') }),
  n('gate1', 'f1', 4, 'security', 'GATE G1', 'aprobacion problema', { sources: S('.claude/commands/propuesta.md', 140, 170) }),

  // Lane f2: 3 · SOTA & Hipótesis
  n('bibSota', 'f2', 0, 'backend', 'bibliografo-propuesta', '§4 SOTA (≥39 refs Q1/Q2)', { sources: A('bibliografo-propuesta') }),
  n('invHip', 'f2', 1, 'backend', 'investigador (F2)', '§5 hipotesis', { sources: A('investigador') }),
  n('tikzSota', 'f2', 2, 'backend', 'disenador-tikz (F2)', 'spec estado_arte', { sources: A('disenador-tikz') }),
  n('gate2', 'f2', 3, 'security', 'GATE G2', 'aprobacion SOTA', { sources: S('.claude/commands/propuesta.md', 180, 210) }),

  // Lane f34: 4 · Justificación & Objetivos
  n('redJust', 'f34', 0, 'backend', 'redactor (F3)', '§2 pertinencia TRL 6/7', { sources: A('redactor') }),
  n('audJust', 'f34', 1, 'backend', 'grant-flow-auditor', 'cadencia y voz activa', { sources: A('grant-flow-auditor') }),
  n('gate3', 'f34', 2, 'security', 'GATE G3', 'aprobacion justificacion', { sources: S('.claude/commands/propuesta.md', 215, 235) }),
  n('invObj', 'f34', 3, 'backend', 'investigador (F4)', '§6 gral y §7 especificos', { sources: A('investigador') }),
  n('gate4', 'f34', 4, 'security', 'GATE G4', 'mapeo 1:1 subproblemas', { sources: S('.claude/commands/propuesta.md', 240, 260) }),

  // Lane f5: 5 · Marco Conceptual & Equipo
  n('invMarco', 'f5', 0, 'backend', 'investigador (F5)', '§8 marco conceptual', { sources: A('investigador') }),
  n('redEquipo', 'f5', 1, 'backend', 'redactor (F5)', 'roles derivados de §7', { sources: A('redactor') }),
  n('gate5', 'f5', 2, 'security', 'GATE G5', 'aprobacion marco y equipo', { sources: S('.claude/commands/propuesta.md', 270, 290) }),

  // Lane f55: 6 · Metodología & Diagrama
  n('redMet', 'f55', 0, 'backend', 'redactor (F5.5)', '§10 metodologia', { sources: A('redactor') }),
  n('tikzMet', 'f55', 1, 'backend', 'disenador-tikz (F5.5)', 'spec metodologico', { sources: A('disenador-tikz') }),
  n('audMet', 'f55', 2, 'backend', 'grant-flow-auditor (F5.5)', 'prosa natural', { sources: A('grant-flow-auditor') }),
  n('gate55', 'f55', 3, 'security', 'GATE G5.5', 'aprobacion metodologia', { sources: S('.claude/commands/propuesta.md', 300, 320) }),

  // Lane f6: 7 · Presupuesto & Entregables
  n('redRes', 'f6', 0, 'backend', 'redactor (F6)', '§11 resultados y §12 etica', { sources: A('redactor') }),
  n('presup', 'f6', 1, 'backend', 'presupuestador (F6.4)', '§13 presupuesto', { sources: A('presupuestador') }),
  n('gate64', 'f6', 2, 'security', 'GATE G6.4', 'aritmetica verificada', { sources: S('.claude/commands/propuesta.md', 330, 350) }),
  n('redGantt', 'f6', 3, 'backend', 'redactor (F6.45)', '§14 cronograma y §15 entregables', { sources: A('redactor') }),
  n('bibBib', 'f6', 4, 'backend', 'bibliografo-propuesta (F6.45)', '§16 bibliografia APA', { sources: A('bibliografo-propuesta') }),

  // Lane f657: 8 · Front-Matter & Compilación
  n('redFront', 'f657', 0, 'backend', 'redactor (F6.5)', 'resumen ejecutivo', { sources: A('redactor') }),
  n('gate65', 'f657', 1, 'security', 'GATE G6.5', 'aprobacion front-matter', { sources: S('.claude/commands/propuesta.md', 370, 390) }),
  n('revFinal', 'f657', 2, 'backend', 'revisor (Fase 7)', 'auditoria integral', { sources: A('revisor') }),
  n('gate7', 'f657', 3, 'security', 'GATE G7 Final', 'aprobacion formal', { sources: S('.claude/commands/propuesta.md', 400, 420) }),
  n('coordEns', 'f657', 4, 'backend', 'coordinador-propuesta', 'ensambla y compila', { sources: A('coordinador-propuesta') }),

  // Lane dash: 9 · Command Center & Grafos
  n('uiServer', 'dash', 0, 'frontend', 'morfeo ui', 'tablero de seguimiento', { sources: S('src/morfeo/core/ui.py', 1, 40) }),
  n('cbmMcp', 'dash', 1, 'external', 'codebase-memory MCP', 'servidor MCP codegraph', { sources: S('AGENTS.md', 100, 125) }),
  n('graphPapers', 'dash', 2, 'database', 'papers-graph', 'grafo interactivo SOTA', { sources: S('scripts/graph_html.py', 1, 40) }),
  n('graphVault', 'dash', 3, 'database', 'vault-graph', 'grafo espejo obsidian', { sources: S('scripts/graph_html.py', 1, 40) }),
  n('pdfViewer', 'dash', 4, 'database', 'PDF Previewer', 'visor PDF en tiempo real', { sources: S('src/morfeo/dashboard/static/index.html', 1, 60) }),

  // Lane quality: Transversal · Calidad & Prosa
  n('skEstilo', 'quality', 0, 'external', 'estilo-natural-es', 'cadencia y naturalidad', { sources: K('estilo-natural-es') }),
  n('skDepur', 'quality', 1, 'external', 'depuracion-redundancias', 'depuracion redundancias', { sources: K('depuracion-redundancias-es') }),
  n('guiaDoc', 'quality', 2, 'database', 'guiaProyectosIA', 'norma 18 secciones', { sources: S('guiaProyectosIA_Agente.md', 1, 50) }),
  n('telemetria', 'quality', 3, 'database', 'telemetria_tokens', 'costo y duracion por fase', { sources: S('AGENTS.md', 170, 190) }),
];

const e = (from, to, label, extra = {}) => ({
  id: `${from}-${to}`,
  from,
  to,
  ...(label ? { label } : {}),
  ...extra,
});

const main = { variant: 'emphasis', role: 'main' };

const edges = [
  // CLI & Setup
  e('cliInit', 'kitBundle'),
  e('kitBundle', 'runRoot'),
  e('runRoot', 'cliStat'),
  e('cliStat', 'cliComp'),
  e('runRoot', 'cmdAnalizar', 'insumos/', main),

  // Fase 0 Ingesta
  e('cmdAnalizar', 'insumosObs'),
  e('insumosObs', 'insumosMd'),
  e('insumosMd', 'gate05', null, { variant: 'security' }),
  e('gate05', 'invProb', 'Fase 1', main),

  // Fase 1 Problema
  e('invProb', 'tikzTree'),
  e('tikzTree', 'figEngine'),
  e('figEngine', 'revFig'),
  e('revFig', 'gate1', null, { variant: 'security' }),
  e('gate1', 'bibSota', 'Fase 2', main),

  // Fase 2 SOTA
  e('bibSota', 'invHip'),
  e('invHip', 'tikzSota'),
  e('tikzSota', 'gate2', null, { variant: 'security' }),
  e('gate2', 'redJust', 'Fase 3', main),

  // Fases 3 & 4 Justificación & Objetivos
  e('redJust', 'audJust'),
  e('audJust', 'gate3', null, { variant: 'security' }),
  e('gate3', 'invObj', null, main),
  e('invObj', 'gate4', null, { variant: 'security' }),
  e('gate4', 'invMarco', 'Fase 5', main),

  // Fase 5 Marco & Equipo
  e('invMarco', 'redEquipo'),
  e('redEquipo', 'gate5', null, { variant: 'security' }),
  e('gate5', 'redMet', 'Fase 5.5', main),

  // Fase 5.5 Metodología
  e('redMet', 'tikzMet'),
  e('tikzMet', 'audMet'),
  e('audMet', 'gate55', null, { variant: 'security' }),
  e('gate55', 'redRes', 'Fase 6', main),

  // Fase 6 Presupuesto & Entregables
  e('redRes', 'presup'),
  e('presup', 'gate64', null, { variant: 'security' }),
  e('gate64', 'redGantt', null, main),
  e('redGantt', 'bibBib'),
  e('bibBib', 'redFront', 'Fase 6.5', main),

  // Fases 6.5 & 7 Ensamble
  e('redFront', 'gate65', null, { variant: 'security' }),
  e('gate65', 'revFinal', null, main),
  e('revFinal', 'gate7', null, { variant: 'security' }),
  e('gate7', 'coordEns'),

  // Command Center
  e('uiServer', 'cbmMcp'),
  e('cbmMcp', 'graphPapers'),
  e('graphPapers', 'graphVault'),
  e('graphVault', 'pdfViewer'),

  // Calidad Transversal
  e('skEstilo', 'skDepur'),
  e('skDepur', 'guiaDoc'),
  e('guiaDoc', 'telemetria'),
];

const lanes = [
  ['cli', '0 · Morfeo CLI & Workspace'],
  ['f0', '1 · Ingesta & TDR (Fase 0)'],
  ['f1', '2 · Problema & TikZ (Fase 1)'],
  ['f2', '3 · SOTA & Hipótesis (Fase 2)'],
  ['f34', '4 · Justificación & Objetivos (Fases 3 y 4)'],
  ['f5', '5 · Marco & Equipo (Fase 5)'],
  ['f55', '6 · Metodología & Diagrama (Fase 5.5)'],
  ['f6', '7 · Resultados, Presupuesto & Gantt (Fase 6)'],
  ['f657', '8 · Front-Matter & Ensamble (Fases 6.5 y 7)'],
  ['dash', '9 · Command Center & Grafos'],
  ['quality', 'Transversal · Calidad & Telemetría'],
].map(([id, label]) => ({ id, label }));

const laneIdx = Object.fromEntries(lanes.map((l, i) => [l.id, i]));
const components = nodes.map(({ lane, col, width, ...r }) => ({
  ...r,
  row: laneIdx[lane],
  col,
  size: [186, 58],
}));

const connections = edges.map(({ role, ...r }) => r);
const boundaries = lanes.map((l) => ({
  kind: 'region',
  label: l.label,
  wraps: nodes.filter((x) => x.lane === l.id).map((x) => x.id),
}));

export const doc = {
  schema_version: 1,
  diagram_type: 'architecture',
  meta: {
    title: 'Morfeo IA — Architecture, Pipeline Stages and Review Gates',
    quality_profile: 'showcase',
    output: 'docs/diagrams/morfeo-pipeline-flow.html',
    repository: {
      url: 'https://github.com/LIAUNAL/propuestasmorfeo-ia',
      provider: 'github',
      link_mode: 'web',
      revision: '45d1c2bce14aaf678e4beac4b94e26503d978735',
    },
    legend: {
      mode: 'auto',
      entries: {
        frontend: { label: 'Comando CLI / UI' },
        backend: { label: 'Subagente Especializado' },
        messagebus: { label: 'Script Determinista' },
        security: { label: 'Gate de Revisión (Humano / Revisor)' },
        database: { label: 'Artefacto en Disco' },
        external: { label: 'Skill / Servicio MCP' },
      },
    },
  },
  layout: {
    mode: 'grid',
    origin: [40, 48],
    cols: 5,
    cellW: 186,
    cellH: 58,
    gapX: 24,
    gapY: 58,
  },
  components,
  boundaries,
  connections,
  cards: [
    {
      dot: 'cyan',
      title: 'Fases Metodológicas: Ingesta, Scoping y Problema',
      items: [
        'Fase 0: Ingesta, clasificación y extracción de insumos del usuario para estructurar el contexto compartido.',
        'Fase 1a: Búsqueda bibliográfica de encuadre en el grafo para delimitar alcance y postular tres subproblemas.',
        'Fase 1b: Consolidación del corpus de literatura Q1/Q2 reciente, extrayendo referencias semilla e indexando.',
        'Fase 1: Redacción de la descripción del problema (§3), formulación de la pregunta central y árbol TikZ.',
      ],
    },
    {
      dot: 'emerald',
      title: 'Fases Metodológicas: Fundamentación, Justificación y Objetivos',
      items: [
        'Fase 2: Construcción del estado del arte Q1/Q2 (§4), hipótesis falsable (§5) y mapa visual conceptual.',
        'Fase 3: Elaboración de justificación y pertinencia (§2), articulando con ODS, PND y madurez TRL 6 o 7.',
        'Fase 4: Formulación del objetivo general (§6) y los tres objetivos específicos (§7), con mapeo biyectivo 1:1.',
        'Fase 5: Fundamentos teóricos (§8) y conformación del equipo (§9), con roles derivados de los objetivos.',
      ],
    },
    {
      dot: 'violet',
      title: 'Fases Metodológicas: Metodología, Presupuesto y Ensamble',
      items: [
        'Fase 5.5: Metodología (§10) por fases y cadena de valor, con diseño y verificación de diagrama TikZ.',
        'Fase 6: Resultados esperados (§11) y fundamentación de consideraciones éticas y datos (§12).',
        'Fase 6.4: Presupuesto (§13) detallando rubros, contrapartidas y cofinanciación con balance exacto.',
        'Fase 6.45: Cronograma de actividades (§14, Gantt), tabla de productos (§15) y bibliografía APA (§16).',
        'Fase 6.46: Articulación territorial (§17) y plan de apropiación social del conocimiento (§18).',
        'Fase 6.5: Resumen técnico, resumen ejecutivo institucional, palabras clave y verificación del título.',
        'Fase 7: Auditoría cruzada integral de dependencias, verificación de consistencia y compilación final.',
      ],
    },
    {
      dot: 'amber',
      title: 'Ecosistema de Agentes, Calidad y CLI',
      items: [
        '11 subagentes especializados orquestados sin invocar agentes anidados.',
        'Bucle determinista de figuras TikZ: Diseñador-TikZ (spec JSON) + figura.py + Revisor-Figuras.',
        'Skill estilo-natural-es: cadencia humana, voz activa y eliminación de fórmulas mecánicas.',
        'morfeo ui: Command Center con visor PDF en tiempo real, grafos interactivos y telemetría.',
      ],
    },
  ],
};

export function enhanceHtml(htmlPath, nodePurposes = NODE_PURPOSES) {
  if (!fs.existsSync(htmlPath)) return false;
  let html = fs.readFileSync(htmlPath, 'utf8');

  const styleMarker = '/* Morfeo Node Purpose Styling */';
  if (!html.includes(styleMarker)) {
    const customCss = `
    ${styleMarker}
    .semantic-passport-purpose {
      margin-top: 0.65rem;
      padding: 0.6rem 0.8rem;
      background: rgba(15, 23, 42, 0.92);
      border: 1px solid rgba(56, 189, 248, 0.35);
      border-left: 3px solid #38bdf8;
      border-radius: 6px;
      font-size: 0.75rem;
      line-height: 1.45;
      color: #f1f5f9;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
    }
    .semantic-passport-purpose-title {
      display: block;
      font-size: 0.625rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #38bdf8;
      margin-bottom: 0.35rem;
    }
    .semantic-passport-purpose-line1 {
      margin: 0 0 0.25rem 0;
      font-weight: 500;
      color: #f8fafc;
      white-space: normal;
    }
    .semantic-passport-purpose-line2 {
      margin: 0;
      color: #94a3b8;
      white-space: normal;
    }
    `;
    html = html.replace('</style>', `${customCss}\n  </style>`);
  }

  const scriptMarker = 'id="morfeo-purpose-enhancer"';
  const enhancerScript = `
  <script ${scriptMarker}>
  (function () {
    const NODE_PURPOSES = ${JSON.stringify(nodePurposes, null, 2)};

    function escHtml(str) {
      return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function updatePurposeForNode(id, el) {
      const p = NODE_PURPOSES[id];
      if (!p) return;

      const chip = document.getElementById('focus-chip');
      if (chip) {
        let purposeBox = document.getElementById('focus-purpose-box');
        if (!purposeBox) {
          purposeBox = document.createElement('div');
          purposeBox.id = 'focus-purpose-box';
          purposeBox.className = 'semantic-passport-purpose';
          const copyContainer = chip.querySelector('.relationship-lens-copy');
          if (copyContainer) {
            copyContainer.appendChild(purposeBox);
          }
        }
        purposeBox.innerHTML = \`
          <span class="semantic-passport-purpose-title">Propósito de la etapa y caja</span>
          <div class="semantic-passport-purpose-desc">
            <p class="semantic-passport-purpose-line1">\${escHtml(p.line1)}</p>
            <p class="semantic-passport-purpose-line2">\${escHtml(p.line2)}</p>
          </div>
        \`;
        purposeBox.style.display = 'block';
      }

      try {
        if (window.parent && window.parent !== window) {
          const laneAttr = el ? el.getAttribute('data-node-context') : '';
          window.parent.postMessage({
            type: 'archify-node-selected',
            id: id,
            title: p.title,
            line1: p.line1,
            line2: p.line2,
            lane: laneAttr || 'ETAPA'
          }, '*');
        }
      } catch (_) {}
    }

    document.querySelectorAll('g[data-node-id]').forEach(function (g) {
      const id = g.getAttribute('data-node-id');
      const p = NODE_PURPOSES[id];
      if (p) {
        const titleEl = g.querySelector('title');
        if (titleEl) {
          titleEl.textContent = \`\${p.title}\\n\\nPropósito:\\n• \${p.line1}\\n• \${p.line2}\`;
        }
        g.addEventListener('click', function () {
          setTimeout(function () { updatePurposeForNode(id, g); }, 20);
        });
        g.addEventListener('keydown', function (ev) {
          if (ev.key === 'Enter' || ev.key === ' ') {
            setTimeout(function () { updatePurposeForNode(id, g); }, 20);
          }
        });
      }
    });

    const focusIdEl = document.getElementById('focus-id');
    if (focusIdEl) {
      const obs = new MutationObserver(function () {
        const activeId = focusIdEl.textContent.trim();
        if (activeId && NODE_PURPOSES[activeId]) {
          const g = document.querySelector('g[data-node-id="' + activeId + '"]');
          updatePurposeForNode(activeId, g);
        }
      });
      obs.observe(focusIdEl, { childList: true, characterData: true, subtree: true });
    }
  })();
  </script>`;

  if (html.includes(scriptMarker)) {
    const regex = new RegExp('<script id="morfeo-purpose-enhancer">[\\s\\S]*?<\\/script>');
    html = html.replace(regex, enhancerScript.trim());
  } else {
    html = html.replace('</body>', `${enhancerScript}\n</body>`);
  }

  fs.writeFileSync(htmlPath, html, 'utf8');
  console.log(`enhanced: ${htmlPath} with node purpose popups`);
  return true;
}

const out = path.resolve(process.argv[2] || fileURLToPath(new URL('./candidate.json', import.meta.url)));
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify(doc, null, 2));
console.log(`candidate: ${out}`);

// If --render flag is passed or run directly with no specific candidate arg, render and enhance HTML
const shouldRender = process.argv.includes('--render') || !process.argv[2];
if (shouldRender) {
  const archifyBin = path.resolve(os.homedir(), '.claude/skills/archify/bin/archify.mjs');
  const targetHtml = path.resolve(REPO, 'docs/diagrams/morfeo-pipeline-flow.html');
  if (fs.existsSync(archifyBin)) {
    console.log(`rendering via archify: ${targetHtml}...`);
    const res = spawnSync('node', [archifyBin, 'render', 'architecture', out, targetHtml, '--repo-root', REPO], {
      stdio: 'inherit'
    });
    if (res.status === 0) {
      enhanceHtml(targetHtml, NODE_PURPOSES);
    } else {
      console.error(`Archify render failed with exit code ${res.status}`);
    }
  } else {
    console.warn(`Archify binary not found at ${archifyBin}; skipping auto-render.`);
  }
}
