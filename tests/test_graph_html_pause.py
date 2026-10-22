"""The graph page stops its loop while nobody sees it and drops to 2D when slow.

Ported from papersmith-ai (atlas viewer, commits fc19c4b1 and cc01c345): the
render loop stops scheduling frames entirely while the page is hidden
(``visibilitychange``) or the dashboard paused the graph tab with
``{"type": "atlas-control", "cmd": "pause"}``, and resumes on show or on
``resume``. A 3D view the heuristics chose on their own is watched for its first
seconds and falls back to the 2D constellation under 20 fps; an explicit
``?view=3d`` or a saved user choice is never overridden.

The loop-control block is plain JS with no WebGL, so it runs under node with
stubbed globals; the wiring into ``animate()`` and the page start is pinned
structurally, since WebGL does not run headless here.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import graph_html  # noqa: E402

TEMPLATE = graph_html.TEMPLATE
NODE = shutil.which("node")


def loop_control_source() -> str:
    match = re.search(r"// loop-control:begin\n(.*?)// loop-control:end", TEMPLATE, re.S)
    assert match, "loop-control block not found"
    return match.group(1)


def animate_body() -> str:
    match = re.search(r"function animate\(\) \{(.*?)\n  \}\n", TEMPLATE, re.S)
    assert match, "animate() not found"
    return match.group(1)


HARNESS = """
var PARENT = { name: "dashboard" };
var window = { parent: PARENT };
var document = { hidden: false };
var rafQueue = [], timeouts = [], frames = 0, modes = [], rotateToggles = 0;
function requestAnimationFrame(f) { rafQueue.push(f); return rafQueue.length; }
function setTimeout(f) { timeouts.push(f); return timeouts.length; }
function requestFrame() { frames += 1; }
function animate() { if (!loopContinues()) return; requestAnimationFrame(animate); }
var viewMode = "3d", viewChoice = { mode: "3d", reason: "gpu" }, renderer = { id: 1 };
var autoRotate = true;
function toggleAutoRotate() { autoRotate = !autoRotate; rotateToggles += 1; }
function setViewMode(m) { modes.push(m); viewMode = m; renderer = { id: renderer.id + 1 }; }
function drain() { var q = rafQueue; rafQueue = []; q.forEach(function(f) { f(); }); }
function msg(data, source) { onControlMessage({ data: data, source: source === undefined ? PARENT : source }); }
%s
%s
process.stdout.write(JSON.stringify({ paused: paused, looping: looping, raf: rafQueue.length,
  frames: frames, modes: modes, reason: viewChoice.reason, rotate: autoRotate, out: OUT }));
"""


def run(scenario: str) -> dict:
    script = HARNESS % (loop_control_source(), "var OUT = null;\n" + scenario)
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@unittest.skipUnless(NODE, "node is not installed")
class DashboardPauseTest(unittest.TestCase):
    def test_pause_stops_scheduling_frames(self) -> None:
        got = run("animate(); msg({type: 'atlas-control', cmd: 'pause'}); drain();")
        self.assertTrue(got["paused"])
        self.assertFalse(got["looping"], "the loop lapses instead of spinning idle")
        self.assertEqual(got["raf"], 0, "no requestAnimationFrame while paused")

    def test_resume_restarts_one_loop_and_redraws(self) -> None:
        got = run(
            "animate(); msg({type: 'atlas-control', cmd: 'pause'}); drain();"
            "var before = frames;"
            "msg({type: 'atlas-control', cmd: 'resume'}); msg({type: 'atlas-control', cmd: 'resume'});"
            "OUT = frames - before;"
        )
        self.assertFalse(got["paused"])
        self.assertTrue(got["looping"])
        self.assertEqual(got["raf"], 1, "a second resume must not start a second loop")
        self.assertGreaterEqual(got["out"], 1, "resuming redraws the view")

    def test_foreign_or_malformed_messages_are_ignored(self) -> None:
        got = run(
            "animate();"
            "msg({type: 'atlas-control', cmd: 'pause'}, {name: 'other'});"
            "msg({type: 'atlas-command', command: 'pause'});"
            "msg({type: 'atlas-control', cmd: 'explode'});"
            "msg('pause');"
        )
        self.assertFalse(got["paused"])

    def test_a_hidden_page_pauses_and_showing_it_redraws_once(self) -> None:
        got = run(
            "animate(); document.hidden = true; onVisibilityChange(); drain();"
            "OUT = {pausedWhileHidden: paused, rafWhileHidden: rafQueue.length};"
            "var before = frames; document.hidden = false; onVisibilityChange();"
            "OUT.redraws = frames - before;"
        )
        self.assertTrue(got["out"]["pausedWhileHidden"])
        self.assertEqual(got["out"]["rafWhileHidden"], 0)
        self.assertFalse(got["paused"])
        self.assertEqual(got["raf"], 1)
        self.assertEqual(got["out"]["redraws"], 1)

    def test_dashboard_pause_survives_the_page_being_shown(self) -> None:
        got = run(
            "animate(); msg({type: 'atlas-control', cmd: 'pause'});"
            "document.hidden = true; onVisibilityChange(); document.hidden = false; onVisibilityChange();"
        )
        self.assertTrue(got["paused"], "the graph tab is still hidden in the dashboard")


def drive(fps: float, until_ms: float = 3200) -> str:
    """Run the watchdog's rAF chain at a steady frame rate."""
    step = 1000.0 / fps
    return (
        "OUT = watchFrameRate(); timeouts.forEach(function(f) { f(); });"
        "for (var t = 1000; t <= %f && rafQueue.length; t += %f) {"
        "  var q = rafQueue; rafQueue = []; q.forEach(function(f) { f(t); });"
        "}" % (1000 + until_ms, step)
    )


@unittest.skipUnless(NODE, "node is not installed")
class FrameRateWatchdogTest(unittest.TestCase):
    def test_a_slow_3d_view_falls_back_to_2d(self) -> None:
        got = run(drive(10))
        self.assertTrue(got["out"], "an automatic 3D choice is watched")
        self.assertEqual(got["modes"], ["2d"])
        self.assertEqual(got["reason"], "slow")
        self.assertFalse(got["rotate"], "the 2D view starts still")

    def test_a_fluid_3d_view_stays(self) -> None:
        got = run(drive(60))
        self.assertEqual(got["modes"], [])
        self.assertEqual(got["reason"], "gpu")
        self.assertEqual(got["raf"], 0, "the watchdog stops after its window")

    def test_an_explicit_3d_choice_is_never_overridden(self) -> None:
        for reason in ("url", "user"):
            with self.subTest(reason=reason):
                got = run("viewChoice = {mode: '3d', reason: '%s'};" % reason + drive(5))
                self.assertFalse(got["out"])
                self.assertEqual(got["modes"], [])

    def test_a_2d_view_is_not_watched(self) -> None:
        got = run("viewMode = '2d'; viewChoice = {mode: '2d', reason: 'weak'};" + drive(5))
        self.assertFalse(got["out"])
        self.assertEqual(got["modes"], [])

    def test_pausing_during_the_window_cancels_the_verdict(self) -> None:
        got = run(
            "OUT = watchFrameRate(); timeouts.forEach(function(f) { f(); });"
            "var q = rafQueue; rafQueue = []; q.forEach(function(f) { f(1000); });"
            "msg({type: 'atlas-control', cmd: 'pause'});"
            "for (var t = 1100; t <= 4500 && rafQueue.length; t += 200) {"
            "  var r = rafQueue; rafQueue = []; r.forEach(function(f) { f(t); });"
            "}"
        )
        self.assertEqual(got["modes"], [], "frames not drawn while paused say nothing about speed")


class LoopWiringTest(unittest.TestCase):
    def test_animate_checks_the_pause_before_scheduling(self) -> None:
        body = animate_body()
        gate = body.index("if (!loopContinues()) return;")
        self.assertLess(gate, body.index("requestAnimationFrame(animate)"))

    def test_listeners_and_watchdog_are_wired_at_start(self) -> None:
        self.assertIn('document.addEventListener("visibilitychange", onVisibilityChange)', TEMPLATE)
        self.assertIn('window.addEventListener("message", onControlMessage)', TEMPLATE)
        start = TEMPLATE.index("setViewMode(viewChoice.mode);")
        self.assertIn("watchFrameRate();", TEMPLATE[start:start + 1500])

    def test_the_slow_fallback_is_noted(self) -> None:
        self.assertRegex(TEMPLATE, r"slow: \"Vista 2D: [^\"]*20 fps")

    def test_pixel_ratio_is_clamped_between_one_and_two(self) -> None:
        ratios = re.findall(r"Math\.min\(Math\.max\(window\.devicePixelRatio \|\| 1, 1\), 2\)", TEMPLATE)
        self.assertGreaterEqual(len(ratios), 2, "WebGL and canvas renderers both clamp")
        self.assertNotRegex(TEMPLATE, r"setPixelRatio\(window\.devicePixelRatio\)")


if __name__ == "__main__":
    unittest.main()
