"""Tests for the external terminal launch of the Morfeo dashboard.

Every test patches `shutil.which`, `subprocess.Popen`, `subprocess.run` and
`sys.platform`, so no real terminal emulator or herdr process is ever started.
"""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from src.morfeo.dashboard import terminal

HERDR = "/usr/bin/herdr"
WORKSPACE = Path("/tmp/morfeo workspace")
CWD = str(WORKSPACE.resolve())


def _completed(argv, returncode=1, stdout=""):
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr="")


class _Env:
    """Patch the probing and launching primitives of terminal.py."""

    def __init__(self, platform, on_path, herdr_client_running=False):
        self.platform = platform
        self.on_path = set(on_path)
        self.herdr_client_running = herdr_client_running
        self.which_calls = []
        self.run_calls = []
        self.popen = mock.MagicMock(name="Popen")
        self._patches = []

    def _which(self, name, *args, **kwargs):
        self.which_calls.append(name)
        return f"/usr/bin/{name}" if name in self.on_path else None

    def _run(self, argv, *args, **kwargs):
        self.run_calls.append((list(argv), kwargs))
        if argv[:2] == ["pgrep", "-x"]:
            return _completed(argv, 0 if self.herdr_client_running else 1,
                              "123\n" if self.herdr_client_running else "")
        return _completed(argv)

    def __enter__(self):
        self._patches = [
            mock.patch.object(terminal.sys, "platform", self.platform),
            mock.patch.object(terminal.shutil, "which", side_effect=self._which),
            mock.patch.object(terminal, "CLI_SEARCH_DIRS", []),
            mock.patch.object(terminal.subprocess, "run", side_effect=self._run),
            mock.patch.object(terminal.subprocess, "Popen", self.popen),
            mock.patch.object(terminal, "_app_installed", return_value=False),
        ]
        for patch in self._patches:
            patch.start()
        return self

    def __exit__(self, *exc):
        for patch in reversed(self._patches):
            patch.stop()
        return False

    def launched_argv(self):
        """The argv given to Popen (Linux launch), asserting a single launch."""
        self.popen.assert_called_once()
        args, kwargs = self.popen.call_args
        return list(args[0]), kwargs

    def open_calls(self):
        return [argv for argv, _ in self.run_calls if argv and argv[0] == "open"]


class TestLinuxTerminalLaunch(unittest.TestCase):
    def _launch(self, terminal_name, herdr_client_running=False):
        with _Env("linux", {"herdr", terminal_name}, herdr_client_running) as env:
            result = terminal.launch_external_terminal(WORKSPACE)
            argv, kwargs = env.launched_argv()
            return result, argv, kwargs, env

    def test_ghostty_argv(self):
        result, argv, kwargs, env = self._launch("ghostty")
        self.assertEqual(argv, ["ghostty", f"--working-directory={CWD}", "-e", HERDR])
        self.assertEqual(result["terminal"], "ghostty")

    def test_wezterm_argv(self):
        result, argv, _, _ = self._launch("wezterm")
        self.assertEqual(argv, ["wezterm", "start", "--cwd", CWD, HERDR])
        self.assertEqual(result["terminal"], "wezterm")

    def test_gnome_terminal_argv(self):
        result, argv, _, _ = self._launch("gnome-terminal")
        self.assertEqual(argv, ["gnome-terminal", f"--working-directory={CWD}", "--", HERDR])
        self.assertEqual(result["terminal"], "gnome-terminal")

    def test_konsole_argv(self):
        result, argv, _, _ = self._launch("konsole")
        self.assertEqual(argv, ["konsole", "--workdir", CWD, "-e", HERDR])
        self.assertEqual(result["terminal"], "konsole")

    def test_x_terminal_emulator_argv_quotes_the_workspace(self):
        result, argv, _, _ = self._launch("x-terminal-emulator")
        self.assertEqual(argv[:4], ["x-terminal-emulator", "-e", "/bin/sh", "-c"])
        # The workspace contains a space, so it must be shell-quoted.
        self.assertEqual(argv[4], f"cd '{CWD}' && exec {HERDR}")
        self.assertEqual(result["terminal"], "x-terminal-emulator")

    def test_launch_is_detached_list_argv_without_shell(self):
        for name in terminal.LINUX_TERMINALS:
            with self.subTest(terminal=name):
                result, argv, kwargs, env = self._launch(name)
                self.assertTrue(result["ok"])
                self.assertEqual(result["action"], "launched")
                self.assertEqual(result["cwd"], CWD)
                self.assertIsInstance(argv, list)
                self.assertTrue(kwargs.get("start_new_session"))
                self.assertFalse(kwargs.get("shell", False))
                self.assertEqual(kwargs.get("cwd"), CWD)
                # macOS open(1) is never used on Linux.
                self.assertEqual(env.open_calls(), [])

    def test_running_herdr_client_still_launches_a_window(self):
        # Linux has no portable way to focus an existing window, so a running
        # herdr process must not turn the launch into a no-op "activated".
        result, argv, _, env = self._launch("konsole", herdr_client_running=True)
        self.assertEqual(result["action"], "launched")
        self.assertEqual(argv[0], "konsole")
        self.assertEqual(env.open_calls(), [])

    def test_probe_order(self):
        self.assertEqual(terminal.LINUX_TERMINALS,
                         ("ghostty", "wezterm", "gnome-terminal", "konsole", "x-terminal-emulator"))
        cases = [
            ({"herdr", "x-terminal-emulator", "konsole"}, "konsole"),
            ({"herdr", "konsole", "gnome-terminal"}, "gnome-terminal"),
            ({"herdr", "gnome-terminal", "wezterm"}, "wezterm"),
            ({"herdr", "x-terminal-emulator", "wezterm", "ghostty"}, "ghostty"),
        ]
        for on_path, expected in cases:
            with self.subTest(on_path=sorted(on_path)), _Env("linux", on_path) as env:
                tools = terminal.detect_terminal_tools(WORKSPACE)
                self.assertEqual(tools["preferred_terminal"], expected)
                self.assertTrue(tools["ready"])
                result = terminal.launch_external_terminal(WORKSPACE)
                self.assertEqual(result["terminal"], expected)
                self.assertEqual(env.launched_argv()[0][0], expected)

    def test_no_terminal_on_linux_reports_generic_missing_and_does_not_launch(self):
        with _Env("linux", {"herdr"}) as env:
            tools = terminal.detect_terminal_tools(WORKSPACE)
            self.assertIsNone(tools["preferred_terminal"])
            self.assertFalse(tools["ready"])
            self.assertEqual(tools["missing"], ["terminal emulator"])
            result = terminal.launch_external_terminal(WORKSPACE)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error"], "missing_tools")
            self.assertEqual(result["missing"], ["terminal emulator"])
            env.popen.assert_not_called()
            self.assertEqual(env.open_calls(), [])

    def test_missing_herdr_and_terminal(self):
        with _Env("linux", set()) as env:
            tools = terminal.detect_terminal_tools(WORKSPACE)
            self.assertEqual(tools["missing"], ["herdr", "terminal emulator"])
            result = terminal.launch_external_terminal(WORKSPACE)
            self.assertFalse(result["ok"])
            env.popen.assert_not_called()


class TestMacTerminalLaunch(unittest.TestCase):
    def test_ghostty_uses_open_na_with_args(self):
        with _Env("darwin", {"herdr", "ghostty"}) as env:
            result = terminal.launch_external_terminal(WORKSPACE)
            self.assertTrue(result["ok"])
            self.assertEqual(result["terminal"], "ghostty")
            self.assertEqual(env.open_calls(), [
                ["open", "-na", "Ghostty", "--args", f"--working-directory={CWD}", "-e", HERDR],
            ])
            env.popen.assert_not_called()

    def test_wezterm_uses_open_na_with_args(self):
        with _Env("darwin", {"herdr", "wezterm"}) as env:
            result = terminal.launch_external_terminal(WORKSPACE)
            self.assertTrue(result["ok"])
            self.assertEqual(result["terminal"], "wezterm")
            self.assertEqual(env.open_calls(), [
                ["open", "-na", "WezTerm", "--args", "start", "--cwd", CWD, HERDR],
            ])
            env.popen.assert_not_called()

    def test_no_terminal_on_macos_keeps_terminal_label(self):
        with _Env("darwin", {"herdr", "konsole"}) as env:
            tools = terminal.detect_terminal_tools(WORKSPACE)
            self.assertIsNone(tools["preferred_terminal"])
            self.assertEqual(tools["missing"], ["terminal"])
            result = terminal.launch_external_terminal(WORKSPACE)
            self.assertFalse(result["ok"])
            env.popen.assert_not_called()
            self.assertEqual(env.open_calls(), [])


class TestTerminalToolsPayload(unittest.TestCase):
    def test_payload_keys_unchanged(self):
        with _Env("linux", {"herdr", "gnome-terminal"}):
            tools = terminal.detect_terminal_tools(WORKSPACE)
        self.assertEqual(set(tools), {"ready", "preferred_terminal", "missing", "active_pane",
                                      "herdr", "ghostty", "wezterm"})
        self.assertEqual(set(tools["herdr"]), {"installed", "path", "server_running",
                                               "client_running", "active_pane"})
        self.assertEqual(set(tools["ghostty"]), {"installed", "path"})
        self.assertEqual(set(tools["wezterm"]), {"installed", "path"})
        self.assertFalse(tools["ghostty"]["installed"])
        self.assertTrue(tools["herdr"]["installed"])


if __name__ == "__main__":
    unittest.main()
