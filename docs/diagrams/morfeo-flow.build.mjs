/**
 * Source for `docs/diagrams/morfeo-pipeline-flow.html` and architecture flow.
 *
 * Regenerable via:
 *   node docs/diagrams/morfeo-flow.build.mjs /tmp/morfeo-flow.json
 *   node ~/.claude/skills/archify/bin/archify.mjs render architecture \
 *     /tmp/morfeo-flow.json docs/diagrams/morfeo-pipeline-flow.html \
 *     --repo-root .
 */
import fs from 'node:fs';
import path from 'node:path';
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
  n('bibSota', 'f2', 0, 'backend', 'bibliografo-propuesta', '§4 SOTA (≥30 refs Q1/Q2)', { sources: A('bibliografo-propuesta') }),
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

  // Lane dash: 9 · Dashboard & Grafos
  n('uiServer', 'dash', 0, 'frontend', 'morfeo ui', 'tablero de seguimiento', { sources: S('src/morfeo/core/ui.py', 1, 40) }),
  n('cbmMcp', 'dash', 1, 'external', 'codebase-memory MCP', 'servidor MCP codegraph', { sources: S('AGENTS.md', 100, 125) }),
  n('graphPapers', 'dash', 2, 'database', 'papers-graph', 'grafo interactivo SOTA', { sources: S('scripts/graph_html.py', 1, 40) }),
  n('graphVault', 'dash', 3, 'database', 'vault-graph', 'grafo espejo obsidian', { sources: S('scripts/graph_html.py', 1, 40) }),
  n('pdfViewer', 'dash', 4, 'database', 'PDF Previewer', 'visor PDF en tiempo real', { sources: S('src/morfeo/dashboard/static/index.html', 1, 60) }),

  // Lane quality: Transversal · Calidad & Prosa
  n('skEstilo', 'quality', 0, 'external', 'estilo-natural-es', 'cadencia y naturalidad', { sources: K('estilo-natural-es') }),
  n('skDepur', 'quality', 1, 'external', 'depuracion-redundancias', 'depuracion redundancias', { sources: K('depuracion-redundancias-es') }),
  n('guiaDoc', 'quality', 2, 'database', 'guiaProyectosIA', 'norma 16 secciones', { sources: S('guiaProyectosIA_Agente.md', 1, 50) }),
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

const doc = {
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

const out = path.resolve(process.argv[2] || fileURLToPath(new URL('./candidate.json', import.meta.url)));
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify(doc, null, 2));
console.log(`candidate: ${out}`);
