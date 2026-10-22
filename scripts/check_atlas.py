#!/usr/bin/env python3
"""Fail-closed validator for a Morfeo SOTA constellation atlas.

Ported from papersmith-ai (skills/plausibility/scripts/check_atlas.py,
https://github.com/LIAUNAL/papersmith-ai), Apache License 2.0. Changes for
Morfeo: system ids are ``paper-N``; quote fidelity is checked against the
``## Abstract`` section of ``<papers>/paper-N.md`` and ``evidence.origin`` must
equal that file's ``- DOI/URL:`` line; the family band is 1..7 (see the
constants below); a ``--json`` report. See scripts/assets/THIRD_PARTY_NOTICES.md.

Reads one ``artefactos/scoping/atlas.json`` and refuses every malformed atlas,
naming every violation in one run. Schema (unchanged from papersmith)::

    {"systems": [{"id": "paper-N", "title": "...",
                  "planets": [{"id", "slot", "orbit", "label", "detail",
                               "provenance": "stated" | "grouped",
                               "evidence": {"origin", "quote",
                                            "retrieved": "YYYY-MM-DD"}}]}],
     "links": [{"from_system", "from", "to_system", "to", "rel"}]}

With ``--papers <dir>`` every quote is held to the abstract it claims:
whitespace runs compare collapsed (a line break is layout, not authorship) and
nothing else is normalized. Without it a green run certifies shape alone.

Usage: check_atlas.py <atlas.json> [--papers <dir>] [--json]

Exit codes: 0 well-formed, 1 at least one violation (all named), 2 usage or
unreadable input (nothing was judged).

Stdlib only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

#: Planets one system may carry (papersmith's ceiling).
MAX_PLANETS = 20

#: Distinct family labels the whole atlas may carry. papersmith asks for 3..5
#: over a 25-paper pool; Morfeo's Fase 1a scopes 5 papers (one theme is a
#: legitimate constellation) and Fase 1c grows the corpus to ~45 or more, where
#: more than 7 families stops reading as a grouping.
MIN_FAMILIES = 1
MAX_FAMILIES = 7

#: Systems (papers) one atlas may carry: Fase 1a has 5, Fase 1c ~45, and real
#: runs have reached ~110 papers. The ceiling only keeps the page drawable.
MIN_SYSTEMS = 1
MAX_SYSTEMS = 200

# slot -> (orbit, min_count, max_count)
SLOTS = {
    "sun": (0, 1, 1),
    "branch": (1, 0, 2),
    "topic_app": (1, 1, 1),
    "topic_ai": (1, 1, 1),
    "problem": (1, 1, 1),
    "application": (1, 1, 1),
    "family": (2, 1, 1),
    "novelty": (1, 1, 1),
    "contribution": (1, 0, 5),
    "result": (3, 1, 3),
    "conclusion": (3, 1, 2),
}

RELS = {"about", "addresses", "extends", "contradicts", "supports",
        "yields", "shares-family-with"}

PROVENANCE = {"stated", "grouped"}

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PAPER_ID = re.compile(r"^paper-\d+$")

#: One sentence per code, so a red run reads without the source at hand.
HINTS = {
    "ATLAS_NOT_AN_OBJECT": "the atlas must be a JSON object",
    "SYSTEMS_NOT_A_NONEMPTY_LIST": "'systems' must be a non-empty list",
    "SYSTEM_COUNT_OUTSIDE_BAND": f"an atlas carries {MIN_SYSTEMS}..{MAX_SYSTEMS} systems",
    "LINKS_NOT_A_LIST": "'links' must be a list (it may be empty)",
    "SYSTEM_NOT_AN_OBJECT": "each system must be an object",
    "SYSTEM_ID_MISSING": "each system needs a non-empty 'id'",
    "SYSTEM_ID_NOT_PAPER_N": "system ids name their paper file: paper-N",
    "DUPLICATE_SYSTEM_ID": "system ids must be unique",
    "PLANETS_NOT_A_LIST": "'planets' must be a list",
    "PLANET_BUDGET_EXCEEDED": f"a system carries at most {MAX_PLANETS} planets",
    "PLANET_NOT_AN_OBJECT": "each planet must be an object",
    "PLANET_ID_MISSING": "each planet needs a non-empty 'id'",
    "DUPLICATE_PLANET_ID": "planet ids must be unique inside their system",
    "SLOT_OUTSIDE_TABLE": "slot must be one of " + ", ".join(sorted(SLOTS)),
    "ORBIT_MISMATCH": "each slot rides a fixed orbit",
    "PROVENANCE_UNLABELED": "provenance must be 'stated' or 'grouped'",
    "LABEL_EMPTY": "the planet needs a non-empty label",
    "DETAIL_EMPTY": "the planet needs a non-empty detail",
    "EVIDENCE_MISSING": "the planet needs an evidence object",
    "EVIDENCE_ORIGIN_EMPTY": "evidence.origin must be the paper's DOI/URL",
    "EVIDENCE_QUOTE_EMPTY": "evidence.quote must be a verbatim fragment of the abstract",
    "EVIDENCE_RETRIEVED_UNDATED": "evidence.retrieved must be a YYYY-MM-DD date",
    "SLOT_COUNT_OUTSIDE_ROW": "the system carries the wrong number of planets in a slot",
    "POOL_FAMILIES_OUTSIDE_1_7": f"the atlas carries {MIN_FAMILIES}..{MAX_FAMILIES} distinct families",
    "LINK_NOT_AN_OBJECT": "each link must be an object",
    "LINK_ENDPOINT_MISSING": "links need from_system, from, to_system and to",
    "LINK_SYSTEM_WITHOUT_SYSTEM": "the link names a system the atlas lacks",
    "LINK_ENDPOINT_WITHOUT_PLANET": "the link names a planet its system lacks",
    "SELF_LOOP": "a link cannot join a planet to itself",
    "REL_OUTSIDE_CLOSED_SET": "rel must be one of " + ", ".join(sorted(RELS)),
    "SHARED_FAMILY_LINK_ON_NON_FAMILY": "shares-family-with joins two family planets only",
    "EVIDENCE_PAPER_MISSING": "no paper-N.md for this system in the papers directory",
    "EVIDENCE_ABSTRACT_MISSING": "the paper file has no '## Abstract' text to quote",
    "EVIDENCE_ORIGIN_MISMATCH": "evidence.origin must equal the paper's '- DOI/URL:' line",
    "EVIDENCE_QUOTE_NOT_IN_ABSTRACT": "the quote is not verbatim in the paper's abstract",
}


def violation(code: str, where: str | None = None, detail: str | None = None) -> dict:
    return {"code": code, "where": where, "detail": detail,
            "message": HINTS.get(code, code.lower().replace("_", " "))}


def render_violation(v: dict) -> str:
    head = f"{v['where']}: {v['code']}" if v["where"] else v["code"]
    tail = f": {v['detail']}" if v["detail"] else ""
    return f"{head}{tail} ({v['message']})"


def _collapsed(text: str) -> str:
    return " ".join(text.split())


def parse_paper(text: str) -> dict:
    """Morfeo's paper file: ``# Title``, ``- Campo: valor`` lines, then a
    ``## Abstract`` section running to the next ``## `` heading or the end.
    Other sections (``## Verificación``) are not abstract text."""
    title, origin = None, None
    abstract_lines: list[str] | None = None
    in_abstract = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_abstract = stripped[3:].strip().lower() == "abstract"
            if in_abstract and abstract_lines is None:
                abstract_lines = []
            continue
        if in_abstract:
            abstract_lines.append(line)
            continue
        if title is None and stripped.startswith("# "):
            title = stripped[2:].strip()
        elif origin is None and stripped.lower().startswith("- doi/url:"):
            origin = stripped.split(":", 1)[1].strip()
    abstract = "\n".join(abstract_lines).strip() if abstract_lines is not None else ""
    return {"title": title, "origin": origin, "abstract": abstract}


def _fidelity_failures(atlas: dict, papers_dir: Path) -> list[dict]:
    found: list[dict] = []
    cache: dict[str, dict | None] = {}
    for system in atlas.get("systems") or []:
        if not isinstance(system, dict) or not isinstance(system.get("id"), str):
            continue
        sid = system["id"]
        if sid not in cache:
            path = papers_dir / f"{sid}.md"
            try:
                cache[sid] = parse_paper(path.read_text(encoding="utf-8"))
            except OSError:
                cache[sid] = None
                found.append(violation("EVIDENCE_PAPER_MISSING", sid, str(path)))
        paper = cache[sid]
        if paper is None:
            continue
        if not paper["abstract"]:
            found.append(violation("EVIDENCE_ABSTRACT_MISSING", sid, f"{sid}.md"))
            continue
        abstract = _collapsed(paper["abstract"])
        for planet in system.get("planets") or []:
            if not isinstance(planet, dict) or not isinstance(planet.get("evidence"), dict):
                continue
            evidence = planet["evidence"]
            origin, quote = evidence.get("origin"), evidence.get("quote")
            where = f"{sid}.{planet.get('id')}"
            if isinstance(origin, str) and origin.strip() and origin.strip() != (paper["origin"] or ""):
                found.append(violation("EVIDENCE_ORIGIN_MISMATCH", where,
                                       f"{origin!r} != {paper['origin']!r}"))
            if isinstance(quote, str) and quote.strip() and _collapsed(quote) not in abstract:
                found.append(violation("EVIDENCE_QUOTE_NOT_IN_ABSTRACT", where,
                                       f"{quote!r} is not verbatim in {sid}.md"))
    return found


def _shape_failures(atlas: object) -> list[dict]:
    found: list[dict] = []
    if not isinstance(atlas, dict):
        return [violation("ATLAS_NOT_AN_OBJECT")]
    systems = atlas.get("systems")
    links = atlas.get("links")
    if not isinstance(systems, list) or not systems:
        return [violation("SYSTEMS_NOT_A_NONEMPTY_LIST")]
    if not MIN_SYSTEMS <= len(systems) <= MAX_SYSTEMS:
        found.append(violation("SYSTEM_COUNT_OUTSIDE_BAND", None, f"{len(systems)} systems"))
    if not isinstance(links, list):
        found.append(violation("LINKS_NOT_A_LIST"))
        links = []

    known: dict[str, set[str]] = {}
    slots_of: dict[tuple[str, str], str] = {}
    for position, system in enumerate(systems):
        where = f"systems[{position}]"
        if not isinstance(system, dict):
            found.append(violation("SYSTEM_NOT_AN_OBJECT", where))
            continue
        sid = system.get("id")
        if not isinstance(sid, str) or not sid:
            found.append(violation("SYSTEM_ID_MISSING", where))
            continue
        if not PAPER_ID.match(sid):
            found.append(violation("SYSTEM_ID_NOT_PAPER_N", where, repr(sid)))
        if sid in known:
            found.append(violation("DUPLICATE_SYSTEM_ID", where, repr(sid)))
            continue
        planets = system.get("planets")
        if not isinstance(planets, list):
            found.append(violation("PLANETS_NOT_A_LIST", sid))
            known[sid] = set()
            continue
        if len(planets) > MAX_PLANETS:
            found.append(violation("PLANET_BUDGET_EXCEEDED", sid,
                                   f"{len(planets)} planets, limit is {MAX_PLANETS}"))
        seen: set[str] = set()
        counts: dict[str, int] = {}
        for index, planet in enumerate(planets):
            plabel = f"{sid}.planets[{index}]"
            if not isinstance(planet, dict):
                found.append(violation("PLANET_NOT_AN_OBJECT", plabel))
                continue
            pid = planet.get("id")
            if not isinstance(pid, str) or not pid:
                found.append(violation("PLANET_ID_MISSING", plabel))
                continue
            if pid in seen:
                found.append(violation("DUPLICATE_PLANET_ID", sid, repr(pid)))
            seen.add(pid)
            at = f"{sid}.{pid}"
            slot = planet.get("slot")
            if slot not in SLOTS:
                found.append(violation("SLOT_OUTSIDE_TABLE", at, repr(slot)))
            else:
                orbit, _, _ = SLOTS[slot]
                if planet.get("orbit") != orbit:
                    found.append(violation("ORBIT_MISMATCH", at,
                                           f"slot {slot!r} rides orbit {orbit}"))
                counts[slot] = counts.get(slot, 0) + 1
                slots_of[(sid, pid)] = slot
            if planet.get("provenance") not in PROVENANCE:
                found.append(violation("PROVENANCE_UNLABELED", at))
            for key in ("label", "detail"):
                if not isinstance(planet.get(key), str) or not planet.get(key).strip():
                    found.append(violation(f"{key.upper()}_EMPTY", at))
            evidence = planet.get("evidence")
            if not isinstance(evidence, dict):
                found.append(violation("EVIDENCE_MISSING", at))
                continue
            origin = evidence.get("origin")
            quote = evidence.get("quote")
            retrieved = evidence.get("retrieved")
            if not isinstance(origin, str) or not origin.strip():
                found.append(violation("EVIDENCE_ORIGIN_EMPTY", at))
            if not isinstance(quote, str) or not quote.strip():
                found.append(violation("EVIDENCE_QUOTE_EMPTY", at))
            if not isinstance(retrieved, str) or not DATE.match(retrieved):
                found.append(violation("EVIDENCE_RETRIEVED_UNDATED", at))
        for slot, (_, minimum, maximum) in SLOTS.items():
            have = counts.get(slot, 0)
            if not minimum <= have <= maximum:
                found.append(violation("SLOT_COUNT_OUTSIDE_ROW", sid,
                                       f"{slot!r} has {have}, row allows {minimum}..{maximum}"))
        known[sid] = seen

    families = _families(systems)
    if not MIN_FAMILIES <= len(families) <= MAX_FAMILIES:
        found.append(violation("POOL_FAMILIES_OUTSIDE_1_7", None,
                               f"{len(families)} distinct families"))

    for position, link in enumerate(links):
        where = f"links[{position}]"
        if not isinstance(link, dict):
            found.append(violation("LINK_NOT_AN_OBJECT", where))
            continue
        endpoints = []
        for key in ("from_system", "from", "to_system", "to"):
            value = link.get(key)
            if not isinstance(value, str) or not value:
                found.append(violation("LINK_ENDPOINT_MISSING", where, key))
                value = None
            endpoints.append(value)
        from_system, from_pid, to_system, to_pid = endpoints
        for name in (from_system, to_system):
            if name is not None and name not in known:
                found.append(violation("LINK_SYSTEM_WITHOUT_SYSTEM", where, repr(name)))
        if from_system in known and from_pid is not None and from_pid not in known[from_system]:
            found.append(violation("LINK_ENDPOINT_WITHOUT_PLANET", where, f"{from_system}.{from_pid}"))
        if to_system in known and to_pid is not None and to_pid not in known[to_system]:
            found.append(violation("LINK_ENDPOINT_WITHOUT_PLANET", where, f"{to_system}.{to_pid}"))
        if (from_system, from_pid) == (to_system, to_pid) and from_system in known:
            found.append(violation("SELF_LOOP", where))
        rel = link.get("rel")
        if rel not in RELS:
            found.append(violation("REL_OUTSIDE_CLOSED_SET", where, repr(rel)))
        elif rel == "shares-family-with":
            ends = [(from_system, from_pid), (to_system, to_pid)]
            if all(e in slots_of for e in ends) and any(slots_of[e] != "family" for e in ends):
                found.append(violation("SHARED_FAMILY_LINK_ON_NON_FAMILY", where))

    return found


def _families(systems: list) -> set[str]:
    labels = set()
    for system in systems:
        if not isinstance(system, dict):
            continue
        for planet in system.get("planets") or []:
            if isinstance(planet, dict) and planet.get("slot") == "family":
                label = planet.get("label")
                if isinstance(label, str) and label.strip():
                    labels.add(label.strip())
    return labels


def failures(atlas: object, papers_dir: Path | None = None) -> list[dict]:
    """Every violation, so one red run names all of them."""
    found = _shape_failures(atlas)
    if papers_dir is not None and isinstance(atlas, dict):
        found.extend(_fidelity_failures(atlas, papers_dir))
    return found


USAGE = "usage: check_atlas.py <atlas.json> [--papers <dir>] [--json]"


def _unjudged(code: str, detail: str, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"ok": False, "unjudged": True, "error": code, "detail": detail},
                         ensure_ascii=False, indent=2))
    else:
        print(f"{code}: {detail}", file=sys.stderr)
    return 2


def main(argv: list[str]) -> int:
    args = list(argv[1:])
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    papers_dir: Path | None = None
    if "--papers" in args:
        at = args.index("--papers")
        if at + 1 >= len(args):
            print(USAGE, file=sys.stderr)
            return 2
        papers_dir = Path(args[at + 1])
        args = args[:at] + args[at + 2:]
    if len(args) != 1 or args[0].startswith("--"):
        print(USAGE, file=sys.stderr)
        return 2
    target = Path(args[0])
    try:
        atlas = json.loads(target.read_text(encoding="utf-8"))
    except OSError as error:
        return _unjudged("ATLAS_UNREADABLE", str(error), as_json)
    except json.JSONDecodeError as error:
        return _unjudged("ATLAS_NOT_JSON", str(error), as_json)
    if papers_dir is not None and not papers_dir.is_dir():
        return _unjudged("PAPERS_DIR_UNREADABLE", f"{papers_dir} is not a directory", as_json)

    found = failures(atlas, papers_dir)
    ok = not found
    systems = atlas.get("systems") if isinstance(atlas, dict) else None
    systems = systems if isinstance(systems, list) else []
    links = atlas.get("links") if isinstance(atlas, dict) else None
    planets = sum(len(s["planets"]) for s in systems
                  if isinstance(s, dict) and isinstance(s.get("planets"), list))
    if as_json:
        print(json.dumps({
            "ok": ok,
            "atlas": str(target),
            "papers": str(papers_dir) if papers_dir is not None else None,
            "fidelity_checked": papers_dir is not None,
            "systems": len(systems),
            "planets": planets,
            "links": len(links) if isinstance(links, list) else 0,
            "families": len(_families(systems)),
            "limits": {"families": [MIN_FAMILIES, MAX_FAMILIES],
                       "systems": [MIN_SYSTEMS, MAX_SYSTEMS], "planets": MAX_PLANETS},
            "violations": found,
        }, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    if not ok:
        for item in found:
            print(render_violation(item))
        print(f"ATLAS_REFUSED: {len(found)} violation(s)")
        return 1
    print(f"ATLAS_WELL_FORMED: {len(systems)} systems, {planets} planets, "
          f"{len(links)} links, {len(_families(systems))} families"
          + ("; every quote verbatim in its paper-N.md abstract" if papers_dir is not None else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
