"""Presentación de la corrida activa con el estilo de LIAUNAL/AgentPt.

El tablero la sirve en /presentacion. Arma cinco diapositivas con lo que la
corrida ya tiene: convocatoria, título y línea temática; entidad proponente y
aliados con sus escudos; los dos árboles (las vistas previas que deja
`figura.py`); y la metodología. Mientras `sections/10_metodologia.tex` no
exista, la última diapositiva se deriva del árbol de objetivos y se marca como
preliminar. Lo que falta se dice («por definir», «pendiente»), nunca se inventa.
El CSS y el JS son copia de AgentPt en `dashboard/static/presentacion/`.
"""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from typing import Any

ASSET_URL = "/api/presentation/asset?path="
# Lo único de redaccion/ que la presentación puede mostrar.
ASSET_DIRS = ("logos", "sections/figuras")
ASSET_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}

_EXTRA_CSS = """
.alliance-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1.4rem; align-items: center; justify-items: center; }
.alliance-grid img { max-height: 120px; max-width: 100%; object-fit: contain; }
.alliance-proponent { display: flex; align-items: center; gap: 1.2rem; margin-bottom: 1.6rem; }
.alliance-proponent img { height: 110px; object-fit: contain; }
.slide-figure.tree-figure img { max-height: 70vh; object-fit: contain; }
.method-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }
.method-card { background: var(--surface, #fff); border: 1px solid var(--line, #dde2ec); border-radius: 14px; padding: 1rem 1.1rem; }
.method-card h3 { margin: 0 0 .5rem; font-size: 1.02rem; }
.method-card ul { margin: 0; padding-left: 1.1rem; font-size: .92rem; }
.placeholder { opacity: .7; font-style: italic; }
"""

#: The deck's own words in English, for /presentacion?lang=en (the dashboard
#: opens it in its language). What the run wrote is shown as it is.
PAGE_LANGUAGES = ("es", "en")
_EN = {
    "Línea temática {code}": "Thematic line {code}",
    "[Convocatoria por definir]": "[Funding call to be defined]",
    "[Título por definir]": "[Title to be defined]",
    "Logo del laboratorio": "Lab logo",
    "[Línea temática por definir]": "[Thematic line to be defined]",
    "Escudo de entidad aliada": "Crest of an allied entity",
    "2 &middot; Alianza": "2 &middot; Alliance",
    "Entidad ejecutora y aliados": "Executing entity and allies",
    "Escudo de la entidad proponente": "Crest of the proposing entity",
    "Entidad proponente:": "Proposing entity:",
    "[por definir]": "[to be defined]",
    "Escudos de los aliados pendientes": "Allies' crests pending",
    "Figura pendiente: falta renderizar {figure}.": "Figure pending: {figure} is not rendered yet.",
    "Fases de la metodología redactada.": "Phases of the written methodology.",
    "Árbol de objetivos pendiente": "Objective tree pending",
    "Metodología preliminar: una línea de trabajo por objetivo específico, con sus medios. Se define en la fase de "
    "metodología.": "Preliminary methodology: one line of work per specific objective, with its means. It is set in "
                    "the methodology phase.",
    "5 &middot; Metodología": "5 &middot; Methodology",
    "Metodología": "Methodology",
    "3 · Problema": "3 · Problem",
    "Árbol de problemas": "Problem tree",
    "Causas, problema central y efectos, según la metodología MGA.": "Causes, central problem and effects, following the MGA methodology.",
    "4 · Objetivos": "4 · Objectives",
    "Árbol de objetivos": "Objective tree",
    "Espejo positivo del árbol de problemas: medios, objetivo general y fines.": "Positive mirror of the problem tree: means, general objective and ends.",
    "Propuesta": "Proposal",
    "Alianza": "Alliance",
    "Problema": "Problem",
    "Objetivos": "Objectives",
    "Módulos": "Modules",
    "Laboratorio de Inteligencia Artificial": "Artificial Intelligence Laboratory",
    "Diapositiva anterior": "Previous slide",
    "Anterior": "Previous",
    "Diapositiva siguiente": "Next slide",
    "Siguiente": "Next",
}


def _w(text: str, lang: str, **values: str) -> str:
    """A word of the deck in ``lang`` (Spanish as is), with ``{name}`` values filled."""
    if lang == "en":
        text = _EN.get(text, text)
    return text.format(**values) if values else text


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _tex_macro(tex: str, name: str) -> str | None:
    match = re.search(r"\\newcommand\{\\" + name + r"\}\{(.*)\}\s*$", tex, re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    return None if not value or value.startswith("[Por definir") else value


def _convocatoria(run_dir: Path) -> str | None:
    first = _read(run_dir / "artefactos" / "guia_ajustada_TDR.md").splitlines()[:1]
    if not first:
        return None
    title = first[0].lstrip("# ").strip()
    return title.split(":", 1)[1].strip() if ":" in title else title or None


def _linea(run_dir: Path) -> tuple[str | None, str | None]:
    estado = _read(run_dir / "artefactos" / "estado_propuesta.md")
    match = re.search(r"\|\s*Línea temática principal\s*\|\s*\**\s*([\d.]+)", estado)
    code = match.group(1).strip(".") if match else None
    if not code:
        return None, None
    guia = _read(run_dir / "artefactos" / "guia_ajustada_TDR.md")
    desc = re.search(re.escape(code) + r"\**\s*\(«([^»]+)»", guia)
    return code, desc.group(1).strip() if desc else None


def _asset(run_dir: Path, rel: str) -> str | None:
    return ASSET_URL + rel if (run_dir / "redaccion" / rel).is_file() else None


def _ally_logos(run_dir: Path) -> list[str]:
    main = _read(run_dir / "redaccion" / "main.tex")
    names = re.findall(r"\\LogoAliado\{([^}]+)\}", main)
    return [url for name in names if (url := _asset(run_dir, f"logos/{name}.png"))]


def _phases_from_section(run_dir: Path) -> list[str]:
    tex = _read(run_dir / "redaccion" / "sections" / "10_metodologia.tex")
    return [re.sub(r"\s+", " ", t).strip() for t in re.findall(r"\\subsection\*?\{([^}]*)\}", tex)]


def _objective_tree(run_dir: Path) -> dict[str, Any]:
    try:
        data = json.loads(_read(run_dir / "artefactos" / "arboles" / "arbol_objetivos.json") or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _slide(index: int, module: int | str, tone: str, body: str, classes: str = "") -> str:
    active = " is-active" if index == 0 else ""
    return (
        f'<article class="slide{(" " + classes) if classes else ""}{active}" data-index="{index}" '
        f'data-module="{module}" data-tone="{tone}">\n{body}\n</article>'
    )


def _value(text: str | None, placeholder: str) -> str:
    return escape(text) if text else f'<span class="placeholder">{escape(placeholder)}</span>'


def _cover(run_dir: Path, datos: str, lang: str = "es") -> str:
    code, desc = _linea(run_dir)
    linea = _w("Línea temática {code}", lang, code=escape(code)) if code else ""
    if code and desc:
        linea += f": {escape(desc)}"
    logo = _asset(run_dir, "logos/logo_labIA.png") or _asset(run_dir, "logos/logo_unal.png")
    pi = _tex_macro(datos, "InvestigadorPrincipal")
    entity = _tex_macro(datos, "EntidadProponente")
    return _slide(0, 0, "cyan", f"""<div class="cover-content">
  <p class="slide-kicker">{_value(_convocatoria(run_dir), _w("[Convocatoria por definir]", lang))}</p>
  <p class="cover-project">{_value(_tex_macro(datos, "TituloProyecto"), _w("[Título por definir]", lang))}</p>
  {f'<img class="cover-logo" src="{logo}" alt="{_w("Logo del laboratorio", lang)}" />' if logo else ""}
  <p class="cover-meta"><span>{linea or _value(None, _w("[Línea temática por definir]", lang))}</span></p>
  <p class="cover-meta">{f"<span>{escape(pi)}</span>" if pi else ""}{f"<span>{escape(entity)}</span>" if entity else ""}</p>
</div>""", "is-cover")


def _alliance(run_dir: Path, datos: str, lang: str = "es") -> str:
    proponent = _asset(run_dir, "logos/logo_unal.png")
    allies = "".join(f'<img src="{url}" alt="{_w("Escudo de entidad aliada", lang)}" />' for url in _ally_logos(run_dir))
    return _slide(1, 1, "green", f"""<div class="slide-content">
  <p class="slide-kicker">{_w("2 &middot; Alianza", lang)}</p>
  <h2>{_w("Entidad ejecutora y aliados", lang)}</h2>
  <div class="alliance-proponent">
    {f'<img src="{proponent}" alt="{_w("Escudo de la entidad proponente", lang)}" />' if proponent else ""}
    <p><strong>{_w("Entidad proponente:", lang)}</strong> {_value(_tex_macro(datos, "EntidadProponente"), _w("[por definir]", lang))}</p>
  </div>
  <div class="alliance-grid">{allies or _value(None, _w("Escudos de los aliados pendientes", lang))}</div>
</div>""", "is-wide")


def _tree(run_dir: Path, index: int, kicker: str, title: str, figure: str, tone: str, lead: str,
          lang: str = "es") -> str:
    url = _asset(run_dir, f"sections/figuras/{figure}-preview-1.png")
    kicker, title, lead = _w(kicker, lang), _w(title, lang), _w(lead, lang)
    fig = (
        f'<figure class="slide-figure tree-figure"><img src="{url}" alt="{escape(title)}" /></figure>'
        if url else f'<figure class="slide-figure"><p class="placeholder">{_w("Figura pendiente: falta renderizar {figure}.", lang, figure=escape(figure))}</p></figure>'
    )
    return _slide(index, index, tone, f"""<div class="slide-content">
  <p class="slide-kicker">{escape(kicker)}</p>
  <h2>{escape(title)}</h2>
  <ul class="slide-list"><li>{lead}</li></ul>
</div>
{fig}""", "is-figure-wide")


def _methodology(run_dir: Path, lang: str = "es") -> str:
    phases = _phases_from_section(run_dir)
    if phases:
        cards = "".join(f'<div class="method-card"><h3>{escape(p)}</h3></div>' for p in phases)
        lead = _w("Fases de la metodología redactada.", lang)
    else:
        tree = _objective_tree(run_dir)
        cards = ""
        for group in tree.get("groups") or []:
            means = "".join(f"<li>{escape(str(m.get('text', '')))}</li>" for m in group.get("means") or [])
            cards += (
                f'<div class="method-card"><h3>{escape(str(group.get("title") or group.get("id") or ""))}</h3>'
                f'<p>{escape(str(group.get("objective") or ""))}</p><ul>{means}</ul></div>'
            )
        cards = cards or _value(None, _w("Árbol de objetivos pendiente", lang))
        lead = _w("Metodología preliminar: una línea de trabajo por objetivo específico, con sus medios. Se define en "
                  "la fase de metodología.", lang)
    return _slide(4, 4, "purple", f"""<div class="slide-content">
  <p class="slide-kicker">{_w("5 &middot; Metodología", lang)}</p>
  <h2>{_w("Metodología", lang)}</h2>
  <p>{escape(lead)}</p>
  <div class="method-grid">{cards}</div>
</div>""", "is-wide")


def build_presentation(run_dir: Path, lang: str = "es") -> str:
    """The deck of the run; ``lang`` ("es" or "en") is the language of its own words."""
    if lang not in PAGE_LANGUAGES:
        raise ValueError(f"unknown page language {lang!r}")
    datos = _read(run_dir / "redaccion" / "datos_proyecto.tex")
    title = _tex_macro(datos, "TituloProyecto") or run_dir.name
    deck = "\n".join([
        _cover(run_dir, datos, lang),
        _alliance(run_dir, datos, lang),
        _tree(run_dir, 2, "3 · Problema", "Árbol de problemas", "fig_arbol_problemas", "red",
              "Causas, problema central y efectos, según la metodología MGA.", lang),
        _tree(run_dir, 3, "4 · Objetivos", "Árbol de objetivos", "fig_arbol_objetivos", "blue",
              "Espejo positivo del árbol de problemas: medios, objetivo general y fines.", lang),
        _methodology(run_dir, lang),
    ])
    rail = "".join(
        f'<div class="rail-module" data-module="{i}"><button class="rail-title" data-first="{i}">'
        f'{i + 1}. {_w(label, lang)}</button><div class="rail-dots" id="dots-{i}"></div></div>'
        for i, label in enumerate(["Propuesta", "Alianza", "Problema", "Objetivos", "Metodología"])
    )
    unal = _asset(run_dir, "logos/logo_unal.png")
    labia = _asset(run_dir, "logos/logo_labIA.png")
    return f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
<title>{escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&amp;family=Source+Serif+4:wght@500;700&amp;display=swap" rel="stylesheet" />
<link rel="stylesheet" href="/static/presentacion/styles.css" />
<style>{_EXTRA_CSS}</style>
</head>
<body>
<div class="ambient"></div>
<div class="deck-app">
<nav class="rail" aria-label="{_w("Módulos", lang)}">{rail}</nav>
<div class="stage-layout"><main class="viewport" id="viewport">
{deck}
</main></div>
<footer class="deck-controls">
  <p class="running-title">{escape(title)}</p>
  {f'<img class="controls-logo controls-logo-unal" src="{unal}" alt="Universidad Nacional de Colombia" />' if unal else ""}
  {f'<img class="controls-logo" src="{labia}" alt="{_w("Laboratorio de Inteligencia Artificial", lang)}" />' if labia else ""}
  <button type="button" id="prev" class="ghost" aria-label="{_w("Diapositiva anterior", lang)}" title="{_w("Anterior", lang)}"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M15 5 L8 12 L15 19" /></svg></button>
  <span id="counter">01 / 05</span>
  <button type="button" id="next" class="solid" aria-label="{_w("Diapositiva siguiente", lang)}" title="{_w("Siguiente", lang)}"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9 5 L16 12 L9 19" /></svg></button>
</footer>
</div>
<script src="/static/presentacion/app.js"></script>
</body>
</html>
"""


def resolve_asset(run_dir: Path, rel: str) -> tuple[Path | None, int]:
    """Archivo de redaccion/ que la presentación puede servir, con su código HTTP."""
    redaccion = (run_dir / "redaccion").resolve()
    target = (redaccion / rel).resolve()
    allowed = [(redaccion / d).resolve() for d in ASSET_DIRS]
    if target.suffix.lower() not in ASSET_TYPES or not any(target.is_relative_to(d) for d in allowed):
        return None, 403
    return (target, 200) if target.is_file() else (None, 404)
