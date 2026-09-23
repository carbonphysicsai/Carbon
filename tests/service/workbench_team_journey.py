"""Operator-run: one continuous team journey against the supported launcher.

Handoff §10 case 11. Starts ``workbench_host serve`` exactly as
``test_workbench_host_process.py`` does (a test-owned synthetic campaign, only
the external hotkey and testnet runtime substituted, a real Julia worker) and
the stage-1 team receiver on loopback, then drives
``Business/Carbon_Fit/workbench/tests/browser_team_journey_launcher.cjs`` through
one browser session. The driver performs the two operator steps a browser
cannot: relaying the client's downloaded package into the receiver under the
adopted relayed-export ingress, and registering the design with
``workbench_host register-draft``.

Not collected by pytest. It needs Node, Playwright and a Chromium build:

    CARBON_JULIA_WORKER_MANIFEST=.carbon-artifacts/julia-worker-image.json \\
    NODE_PATH=/path/to/node_modules \\
    .venv/bin/python tests/service/workbench_team_journey.py [--mobile]

It prints the browser's checks and the receiver's record of the same inquiry.
Nothing here is a deployment, a real user, or a scientific result.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import signal
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(REPOSITORY),
    str(REPOSITORY / "tests/cpu"),
    str(Path(__file__).parent),
]

import pytest
from test_workbench_host_process import (
    BUILD,
    HOST,
    TOKEN,
    Launcher,
    free_port,
    prepare,
)

from carbon.reconstruction.worker.docker_runtime import (
    load_image_identity,
)

WORKBENCH = REPOSITORY / "Business/Carbon_Fit/workbench"
JOURNEY = WORKBENCH / "tests/browser_team_journey_launcher.cjs"
RECEIVER = WORKBENCH / "tools/team_intake_server.cjs"
RELAY_TOKEN = "journey-receiver-token-" + "c" * 20
REVIEW_TOKEN = "journey-reviewer-token-" + "d" * 20


def totp_secret(token: str) -> str:
    """A synthetic 160-bit base32 second-factor secret for a test credential."""
    return base64.b32encode(
        hashlib.sha256(("totp:" + token).encode()).digest()[:20]
    ).decode()


def totp(secret: str, now: float) -> str:
    """RFC 6238 TOTP: HMAC-SHA1, 30-second steps, six digits."""
    counter = struct.pack(">Q", int(now // 30))
    mac = hmac.new(base64.b32decode(secret), counter, "sha1").digest()
    offset = mac[-1] & 0x0F
    code = (int.from_bytes(mac[offset : offset + 4], "big") & 0x7FFFFFFF) % 10**6
    return f"{code:06d}"


SESSIONS: dict[str, str] = {}


def session_for(base, token):
    """Open one real session per credential, with its second factor (E9)."""
    if token not in SESSIONS:
        request = urllib.request.Request(
            base + "/private/session",
            data=json.dumps({"code": totp(totp_secret(token), time.time())}).encode(),
            method="POST",
            headers={
                "authorization": "Bearer " + token,
                "content-type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            SESSIONS[token] = json.loads(response.read())["session_token"]
    return SESSIONS[token]


def receiver_request(base, method, route, token, body=None, headers=None):
    token = session_for(base, token)
    request = urllib.request.Request(
        base + route,
        data=body,
        method=method,
        headers={"authorization": "Bearer " + token, **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.loads(response.read())


def start_receiver(root: Path):
    users = root / "receiver-users.json"
    users.write_text(
        json.dumps(
            [
                {
                    "principal": principal,
                    "team": "carbon-fit",
                    "roles": roles,
                    "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
                    "totp_secret": totp_secret(token),
                    "status": "ACTIVE",
                }
                for principal, roles, token in (
                    ("journey-receiver", ["INTAKE_RECEIVER"], RELAY_TOKEN),
                    ("journey-reviewer", ["TEAM_REVIEWER"], REVIEW_TOKEN),
                )
            ]
        )
    )
    users.chmod(0o600)
    port = free_port()
    environment = {
        **os.environ,
        "CARBON_TEAM_INTAKE_STORE": str(root / "receiver-store.json"),
        "CARBON_TEAM_USERS_FILE": str(users),
        "CARBON_TEAM_INTAKE_PORT": str(port),
    }
    environment.pop("CARBON_TEAM_NOTIFY_DESTINATION", None)
    process = subprocess.Popen(
        ["node", str(RECEIVER)],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    line = process.stdout.readline()
    if "listening" not in line:
        process.kill()
        raise RuntimeError("receiver did not start: " + line)
    return process, f"http://127.0.0.1:{port}"


def relay(base, work: Path, request):
    raw = Path(request["package"]).read_bytes()
    status, receipt = receiver_request(
        base,
        "POST",
        "/private/intake",
        RELAY_TOKEN,
        raw,
        {"idempotency-key": "journey-001", "content-type": "application/json"},
    )
    assert status == 201 and receipt["disposition"] == "ACCEPTED", receipt
    _, record = receiver_request(
        base, "GET", f"/private/intake/{receipt['inquiry_id']}/export", REVIEW_TOKEN
    )
    stored = work / "inquiry-from-receiver.json"
    stored.write_bytes(record["raw_json"].encode("utf-8"))
    assert stored.read_bytes() == raw, "the receiver returned different bytes"
    return {
        "inquiry_id": receipt["inquiry_id"],
        "raw_sha256": record["raw_sha256"],
        "downloaded_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "stored_package": str(stored),
    }


def register(profile: Path, registry: Path, work: Path, request):
    draft = work / "draft.json"
    draft.write_text(json.dumps(request))
    subprocess.run(
        [
            *HOST,
            "register-draft",
            "--configuration",
            str(profile),
            "--draft-registry",
            str(registry),
            "--draft",
            str(draft),
        ],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    )
    return {"registered": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mobile", action="store_true")
    args = parser.parse_args()
    manifest = Path(os.environ["CARBON_JULIA_WORKER_MANIFEST"]).resolve()
    image = load_image_identity(manifest)
    root = Path(tempfile.mkdtemp(prefix="carbon-team-journey-"))
    work = root / "browser"
    work.mkdir()
    monkeypatch = pytest.MonkeyPatch()
    profile, principals, _grant, _owner = prepare(root, manifest, image, monkeypatch)
    monkeypatch.undo()
    static = (root / "workbench-private").resolve()
    subprocess.run(
        [
            sys.executable,
            str(BUILD),
            "--private-science",
            "--output-directory",
            str(static),
        ],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    )
    registry = root / "private" / "drafts.json"
    launcher = Launcher(root, profile, principals, static)
    receiver, receiver_base = start_receiver(root)
    host, origin, log = launcher.start()
    code = 1
    try:
        launcher.wait_serving(host, origin, log)
        environment = {
            **os.environ,
            "CARBON_FIXTURE_STAFF_TOKEN": TOKEN,
            **({"CARBON_MOBILE": "1"} if args.mobile else {}),
        }
        browser = subprocess.Popen(
            ["node", str(JOURNEY), origin, str(work)], env=environment
        )
        steps = {
            "relay": lambda request: relay(receiver_base, work, request),
            "register": lambda request: register(profile, registry, work, request),
        }
        done = set()
        while browser.poll() is None:
            for step, handle in steps.items():
                need = work / f"need-{step}.json"
                if step not in done and need.exists():
                    answer = handle(json.loads(need.read_text()))
                    (work / f"done-{step}.json").write_text(json.dumps(answer))
                    done.add(step)
            time.sleep(0.2)
        code = browser.returncode
        if code == 0:
            relayed = json.loads((work / "done-relay.json").read_text())
            _, record = receiver_request(
                receiver_base,
                "GET",
                f"/private/intake/{relayed['inquiry_id']}",
                REVIEW_TOKEN,
            )
            print(
                json.dumps(
                    {
                        "journey": json.loads(
                            (work / "journey-result.json").read_text()
                        ),
                        "receiver": {
                            "inquiry_id": record["inquiry_id"],
                            "lifecycle": record["lifecycle"],
                            "raw_sha256_matches_download": relayed["raw_sha256"]
                            == relayed["downloaded_sha256"],
                        },
                    },
                    indent=2,
                )
            )
    finally:
        stopped = launcher.stop(host)
        receiver.send_signal(signal.SIGTERM)
        receiver.wait(timeout=30)
    if stopped != 0:
        print("launcher did not stop cleanly: " + log.read_text(), file=sys.stderr)
        return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
