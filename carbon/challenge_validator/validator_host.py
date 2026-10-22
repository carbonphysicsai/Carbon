"""One validator host: a receiver service per Challenge, its proxy, its status.

    scripts/install_validator.sh --setup --hotkey SS58 [--challenges current|all|ID@VERSION,...]
                                 [--packs DIR] [--domain NAME]
    scripts/install_validator.sh --status

`install_validator.sh` installs the host and its images, then calls this:

    .venv/bin/python -B -m carbon.challenge_validator.validator_host setup \\
        --installed-state STATE --hotkey SS58 [--challenges ...] [--packs DIR] \\
        [--domain NAME] [--base-port N]
    .venv/bin/python -B -m carbon.challenge_validator.validator_host status \\
        --installed-state STATE

`setup` prepares one receiver per selected Challenge version (each its own
receiver state and loopback port, under STATE/validator/receivers), installs
each as a persistent `systemd --user` service, and records the host's layout
(STATE/validator/host.json, owner-only). Running it again keeps what is there
and adds what is new; the hotkey never changes under a prepared host. With
`--packs DIR`, a receiver selects the evaluation pack at DIR/ID-VERSION when
there is one. With `--domain`, it writes a Caddy reverse-proxy configuration
(TLS from Caddy's automatic certificates) that serves each receiver at
https://DOMAIN/ID/VERSION, and the matching endpoint entries for Carbon's
published-endpoints list, so miners' Launchpad finds them.

`status` reports every receiver (`receiver_setup.status`). Nothing here holds
a key: the hotkey is its public ss58 address. DEVELOPMENT only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import receiver_setup
from .receiver_setup import SetupRefused

HOST_SCHEMA = "carbon.validator-host.v1"
HOST_FILE = "host.json"
CADDY_FILE = "Caddyfile"
ENDPOINTS_FILE = "published-endpoints-entries.json"
DEFAULT_BASE_PORT = receiver_setup.DEFAULT_PORT
#: The published-endpoints list a miner's Launchpad reads (an entry is added
#: there by pull request).
PUBLISHED = "scripts/dev/miner_launchpad/published_endpoints.json"


def _host_dir(installed_state: Path) -> Path:
    return installed_state / "validator"


def _write_private(path: Path, raw: bytes) -> None:
    from scripts.dev.miner_launchpad.environment_setup import write_private

    write_private(path, raw)


def _canonical(value) -> bytes:
    from carbon.development_session.profile import canonical

    return canonical(value)


def select(choice: str) -> list[dict]:
    """`current` (each Challenge's newest version), `all`, or ID@VERSION,..."""
    if choice == "current":
        return list(receiver_setup.current())
    if choice == "all":
        return list(receiver_setup.served())
    selected = []
    for item in choice.split(","):
        challenge_id, _, version = item.strip().partition("@")
        found = receiver_setup._challenge(challenge_id, version)
        if found not in selected:
            selected.append(found)
    if not selected:
        raise SetupRefused(
            "challenges_empty", "name at least one Challenge, or `current`."
        )
    return selected


def _slug(challenge: dict) -> str:
    return f"{challenge['id']}-{challenge['version']}"


def read_host(installed_state: Path):
    path = _host_dir(installed_state) / HOST_FILE
    if not path.exists():
        return None
    from carbon.development_session.private_records import private_json

    value = private_json(path)
    if type(value) is not dict or value.get("schema") != HOST_SCHEMA:
        raise SetupRefused(
            "validator_host_record_invalid",
            f"{path} is not a validator host record; move it aside and run "
            "--setup again.",
        )
    return value


def setup(
    *,
    installed_state: Path,
    hotkey: str,
    challenges: list[dict],
    packs: Path | None = None,
    domain: str | None = None,
    base_port: int = DEFAULT_BASE_PORT,
    prepare=None,
    service=None,
) -> dict:
    """Prepare and start one receiver service per Challenge; return the layout."""
    prepare = prepare or receiver_setup.prepare
    service = service or receiver_setup.service
    root = _host_dir(installed_state)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    host = read_host(installed_state) or {
        "schema": HOST_SCHEMA,
        "hotkey": hotkey,
        "receivers": [],
    }
    if host["hotkey"] != hotkey:
        raise SetupRefused(
            "validator_hotkey_differs",
            "this host's receivers belong to another hotkey; use that hotkey, "
            "or a new CARBON_STATE_DIR for a new one.",
        )
    used = {entry["port"] for entry in host["receivers"]}
    by_challenge = {
        (e["challenge"]["id"], e["challenge"]["version"]): e for e in host["receivers"]
    }
    results = []
    for challenge in challenges:
        key = (challenge["id"], challenge["version"])
        entry = by_challenge.get(key)
        if entry is None:
            port = base_port
            while port in used:
                port += 1
            used.add(port)
            entry = {
                "challenge": challenge,
                "port": port,
                "receiver_state": str(root / "receivers" / _slug(challenge)),
            }
            pack = None if packs is None else packs / _slug(challenge)
            prepare(
                installed_state=installed_state,
                receiver_state=Path(entry["receiver_state"]),
                challenge=challenge,
                hotkey=hotkey,
                pack=pack if pack is not None and pack.is_dir() else None,
                port=port,
            )
            host["receivers"].append(entry)
            by_challenge[key] = entry
            # Recorded before the service starts: a failed start keeps the
            # prepared receiver, and running --setup again starts it.
            _write_private(root / HOST_FILE, _canonical(host))
        started = service(Path(entry["receiver_state"]))
        results.append({**entry, "unit": started["unit"]})
    _write_private(root / HOST_FILE, _canonical(host))
    found = {
        "status": "VALIDATOR_RECEIVERS_ENABLED",
        "hotkey": hotkey,
        "receivers": results,
        "host_record": str(root / HOST_FILE),
    }
    if domain is not None:
        found["proxy"] = write_proxy(installed_state, domain)
    return found


def _domain(value: str) -> str:
    import re

    if type(value) is not str or not re.fullmatch(
        r"(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", value
    ):
        raise SetupRefused(
            "domain_invalid",
            "give the public DNS name that points at this host, e.g. "
            "validator.example.org (lower case, no scheme or path).",
        )
    return value


def write_proxy(installed_state: Path, domain: str) -> dict:
    """A Caddy configuration serving each receiver at https://DOMAIN/ID/VERSION
    (TLS by Caddy's automatic certificates), and the endpoint entries to add to
    Carbon's published-endpoints list. The receivers stay on 127.0.0.1."""
    from carbon.development_session.intake_targets import intake_url

    domain = _domain(domain)
    host = read_host(installed_state)
    if host is None or not host["receivers"]:
        raise SetupRefused(
            "validator_host_not_set_up", "run --setup with --hotkey first."
        )
    lines = [f"{domain} {{"]
    entries = []
    for entry in host["receivers"]:
        challenge = entry["challenge"]
        prefix = f"/{challenge['id']}/{challenge['version']}"
        lines += [
            f"    handle_path {prefix}/* {{",
            f"        reverse_proxy 127.0.0.1:{entry['port']}",
            "    }",
        ]
        network = json.loads(
            (
                Path(entry["receiver_state"]) / "environment" / "miner-network.json"
            ).read_bytes()
        )["context"]
        url = f"https://{domain}{prefix}"
        if not intake_url(url):
            raise SetupRefused("domain_invalid", "the intake URL is not valid.")
        entries.append(
            {
                "network": network["network"],
                "netuid": network["netuid"],
                "challenge": challenge["id"],
                "version": challenge["version"],
                "intake_url": url,
                "receiver_hotkey": host["hotkey"],
            }
        )
    lines += ["    respond 404", "}", ""]
    root = _host_dir(installed_state)
    (root / CADDY_FILE).write_bytes("\n".join(lines).encode("utf-8"))
    _write_private(
        root / ENDPOINTS_FILE,
        _canonical({"add_to": PUBLISHED, "endpoints": entries}),
    )
    return {
        "caddyfile": str(root / CADDY_FILE),
        "endpoint_entries": str(root / ENDPOINTS_FILE),
        "intake_urls": [e["intake_url"] for e in entries],
        "next": (
            "install Caddy, point it at the Caddyfile (sudo caddy run --config "
            "PATH, or copy it to /etc/caddy/Caddyfile), open port 443, then send "
            "the endpoint entries to Carbon to list them for miners."
        ),
    }


def status(installed_state: Path, *, receiver_status=None) -> dict:
    """Every receiver's status (E7); healthy only when all are."""
    receiver_status = receiver_status or receiver_setup.status
    host = read_host(installed_state)
    if host is None:
        raise SetupRefused(
            "validator_host_not_set_up", "run install_validator.sh --setup first."
        )
    rows = []
    for entry in host["receivers"]:
        try:
            rows.append(receiver_status(Path(entry["receiver_state"])))
        except (SetupRefused, ValueError, OSError):
            rows.append(
                {
                    "status": "RECEIVER_NOT_HEALTHY",
                    "challenge": entry["challenge"],
                    "service": "unknown",
                    "intake": "UNREADABLE",
                }
            )
    healthy = bool(rows) and all(r["status"] == "RECEIVER_HEALTHY" for r in rows)
    return {
        "status": "VALIDATOR_HEALTHY" if healthy else "VALIDATOR_NOT_HEALTHY",
        "hotkey": host["hotkey"],
        "receivers": rows,
        # Weights are set by the separate weights service, owner-gated; not here.
        "weights": "NOT_SET_BY_RECEIVERS",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -B -m carbon.challenge_validator.validator_host"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    up = sub.add_parser("setup")
    up.add_argument("--installed-state", type=Path, required=True)
    up.add_argument("--hotkey", required=True)
    up.add_argument("--challenges", default="current")
    up.add_argument("--packs", type=Path)
    up.add_argument("--domain")
    up.add_argument("--base-port", type=int, default=DEFAULT_BASE_PORT)
    proxy = sub.add_parser("proxy")
    proxy.add_argument("--installed-state", type=Path, required=True)
    proxy.add_argument("--domain", required=True)
    shown = sub.add_parser("status")
    shown.add_argument("--installed-state", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            result = status(args.installed_state)
            print(json.dumps(result, sort_keys=True, indent=2))
            return 0 if result["status"] == "VALIDATOR_HEALTHY" else 3
        if args.command == "proxy":
            result = write_proxy(args.installed_state, args.domain)
        else:
            result = setup(
                installed_state=args.installed_state,
                hotkey=args.hotkey,
                challenges=select(args.challenges),
                packs=args.packs,
                domain=args.domain,
                base_port=args.base_port,
            )
    except SetupRefused as refusal:
        print(
            json.dumps({"refused": refusal.code, "next": refusal.next_step}),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
