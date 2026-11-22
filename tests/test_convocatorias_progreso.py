"""Search progress for the «Convocatorias» tab (odd/tasks/tablero-juez-novedad.md, T1: S1).

The agent records the start and end of each of its five phases with
`scripts/convocatorias.py progreso`, which writes `convocatorias/progreso.json`
(schema `morfeo.convocatorias-progreso/v1`). The dashboard turns that file into
an estimated percent and time left (`morfeo.core.opportunities.estimate_progress`,
served by GET /api/convocatorias/progreso). Every test builds a throwaway
workspace outside the repository and goes through the CLI, the public core
functions or the HTTP handler.
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "convocatorias.py"
sys.path.insert(0, str(REPO / "src"))

from morfeo.core.opportunities import (  # noqa: E402
    PHASE_PRIORS,
    PROGRESS_SCHEMA,
    STALE_SECONDS,
    estimate_progress,
    load_progress,
)

T0 = datetime.datetime(2026, 11, 22, 10, 0, 0, tzinfo=datetime.timezone.utc)
NAMES = ["Perfil", "Fuentes fijas", "Búsqueda abierta", "Registro", "Verificación"]


def at(seconds: float) -> str:
    return (T0 + datetime.timedelta(seconds=seconds)).isoformat(timespec="seconds")


def cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, timeout=60)


def progress(phases: dict[int, tuple[float | None, float | None]] | None = None, *, finished=None,
             historial=None, started=0.0, updated=None) -> dict:
    """A progress document; `phases` maps n to (start, end) offsets in seconds from T0."""
    phases = phases or {}
    rows = []
    for n, name in enumerate(NAMES, start=1):
        start, end = phases.get(n, (None, None))
        rows.append({"n": n, "nombre": name, "started_at": None if start is None else at(start),
                     "ended_at": None if end is None else at(end), "detalle": None})
    stamps = [started] + [s for pair in phases.values() for s in pair if s is not None]
    return {"schema": PROGRESS_SCHEMA, "alcance": "proyecto", "started_at": at(started),
            "updated_at": at(updated if updated is not None else max(stamps)),
            "finished_at": None if finished is None else at(finished), "phases": rows,
            "historial": historial or []}


class Workspace(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="convocatorias-progreso-test-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / ".morfeo").mkdir()
        (self.root / ".morfeo" / "config.json").write_text(json.dumps({"title": "Demo"}), encoding="utf-8")
        self.file = self.root / "convocatorias" / "progreso.json"

    def read(self) -> dict:
        return json.loads(self.file.read_text(encoding="utf-8"))

    def run_ok(self, *args: str) -> subprocess.CompletedProcess:
        result = cli("progreso", str(self.root), *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result


class TestProgressWriter(Workspace):
    def test_reset_writes_a_fresh_document_with_five_pending_phases(self):
        result = self.run_ok("--reiniciar", "--alcance", "banco", "--ahora", at(0))
        self.assertEqual(result.stdout.strip(), str(self.file.resolve()))
        data = self.read()
        self.assertEqual(data["schema"], "morfeo.convocatorias-progreso/v1")
        self.assertEqual(data["alcance"], "banco")
        self.assertEqual(data["started_at"], at(0))
        self.assertEqual(data["updated_at"], at(0))
        self.assertIsNone(data["finished_at"])
        self.assertEqual([p["n"] for p in data["phases"]], [1, 2, 3, 4, 5])
        self.assertEqual([p["nombre"] for p in data["phases"]], NAMES)
        self.assertTrue(all(p["started_at"] is None and p["ended_at"] is None for p in data["phases"]))
        self.assertEqual(data["historial"], [])
        self.assertEqual(sorted(p.name for p in self.file.parent.iterdir()), ["progreso.json"], "no temp file left")

    def test_phase_start_and_end_are_stamped_with_their_detail(self):
        self.run_ok("--reiniciar", "--ahora", at(0))
        self.run_ok("--fase", "1", "--estado", "inicio", "--detalle", "perfil del proyecto", "--ahora", at(5))
        self.run_ok("--fase", "1", "--estado", "fin", "--ahora", at(70))
        phase = self.read()["phases"][0]
        self.assertEqual((phase["started_at"], phase["ended_at"], phase["detalle"]), (at(5), at(70), "perfil del proyecto"))
        self.assertEqual(self.read()["updated_at"], at(70))

    def test_starting_a_phase_closes_an_earlier_phase_left_running(self):
        self.run_ok("--reiniciar", "--ahora", at(0))
        self.run_ok("--fase", "1", "--estado", "inicio", "--ahora", at(0))
        self.run_ok("--fase", "2", "--estado", "inicio", "--ahora", at(90))
        phases = self.read()["phases"]
        self.assertEqual(phases[0]["ended_at"], at(90))
        self.assertEqual((phases[1]["started_at"], phases[1]["ended_at"]), (at(90), None))

    def test_without_a_reset_the_first_phase_creates_the_document(self):
        self.run_ok("--fase", "1", "--estado", "inicio", "--ahora", at(3))
        data = self.read()
        self.assertEqual((data["started_at"], data["alcance"]), (at(3), "proyecto"))
        self.assertEqual(data["phases"][0]["started_at"], at(3))

    def test_closing_the_last_phase_finishes_and_records_the_durations(self):
        self.run_ok("--reiniciar", "--ahora", at(0))
        offsets = [(0, 50), (50, 250), (250, 600), (600, 700), (700, 720)]
        for n, (start, end) in enumerate(offsets, start=1):
            self.run_ok("--fase", str(n), "--estado", "inicio", "--ahora", at(start))
            self.run_ok("--fase", str(n), "--estado", "fin", "--ahora", at(end))
        data = self.read()
        self.assertEqual(data["finished_at"], at(720))
        self.assertEqual(len(data["historial"]), 1)
        entry = data["historial"][0]
        self.assertEqual(entry["finished_at"], at(720))
        self.assertEqual(entry["alcance"], "proyecto")
        self.assertEqual(entry["duraciones"], {"1": 50, "2": 200, "3": 350, "4": 100, "5": 20})

    def test_a_reset_keeps_the_history_and_caps_it(self):
        history = [{"finished_at": at(i), "alcance": "proyecto", "duraciones": {"1": i}} for i in range(25)]
        self.file.parent.mkdir(parents=True)
        self.file.write_text(json.dumps(progress(historial=history)), encoding="utf-8")
        self.run_ok("--reiniciar", "--ahora", at(1000))
        data = self.read()
        self.assertEqual(data["started_at"], at(1000))
        self.assertEqual(len(data["historial"]), 20)
        self.assertEqual(data["historial"][-1]["duraciones"], {"1": 24}, "the newest entries stay")

    def test_bad_input_exits_with_code_2_and_writes_nothing(self):
        cases = [
            ("progreso", str(self.root)),  # neither --reiniciar nor a phase
            ("progreso", str(self.root), "--fase", "1"),  # phase without --estado
            ("progreso", str(self.root), "--fase", "6", "--estado", "inicio"),
            ("progreso", str(self.root), "--fase", "1", "--estado", "pausa"),
            ("progreso", str(self.root), "--reiniciar", "--alcance", "todo"),
            ("progreso", str(self.root), "--reiniciar", "--ahora", "ayer"),
            ("progreso", str(self.root.parent / "no-existe"), "--reiniciar"),
        ]
        for args in cases:
            result = cli(*args)
            self.assertEqual(result.returncode, 2, args)
        self.assertFalse(self.file.exists())

    def test_check_and_datos_ignore_the_progress_file(self):
        before_check = cli("check", str(self.root))
        before_datos = cli("datos", str(self.root), "--json", "--hoy", "2026-11-22")
        self.run_ok("--reiniciar", "--ahora", at(0))
        self.run_ok("--fase", "1", "--estado", "inicio", "--ahora", at(1))
        after_check = cli("check", str(self.root))
        after_datos = cli("datos", str(self.root), "--json", "--hoy", "2026-11-22")
        self.assertEqual((after_check.returncode, after_check.stdout), (before_check.returncode, before_check.stdout))
        self.assertEqual((after_datos.returncode, after_datos.stdout), (before_datos.returncode, before_datos.stdout))


class TestEstimator(unittest.TestCase):
    TOTAL = sum(PHASE_PRIORS.values())

    def estimate(self, data, now: float, calls_mtime: float | None = None) -> dict:
        mtime = None if calls_mtime is None else (T0 + datetime.timedelta(seconds=calls_mtime)).timestamp()
        return estimate_progress(data, T0 + datetime.timedelta(seconds=now), mtime)

    def test_default_priors_are_documented(self):
        self.assertEqual(PHASE_PRIORS, {1: 60, 2: 240, 3: 300, 4: 120, 5: 30})
        self.assertEqual(STALE_SECONDS, 20 * 60)

    def test_before_any_phase_starts_the_estimate_is_zero_and_the_full_prior(self):
        est = self.estimate(progress(), now=10)
        self.assertEqual(est["estado"], "en_curso")
        self.assertEqual((est["fase"], est["fases_total"], est["phase_label"]), (1, 5, "Fase 1/5 · Perfil"))
        self.assertEqual(est["percent"], 0)
        self.assertEqual(est["remaining_seconds"], self.TOTAL)
        self.assertFalse(est["stale"])

    def test_percent_is_weighted_by_priors_and_remaining_follows_the_running_phase(self):
        # Phases 1 and 2 took exactly their priors; phase 3 runs for half its prior.
        data = progress({1: (0, 60), 2: (60, 300), 3: (300, None)})
        est = self.estimate(data, now=450)
        self.assertEqual(est["phase_label"], "Fase 3/5 · Búsqueda abierta")
        self.assertEqual(est["percent"], int(100 * (60 + 240 + 150) / self.TOTAL))  # 60
        self.assertEqual(est["remaining_seconds"], 150 + 120 + 30)

    def test_the_measured_pace_scales_what_is_left(self):
        # Phases 1 and 2 took twice their priors: what is left doubles.
        data = progress({1: (0, 120), 2: (120, 600)})
        est = self.estimate(data, now=600)
        self.assertEqual(est["fase"], 3, "between phases the next one is shown")
        self.assertEqual(est["percent"], int(100 * 300 / self.TOTAL))
        self.assertEqual(est["remaining_seconds"], 2 * (300 + 120 + 30))

    def test_an_overrunning_phase_keeps_a_floor_and_the_percent_stays_below_its_end(self):
        data = progress({1: (0, 60), 2: (60, 300), 3: (300, None)})
        est = self.estimate(data, now=300 + 3 * 300)
        self.assertEqual(est["remaining_seconds"], round(0.15 * 300) + 120 + 30)
        self.assertEqual(est["percent"], int(100 * (60 + 240 + 0.95 * 300) / self.TOTAL))

    def test_the_percent_is_capped_at_99_until_the_search_finishes(self):
        data = progress({1: (0, 60), 2: (60, 300), 3: (300, 600), 4: (600, 720), 5: (720, None)})
        est = self.estimate(data, now=10_000, calls_mtime=None)
        self.assertLessEqual(est["percent"], 99)
        self.assertNotEqual(est["estado"], "terminada")

    def test_finished_at_means_100_percent_and_nothing_left(self):
        data = progress({n: (i * 10, i * 10 + 10) for i, n in enumerate(range(1, 6))}, finished=50)
        est = self.estimate(data, now=60)
        self.assertEqual((est["estado"], est["percent"], est["remaining_seconds"]), ("terminada", 100, 0))
        self.assertFalse(est["stale"])

    def test_a_fresh_calls_file_after_the_register_phase_means_100_percent(self):
        data = progress({1: (0, 60), 2: (60, 300), 3: (300, 600), 4: (600, 720), 5: (720, None)})
        self.assertEqual(self.estimate(data, now=730, calls_mtime=700)["percent"], 100)
        # A calls file older than the search start belongs to an earlier search.
        self.assertLess(self.estimate(data, now=730, calls_mtime=-5)["percent"], 100)
        # Written while the register phase still runs: not finished yet.
        running = progress({1: (0, 60), 2: (60, 300), 3: (300, 600), 4: (600, None)})
        self.assertLess(self.estimate(running, now=650, calls_mtime=640)["percent"], 100)

    def test_no_update_for_twenty_minutes_is_stale(self):
        data = progress({1: (0, 60), 2: (60, None)})
        self.assertFalse(self.estimate(data, now=60 + STALE_SECONDS - 1)["stale"])
        est = self.estimate(data, now=60 + STALE_SECONDS + 1)
        self.assertTrue(est["stale"])
        self.assertEqual(est["estado"], "detenida")

    def test_two_earlier_runs_replace_a_prior_with_their_median(self):
        one = [{"finished_at": at(0), "alcance": "proyecto", "duraciones": {"1": 30}}]
        est = self.estimate(progress(historial=one), now=1)
        self.assertEqual(est["priors"]["1"], 60, "one run is not enough")
        three = one + [{"finished_at": at(1), "alcance": "proyecto", "duraciones": {"1": 90, "2": 100}},
                       {"finished_at": at(2), "alcance": "proyecto", "duraciones": {"1": 40}}]
        est = self.estimate(progress(historial=three), now=1)
        self.assertEqual(est["priors"]["1"], 40)
        self.assertEqual(est["priors"]["2"], 240, "phase 2 has a single recorded run")
        self.assertEqual(est["remaining_seconds"], 40 + 240 + 300 + 120 + 30)


class TestLoadProgress(Workspace):
    def test_absent_file_is_no_progress_and_no_error(self):
        self.assertEqual(load_progress(self.root), {"progreso": None, "error": None})

    def test_unreadable_or_foreign_files_degrade_to_an_error(self):
        self.file.parent.mkdir(parents=True)
        for text in ("{no", json.dumps({"schema": "otro/v1"}), json.dumps([1, 2])):
            self.file.write_text(text, encoding="utf-8")
            data = load_progress(self.root, now=T0)
            self.assertIsNone(data["progreso"], text)
            self.assertIn("progreso.json", data["error"])

    def test_reads_the_calls_file_time_to_detect_the_end(self):
        self.file.parent.mkdir(parents=True)
        doc = progress({1: (0, 60), 2: (60, 300), 3: (300, 600), 4: (600, 720), 5: (720, None)})
        self.file.write_text(json.dumps(doc), encoding="utf-8")
        calls = self.root / "convocatorias" / "oportunidades.json"
        calls.write_text("{}", encoding="utf-8")
        stamp = (T0 + datetime.timedelta(seconds=710)).timestamp()
        os.utime(calls, (stamp, stamp))
        data = load_progress(self.root, now=T0 + datetime.timedelta(seconds=730))
        self.assertIsNone(data["error"])
        self.assertEqual((data["progreso"]["estado"], data["progreso"]["percent"]), ("terminada", 100))


class TestProgressHttpApi(Workspace):
    def _serve(self):
        from morfeo.dashboard.server import MorfeoDashboardHandler

        handler = type("H", (MorfeoDashboardHandler,), {"workspace_dir": self.root})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _get(self, url: str):
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())

    def test_get_progress_without_a_file_answers_no_progress(self):
        code, data = self._get(self._serve() + "/api/convocatorias/progreso")
        self.assertEqual(code, 200)
        self.assertEqual(data, {"ok": True, "progreso": None, "error": None})
        self.assertFalse((self.root / "convocatorias").exists(), "the endpoint never writes")

    def test_get_progress_returns_the_estimate_of_the_running_search(self):
        now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        doc = progress()
        doc["started_at"] = doc["updated_at"] = (now - datetime.timedelta(seconds=30)).isoformat()
        doc["phases"][0]["started_at"] = doc["started_at"]
        self.file.parent.mkdir(parents=True)
        self.file.write_text(json.dumps(doc), encoding="utf-8")
        code, data = self._get(self._serve() + "/api/convocatorias/progreso")
        self.assertEqual(code, 200)
        self.assertTrue(data["ok"])
        est = data["progreso"]
        self.assertEqual((est["estado"], est["fase"], est["phase_label"]), ("en_curso", 1, "Fase 1/5 · Perfil"))
        self.assertTrue(0 <= est["percent"] < 100)
        self.assertGreater(est["remaining_seconds"], 0)
        self.assertFalse(est["stale"])

    def test_the_progress_script_is_served_without_cache(self):
        with urllib.request.urlopen(self._serve() + "/static/convocatorias-progress.js") as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers["Cache-Control"], "no-cache")
            self.assertIn("javascript", resp.headers["Content-Type"])


if __name__ == "__main__":
    unittest.main()
