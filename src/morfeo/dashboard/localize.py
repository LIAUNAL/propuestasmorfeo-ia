"""Display language of the JSON API: Spanish always, English on request.

Ported from papersmith-ai (``skills/_core/command_center/localize.py``), with
the direction reversed: Morfeo's server builds its labels in Spanish, and every
response is Spanish unless the request asks otherwise. A request to an
``/api/`` route that carries ``?lang=en`` (the dashboard's fetch wrapper adds
it while the page is in English, see ``static/i18n.js``) gets the same JSON
with its DISPLAY fields translated; nothing else changes.

What is translated is chosen explicitly, never guessed:

* ``DISPLAY_FIELDS`` maps a route to the dotted JSON paths whose values are
  labels the server wrote (``gates.name``, ``pipeline_units.desc``…; list
  levels are left out of a path, and ``*`` stands for any one key, such as a
  unit id in ``unit_progress.*.missing``). ``COMMON_FIELDS`` (the top-level
  ``error``, ``errores``, ``message`` and ``mensaje``) apply to every route. A
  string at any other path (an id, a state, a kind, a path, a command, a file
  name, a text an agent wrote) is never touched, even when it happens to equal
  a catalogue entry, because the panels compare those values
  (``state === 'verified'``). A list at a display path is translated item by
  item; a dict at one is walked with the same rule.
* ``static/i18n/server-en.json`` maps a Spanish text to its English. A key with
  ``{name}`` placeholders is a template: ``"Compuerta {gate} en PASS"`` matches
  any text of that shape and keeps the matched values; a matched value that has
  an entry of its own is translated too. Exact entries win over templates, and
  longer templates are tried before shorter ones.
* A display string with no entry stays Spanish; it is never emptied.

A request without ``lang``, or with any value but ``en``, gets the handler's
payload untouched, so its bytes are exactly those of a Spanish request. The
pages the dashboard embeds (the constellations, the presentation) take the
same ``?lang=`` parameter and translate their own chrome.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Iterator

CATALOGUE = Path(__file__).resolve().parent / "static" / "i18n" / "server-en.json"
DEFAULT_LANGUAGE = "es"
LANGUAGES = frozenset({"en"})

#: Top-level fields every route may carry with a message the server wrote.
COMMON_FIELDS = ("error", "errores", "message", "mensaje")

_SUMMARY = ("current.name", "missing", "open_gates.name", "failed_gates.name",
            "failed_artifacts.label", "failed_artifacts.detail")
_ARTIFACTS = ("artifacts.label", "artifacts.detail")


def _under(prefix: str, *keys: str) -> list[str]:
    return [f"{prefix}.{key}" for key in keys]


#: Route -> the dotted JSON paths whose string values are labels the server
#: wrote. Everything else in a response is a machine value or the workspace's
#: own content and is never translated.
DISPLAY_FIELDS: dict[str, tuple[str, ...]] = {
    "/api/status": (
        "gates.name", "gates.criteria", "gates.phase", "gates.reviewer",
        "pipeline_units.name", "pipeline_units.desc",
        "unit_progress.*.checks.label", "unit_progress.*.missing",
        "sections.title",
    ),
    "/api/board/summary": (
        *_under("summary", *_SUMMARY),
        *_under("last_refresh", *_ARTIFACTS), *_under("last_refresh.summary", *_SUMMARY),
    ),
    "/api/board/refresh": (*_ARTIFACTS, *_under("summary", *_SUMMARY)),
    "/api/trees": (
        "problem.tree.trunk.label", "problem.tree.crown.label",
        "objectives.tree.trunk.label", "objectives.tree.crown.label",
    ),
    "/api/judge-avance": ("errores",),
    "/api/novedad": ("errores", "validacion.errores"),
    "/api/convocatorias": ("vista.oportunidades.alertas.texto",),
    "/api/convocatorias/progreso": ("progreso.fase_nombre", "progreso.phase_label"),
}

_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


@lru_cache(maxsize=1)
def _catalogue() -> tuple[dict[str, str], tuple[tuple[re.Pattern[str], str], ...]]:
    try:
        entries = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        entries = {}
    exact = {spanish: english for spanish, english in entries.items()
             if not _PLACEHOLDER.search(spanish)}
    templates = []
    for spanish, english in entries.items():
        if not _PLACEHOLDER.search(spanish):
            continue
        pattern, last = [], 0
        for match in _PLACEHOLDER.finditer(spanish):
            pattern.append(re.escape(spanish[last:match.start()]))
            pattern.append(f"(?P<{match.group(1)}>.*?)")
            last = match.end()
        pattern.append(re.escape(spanish[last:]))
        templates.append((re.compile("".join(pattern), re.S), english))
    # Longer templates are more specific: try them first.
    templates.sort(key=lambda item: -len(item[0].pattern))
    return exact, tuple(templates)


@lru_cache(maxsize=8192)
def lookup(text: str) -> str | None:
    """The English of ``text``, or ``None`` when the catalogue has no entry.

    A template's matched values are looked up too (a gate name inside a
    message); a value with no entry of its own is kept as it is.
    """
    exact, templates = _catalogue()
    if text in exact:
        return exact[text]
    for pattern, english in templates:
        match = pattern.fullmatch(text)
        if match:
            values = {name: (lookup(value) or value) if value and value != text else value
                      for name, value in match.groupdict().items()}
            return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), english)
    return None


def translate(text: str, lang: str) -> str:
    """``text`` in ``lang``; Spanish (the text itself) when there is no entry."""
    if lang not in LANGUAGES or not text:
        return text
    return lookup(text) or text


def _compile(fields: Iterable[str]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(field.split(".")) for field in fields)


def _is_display(path: tuple[str, ...], fields: tuple[tuple[str, ...], ...]) -> bool:
    return any(len(field) == len(path) and all(f in ("*", p) for f, p in zip(field, path))
               for field in fields)


def _display(value: Any, lang: str, fields: tuple[tuple[str, ...], ...], path: tuple[str, ...]) -> Any:
    if isinstance(value, str):
        return translate(value, lang)
    if isinstance(value, list):
        return [_display(item, lang, fields, path) for item in value]
    if isinstance(value, dict):
        return _walk(value, lang, fields, path)
    return value


def _walk(payload: Any, lang: str, fields: tuple[tuple[str, ...], ...], path: tuple[str, ...]) -> Any:
    if isinstance(payload, dict):
        out = {}
        for key, value in payload.items():
            where = (*path, str(key))
            out[key] = (_display(value, lang, fields, where) if _is_display(where, fields)
                        else _walk(value, lang, fields, where))
        return out
    if isinstance(payload, list):
        return [_walk(item, lang, fields, path) for item in payload]
    return payload


def localize(payload: Any, lang: str, fields: Iterable[str]) -> Any:
    """``payload`` with the string values at the display ``fields`` translated.

    A field is a dotted path of JSON keys from the root, list levels left out
    and ``*`` matching any one key: ``gates.name`` is the ``name`` of every gate.
    """
    if lang not in LANGUAGES:
        return payload
    return _walk(payload, lang, _compile(fields), ())


def fields_for(route: str) -> tuple[str, ...]:
    """Every display field of ``route``: its own plus :data:`COMMON_FIELDS`."""
    return (*COMMON_FIELDS, *DISPLAY_FIELDS.get(route, ()))


def display_strings(payload: Any, fields: Iterable[str]) -> Iterator[str]:
    """Every string :func:`localize` would offer to the catalogue."""
    compiled = _compile(fields)

    def walk(value: Any, path: tuple[str, ...], inside: bool) -> Iterator[str]:
        if isinstance(value, str):
            if inside:
                yield value
        elif isinstance(value, list):
            for item in value:
                yield from walk(item, path, inside)
        elif isinstance(value, dict):
            for key, item in value.items():
                where = (*path, str(key))
                yield from walk(item, where, inside or _is_display(where, compiled))

    yield from walk(payload, (), False)


def requested_language(request_path: str) -> str:
    """``en`` when the request's query asks for English; ``es`` otherwise."""
    query = urllib.parse.urlsplit(request_path).query
    values = urllib.parse.parse_qs(query).get("lang") or [""]
    return values[0] if values[0] in LANGUAGES else DEFAULT_LANGUAGE


def localize_response(request_path: str, payload: Any) -> Any:
    """The payload a JSON route answers for ``request_path`` (path and query).

    Spanish requests get ``payload`` itself, untouched.
    """
    lang = requested_language(request_path)
    if lang not in LANGUAGES:
        return payload
    route = urllib.parse.urlsplit(request_path).path
    return localize(payload, lang, fields_for(route))


__all__ = ["CATALOGUE", "COMMON_FIELDS", "DEFAULT_LANGUAGE", "DISPLAY_FIELDS", "LANGUAGES",
           "display_strings", "fields_for", "localize", "localize_response", "lookup",
           "requested_language", "translate"]
