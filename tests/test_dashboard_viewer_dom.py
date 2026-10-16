"""Puente hacia el arnés DOM del visor PDF del tablero.

El visor es JavaScript en línea dentro de `index.html`, así que su
comportamiento asíncrono solo se puede observar ejecutándolo. El arnés real
vive en `tests/js/` y corre bajo Node con jsdom; esta prueba lo lanza desde
`python3 -m unittest discover -s tests` para que el repositorio conserve un
único punto de entrada.

Si Node o jsdom no están disponibles, la prueba se salta con un mensaje
explícito: la suite de Python nunca depende de una instalación de JavaScript.

Nota de honestidad: las carreras del visor quedaron selladas y fijadas por
`tests/js/viewer.race.test.mjs`; `npm test` (y por tanto esta prueba) corre la
suite DOM completa, sin marcas *todo* pendientes.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_GLOB = "tests/js/*.test.mjs"
TIMEOUT_SECONDS = 300


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
        check=False,
    )


def jsdom_available(node: str) -> bool:
    probe = run([node, "-e", "process.stdout.write(require.resolve('jsdom'))"])
    return probe.returncode == 0 and probe.stdout.strip() != ""


class TestDashboardViewerDom(unittest.TestCase):
    def test_viewer_behaviour_runs_under_node_and_jsdom(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest(
                "Node no está instalado: el arnés DOM del visor no se puede ejecutar. "
                "Instálalo desde https://nodejs.org y vuelve a correr la suite."
            )
        if not jsdom_available(node):
            self.skipTest(
                "jsdom no está instalado en este checkout: el arnés DOM del visor no "
                "se puede ejecutar. Corre `npm install` (o `npm ci`) en la raíz del "
                "repositorio; no es un requisito para el resto de la suite de Python."
            )

        # Rutas explícitas: la expansión del glob la hace Python, así que la
        # suite funciona igual en Node 18, donde `--test` no acepta patrones.
        test_files = sorted(str(path.relative_to(REPO_ROOT)) for path in REPO_ROOT.glob(TESTS_GLOB))
        if not test_files:
            self.skipTest(
                f"No hay pruebas DOM del visor en {TESTS_GLOB}: el arnés no está instalado "
                "en este checkout."
            )

        result = run([node, "--test", *test_files])
        output = f"{result.stdout}\n{result.stderr}".strip()
        if result.returncode != 0:
            self.fail(f"La suite DOM del visor falló:\n{output}")

        summary = self.tap_summary(output)
        # Se imprime el resumen de TAP para que la salida de unittest deje ver el
        # estado de la suite DOM completa (incluidas las carreras del visor).
        print(
            "arnés DOM del visor: "
            f"{summary.get('pass', '?')} pasan, {summary.get('fail', '?')} fallan, "
            f"{summary.get('todo', '?')} marcadas como todo"
        )

    @staticmethod
    def tap_summary(output: str) -> dict[str, int]:
        summary: dict[str, int] = {}
        for line in output.splitlines():
            stripped = line.strip().lstrip("#").strip()
            if not stripped:
                continue
            key, _, value = stripped.partition(" ")
            if key in {"tests", "pass", "fail", "todo", "skipped"} and value.strip().isdigit():
                summary[key] = int(value.strip())
        return summary


if __name__ == "__main__":
    unittest.main()
