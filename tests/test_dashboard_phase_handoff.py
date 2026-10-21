"""The phase tracker follows a chained unit (fase0 -> g0_5 in /propuesta-analizar).

The tracker kept following the unit the dashboard launched (stored in
localStorage). When that command chained into the next unit, the new heartbeat
was ignored because a PHASE_RUN already existed, so once fase0 was verified the
bar disappeared while g0_5 was still running. These tests execute the real
phaseRunView/liveHeartbeat source under node with stubbed globals.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HTML = (REPO / "src" / "morfeo" / "dashboard" / "static" / "index.html").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _slice(start: str, end: str) -> str:
    i = HTML.index(start)
    return HTML[i : HTML.index(end, i)]


HARNESS = """
let PHASE_RUN = null, PHASE_RUN_DISMISSED = null, PHASES_INFO = [];
const PHASE_RUN_SIGNAL_TIMEOUT_MS = 90000, PHASE_RUN_IDLE_MS = 120000;
let SAVED = 0;
function savePhaseRun() { SAVED += 1; }
function stoppedPhaseRun() { return null; }
function resolvePhaseState(p, data) { return (data.unit_progress?.[p.id]?.state) || 'pending'; }
function terminalActivity() { return { sessionId: 's1', connected: true, lastOutputAt: Date.now() }; }
%s
%s
const input = JSON.parse(process.argv[1]);
PHASE_RUN = input.run;
PHASE_RUN_DISMISSED = input.dismissed || null;
const view = phaseRunView(input.data);
console.log(JSON.stringify({ unit: view && view.run.unit, running: view && view.running,
  phaseRun: PHASE_RUN, saved: SAVED }));
"""


@unittest.skipUnless(NODE, "node not installed")
class PhaseRunHandoff(unittest.TestCase):
    def view(self, run: dict | None, data: dict, dismissed: str | None = None) -> dict:
        script = HARNESS % (
            _slice("function liveHeartbeat(", "// Qué falta para que una unidad pase"),
            _slice("function phaseRunView(", "function phaseRunRenderKey("),
        )
        payload = json.dumps({"run": run, "data": data, "dismissed": dismissed})
        out = subprocess.run([NODE, "-e", script, payload], capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def units(self) -> list[dict]:
        return [{"id": "fase0", "name": "Intake"}, {"id": "g0_5", "name": "Guía ajustada al TDR"}]

    def test_chained_unit_takes_over_a_finished_run(self) -> None:
        sent = 1_800_000_000_000
        run = {"unit": "fase0", "command": "/propuesta-analizar", "sentAt": sent, "initialState": "pending",
               "seenRunning": True, "finished": True, "finishedAt": sent + 50_000, "sessionId": "s1", "agent": "claude"}
        data = {
            "pipeline_units": self.units(),
            "unit_progress": {"fase0": {"state": "verified"}, "g0_5": {"state": "running"}},
            "en_curso": {"fase": "g0_5", "inicio": "2027-01-15T08:01:40Z", "stale": False},
        }
        got = self.view(run, data)
        self.assertEqual(got["unit"], "g0_5")
        self.assertTrue(got["running"])
        # The persisted run hands over, keeping the terminal session for «Detener».
        self.assertEqual(got["phaseRun"]["unit"], "g0_5")
        self.assertEqual(got["phaseRun"]["sessionId"], "s1")
        self.assertEqual(got["phaseRun"]["chainedFrom"], "fase0")
        self.assertGreater(got["saved"], 0)

    def test_older_heartbeat_does_not_steal_a_just_launched_run(self) -> None:
        sent = 1_800_000_000_000  # 2027-01-15T08:00:00Z
        run = {"unit": "fase1a", "command": "/propuesta-continuar", "sentAt": sent, "initialState": "pending",
               "seenRunning": False, "sessionId": "s1"}
        data = {
            "pipeline_units": self.units() + [{"id": "fase1a", "name": "Scoping"}],
            "unit_progress": {},
            "en_curso": {"fase": "g0_5", "inicio": "2027-01-15T07:50:00Z", "stale": False},
        }
        got = self.view(run, data)
        self.assertEqual(got["unit"], "fase1a")
        self.assertEqual(got["phaseRun"]["unit"], "fase1a")

    def test_same_unit_heartbeat_keeps_the_run(self) -> None:
        sent = 1_800_000_000_000
        run = {"unit": "g0_5", "command": "/propuesta-continuar", "sentAt": sent, "initialState": "pending",
               "seenRunning": False, "sessionId": "s1"}
        data = {"pipeline_units": self.units(), "unit_progress": {},
                "en_curso": {"fase": "g0_5", "inicio": "2027-01-15T08:00:05Z", "stale": False}}
        got = self.view(run, data)
        self.assertEqual(got["unit"], "g0_5")
        self.assertTrue(got["running"])
        self.assertNotIn("chainedFrom", got["phaseRun"])

    def test_external_heartbeat_without_run_still_shows(self) -> None:
        data = {"pipeline_units": self.units(), "unit_progress": {},
                "en_curso": {"fase": "g0_5", "inicio": "2027-01-15T08:00:05Z", "stale": False}}
        got = self.view(None, data)
        self.assertEqual(got["unit"], "g0_5")
        self.assertIsNone(got["phaseRun"])

    def test_dismissed_heartbeat_stays_hidden(self) -> None:
        data = {"pipeline_units": self.units(), "unit_progress": {},
                "en_curso": {"fase": "g0_5", "inicio": "2027-01-15T08:00:05Z", "stale": False}}
        got = self.view(None, data, dismissed="g0_5@2027-01-15T08:00:05Z")
        self.assertIsNone(got["unit"])


if __name__ == "__main__":
    unittest.main()
