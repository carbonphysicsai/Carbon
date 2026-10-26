"""Build, sign and upload the dashboard's launch boards on the validator host
(OWNER-DASHBOARD-01; the Test Engineer's valV3 step 6).

One run, for every launch Challenge in the config:

1. fetch the receiver's own public king document (`GET /carbon/v1/koth/<id>`; an
   unpublished or unreachable one is handled below);
2. read the receiver's Ladder from its attempt-ledger file, read-only;
3. build the closed launch board (`carbon.challenge_validator.launch_board`) and sign it
   with the validator's feed key (loaded here, on the validator host, never printed,
   never copied);
4. write `<out>/<slug>.json` atomically, check it with the dashboard's own reader and
   the PUBLIC key, and upload it.

Before the first graded hotkey the board is the empty one (`PRE_FIRST_RELEASE`); the
moment a result is recorded the next run shows it. A receiver that cannot be reached
leaves the last written board in place (the dashboard marks a stale board STALE by its
own age) and the run says so; nothing finer than the receiver's own king document and
the Ladder's rounded totals ever enters a board.

    python scripts/dev/launch_board_operator.py run --config BOARDS.json
    python scripts/dev/launch_board_operator.py run --config BOARDS.json --every 300
    python scripts/dev/launch_board_operator.py systemd --config BOARDS.json

Config (`carbon.launch-board.operator.config.v1`, mode 600, never committed):

    {"schema": "carbon.launch-board.operator.config.v1",
     "network": "testnet",
     "ledger": "<the receiver's attempt-ledger file>",
     "receiver_url": "http://127.0.0.1:<receiver port>",
     "key": "<the validator's feed key file>",
     "out": "<directory the boards are written to>",
     "upload_command": ["npx", "wrangler@4", "r2", "object", "put",
                        "<bucket>/valv3/{name}", "--file", "{file}",
                        "--content-type", "application/json", "--remote"],
     "challenges": [
       {"id": "electric-motor-magnetics", "version": "1.4", "exam_version_label": "<label>"},
       {"id": "chip-cold-plate", "version": "1.4", "exam_version_label": "<label>"},
       {"id": "f08-ribbed-bracket", "version": "1.5", "exam_version_label": "<label>"},
       {"id": "f02", "version": "2.4", "exam_version_label": "<label>"}]}

`exam_version_label` is only used while the receiver publishes no king document yet (a
404); `exam_key` is optional per Challenge (default "latest": the exam of the most
recent graded result). `upload_command` is optional; `{file}` and `{name}` are
replaced, and nothing else is ever put on the command line.

Exit codes: 0 every board written and uploaded; 2 a board could not be built, checked
or uploaded (the run names which and why).

DEVELOPMENT / TESTNET only: display data, no score, weight or reward authority.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from carbon.challenge_validator import koth_public, launch_board
from carbon.challenge_validator.feed_file import write_feed
from carbon.challenge_validator.score_feed import FeedRefused
from carbon.dashboard import feed as dashboard_feed

CONFIG_SCHEMA = "carbon.launch-board.operator.config.v1"
NAMES = {"schema", "network", "ledger", "receiver_url", "key", "out", "challenges"}
OPTIONAL = {"upload_command", "fetch_timeout_seconds"}
MAX_KOTH_BYTES = koth_public.MAX_BYTES
_PLACEHOLDER = re.compile(r"\{(file|name)\}")


class OperatorRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def load_config(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if (
        type(raw) is not dict
        or raw.get("schema") != CONFIG_SCHEMA
        or not NAMES <= set(raw)
        or set(raw) - NAMES - OPTIONAL
        or raw["network"] not in launch_board.NETWORKS
        or type(raw["challenges"]) is not list
        or not raw["challenges"]
    ):
        raise OperatorRefused("operator_config")
    for item in raw["challenges"]:
        if (
            type(item) is not dict
            or not {"id", "version", "exam_version_label"} <= set(item)
            or set(item) - {"id", "version", "exam_version_label", "exam_key"}
        ):
            raise OperatorRefused("operator_config_challenge")
    command = raw.get("upload_command")
    if command is not None and (
        type(command) is not list or not all(type(part) is str for part in command)
    ):
        raise OperatorRefused("operator_config_upload")
    if not re.fullmatch(r"https?://[^/\s]+", raw["receiver_url"]):
        raise OperatorRefused("operator_config_receiver")
    return raw


def fetch_king(receiver_url, challenge, timeout):
    """The receiver's king document for ``challenge``, or None when it publishes none
    yet (404); an unreachable or malformed answer is `OperatorRefused`."""
    url = f"{receiver_url}{koth_public.PATH}{challenge['id']}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(MAX_KOTH_BYTES + 1)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise OperatorRefused("receiver_unavailable") from None
    except (urllib.error.URLError, OSError, TimeoutError):
        raise OperatorRefused("receiver_unavailable") from None
    if len(body) > MAX_KOTH_BYTES:
        raise OperatorRefused("receiver_answer_too_large")
    try:
        document = json.loads(body)
    except ValueError:
        raise OperatorRefused("receiver_answer_malformed") from None
    if type(document) is not dict or document.get("challenge_id") != challenge["id"]:
        raise OperatorRefused("receiver_answer_other_challenge")
    return document


def unpublished_king(challenge):
    """The king document of a receiver that publishes none yet: no king, no margin."""
    return koth_public.document(
        challenge_id=challenge["id"],
        challenge_version=challenge["version"],
        exam_version_label=challenge["exam_version_label"],
        king=None,
        rebuild_noise=None,
        baseline_total=None,
    )


def slug_of(challenge):
    return dashboard_feed.board_slug(challenge["id"], "no-class")


def upload(command, path, name):
    """Run the configured upload command with `{file}` and `{name}` filled in."""
    if command is None:
        return None
    argv = [
        _PLACEHOLDER.sub(lambda m: {"file": str(path), "name": name}[m[1]], part)
        for part in command
    ]
    done = subprocess.run(
        argv, capture_output=True, text=True, timeout=300, check=False
    )
    if done.returncode != 0:
        raise OperatorRefused("upload_failed")
    return name


def run_once(config, *, version=None):
    """Build, sign, check and upload every board; the list of result rows."""
    key = launch_board.LaunchBoardKey.load(config["key"])
    trust = dashboard_feed.Trust(keys=frozenset({key.public_key}))
    out = Path(config["out"])
    out.mkdir(parents=True, exist_ok=True)
    version = launch_board.now_version() if version is None else version
    timeout = config.get("fetch_timeout_seconds", 10)
    rows = []
    for item in config["challenges"]:
        challenge = type(
            "Challenge", (), {"challenge_id": item["id"], "version": item["version"]}
        )()
        name = slug_of(item) + ".json"
        row = {"challenge": item["id"], "version": item["version"], "file": name}
        try:
            king = fetch_king(config["receiver_url"], item, timeout)
            board = launch_board.build_from_ledger(
                ledger=config["ledger"],
                challenge=challenge,
                exam_key=item.get("exam_key", "latest"),
                king_document=unpublished_king(item) if king is None else king,
                network=config["network"],
                key=key,
                version=version,
            )
            path = out / name
            write_feed(path, board)
            # The dashboard's own reader, under the PUBLIC key, must accept what was
            # written before it is uploaded.
            projected = dashboard_feed.project(
                json.loads(path.read_text(encoding="utf-8")), trust
            )
            row.update(
                state="WROTE",
                graded=board["counts"]["graded"],
                king=board["king"]["king"] is not None,
                shown=projected["launch"]["counts"]["graded"],
            )
            if upload(config.get("upload_command"), path, name):
                row["state"] = "UPLOADED"
        except (
            OperatorRefused,
            launch_board.BoardRefused,
            dashboard_feed.FeedRefused,
            ValueError,
            OSError,
            subprocess.SubprocessError,
        ) as error:
            row.update(
                state="REFUSED", code=getattr(error, "code", type(error).__name__)
            )
        rows.append(row)
    return rows


def systemd_units(config_path, *, every=300):
    """A oneshot service and a timer that run this script every ``every`` seconds."""
    script = Path(__file__).resolve()
    return f"""# /etc/systemd/system/carbon-launch-board.service
[Unit]
Description=Carbon launch boards: build, sign and upload the dashboard standing

[Service]
Type=oneshot
ExecStart={sys.executable} {script} run --config {Path(config_path).resolve()}

# /etc/systemd/system/carbon-launch-board.timer
[Unit]
Description=Carbon launch boards every {every} s

[Timer]
OnBootSec=1min
OnUnitActiveSec={every}s

[Install]
WantedBy=timers.target
"""


def main(argv=None):
    parser = argparse.ArgumentParser(prog="launch_board_operator")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", required=True, type=Path)
    run.add_argument(
        "--every", type=int, default=0, help="repeat every N seconds (0: once)"
    )
    unit = commands.add_parser("systemd")
    unit.add_argument("--config", required=True, type=Path)
    unit.add_argument("--every", type=int, default=300)
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except (OperatorRefused, OSError, ValueError) as error:
        print(json.dumps({"refused": getattr(error, "code", type(error).__name__)}))
        return 2
    if args.command == "systemd":
        print(systemd_units(args.config, every=args.every))
        return 0
    while True:
        try:
            rows = run_once(config)
        except (FeedRefused, OSError) as error:
            print(json.dumps({"refused": getattr(error, "code", type(error).__name__)}))
            return 2
        print(json.dumps({"boards": rows}, sort_keys=True), flush=True)
        failed = any(row["state"] == "REFUSED" for row in rows)
        if args.every <= 0:
            return 2 if failed else 0
        time.sleep(args.every)


if __name__ == "__main__":
    sys.exit(main())
