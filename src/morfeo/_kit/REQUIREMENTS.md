# Requirements — AI Research Proposal Writing Framework

All dependencies needed to run the multi-agent framework, build the knowledge graph, and compile the LaTeX proposal.

## 1. System tools

| Tool | Min version | Purpose | Install |
|------|-------------|---------|---------|
| **Python** | 3.11+ | Framework scripting (stdlib-only) | `brew install python@3.11` |
| **uv** | 0.11+ | Python package manager (recommended) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node.js** | 20+ | MCP servers via npx | `brew install node` |
| **npm / npx** | 10+ | MCP server fetching | bundled with Node |
| **TeX Live** | 2024+ | LaTeX compilation (pdflatex + bibtex) | `brew install --cask mactex` |
| **git** | 2.40+ | Version control | `brew install git` |
| **codegraph** | 1.2+ | **codebase-memory** knowledge-graph MCP server (required: `.mcp.json`'s `codegraph` server invokes this binary as `codegraph serve --mcp`) | `npm i -g @colbymchenry/codegraph` |
| **engram** | 1.18+ | Persistent memory MCP server (required: `.mcp.json`'s `engram` server invokes this binary directly) | `brew install gentleman-programming/tap/engram` |
| **gentle-ai** (recommended) | 1.43+ | SDD workflow orchestration, skill registry, model-assignment dispatch for `/sdd-*` commands | `brew install gentleman-programming/tap/gentle-ai` |
| **OpenCode** (optional) | — | Secondary runtime for `.opencode/agents/` + `.opencode/commands/propuesta.md` (generated from `.claude/` via `scripts/gen-opencode.py`, stdlib-only, no new Python deps); interactive session required — gates don't work under `opencode run` headless | see [opencode.ai](https://opencode.ai) |
| **Pi** (optional) | 0.87+ | Secondary runtime for `.pi/agents/` + `.pi/prompts/propuesta.md` (generated from `.claude/` via `scripts/gen-pi.py`); interactive session required for the approval gates | `npm i -g @earendil-works/pi-coding-agent` |
| **Google Antigravity** (optional) | — | Secondary runtime for `.agent/skills/` + `.agent/workflows/` (generated from `.claude/` via `scripts/gen-antigravity.py`) | see [antigravity.google](https://antigravity.google) |

## 2. Python packages (`requirements.txt`)

Install:
```bash
pip install -r requirements.txt
```

These are the extraction toolchain `insumos-observador` uses to read the files
dropped into a run's `insumos/`:

| Package | Used for | Fallback if absent |
|---------|----------|--------------------|
| `pymupdf4llm` | PDF → Markdown preserving tables and structure | none; PDF intake degrades badly |
| `markitdown` | Office documents (`.docx`, `.pptx`, `.xlsx`) | `textutil -convert txt` / `unzip -p ... word/document.xml` on macOS |
| `markdownify` | HTML → Markdown for web-sourced inputs | none |
| `python-docx` | DOCX structure when Markdown is not enough | same as `markitdown` |

Skip them only if you never feed PDFs or Office documents to a run:
`insumos-observador` names them as its primary path and the documented
fallbacks are macOS-only.

**Scope note:** nothing *else* in the pipeline needs Python packages. The
knowledge-graph layer is `codebase-memory` (the `codegraph` MCP server, a Node
binary — see section 1), not a Python library, and every framework script is
stdlib-only: `plantilla/scripts/compile_tikz.py`,
`plantilla/scripts/prep_docx.py`, `scripts/marco_cli.py`, and the three
runtime generators import nothing from this file.

## 3. Node.js / MCP servers

All MCP servers run via `npx -y` (fetched on demand, no global install needed). All eight are registered as Claude Code MCP servers in `.mcp.json` (`engram`, `consensus`, and the six below); the six below are used directly by the proposal agents as Claude Code tools for literature/citation search:

| Server | npm package | Purpose |
|--------|-------------|---------|
| **arxiv** | `@cyanheads/arxiv-mcp-server` | arXiv paper search & full-text |
| **crossref** | `@botanicastudios/crossref-mcp` | DOI metadata, references, funders |
| **openalex** | `@cyanheads/openalex-mcp-server` | Scholarly catalog, citation graphs |
| **pubmed** | `@cyanheads/pubmed-mcp-server` | PubMed/PMC search, full-text, MeSH |
| **semantic scholar** | `@xbghc/semanticscholar-mcp` | Paper search, citations, recommendations |
| **context7** | `@upstash/context7-mcp` | Library documentation lookup |

## 4. LaTeX packages (TeX Live)

All loaded in the run's `redaccion/main.tex`. Install via `tlmgr install <pkg>` or MacTeX/full:

| Package | Collection | Purpose |
|---------|-----------|---------|
| `inputenc` | latex-base | UTF-8 input |
| `fontenc` | latex-base | T1 font encoding |
| `babel` (spanish, es-tabla) | babel-spanish | Spanish hyphenation + tabla naming |
| `geometry` | geometry | Page margins (2.5cm) |
| `graphicx` | graphics | Logo embedding (header/footer) |
| `amsmath` | amsmath | Math environments |
| `amssymb` | amsfonts | Math symbols (\bigstar) |
| `booktabs` | booktabs | Professional tables |
| `tabularx` | tools | Auto-width table columns |
| `longtable` | tools | Multi-page tables |
| `tikz` | pgf | Diagrams (arbol, metodológico) |
| `pgfgantt` | pgfgantt | Gantt chart |
| `hyperref` | hyperref | Clickable cross-references |
| `url` | url | URL formatting |
| `csquotes` | csquotes | Quote environments |
| `fancyhdr` | fancyhdr | Split header/footer with institutional logos (UNAL header; GCPDS/LabIA footer) |
| `natbib` (style=apalike, backend=bibtex) | natbib + apalike.bst | Citas autor-año APA (ver guiaProyectosIA_Agente.md §16) |
| `cm-super` | cm-super | T1-compatible Computer Modern fonts (Spanish) |

Compile sequence (or just run `./build.sh` / `./build.sh --manual`):
```bash
cd proposal
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## 5. Knowledge graph (codebase-memory)

The pipeline's graph layer is the `codegraph` MCP server declared in
`.mcp.json`. The dispatcher calls it with MCP tools (`index_repository`,
`get_architecture`, `search_graph`, `query_graph`, `check_index_coverage`,
`delete_project`) — never a CLI binary through Bash, and never with an API
key.

Two indexes per run, both scoped to the run's own corpus directory:

| Index | `repo_path` | Report |
|-------|-------------|--------|
| `<run-id>-papers` | `<RUN_ROOT>/artefactos/scoping/papers` | `grafos/papers-graph-report.md` |
| `<run-id>-vault` | `<RUN_ROOT>/artefactos/vault` | `grafos/vault-graph-report.md` |

Two verified constraints drive that shape:
- `codegraph` honors `.gitignore`, and all run content is gitignored, so a
  root-level index reports the corpus as `not_indexed` /
  `reason: "gitignore"`. Indexing the corpus directory **as its own root**
  bypasses the parent `.gitignore`.
- `.cbmignore` can exclude noise inside a corpus (e.g. `artefactos/vault/.cbmignore`
  drops `.obsidian/`) but its `!path` negations do **not** re-include a
  `.gitignore`d path.

It has no HTML export and no `[[wikilink]]` edges: the user-facing artifact is
the Markdown report the dispatcher writes, and broken wikilinks are detected
deterministically with `Grep`.

## 6. Environment variables

| Variable | Required by | Description |
|----------|-------------|-------------|
| `CONTACT_EMAIL` | openalex, crossref, pubmed MCP | Polite-pool access (set in shell or `.env`) |
| `CROSSREF_MAILTO` | crossref MCP | Polite-pool (falls back to CONTACT_EMAIL) |

## 7. Project structure

```
.
├── requirements.txt          # Optional Python deps — manual insumos/ input conversion only
├── REQUIREMENTS.md           # This file
├── AGENTS.md                 # Framework playbook
├── guiaProyectosIA_Agente.md # Section-by-section writing guide
├── logos/                    # Repo/README branding logos (LabIA, UNAL, GCPDS)
├── scripts/                  # Repo tooling: gen-opencode.py, gen-pi.py + rules JSON
├── .claude/                  # CANONICAL runtime — single source of truth, hand-edited
│   ├── agents/                # 10 agent markdown files
│   └── commands/              # /propuesta-* dispatchers + _propuesta-steps.md
├── .opencode/                 # Secondary — GENERATED (gen-opencode.py), never hand-edited
│   ├── agents/
│   └── commands/
│       └── propuesta.md      # Comando /propuesta — dispatcher real del pipeline
├── .opencode/                 # Secondary runtime — GENERATED from .claude/, never hand-edited
│   ├── agents/                 # 9 ported subagents (1:1 with .claude/agents/, no coordinador)
│   └── commands/propuesta.md   # Ported /propuesta command
├── proposals/                 # Runs — nothing here is versioned; init creates it
│   ├── registry.md             # Local append-only table: run-id, estado, archivo
│   ├── .current-run            # Active run-id pointer
│   └── <run-id>/               # RUN_ROOT — every run artifact lives here (gitignored):
│                               #   _run.md + insumos/ + artefactos/ + grafos/ + redaccion/
├── plantilla/                # LaTeX skeleton committed to git, copied into each RUN_ROOT
│                              #   as redaccion/. The repo root never holds run artifacts.
│   ├── build.sh              # Compilación PDF/DOCX (logos header/footer)
│   ├── scripts/               # compile_tikz.py, prep_docx.py — LaTeX/DOCX build-specific,
│   │                           #   distinct from the root-level scripts/ (repo tooling)
│   ├── logos/                 # LabIA, UNAL, GCPDS logos embedded in the built PDF
│   └── templates/reference.docx  # Plantilla pandoc para export DOCX
│   # Una corrida no escribe acá: sus artefactos van a proposals/<run-id>/
│   #   (redaccion/main.tex, redaccion/sections/*.tex, redaccion/refs.bib,
│   #    artefactos/insumos.md, artefactos/estado_propuesta.md,
│   #    artefactos/guia_ajustada_TDR.md, artefactos/pipeline/,
│   #    artefactos/scoping/, grafos/*.md)
└── .codegraph/               # codebase-memory index database (gitignored)
```
