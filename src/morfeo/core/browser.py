"""Open a URL in a browser that fits the platform (used by `morfeo ui`).

Ported from papersmith-ai's command center (`open_browser`, release 0.79.1):

- Under WSL the Windows browser is reached through `wslview` (wslu), then
  `explorer.exe`.
- On Linux without DISPLAY or WAYLAND_DISPLAY, Python's `webbrowser` would
  start a text browser (w3m, lynx) on the server's own terminal, so the URL is
  printed instead. A terminal multiplexer started outside the desktop session
  inherits neither variable, yet the session's display sockets are there: the
  compositor's `wayland-N` in XDG_RUNTIME_DIR or an X server's `X<N>` in
  /tmp/.X11-unix. A socket of this user found that way is named to `xdg-open`
  in the child's environment only.
- macOS, Windows and desktop Linux use `webbrowser`.

Stdlib only. `open_browser` never raises.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

#: Launchers that hand a URL to the Windows browser from WSL, in order.
WSL_BROWSER_LAUNCHERS = ("wslview", "explorer.exe")

#: Where an X server listens on its local socket, one `X<N>` per display.
X11_SOCKET_DIR = Path("/tmp/.X11-unix")
_WAYLAND_SOCKET = re.compile(r"wayland-(\d+)")
_X11_SOCKET = re.compile(r"X(\d+)")
#: Seconds to wait for `xdg-open` to report a failure; one still running after
#: that started a browser in the foreground.
XDG_OPEN_WAIT_S = 5.0


def _is_wsl() -> bool:
    """Identify WSL by its kernel release, not by inherited environment flags."""
    return sys.platform == "linux" and "microsoft" in platform.release().lower()


def _own_sockets(directory: str | Path, pattern: re.Pattern[str]) -> list[tuple[int, str]]:
    """`(N, name)` of each Unix socket in `directory` whose whole name matches
    `pattern` and that belongs to this user, lowest `N` first.

    A `wayland-0.lock` file, a plain file and another user's socket do not
    count: the CLI activation link must never reach another user's display.
    """
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return []
    found: list[tuple[int, str]] = []
    for entry in entries:
        match = pattern.fullmatch(entry.name)
        if match is None:
            continue
        try:
            info = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        if stat.S_ISSOCK(info.st_mode) and info.st_uid == os.getuid():
            found.append((int(match.group(1)), entry.name))
    return sorted(found)


def _socket_display() -> dict[str, str] | None:
    """The variable naming a graphical session this user can reach, found
    through its socket; `None` without one."""
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        wayland = _own_sockets(runtime, _WAYLAND_SOCKET)
        if wayland:
            return {"WAYLAND_DISPLAY": wayland[0][1]}
    x11 = _own_sockets(X11_SOCKET_DIR, _X11_SOCKET)
    if x11:
        return {"DISPLAY": f":{x11[0][0]}"}
    return None


def _named_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def has_graphical_display() -> bool:
    """Whether a display is named in the environment or found through its socket."""
    return _named_display() or _socket_display() is not None


def _print_url(url: str) -> None:
    print(f"Abre este enlace en un navegador: {url}", flush=True)


def _open_on_display(url: str, display: dict[str, str]) -> bool:
    """Hand `url` to `xdg-open` with `display` added to a copy of the
    environment (this process's own is left alone); print it on failure."""
    launcher = shutil.which("xdg-open")
    if launcher:
        try:
            # argv keeps the query string intact; the activation link never
            # travels through the child's output.
            child = subprocess.Popen([launcher, url], stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     close_fds=True, env={**os.environ, **display})
            try:
                if child.wait(timeout=XDG_OPEN_WAIT_S) == 0:
                    return True
            except subprocess.TimeoutExpired:
                return True
        except OSError:
            pass
    _print_url(url)
    return False


def open_browser(url: str) -> bool:
    """Open `url` in a browser that fits the platform; never raises.

    Returns whether a browser was launched; False means the URL was only
    printed on the terminal.
    """
    if _is_wsl():
        for launcher in WSL_BROWSER_LAUNCHERS:
            executable = shutil.which(launcher)
            if not executable:
                continue
            # argv avoids cmd.exe and shell interpolation of the query string;
            # the child's output is discarded so the link is not echoed.
            try:
                subprocess.Popen([executable, url], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 close_fds=True)
                return True
            except OSError:
                continue
    if sys.platform.startswith("linux") and not _named_display():
        display = _socket_display()
        if display is None:
            _print_url(url)
            return False
        return _open_on_display(url, display)
    import webbrowser

    try:
        if webbrowser.open(url):
            return True
    except Exception:  # noqa: BLE001 - a browser problem must not stop the server
        pass
    _print_url(url)
    return False


__all__ = ["open_browser", "has_graphical_display", "WSL_BROWSER_LAUNCHERS", "X11_SOCKET_DIR"]
