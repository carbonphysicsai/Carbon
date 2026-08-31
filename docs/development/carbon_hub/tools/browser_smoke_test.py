#!/usr/bin/env python3
"""Run dependency-free Chromium browser smoke tests for the generated hub.

The test launches an installed Chrome, Chromium, or Edge binary and speaks the
Chrome DevTools Protocol (CDP) directly using only Python's standard library.
It intentionally fails when no supported browser is present: a DOM parser is
not a truthful substitute for the JavaScript-on/off and console checks here.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
import platform
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from serve_hub import HUB_ROOT, create_server

EXPECTED_PRIMARY_TEXT: dict[str, tuple[str, ...]] = {
    "orientation": ("orientation", "start here"),
    "Wave B": ("wave b",),
    "B-03": ("b-03",),
    "change routes": (
        "change routes",
        "change route",
        "how a change enters",
        "place a change",
        "protocol-change routers",
        "protocol change routes",
    ),
    "maturity": ("maturity",),
    "glossary": ("glossary",),
    "sources": ("authority and sources", "where authority lives", "sources"),
}

INTERACTIVE_ROUTES: dict[str, tuple[str, ...]] = {
    "#/home": ("understand what is changing", "carbon development hub"),
    "#/start": ("new to carbon", "start here"),
    "#/wave/B": ("wave b",),
    "#/ticket/B-03": ("b-03",),
    "#/changes": ("place a change", "change routes", "change route"),
    "#/maturity": ("maturity",),
    "#/glossary": ("glossary",),
    "#/sources": ("where authority lives", "authority", "sources"),
}


class SmokeFailure(RuntimeError):
    """A browser smoke assertion or protocol operation failed."""


@dataclass(frozen=True)
class Viewport:
    name: str
    width: int
    height: int
    mobile: bool


VIEWPORTS = (
    Viewport("desktop", 1440, 1100, False),
    Viewport("mobile", 390, 844, True),
)


def _browser_candidates() -> Iterator[Path]:
    configured = os.environ.get("CARBON_HUB_BROWSER")
    if configured:
        yield Path(configured).expanduser()

    executable_names = (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
        "chrome.exe",
        "msedge",
        "msedge.exe",
    )
    for name in executable_names:
        located = shutil.which(name)
        if located:
            yield Path(located)

    system = platform.system()
    if system == "Windows":
        roots = [
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        suffixes = (
            Path("Google/Chrome/Application/chrome.exe"),
            Path("Microsoft/Edge/Application/msedge.exe"),
            Path("Chromium/Application/chrome.exe"),
        )
        for root in roots:
            if root:
                for suffix in suffixes:
                    yield Path(root) / suffix
    elif system == "Darwin":
        yield Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        yield Path("/Applications/Chromium.app/Contents/MacOS/Chromium")
        yield Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
    else:
        yield Path("/usr/bin/google-chrome")
        yield Path("/usr/bin/google-chrome-stable")
        yield Path("/usr/bin/chromium")
        yield Path("/usr/bin/chromium-browser")
        yield Path("/usr/bin/microsoft-edge")


def discover_browser(explicit: Path | None = None) -> Path:
    if explicit is not None:
        candidate = explicit.expanduser().resolve()
        if not candidate.is_file():
            raise SmokeFailure(f"Requested browser does not exist: {candidate}")
        return candidate

    seen: set[str] = set()
    for candidate in _browser_candidates():
        key = os.path.normcase(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            return candidate.resolve()
    raise SmokeFailure(
        "No Chrome, Chromium, or Edge executable was found. Install a Chromium-"
        "family browser, pass --browser PATH, or set CARBON_HUB_BROWSER. The test "
        "will not claim browser coverage from an HTML-parser fallback."
    )


class WebSocket:
    """Small RFC 6455 client sufficient for localhost CDP JSON messages."""

    def __init__(self, url: str, timeout: float) -> None:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "ws" or not parsed.hostname:
            raise SmokeFailure(f"Unsupported DevTools WebSocket URL: {url}")
        self.sock = socket.create_connection(
            (parsed.hostname, parsed.port or 80), timeout=timeout
        )
        self.sock.settimeout(timeout)
        self._buffer = bytearray()
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port or 80}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        self.sock.sendall(request)
        response = bytearray()
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise SmokeFailure("DevTools WebSocket closed during handshake")
            response.extend(chunk)
            if len(response) > 65536:
                raise SmokeFailure("Oversized DevTools WebSocket handshake")
        header_bytes, remainder = bytes(response).split(b"\r\n\r\n", 1)
        header_text = header_bytes.decode("iso-8859-1")
        if " 101 " not in header_text.split("\r\n", 1)[0]:
            raise SmokeFailure(f"DevTools WebSocket upgrade failed: {header_text}")
        headers: dict[str, str] = {}
        for line in header_text.split("\r\n")[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()
        expected_accept = base64.b64encode(
            hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest()
        ).decode("ascii")
        if headers.get("sec-websocket-accept") != expected_accept:
            raise SmokeFailure("DevTools WebSocket returned an invalid accept key")
        self._buffer.extend(remainder)

    def _recv_exact(self, size: int) -> bytes:
        while len(self._buffer) < size:
            try:
                chunk = self.sock.recv(max(4096, size - len(self._buffer)))
            except TimeoutError:
                raise
            except OSError as exc:
                raise SmokeFailure(f"DevTools WebSocket receive failed: {exc}") from exc
            if not chunk:
                raise SmokeFailure("DevTools WebSocket closed unexpectedly")
            self._buffer.extend(chunk)
        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        return data

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        first = 0x80 | opcode
        length = len(payload)
        if length < 126:
            header = struct.pack("!BB", first, 0x80 | length)
        elif length <= 0xFFFF:
            header = struct.pack("!BBH", first, 0x80 | 126, length)
        else:
            header = struct.pack("!BBQ", first, 0x80 | 127, length)
        mask = os.urandom(4)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        try:
            self.sock.sendall(header + mask + masked)
        except OSError as exc:
            raise SmokeFailure(f"DevTools WebSocket send failed: {exc}") from exc

    def send_json(self, message: dict[str, Any]) -> None:
        self._send_frame(0x1, json.dumps(message, separators=(",", ":")).encode())

    def recv_json(self, timeout: float) -> dict[str, Any]:
        self.sock.settimeout(timeout)
        fragments = bytearray()
        active_opcode: int | None = None
        while True:
            first, second = self._recv_exact(2)
            final = bool(first & 0x80)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if masked else b""
            payload = self._recv_exact(length)
            if masked:
                payload = bytes(
                    value ^ mask[index % 4] for index, value in enumerate(payload)
                )
            if opcode == 0x8:
                raise SmokeFailure("DevTools WebSocket closed the session")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode in (0x1, 0x2):
                active_opcode = opcode
                fragments.extend(payload)
            elif opcode == 0x0 and active_opcode is not None:
                fragments.extend(payload)
            else:
                raise SmokeFailure(f"Unexpected WebSocket opcode: {opcode}")
            if final:
                if active_opcode != 0x1:
                    raise SmokeFailure("DevTools returned a non-text message")
                try:
                    value = json.loads(fragments.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise SmokeFailure(f"Invalid DevTools JSON message: {exc}") from exc
                if not isinstance(value, dict):
                    raise SmokeFailure("DevTools returned a non-object JSON message")
                return value

    def close(self) -> None:
        with contextlib.suppress(OSError):
            self._send_frame(0x8, b"")
        with contextlib.suppress(OSError):
            self.sock.close()


class CDPSession:
    def __init__(self, websocket_url: str, timeout: float) -> None:
        self.timeout = timeout
        self.websocket = WebSocket(websocket_url, timeout)
        self.next_id = 1
        self.events: list[dict[str, Any]] = []
        self._responses: dict[int, dict[str, Any]] = {}

    def _read(self, timeout: float) -> dict[str, Any]:
        message = self.websocket.recv_json(timeout)
        if "method" in message:
            self.events.append(message)
        elif isinstance(message.get("id"), int):
            self._responses[int(message["id"])] = message
        return message

    def command(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        message_id = self.next_id
        self.next_id += 1
        self.websocket.send_json(
            {"id": message_id, "method": method, "params": params or {}}
        )
        deadline = time.monotonic() + self.timeout
        while message_id not in self._responses:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SmokeFailure(f"Timed out waiting for CDP command {method}")
            self._read(remaining)
        response = self._responses.pop(message_id)
        if "error" in response:
            error = response["error"]
            raise SmokeFailure(
                f"CDP command {method} failed: {error.get('message', error)}"
            )
        result = response.get("result", {})
        return result if isinstance(result, dict) else {}

    def wait_for_event(self, method: str, start: int) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        inspected = start
        while True:
            while inspected < len(self.events):
                event = self.events[inspected]
                inspected += 1
                if event.get("method") == method:
                    return event
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SmokeFailure(f"Timed out waiting for CDP event {method}")
            self._read(remaining)

    def drain(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            try:
                self._read(min(0.1, remaining))
            except TimeoutError:
                continue

    def evaluate(self, expression: str) -> Any:
        result = self.command(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        if result.get("exceptionDetails"):
            details = result["exceptionDetails"]
            raise SmokeFailure(
                f"Runtime evaluation failed: {details.get('text', details)}"
            )
        remote = result.get("result", {})
        if remote.get("subtype") == "error":
            raise SmokeFailure(
                f"Runtime evaluation returned an error: {remote.get('description')}"
            )
        return remote.get("value")

    def close(self) -> None:
        self.websocket.close()


def _http_json(url: str, *, method: str = "GET", timeout: float = 2.0) -> Any:
    request = urllib.request.Request(url, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


@contextlib.contextmanager
def launch_browser(
    browser: Path, timeout: float
) -> Iterator[tuple[subprocess.Popen[bytes], int]]:
    with tempfile.TemporaryDirectory(
        prefix="carbon-hub-browser-", ignore_cleanup_errors=True
    ) as profile_dir:
        log_path = Path(profile_dir) / "browser-stderr.log"
        command = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-domain-reliability",
            "--disable-extensions",
            "--disable-breakpad",
            "--disable-crash-reporter",
            "--disable-sync",
            "--metrics-recording-only",
            "--mute-audio",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--noerrdialogs",
            "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=0",
            f"--user-data-dir={profile_dir}",
            "--window-size=1440,1100",
            "about:blank",
        ]
        with log_path.open("wb") as log_file:
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=log_file,
                )
            except OSError as exc:
                raise SmokeFailure(
                    f"Unable to launch browser {browser}: {exc}"
                ) from exc
            try:
                active_port_file = Path(profile_dir) / "DevToolsActivePort"
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        break
                    if active_port_file.exists():
                        lines = active_port_file.read_text(
                            encoding="utf-8"
                        ).splitlines()
                        if lines and lines[0].isdigit():
                            yield process, int(lines[0])
                            return
                    time.sleep(0.05)
                log_file.flush()
                detail = log_path.read_text(encoding="utf-8", errors="replace").strip()
                raise SmokeFailure(
                    f"Browser did not expose a DevTools port within {timeout:.1f}s."
                    + (f" Browser output: {detail[-2000:]}" if detail else "")
                )
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


def _open_page_session(port: int, timeout: float) -> CDPSession:
    endpoint = f"http://127.0.0.1:{port}"
    try:
        targets = _http_json(f"{endpoint}/json/list", timeout=timeout)
    except Exception as exc:
        raise SmokeFailure(f"Unable to inspect browser targets: {exc}") from exc
    page = next(
        (
            target
            for target in targets
            if target.get("type") == "page" and target.get("webSocketDebuggerUrl")
        ),
        None,
    )
    if page is None:
        try:
            page = _http_json(
                f"{endpoint}/json/new?{urllib.parse.quote('about:blank', safe='')}",
                method="PUT",
                timeout=timeout,
            )
        except Exception as exc:
            raise SmokeFailure(
                f"Unable to create a browser page target: {exc}"
            ) from exc
    websocket_url = page.get("webSocketDebuggerUrl")
    if not websocket_url:
        raise SmokeFailure("Browser page target has no DevTools WebSocket URL")
    return CDPSession(str(websocket_url), timeout)


def _normalise_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _contains_any(text: str, alternatives: Sequence[str]) -> bool:
    return any(alternative.casefold() in text for alternative in alternatives)


def _event_errors(events: Sequence[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for event in events:
        method = event.get("method")
        params = event.get("params", {})
        if method == "Runtime.exceptionThrown":
            details = params.get("exceptionDetails", {})
            exception = details.get("exception", {})
            description = exception.get("description") or details.get("text")
            errors.append(f"uncaught exception: {description}")
        elif method == "Runtime.consoleAPICalled" and params.get("type") in {
            "error",
            "assert",
        }:
            values = []
            for argument in params.get("args", []):
                values.append(str(argument.get("value") or argument.get("description")))
            errors.append(f"console.{params.get('type')}: {' '.join(values)}")
        elif method == "Log.entryAdded":
            entry = params.get("entry", {})
            entry_path = urllib.parse.urlsplit(str(entry.get("url", ""))).path
            if entry.get("level") == "error" and not entry_path.endswith(
                "/favicon.ico"
            ):
                errors.append(f"browser log error: {entry.get('text')}")
        elif method == "Network.loadingFailed" and not params.get("canceled"):
            errors.append(
                f"network load failed: {params.get('errorText')} "
                f"({params.get('type', 'unknown resource')})"
            )
        elif method == "Network.responseReceived":
            response = params.get("response", {})
            status = response.get("status", 0)
            resource_type = params.get("type")
            url = str(response.get("url", ""))
            if (
                isinstance(status, (int, float))
                and status >= 400
                and resource_type
                in {"Document", "Stylesheet", "Script", "Image", "Font"}
                and not urllib.parse.urlsplit(url).path.endswith("/favicon.ico")
            ):
                errors.append(f"HTTP {status:g} for {resource_type}: {url}")
        elif method == "Inspector.targetCrashed":
            errors.append("browser target crashed")
    return errors


def _external_requests(
    events: Sequence[dict[str, Any]], expected_host: str, expected_port: int
) -> list[str]:
    external: list[str] = []
    for event in events:
        if event.get("method") != "Network.requestWillBeSent":
            continue
        url = str(event.get("params", {}).get("request", {}).get("url", ""))
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.hostname != expected_host or parsed.port != expected_port:
            external.append(url)
    return sorted(set(external))


def _load(
    session: CDPSession,
    url: str,
    viewport: Viewport,
    *,
    javascript_enabled: bool,
) -> tuple[str, list[dict[str, Any]]]:
    session.command(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": viewport.width,
            "height": viewport.height,
            "deviceScaleFactor": 1,
            "mobile": viewport.mobile,
            "screenWidth": viewport.width,
            "screenHeight": viewport.height,
        },
    )
    session.command(
        "Emulation.setScriptExecutionDisabled", {"value": not javascript_enabled}
    )
    start = len(session.events)
    result = session.command("Page.navigate", {"url": url})
    if result.get("errorText"):
        raise SmokeFailure(f"Navigation to {url} failed: {result['errorText']}")
    session.wait_for_event("Page.loadEventFired", start)
    session.drain(0.35)
    ready_state = session.evaluate("document.readyState")
    if ready_state != "complete":
        raise SmokeFailure(f"{url} stopped at document.readyState={ready_state!r}")
    actual_width = session.evaluate("window.innerWidth")
    if not isinstance(actual_width, (int, float)):
        raise SmokeFailure(
            f"{viewport.name} viewport did not report a numeric width: {actual_width!r}"
        )
    if viewport.mobile:
        # Some Chromium builds clamp emulated layout width slightly above the
        # requested device width.  The material assertion is that the narrow
        # responsive breakpoint is genuinely exercised.
        width_is_expected = 280 <= actual_width <= 480
    else:
        width_is_expected = abs(actual_width - viewport.width) <= 2
    if not width_is_expected:
        raise SmokeFailure(
            f"{viewport.name} viewport requested {viewport.width}px but rendered "
            f"at {actual_width!r}px"
        )
    body_text = session.evaluate("document.body ? document.body.innerText : ''")
    if not isinstance(body_text, str):
        raise SmokeFailure(f"{url} did not expose body text")
    session.drain(0.15)
    return _normalise_text(body_text), session.events[start:]


def _assert_primary(
    session: CDPSession,
    base_url: str,
    server_port: int,
    viewport: Viewport,
    *,
    javascript_enabled: bool,
    nonce: int,
) -> str:
    mode = "javascript-on" if javascript_enabled else "javascript-off"
    url = f"{base_url}/index.html?smoke={nonce}-{viewport.name}-{mode}"
    text, events = _load(
        session,
        url,
        viewport,
        javascript_enabled=javascript_enabled,
    )
    if len(text) < 1000:
        raise SmokeFailure(
            f"Primary page was not semantically complete in {viewport.name}/{mode}: "
            f"only {len(text)} normalized characters"
        )
    missing = [
        label
        for label, alternatives in EXPECTED_PRIMARY_TEXT.items()
        if not _contains_any(text, alternatives)
    ]
    if missing:
        raise SmokeFailure(
            f"Primary page missing expected content in {viewport.name}/{mode}: "
            + ", ".join(missing)
        )
    script_count = session.evaluate("document.scripts.length")
    if script_count != 0:
        raise SmokeFailure(
            f"Primary page must be static-first; found {script_count} script element(s)"
        )
    errors = _event_errors(events)
    if errors:
        raise SmokeFailure(
            f"Primary page errors in {viewport.name}/{mode}: " + "; ".join(errors)
        )
    external = _external_requests(events, "127.0.0.1", server_port)
    if external:
        raise SmokeFailure(
            "Primary page made external network request(s): " + ", ".join(external)
        )
    print(f"PASS primary {viewport.name} {mode}")
    return text


def _assert_interactive(
    session: CDPSession,
    base_url: str,
    viewport: Viewport,
    *,
    nonce: int,
) -> None:
    url = f"{base_url}/interactive.html?smoke={nonce}#/home"
    text, initial_events = _load(
        session,
        url,
        viewport,
        javascript_enabled=True,
    )
    if len(text) < 500:
        raise SmokeFailure(
            "Interactive page did not render meaningful content "
            f"({len(text)} characters)"
        )
    unsafe_attributes = session.evaluate(
        """[...document.querySelectorAll('*')].flatMap(element =>
          [...element.attributes]
            .filter(attribute =>
              attribute.name.toLowerCase().startsWith('on') ||
              (attribute.name.toLowerCase() === 'href' &&
               attribute.value.trim().toLowerCase().startsWith('javascript:'))
            )
            .map(attribute => `${element.tagName}.${attribute.name}`)
        )"""
    )
    if unsafe_attributes:
        raise SmokeFailure(
            "Interactive page rendered unsafe inline event/URL attributes: "
            + ", ".join(str(value) for value in unsafe_attributes)
        )
    all_events = list(initial_events)
    for route, alternatives in INTERACTIVE_ROUTES.items():
        start = len(session.events)
        session.evaluate(f"location.hash = {json.dumps(route)}")
        session.drain(0.15)
        route_text = session.evaluate("document.body ? document.body.innerText : ''")
        normalised = _normalise_text(route_text if isinstance(route_text, str) else "")
        if not _contains_any(normalised, alternatives):
            raise SmokeFailure(
                f"Interactive route {route} did not render any of: "
                + ", ".join(alternatives)
            )
        all_events.extend(session.events[start:])
    errors = _event_errors(all_events)
    if errors:
        raise SmokeFailure("Interactive page errors: " + "; ".join(errors))
    print(f"PASS interactive routes ({len(INTERACTIVE_ROUTES)})")


def _assert_mobile_navigation(
    session: CDPSession,
    base_url: str,
    viewport: Viewport,
    *,
    nonce: int,
) -> None:
    url = f"{base_url}/interactive.html?smoke={nonce}-mobile-nav#/home"
    _, initial_events = _load(
        session,
        url,
        viewport,
        javascript_enabled=True,
    )
    closed = session.evaluate("""(() => {
          const button = document.querySelector('#menuBtn');
          const sidebar = document.querySelector('#sidebar');
          return {
            expanded: button.getAttribute('aria-expanded'),
            hidden: sidebar.getAttribute('aria-hidden'),
            inert: sidebar.inert,
            visibility: getComputedStyle(sidebar).visibility
          };
        })()""")
    expected_closed = {
        "expanded": "false",
        "hidden": "true",
        "inert": True,
        "visibility": "hidden",
    }
    if closed != expected_closed:
        raise SmokeFailure(
            f"Mobile navigation did not start inaccessible and closed: {closed!r}"
        )

    session.evaluate("document.querySelector('#menuBtn').click()")
    opened = session.evaluate("""(() => {
          const button = document.querySelector('#menuBtn');
          const sidebar = document.querySelector('#sidebar');
          return {
            expanded: button.getAttribute('aria-expanded'),
            hidden: sidebar.getAttribute('aria-hidden'),
            inert: sidebar.inert,
            visibility: getComputedStyle(sidebar).visibility,
            focusedNav: document.activeElement?.classList.contains('nav-link') || false
          };
        })()""")
    expected_opened = {
        "expanded": "true",
        "hidden": "false",
        "inert": False,
        "visibility": "visible",
        "focusedNav": True,
    }
    if opened != expected_opened:
        raise SmokeFailure(
            f"Mobile navigation did not expose and focus its links: {opened!r}"
        )

    session.evaluate(
        "document.dispatchEvent(new KeyboardEvent('keydown', "
        "{key:'Escape', bubbles:true}))"
    )
    escaped = session.evaluate("""(() => {
          const button = document.querySelector('#menuBtn');
          const sidebar = document.querySelector('#sidebar');
          return {
            expanded: button.getAttribute('aria-expanded'),
            hidden: sidebar.getAttribute('aria-hidden'),
            inert: sidebar.inert,
            menuFocused: document.activeElement === button
          };
        })()""")
    expected_escaped = {
        "expanded": "false",
        "hidden": "true",
        "inert": True,
        "menuFocused": True,
    }
    if escaped != expected_escaped:
        raise SmokeFailure(
            f"Mobile navigation did not close and restore focus on Escape: {escaped!r}"
        )
    session.drain(0.15)
    errors = _event_errors(initial_events)
    if errors:
        raise SmokeFailure("Mobile navigation page errors: " + "; ".join(errors))
    print("PASS interactive mobile navigation accessibility")


def run_smoke(root: Path, browser: Path, timeout: float) -> None:
    index_path = root / "index.html"
    if not index_path.is_file():
        raise SmokeFailure(f"Generated primary page is missing: {index_path}")

    server = create_server(root, "127.0.0.1", 0, quiet=True)
    server_thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.1},
        daemon=True,
        name="carbon-hub-smoke-server",
    )
    server_thread.start()
    server_port = int(server.server_address[1])
    base_url = f"http://127.0.0.1:{server_port}"
    try:
        with launch_browser(browser, timeout) as (_, devtools_port):
            session = _open_page_session(devtools_port, timeout)
            try:
                for domain in ("Page", "Runtime", "Network", "Log", "Inspector"):
                    session.command(f"{domain}.enable")
                session.command("Network.setCacheDisabled", {"cacheDisabled": True})
                nonce = int(time.time() * 1000)
                for viewport in VIEWPORTS:
                    enabled_text = _assert_primary(
                        session,
                        base_url,
                        server_port,
                        viewport,
                        javascript_enabled=True,
                        nonce=nonce,
                    )
                    disabled_text = _assert_primary(
                        session,
                        base_url,
                        server_port,
                        viewport,
                        javascript_enabled=False,
                        nonce=nonce,
                    )
                    if enabled_text != disabled_text:
                        raise SmokeFailure(
                            "Primary page visible text changed when JavaScript was "
                            f"disabled at the {viewport.name} viewport"
                        )
                    print(f"PASS primary {viewport.name} JavaScript parity")
                interactive_path = root / "interactive.html"
                if interactive_path.is_file():
                    _assert_interactive(
                        session,
                        base_url,
                        VIEWPORTS[0],
                        nonce=nonce,
                    )
                    _assert_mobile_navigation(
                        session,
                        base_url,
                        VIEWPORTS[1],
                        nonce=nonce,
                    )
                else:
                    print("SKIP interactive.html (optional artifact is absent)")
            finally:
                session.close()
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Load the Carbon Development Hub in a real Chromium browser with "
            "JavaScript enabled and disabled at desktop and mobile viewports."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=HUB_ROOT,
        help="hub directory (default: parent of this tools directory)",
    )
    parser.add_argument(
        "--browser",
        type=Path,
        help="Chrome, Chromium, or Edge executable (also CARBON_HUB_BROWSER)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="browser/CDP operation timeout in seconds (default: 15)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.timeout <= 0:
        raise SystemExit("--timeout must be greater than zero")
    try:
        browser = discover_browser(args.browser)
        print(f"Browser: {browser}")
        print(f"Hub root: {args.root.resolve()}")
        run_smoke(args.root.resolve(), browser, args.timeout)
    except SmokeFailure as exc:
        print(f"BROWSER SMOKE FAILED: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("BROWSER SMOKE INTERRUPTED", file=sys.stderr)
        return 130
    print("Browser smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
