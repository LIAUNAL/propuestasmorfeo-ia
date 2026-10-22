"""The `### SGR §N` blocks of the SGR guide, for the dashboard sections panel.

The dispatcher injects these blocks into each section's guide fragment; the
panel reads the same project file, so both show the same rules.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..errors import KitError
from ..kit import get_kit_root

GUIDE = "guiaProyectosIA_Agente_Regalias.md"
_HEADING = re.compile(r"^### SGR (§\d+|A\d+)\s*$", re.MULTILINE)


def parse_sgr_blocks(text: str) -> dict[str, str]:
    """Map "§3", "A19", ... to the Markdown body under its `### SGR` heading."""
    matches = list(_HEADING.finditer(text))
    blocks: dict[str, str] = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end():end]
        cut = re.search(r"^#{1,3} ", body, re.MULTILINE)
        blocks[match.group(1)] = (body[:cut.start()] if cut else body).strip()
    return blocks


def load_sgr_blocks(workspace: Path) -> tuple[dict[str, str], str | None]:
    """Blocks from the project's guide, else the bundled kit copy; also the source used."""
    try:
        kit = get_kit_root()
    except KitError:
        kit = None
    for base, label in ((workspace, GUIDE), (kit, f"kit/{GUIDE}")):
        if base is None:
            continue
        path = base / GUIDE
        if path.is_file():
            return parse_sgr_blocks(path.read_text(encoding="utf-8", errors="replace")), label
    return {}, None
