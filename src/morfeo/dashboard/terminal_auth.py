"""Access control of the dashboard: Host allow-list, same-origin guard and the
embedded terminal's login.

The dashboard is a stdlib `ThreadingHTTPServer` on a loopback address. Without
a guard, any page the browser opens could drive it: browsers apply no CORS to
WebSockets, so a cross-site page could open `/ws/terminal` and get a shell, and
a form could POST to any route. A DNS-rebinding page could even read answers.
This module holds the three checks `terminal_routes.dispatch` applies before
routing any request:

* the Host allow-list: only `127.0.0.1:PORT`, `localhost:PORT` and
  `[::1]:PORT` (plus hosts the server is told about) reach a route; any other
  name gets 421, which stops DNS rebinding;
* the same-origin guard: a state-changing request (POST, DELETE) whose
  `Origin` (or, failing that, `Referer`) names another origin, or `null`, is
  refused. The server's own origins are built from the socket it listens on,
  never from a request header. A request with neither header passes on
  ordinary routes (browsers always send `Origin` on a cross-origin POST, and a
  local process can forge any header anyway); the terminal's own routes and
  its WebSocket upgrade require `Origin`;
* the terminal login: a per-server login secret, opened only in the desktop
  browser, is exchanged once for a session cookie (HttpOnly, SameSite=Strict,
  Path=/ so it reaches both `/api/terminal/` and `/ws/terminal`). The terminal
  routes and the WebSocket upgrade require that cookie.

Secrets live only in memory and die with the server; every comparison is
constant-time.
"""

from __future__ import annotations

import hmac
import ipaddress
import secrets
import threading
import time
from collections import OrderedDict
from http.cookies import CookieError, SimpleCookie
from typing import Any, Iterable
from urllib.parse import quote, urlsplit

#: Seconds between two activations (each one opens a browser tab).
ACTIVATION_THROTTLE_S = 10.0
#: Session tokens kept per server; the oldest is forgotten first.
MAX_SESSION_TOKENS = 32
#: Methods that change state and so must come from the dashboard's own page.
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
#: `Sec-Fetch-Site` values a same-origin request may carry ("none" is a
#: navigation the user typed or opened from outside any page).
_SAFE_FETCH_SITES = frozenset({"same-origin", "none"})

_ATTACH_LOCK = threading.Lock()
_ATTR = "_morfeo_terminal_auth"


def _same_secret(presented: Any, expected: str) -> bool:
    if not isinstance(presented, str) or not presented or not expected:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def _server_host_port(server: Any) -> tuple[str, int]:
    address = getattr(server, "server_address", None) or ("", 0)
    host, port = str(address[0]), int(address[1])
    return host, port


def bound_origin(server: Any) -> str | None:
    """`http://host:port` of the socket the server listens on, or None unless loopback."""
    try:
        host, port = _server_host_port(server)
        ip = ipaddress.ip_address(host)
    except (TypeError, ValueError, IndexError):
        return None
    if not ip.is_loopback or not 0 < port < 65536:
        return None
    name = f"[{ip.compressed}]" if ip.version == 6 else ip.compressed
    return f"http://{name}:{port}"


class TerminalAuth:
    """The access state of one dashboard server (secrets, allow-lists, throttle)."""

    def __init__(self, server: Any, extra_hosts: Iterable[str] = ()) -> None:
        host, port = _server_host_port(server)
        self.port = port
        self.origin = bound_origin(server)
        #: Presented once, in the login URL opened in the desktop browser.
        self.login_secret = secrets.token_urlsafe(32)
        #: One cookie name per port: cookies ignore the port, so two dashboards
        #: on the same host must not overwrite each other's session.
        self.cookie_name = f"morfeo_terminal_{port}"
        self._sessions: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.Lock()
        self._last_activation = 0.0
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
        hosts.update(h.strip().lower() for h in extra_hosts if h and h.strip())
        self.allowed_hosts = frozenset(hosts)
        # Only names that reach this very socket count as its origin: a page on
        # [::1]:PORT is someone else's server when this one listens on IPv4.
        origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
        if self.origin:
            origins.add(self.origin)
        self.allowed_origins = frozenset(origins)

    # -- login and sessions ------------------------------------------------
    def accepts_login(self, presented: Any) -> bool:
        return _same_secret(presented, self.login_secret)

    def issue_session(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[token] = None
            while len(self._sessions) > MAX_SESSION_TOKENS:
                self._sessions.popitem(last=False)
        return token

    def authorized(self, presented: Any) -> bool:
        with self._lock:
            tokens = list(self._sessions)
        found = False
        for token in tokens:  # every token is compared: no early exit
            found = _same_secret(presented, token) or found
        return found

    def set_cookie_value(self, token: str) -> str:
        """The `Set-Cookie` value that hands `token` to the browser."""
        return f"{self.cookie_name}={token}; Path=/; HttpOnly; SameSite=Strict"

    def login_url(self, base: str | None = None) -> str:
        """The URL that logs a browser in; `base` defaults to the bound origin."""
        root = (base or self.origin or f"http://127.0.0.1:{self.port}").rstrip("/")
        return f"{root}/api/terminal/login?token={quote(self.login_secret, safe='')}"

    def claim_activation(self, now: float | None = None) -> bool:
        """True when an activation may run now (at most one per throttle window)."""
        moment = time.monotonic() if now is None else now
        with self._lock:
            if self._last_activation and moment - self._last_activation < ACTIVATION_THROTTLE_S:
                return False
            self._last_activation = moment
            return True


def auth_for(server: Any) -> TerminalAuth:
    """The server's `TerminalAuth`, created on first use and kept on the server."""
    auth = getattr(server, _ATTR, None)
    if auth is not None:
        return auth
    with _ATTACH_LOCK:
        auth = getattr(server, _ATTR, None)
        if auth is None:
            auth = TerminalAuth(server, getattr(server, "morfeo_allowed_hosts", ()) or ())
            setattr(server, _ATTR, auth)
    return auth


def login_url(base: str | None, server: Any) -> str:
    """The login URL of `server` (for `morfeo ui`, which opens or prints it)."""
    return auth_for(server).login_url(base)


# -- request checks -----------------------------------------------------------
def host_allowed(handler: Any) -> bool:
    """Whether the request's Host header names this server (stops DNS rebinding)."""
    host = (handler.headers.get("Host") or "").strip().lower()
    return bool(host) and host in auth_for(handler.server).allowed_hosts


def _origin_of(url: str) -> str | None:
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


def origin_refusal(handler: Any, *, allow_referer: bool = True,
                   require_origin: bool = True) -> str | None:
    """The reason to refuse a request that must be same-origin, or None.

    A present `Origin` must be one of the server's own origins (`null` never
    is); when `Origin` is absent and `allow_referer`, a present `Referer`'s
    origin stands in. A request with neither is refused only with
    `require_origin`. A request a browser marks as cross-site with
    `Sec-Fetch-Site` is always refused.
    """
    headers = handler.headers
    site = (headers.get("Sec-Fetch-Site") or "").strip().lower()
    if site and site not in _SAFE_FETCH_SITES:
        return "solicitud de otro sitio"
    allowed = auth_for(handler.server).allowed_origins
    origin = headers.get("Origin")
    if origin is not None:
        return None if origin.strip().lower() in allowed else "origen ajeno"
    referer = headers.get("Referer") if allow_referer else None
    if referer:
        return None if _origin_of(referer) in allowed else "origen ajeno"
    return "falta la cabecera Origin" if require_origin else None


def same_origin(handler: Any) -> bool:
    """Whether the request provably comes from the dashboard's own page (Origin required)."""
    return origin_refusal(handler) is None


def presented_cookie(handler: Any) -> str | None:
    """The value of this server's terminal cookie in the request, if any."""
    raw = "; ".join(handler.headers.get_all("Cookie") or [])
    if not raw:
        return None
    jar = SimpleCookie()
    try:
        jar.load(raw)
    except CookieError:
        return None
    morsel = jar.get(auth_for(handler.server).cookie_name)
    return morsel.value if morsel is not None else None


def has_session(handler: Any) -> bool:
    """Whether the request carries a valid terminal session cookie."""
    return auth_for(handler.server).authorized(presented_cookie(handler))


__all__ = [
    "ACTIVATION_THROTTLE_S",
    "MUTATING_METHODS",
    "TerminalAuth",
    "auth_for",
    "bound_origin",
    "has_session",
    "host_allowed",
    "login_url",
    "origin_refusal",
    "presented_cookie",
    "same_origin",
]
