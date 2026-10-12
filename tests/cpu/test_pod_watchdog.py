"""The confirmation pods' watchdog (OWNER-STARTUP-HOST-CUSTODY-03-EXT-02 §2) in
dry mode: every path under a temporary root, a local HTTP stub in place of
RunPod's endpoint, and a fake key. No pod, key or network beyond 127.0.0.1."""

from __future__ import annotations

import hashlib
import http.server
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import ClassVar

import pytest

ROOT = Path(__file__).resolve().parents[2]
WATCHDOG = ROOT / "scripts/dev/battery/pod_watchdog.py"
START = ROOT / "scripts/dev/battery/pod_watchdog_start.tmpl"
FAKE_KEY = "rpa_FAKEFAKEFAKE0123456789abcdefFAKE"


class Stub(http.server.BaseHTTPRequestHandler):
    seen: ClassVar[list] = []
    status = 200

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        Stub.seen.append((self.headers.get("Authorization"), json.loads(body)))
        self.send_response(Stub.status)
        self.end_headers()
        self.wfile.write(b'{"data":{"podTerminate":null}}')

    def log_message(self, *args):
        pass


@pytest.fixture
def endpoint():
    Stub.seen, Stub.status = [], 200
    server = http.server.HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/graphql"
    server.shutdown()


def pod(base):
    home = base / "var/lib/carbon-producer/startup"
    watch = base / "var/lib/carbon-producer/watchdog"
    for d in (home / ".ssh", home / "shard-0", home / "overlay", watch, base / "tmp"):
        d.mkdir(parents=True, exist_ok=True)
    (home / ".ssh/authorized_keys").write_text("ssh-ed25519 AAAA test\n")
    (home / "shard-0/records.jsonl").write_text("{}\n")
    (home / "overlay/x.py").write_text("x\n")
    (base / "tmp/cache.bin").write_bytes(b"\0" * 64)
    return home, watch


def run(base, deadline, endpoint, *, marker_after=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("RUNPOD")}
    env.update(RUNPOD_API_KEY=FAKE_KEY, RUNPOD_POD_ID="podDRY01")
    proc = subprocess.Popen(
        [sys.executable, "-I", str(WATCHDOG), str(deadline), "--dry"]
        + ["--base", str(base), "--endpoint", endpoint],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if marker_after is not None:
        time.sleep(marker_after)
        (base / "var/lib/carbon-producer/watchdog/teardown").touch()
    out, _ = proc.communicate(timeout=60)
    return proc.returncode, out


def test_the_marker_wipes_then_terminates_with_the_injected_key(tmp_path, endpoint):
    home, watch = pod(tmp_path)
    code, out = run(tmp_path, int(time.time()) + 3600, endpoint, marker_after=0.5)
    assert code == 0 and "TEARDOWN teardown" in out and "WIPED remaining 0" in out
    assert (home / ".ssh/authorized_keys").exists()
    assert not any(p.is_file() for p in home.rglob("*") if ".ssh" not in p.parts)
    assert not (tmp_path / "tmp/cache.bin").exists()
    [(auth, body)] = Stub.seen
    assert auth == "Bearer " + FAKE_KEY
    assert 'podTerminate(input: {podId: "podDRY01"})' in body["query"]
    # The key is never printed or written.
    assert FAKE_KEY not in out and FAKE_KEY not in (watch / "armed").read_text()
    assert (watch / "armed").read_text().startswith("ARMED deadline")


def test_the_max_lifetime_wipes_and_terminates_without_a_marker(tmp_path, endpoint):
    pod(tmp_path)
    code, out = run(tmp_path, int(time.time()) + 1, endpoint)
    assert code == 0 and "TEARDOWN max_lifetime" in out and "WIPED remaining 0" in out
    assert len(Stub.seen) == 1


def test_a_provider_error_is_retried_then_the_owner_is_told(tmp_path, endpoint):
    pod(tmp_path)
    Stub.status = 500
    code, out = run(tmp_path, int(time.time()) + 3600, endpoint, marker_after=0.3)
    assert code == 1 and len(Stub.seen) == 10 and "TERMINATE_FAILED" in out
    assert FAKE_KEY not in out


def test_real_mode_refuses_the_dry_overrides():
    for extra in (["--base", "/x"], ["--endpoint", "http://127.0.0.1:9/"]):
        r = subprocess.run(
            [sys.executable, "-I", str(WATCHDOG), "1", *extra],
            capture_output=True,
            check=False,
            text=True,
        )
        assert r.returncode != 0 and "refused" in r.stderr


@pytest.mark.parametrize("case", ["absent", "wrong", "pinned"])
def test_the_start_command_runs_only_the_pinned_watchdog(tmp_path, case):
    """The start command's arming loop, verbatim except that its paths move
    under a temporary root and its 15 s poll is 1 s."""
    template = START.read_text().strip()
    loop = template[template.index("D=$((") : template.index(" & ssh-keygen")]
    stub = '#!/bin/sh\necho "STUB_ARMED deadline=$3 key=${RUNPOD_API_KEY:+present}"\n'
    (tmp_path / "var/lib/carbon-producer/watchdog").mkdir(parents=True)
    (tmp_path / "root").mkdir()
    python = tmp_path / "opt/carbon-worker/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\nexec sh "$2" "$@"\n')
    python.chmod(0o755)
    if case != "absent":
        (tmp_path / "var/lib/carbon-producer/watchdog/watchdog.py").write_text(stub)
    pinned = stub if case == "pinned" else "something else"
    script = (
        (loop + " & wait")
        .replace("{MAXLIFE}", "4")
        .replace("{HASH}", hashlib.sha256(pinned.encode()).hexdigest())
        .replace("/var/lib/carbon-producer", f"{tmp_path}/var/lib/carbon-producer")
        .replace("/root/watchdog.py", f"{tmp_path}/root/watchdog.py")
        .replace("/opt/carbon-worker/bin/python", str(python))
        .replace("sleep 15", "sleep 1")
    )
    env = dict(os.environ, RUNPOD_API_KEY=FAKE_KEY)
    r = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    out = r.stdout + r.stderr
    assert "MAX_LIFETIME_UNTIL" in out
    if case == "pinned":
        assert "STUB_ARMED" in out and "key=present" in out
    else:
        assert "STUB_ARMED" not in out and "WATCHDOG_NEVER_ARMED" in out


def test_the_start_command_installs_only_openssh_and_pins_two_values():
    template = START.read_text()
    assert template.count("{HASH}") == 1 and template.count("{MAXLIFE}") == 1
    assert "apt-get install -y -qq --no-install-recommends openssh-server >" in template
    assert template.count("apt-get install") == 1
