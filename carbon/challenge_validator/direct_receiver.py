"""Finite operator bootstrap for the existing signed DEVELOPMENT recipe intake.

The installed profile supplies trusted source, image and chain identities. An
authenticated hotkey selects only its own durable task workspace. This module
never holds a signer, builds an image or imports participant construction code.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import signal
import threading
from pathlib import Path

from carbon.development_session.data import write_once
from carbon.development_session.intake_targets import ADDRESS, intake_url
from carbon.development_session.private_records import private_json
from carbon.development_session.profile import canonical

SCHEMA = "carbon.construction.direct-receiver-operator.v1"
_FIELDS = {
    "schema",
    "root",
    "runner_profile",
    "receiver_hotkey",
    "host",
    "port",
    "lifetime_seconds",
    "measure_query",
}


class ReceiverUnavailable(RuntimeError):
    """A named operator/infrastructure refusal; never a scientific result."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def load_config(path: Path) -> dict:
    """Read the closed bounded private record; miner calls select no paths."""
    value = private_json(path)
    if (
        type(value) is not dict
        or set(value) != _FIELDS
        or value.get("schema") != SCHEMA
        or value.get("host") not in ("127.0.0.1", "localhost")
        or type(value.get("port")) is not int
        or not 1 <= value["port"] <= 65535
        or type(value.get("lifetime_seconds")) is not int
        or not 0 < value["lifetime_seconds"] < 2**31
        or type(value.get("measure_query")) is not bool
        or type(value.get("receiver_hotkey")) is not str
        or not ADDRESS.fullmatch(value["receiver_hotkey"])
    ):
        raise ValueError("invalid DEVELOPMENT receiver configuration")
    for name in ("root", "runner_profile"):
        if type(value[name]) is not str:
            raise ValueError("operator path required")
        selected = Path(value[name])
        if not selected.is_absolute() or selected.resolve() != selected:
            raise ValueError("exact private operator path required")
    return value


def _private_directory(path: Path) -> Path:
    if not path.is_absolute() or path.resolve() != path or path.is_symlink():
        raise ValueError("exact private operator directory required")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir() or path.stat().st_mode & 0o077:
        raise ValueError("owner-only operator directory required")
    return path


def installed_source(profile_path: Path):
    """Verify maintained accepted source/image/chain without opening a signer."""
    from carbon.development_session.miner_network import binding
    from carbon.development_session.research_campaign import (
        accepted_implementation,
        verify_current_worker,
    )
    from carbon.reconstruction.worker.docker_runtime import doctor, load_image_identity
    from scripts.dev.miner_launchpad.runner import validated_profile

    cfg = validated_profile(private_json(profile_path))
    if cfg["enabled"] is not True:
        raise ValueError("installed dispatch is disabled")
    implementation = accepted_implementation(cfg["accepted_revision"])
    paths = {name: Path(value) for name, value in cfg["paths"].items()}
    parent = load_image_identity(Path(cfg.get("gpu_image", paths["image_manifest"])))
    verify_current_worker(parent, implementation)
    if not doctor(image_id=parent.image_id, image_identity=parent).eligible:
        raise ReceiverUnavailable("installed_reconstruction_worker_unavailable")
    network = binding(
        operator_config=paths.get("operator_config"),
        miner_network=paths.get("miner_network"),
    )
    cache = Path(cfg["campaigns_root"]) / ".direct-development" / "library-cache"
    if not cache.is_absolute() or cache.resolve() != cache or cache.is_symlink():
        raise ValueError("installed library cache path differs")
    return implementation, parent, network, cache


class OwnerProviders:
    """One maintained task supervisor and ledger per authenticated hotkey."""

    def __init__(self, root, discovery, parent, cache_root):
        self.root, self.discovery = root, discovery
        self.parent, self.cache_root = parent, cache_root
        self._lock = threading.RLock()
        self._providers = {}
        self._closing = False

    def __call__(self, hotkey):
        from carbon.challenge_validator.interface import Unavailable
        from carbon.development_session.research_ledger import CampaignLedger
        from carbon.development_session.research_tasks import DirectDevelopmentTasksV3
        from carbon.miner_mcp.standard_cli import DirectOwnerImageResolver

        if type(hotkey) is not str or not ADDRESS.fullmatch(hotkey):
            raise Unavailable("direct_provider_owner_invalid")
        with self._lock:
            if self._closing:
                raise Unavailable("direct_receiver_stopping")
            if hotkey not in self._providers:
                directory = _private_directory(
                    self.root / hashlib.sha256(hotkey.encode()).hexdigest()
                )
                write_once(directory / "owner.json", canonical({"hotkey": hotkey}))
                self._providers[hotkey] = DirectDevelopmentTasksV3(
                    root=directory / "tasks",
                    requester=hotkey,
                    owner=hotkey,
                    ledger=CampaignLedger(directory / "ledger"),
                    discovery=self.discovery,
                    image=None,
                    inference_image=self.parent,
                    image_resolver=DirectOwnerImageResolver(
                        self.cache_root, self.parent
                    ),
                )
            return self._providers[hotkey]

    def restore(self):
        """Reopen every retained owner before listening, including interrupted work."""
        for directory in sorted(self.root.iterdir()):
            _private_directory(directory)
            owner = private_json(directory / "owner.json")
            if (
                type(owner) is not dict
                or set(owner) != {"hotkey"}
                or type(owner["hotkey"]) is not str
                or hashlib.sha256(owner["hotkey"].encode()).hexdigest()
                != directory.name
            ):
                raise ValueError("retained receiver owner binding differs")
            self(owner["hotkey"])

    def cancel(self):
        """Close admission and request only our providers' domain cancellation."""
        with self._lock:
            self._closing = True
            providers = tuple(self._providers.values())
        errors = []
        for provider in providers:
            with provider._lock:
                views = tuple(provider._views.values())
            for view in views:
                try:
                    provider.cancel_observed_task(
                        view.task_id, self.discovery.info.challenge_key
                    )
                except Exception as failure:  # noqa: BLE001 - cancel all owned tasks
                    errors.append(type(failure).__name__)
        if errors:
            raise ReceiverUnavailable("direct_receiver_cancellation_unresolved")

    def close(self):
        """Release no provider lock while its children need reconciliation."""
        providers = tuple(self._providers.values())
        if any(
            provider.requires_reconciliation(view.task_id)
            for provider in providers
            for view in tuple(provider._views.values())
        ):
            raise ReceiverUnavailable("direct_receiver_cleanup_unresolved")
        for provider in providers:
            provider.close()


def serve(config_path: Path, *, stop=None, reader=None, verifier=None, ready=None):
    """Run the same signed intake/task loop with finite admission and owned stop."""
    from dataclasses import asdict

    from carbon.battery.intake import SnapshotWindow
    from carbon.chain.auth import BittensorHotkeyVerifier
    from carbon.chain.sdk import BittensorReader
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
    from carbon.challenge_validator.direct_intake import (
        DirectRecipeIntake,
        serve_loopback,
    )
    from carbon.challenge_validator.ledger import AttemptLedger
    from carbon.development_session.research_service import DirectFixtureDiscovery
    from carbon.transport.store import ReceiptJournal
    from scripts.dev.miner_launchpad.controller import owner_lock

    cfg = load_config(config_path)
    implementation, parent, network, cache = installed_source(
        Path(cfg["runner_profile"])
    )
    if cfg["receiver_hotkey"] != network.publisher_hotkey:
        raise ValueError("receiver differs from installed network publisher")
    stop = threading.Event() if stop is None else stop
    reader = BittensorReader() if reader is None else reader
    snapshot = asyncio.run(reader.capture(network.context))
    if (
        snapshot.context != network.context
        or snapshot.resolve(cfg["receiver_hotkey"]) is None
    ):
        raise ValueError("registered receiver snapshot required")
    window = SnapshotWindow()
    window.add(snapshot)
    root = _private_directory(Path(cfg["root"]))
    discovery = DirectFixtureDiscovery(bundle_material_v5(), task_admission=True)
    immutable = {
        "schema": SCHEMA,
        "implementation": implementation,
        "parent": asdict(parent),
        "context": asdict(network.context),
        "receiver_hotkey": cfg["receiver_hotkey"],
        "challenge": {
            "id": discovery.info.challenge_key.challenge_id,
            "version": discovery.info.challenge_key.version,
        },
        "measure_query": cfg["measure_query"],
    }
    with owner_lock(root):
        write_once(root / "receiver-binding.json", canonical(immutable))
        providers = OwnerProviders(
            _private_directory(root / "owners"), discovery, parent, cache
        )
        timer = threading.Timer(cfg["lifetime_seconds"], stop.set)
        timer.daemon = True

        def listening(address):
            target = {
                "intake_url": f"http://{cfg['host']}:{address[1]}",
                "receiver_hotkey": cfg["receiver_hotkey"],
            }
            if not intake_url(target["intake_url"]):
                raise ValueError("invalid listening target")
            if ready is not None:
                ready(
                    {
                        "schema": SCHEMA,
                        "state": "LISTENING",
                        "direct_intake_target": target,
                        "qualification": False,
                        "reward": False,
                    }
                )

        try:
            providers.restore()
            intake = DirectRecipeIntake(
                context=network.context,
                receiver=cfg["receiver_hotkey"],
                journal=ReceiptJournal(root / "transport.sqlite3", network.context),
                verifier=BittensorHotkeyVerifier() if verifier is None else verifier,
                window=window,
                discovery=discovery,
                provider_for=providers,
                attempt_ledger=AttemptLedger(root / "attempts.sqlite3"),
                measure_query=cfg["measure_query"],
            )
            timer.start()
            serve_loopback(
                intake,
                {"host": cfg["host"], "port": cfg["port"]},
                stop=stop,
                reader=reader,
                ready=listening,
                closing=providers.cancel,
            )
        finally:
            stop.set()
            timer.cancel()
            # The shared listener waits for its worker, even if cancellation
            # raises. No worker or carrier is reimplemented here.
            try:
                providers.cancel()
            finally:
                providers.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m carbon.challenge_validator.direct_receiver"
    )
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    stop = threading.Event()
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: stop.set())
    try:
        serve(
            args.config,
            stop=stop,
            ready=lambda item: print(json.dumps(item), flush=True),
        )
    except Exception as failure:  # noqa: BLE001 - no private exception text
        code = getattr(failure, "code", None)
        if type(code) is not str:
            code = "direct_receiver_unavailable"
        print(json.dumps({"unavailable": code}), flush=True)
        return 1
    print(json.dumps({"schema": SCHEMA, "state": "STOPPED"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
