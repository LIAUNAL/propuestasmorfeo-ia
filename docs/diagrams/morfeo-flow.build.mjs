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
  const lines = fs.readFileSync(p, 'utf8').split('\n');
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
  n('cliInit', 'cli', 0, 'frontend', 'morfeo init', 'workspace per proposal', { sources: S('src/morfeo/cli.py', 1, 40) }),
  n('kitBundle', 'cli', 1, 'database', 'morfeo._kit', '67 bundled template assets', { sources: S('src/morfeo/kit.py', 1, 35) }),
  n('runRoot', 'cli', 2, 'database', 'proposals/<run-id>/', 'insumos · artefactos · grafos · redaccion', { sources: S('AGENTS.md', 60, 95) }),
  n('cliStat', 'cli', 3, 'messagebus', 'morfeo status', 'gate audit & run state', { sources: S('src/morfeo/core/status.py', 1, 45) }),
  n('cliComp', 'cli', 4, 'messagebus', 'morfeo compile', 'build.sh PDF & DOCX', { sources: S('src/morfeo/core/compile.py', 1, 45) }),

  // Lane f0: 1 · Ingesta & TDR
  n('cmdAnalizar', 'f0', 0, 'frontend', '/propuesta-analizar', 'Fase 0 intake & checklist', { sources: S('.claude/commands/propuesta.md', 1, 40) }),
  n('insumosObs', 'f0', 1, 'backend', 'insumos-observador', 'ingests PDFs, papers, TDRs', { sources: A('insumos-observador') }),
  n('insumosMd', 'f0', 2, 'database', 'insumos.md', 'structured corpus & idea-seed', { sources: S('AGENTS.md', 35, 55) }),
  n('gate05', 'f0', 3, 'security', 'GATE G0.5 (TDR)', 'tabla secciones TDR aprobada', { sources: S('.claude/commands/propuesta.md', 100, 130) }),

  // Lane f1: 2 · Problema & TikZ
  n('invProb', 'f1', 0, 'backend', 'investigador (F1)', '§3 problema & pregunta', { sources: A('investigador') }),
  n('tikzTree', 'f1', 1, 'backend', 'disenador-tikz', 'spec JSON arbol_problemas', { sources: A('disenador-tikz') }),
  n('figEngine', 'f1', 2, 'messagebus', 'figura.py', 'render · compile · autofix', { sources: S('scripts/figura.py', 1, 50) }),
  n('revFig', 'f1', 3, 'backend', 'revisor-figuras', 'audits visual criteria on PNG', { sources: A('revisor-figuras') }),
  n('gate1', 'f1', 4, 'security', 'GATE G1', 'aprobacion problema & arbol', { sources: S('.claude/commands/propuesta.md', 140, 170) }),

  // Lane f2: 3 · SOTA & Hipótesis
  n('bibSota', 'f2', 0, 'backend', 'bibliografo-propuesta', '§4 SOTA (≥30 refs Q1/Q2)', { sources: A('bibliografo-propuesta') }),
  n('invHip', 'f2', 1, 'backend', 'investigador (F2)', '§5 hipotesis de investigacion', { sources: A('investigador') }),
  n('tikzSota', 'f2', 2, 'backend', 'disenador-tikz (F2)', 'spec JSON estado_arte', { sources: A('disenador-tikz') }),
  n('gate2', 'f2', 3, 'security', 'GATE G2', 'aprobacion SOTA e hipotesis', { sources: S('.claude/commands/propuesta.md', 180, 210) }),

  // Lane f34: 4 · Justificación & Objetivos
  n('redJust', 'f34', 0, 'backend', 'redactor (F3)', '§2 justificacion & pertinencia (TRL)', { sources: A('redactor') }),
  n('audJust', 'f34', 1, 'backend', 'grant-flow-auditor', 'cadencia & voz activa', { sources: A('grant-flow-auditor') }),
  n('gate3', 'f34', 2, 'security', 'GATE G3', 'aprobacion pertinencia TRL 6/7', { sources: S('.claude/commands/propuesta.md', 215, 235) }),
  n('invObj', 'f34', 3, 'backend', 'investigador (F4)', '§6 gral & §7 3 especificos', { sources: A('investigador') }),
  n('gate4', 'f34', 4, 'security', 'GATE G4', 'mapeo 1:1 subproblema↔objetivo', { sources: S('.claude/commands/propuesta.md', 240, 260) }),

  // Lane f5: 5 · Marco Conceptual & Equipo
  n('invMarco', 'f5', 0, 'backend', 'investigador (F5)', '§8 marco conceptual', { sources: A('investigador') }),
  n('redEquipo', 'f5', 1, 'backend', 'redactor (F5)', '§9 equipo (roles derivados de §7)', { sources: A('redactor') }),
  n('gate5', 'f5', 2, 'security', 'GATE G5', 'aprobacion marco & equipo', { sources: S('.claude/commands/propuesta.md', 270, 290) }),

  // Lane f55: 6 · Metodología & Diagrama
  n('redMet', 'f55', 0, 'backend', 'redactor (F5.5)', '§10 metodologia articulada', { sources: A('redactor') }),
  n('tikzMet', 'f55', 1, 'backend', 'disenador-tikz (F5.5)', 'spec JSON metodologico', { sources: A('disenador-tikz') }),
  n('audMet', 'f55', 2, 'backend', 'grant-flow-auditor (F5.5)', 'pulido prosa natural', { sources: A('grant-flow-auditor') }),
  n('gate55', 'f55', 3, 'security', 'GATE G5.5', 'aprobacion metodologia & diagrama', { sources: S('.claude/commands/propuesta.md', 300, 320) }),

  // Lane f6: 7 · Presupuesto & Entregables
  n('redRes', 'f6', 0, 'backend', 'redactor (F6)', '§11 resultados & §12 etica', { sources: A('redactor') }),
  n('presup', 'f6', 1, 'backend', 'presupuestador (F6.4)', '§13 presupuesto & cofinanciacion', { sources: A('presupuestador') }),
  n('gate64', 'f6', 2, 'security', 'GATE G6.4', 'aritmetica de rubros verificada', { sources: S('.claude/commands/propuesta.md', 330, 350) }),
  n('redGantt', 'f6', 3, 'backend', 'redactor (F6.45)', '§14 cronograma & §15 productos', { sources: A('redactor') }),
  n('bibBib', 'f6', 4, 'backend', 'bibliografo-propuesta (F6.45)', '§16 bibliografia (≥50 refs APA)', { sources: A('bibliografo-propuesta') }),

  // Lane f657: 8 · Front-Matter & Compilación
  n('redFront', 'f657', 0, 'backend', 'redactor (F6.5)', 'resumen ejecutivo & palabras clave', { sources: A('redactor') }),
  n('gate65', 'f657', 1, 'security', 'GATE G6.5', 'aprobacion sintesis front-matter', { sources: S('.claude/commands/propuesta.md', 370, 390) }),
  n('revFinal', 'f657', 2, 'backend', 'revisor (Fase 7)', 'auditoria integral cruzada', { sources: A('revisor') }),
  n('gate7', 'f657', 3, 'security', 'GATE G7 Final', 'aprobacion formal para ensamble', { sources: S('.claude/commands/propuesta.md', 400, 420) }),
  n('coordEns', 'f657', 4, 'backend', 'coordinador-propuesta', 'ensambla main.tex & genera PDF', { sources: A('coordinador-propuesta') }),

  // Lane dash: 9 · Dashboard & Grafos
  n('uiServer', 'dash', 0, 'frontend', 'morfeo ui', 'command center web dashboard', { sources: S('src/morfeo/core/ui.py', 1, 45) }),
  n('cbmMcp', 'dash', 1, 'external', 'codebase-memory MCP', 'codegraph serve --mcp', { sources: S('AGENTS.md', 100, 125) }),
  n('graphPapers', 'dash', 2, 'database', 'papers-graph', 'interactive SOTA citation graph', { sources: S('scripts/graph_html.py', 1, 40) }),
  n('graphVault', 'dash', 3, 'database', 'vault-graph', 'obsidian-compatible vault graph', { sources: S('scripts/graph_html.py', 1, 40) }),
  n('pdfViewer', 'dash', 4, 'database', 'PDF Previewer', 'real-time preview in iframe', { sources: S('src/morfeo/dashboard/static/index.html', 1, 60) }),

  // Lane quality: Transversal · Calidad & Prosa
  n('skEstilo', 'quality', 0, 'external', 'estilo-natural-es', 'humanizacion y cadencia', { sources: K('estilo-natural-es') }),
  n('skDepur', 'quality', 1, 'external', 'depuracion-redundancias', 'auditoria de redundancias', { sources: K('depuracion-redundancias-es') }),
  n('guiaDoc', 'quality', 2, 'database', 'guiaProyectosIA', 'norma metodologica 16 secciones', { sources: S('guiaProyectosIA_Agente.md', 1, 50) }),
  n('telemetria', 'quality', 3, 'database', 'telemetria_tokens', 'costo & duracion por fase', { sources: S('AGENTS.md', 170, 190) }),
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
  // Primary flow
  e('cliInit', 'kitBundle', 'despliega'),
  e('kitBundle', 'runRoot', 'inicializa'),
  e('runRoot', 'cmdAnalizar', 'insumos/'),
  e('cmdAnalizar', 'insumosObs', 'procesa'),
  e('insumosObs', 'insumosMd', 'extrae'),
  e('insumosMd', 'gate05', 'TDR verificado', { variant: 'security' }),

  e('gate05', 'invProb', 'Fase 1', main),
  e('invProb', 'tikzTree', '§3 aprobado'),
  e('tikzTree', 'figEngine', 'spec JSON'),
  e('figEngine', 'revFig', 'PNG preview'),
  e('revFig', 'gate1', 'PASS visual', { variant: 'security' }),

  e('gate1', 'bibSota', 'Fase 2', main),
  e('bibSota', 'invHip', '≥30 refs Q1/Q2'),
  e('invHip', 'tikzSota', '§5 hipotesis'),
  e('tikzSota', 'gate2', 'spec renderizada', { variant: 'security' }),

  e('gate2', 'redJust', 'Fase 3', main),
  e('redJust', 'audJust', 'borrador §2'),
  e('audJust', 'gate3', 'PASS prosa', { variant: 'security' }),

  e('gate3', 'invObj', 'Fase 4', main),
  e('invObj', 'gate4', '1:1 subproblemas', { variant: 'security' }),

  e('gate4', 'invMarco', 'Fase 5', main),
  e('invMarco', 'redEquipo', '§8 marco'),
  e('redEquipo', 'gate5', 'roles desde §7', { variant: 'security' }),

  e('gate5', 'redMet', 'Fase 5.5', main),
  e('redMet', 'tikzMet', '§10 metodo'),
  e('tikzMet', 'audMet', 'spec diagrama'),
  e('audMet', 'gate55', 'PASS metodologico', { variant: 'security' }),

  e('gate55', 'redRes', 'Fase 6', main),
  e('redRes', 'presup', '§11-§12'),
  e('presup', 'gate64', 'aritmetica exacta', { variant: 'security' }),
  e('gate64', 'redGantt', 'presupuesto aprobado'),
  e('redGantt', 'bibBib', '§14 & §15'),

  e('bibBib', 'redFront', 'Fase 6.5', main),
  e('redFront', 'gate65', 'sintesis final', { variant: 'security' }),

  e('gate65', 'revFinal', 'Fase 7', main),
  e('revFinal', 'gate7', 'PASS auditoria', { variant: 'security' }),
  e('gate7', 'coordEns', 'ensambla'),
  e('coordEns', 'cliComp', 'compila PDF/DOCX', main),

  // UI and Graphs
  e('uiServer', 'runRoot', 'lee estado', { variant: 'dashed' }),
  e('cbmMcp', 'graphPapers', 'indexa papers', { variant: 'dashed' }),
  e('cbmMcp', 'graphVault', 'indexa vault', { variant: 'dashed' }),
  e('uiServer', 'pdfViewer', 'sirve PDF', { variant: 'dashed' }),

  // Quality connections
  e('skEstilo', 'audJust', 'aplica', { variant: 'dashed' }),
  e('skDepur', 'audMet', 'aplica', { variant: 'dashed' }),
  e('guiaDoc', 'revFinal', 'valida', { variant: 'dashed' }),
  e('telemetria', 'cliStat', 'reporta', { variant: 'dashed' }),
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
      revision: '02216fdf83fe3f623b6997f7a627ddecc082b2d8',
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
      title: 'Ecosistema de Agentes y Roles',
      items: [
        '11 subagentes especializados orquestados sin invocar agentes anidados.',
        'Investigador: estructura académica (§3, §5, §6, §7, §8).',
        'Redactor: prosa narrativa rigurosa (§2, §9, §10, §11, §14, §15, front-matter).',
        'Revisor: validación de coherencia en cada compuerta de aprobación (G0.5–G7).',
        'Presupuestador: desglose de rubros y cofinanciación con aritmética exacta.',
      ],
    },
    {
      dot: 'emerald',
      title: 'Comandos CLI Morfeo',
      items: [
        'morfeo init <dir> — inicializa workspace reproducible con 67 activos base.',
        'morfeo status — audita gates aprobados, archivos faltantes y telemetría.',
        'morfeo compile — compila PDF con build.sh y logos institucionales vía fancyhdr.',
        'morfeo ui — levanta Command Center web (tablero, telemetría, grafos y visor PDF).',
        'morfeo audit — detecta deriva de archivos protegidos frente al manifiesto.',
        'morfeo upgrade — actualiza plantillas preservando insumos y propuestas.',
      ],
    },
    {
      dot: 'amber',
      title: 'Bucle Determinista de Figuras',
      items: [
        'Diseñador-TikZ genera únicamente la spec JSON (nunca código LaTeX manual).',
        'python3 scripts/figura.py calcula geometría exacta y audita 17 criterios mecánicos.',
        'Revisor-Figuras evalúa únicamente criterios visuales sobre el preview PNG.',
        'Tikz-Optimizer corrige la spec ante cualquier fallo, con un máximo de 4 intentos.',
      ],
    },
    {
      dot: 'violet',
      title: 'Calidad de Prosa y Vistas de Grafo',
      items: [
        'Skill estilo-natural-es: cadencia humana, voz activa y eliminación de fórmulas mecánicas.',
        'Skill depuracion-redundancias-es: audita duplicidad conceptual y léxica dentro de cada sección.',
        'Capa de grafo dual vía codebase-memory MCP: índice de papers y espejo vault en Obsidian.',
        'Visualizador gemelo en HTML generado con scripts/graph_html.py para navegación visual.',
      ],
    },
  ],
};

const out = path.resolve(process.argv[2] || fileURLToPath(new URL('./candidate.json', import.meta.url)));
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify(doc, null, 2));
console.log(`candidate: ${out}`);
