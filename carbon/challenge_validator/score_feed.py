"""A validator's public score feed (VALIDATOR-29): released windows only.

Under rule v2's SEALED disclosure (OWNER-BATTERY-3B-AND-EXPOSURE-01), nothing
computed from a hidden window is shown before the window is **released**:
every case it drew is retired and published in the Challenge's public training
pool. A submission appears only when every window its score used is released.
Under the bank a case retires after E draws, so the feed lags the pool by
about E rotations; its `release` metadata says so.

- **Release records** (`record_releases`): the public training listing is
  read, each file is verified in full (`training_pool.verify`: producer
  signature, records digest, every Merkle proof), and its case ids are
  recorded. Nothing unverified counts.
- **The document** (`build`): `carbon.validator.score-feed.v1`. It holds the
  released windows; each released submission's sections (accuracy, the
  design-q leg, gates, near-limit) rounded to the registered precision; and
  a lagged leaderboard (incumbent, challengers, standing, history).
  - Canary hotkeys never appear; only their count does.
  - It is labelled DEVELOPMENT, and TESTNET on testnet.
  - It is signed by the validator's feed key and versioned whenever it
    changes.
- **Signed bytes:** `FEED_DOMAIN` followed by the feed without its
  `signature` field, as `json.dumps(sort_keys=True, separators=(",", ":"),
  allow_nan=False, ensure_ascii=True)` encoded UTF-8. The feed key is pinned
  out of band (`verify_feed(feed, pinned_key=…)`); the in-document
  `feed_key` is informational.
- **Values** (`VALUES`): registered by the Test Lead, 2026-10-08. Released
  data is shown at precision 0.001 with no display threshold, because its
  cases are public. The live feed (item 1) is unregistered and refused until
  the owner's record.

    python -m carbon.challenge_validator.score_feed keygen --out FEED.key
    python -m carbon.challenge_validator.score_feed releases --config FETCH.json
    python -m carbon.challenge_validator.score_feed build --deployment DEPLOYMENT.json --key FEED.key --hotkey SS58 --network testnet --out FEED.json

`--out` is the file the validator's door serves at
`GET /carbon/v1/feed/<challenge>` (the intake's `feed` key). It is written
atomically, and the door serves it only when its signature verifies.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
FEED_SCHEMA = "carbon.validator.score-feed.v1"
FEED_DOMAIN = b"carbon.validator.score-feed.v1\x00"
#: Registered by the Test Lead, 2026-10-08 (VALIDATOR-29). Released data's
#: cases are public, so no display threshold applies to it.
VALUES = {
    "registered": "Test Lead, 2026-10-08 (VALIDATOR-29)",
    "released": {"precision": 0.001, "display_threshold": None},
    # Item 1, live scores on unreleased windows: refused until the owner's
    # record (it would reverse the SEALED disclosure).
    "live": None,
}
#: The registered public showcase task (VALIDATOR-29 showcase; the Test
#: Lead, 2026-10-08): EV4's public synthetic decision contract, its
#: development scenarios, pinned by the contract file's sha256. The leader's
#: rebuilt model is queried on these public inputs only; the dashboard runs
#: Carbon's optimizer on the panel against the public reference truth.
SHOWCASE = {
    "task_id": "ev4-charge-protocol-selection.v1:development",
    "contract": "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json",
    "contract_sha256": "fc6f504f3ff69b3add10099056b7a652a28112d3ca1d63ada2fb194aac2d3e18",
    "split": "development",
    "data_scope": "PUBLIC_SYNTHETIC",
    "registered": "Test Lead, 2026-10-08 (VALIDATOR-29 showcase)",
}
SHOWCASE_SCHEMA = "carbon.validator.showcase-panel.v1"
#: Showcase predictions are stored apart from every scored, quiz and design one.
SHOWCASE_PREDICTIONS = "showcase/"
SECTIONS = ("accuracy", "design_q", "near_limit")
#: How a dashboard shows each section: its name, unit and sense (battery's
#: scores are lower-is-better; the design q is higher-is-better).
SECTION_META = {
    "accuracy": {
        "display": "Accuracy",
        "unit": "battery score",
        "sense": "lower_is_better",
    },
    "design_q": {"display": "Design q", "unit": "q", "sense": "higher_is_better"},
    "near_limit": {
        "display": "Near-limit accuracy",
        "unit": "battery score",
        "sense": "lower_is_better",
    },
    "gates": {"display": "Safety gates", "unit": "PASS/FAIL", "sense": None},
}


class FeedRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=True
    )


# --- the feed key -------------------------------------------------------------------


class FeedKey:
    """The validator's feed signing key: ed25519, owner-only, never printed."""

    def __init__(self, raw):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
        )

        self._key = Ed25519PrivateKey.from_private_bytes(raw)

    def __repr__(self):
        return "FeedKey(<redacted>)"

    def __reduce__(self):
        raise TypeError("a feed key is never pickled")

    @classmethod
    def create(cls, path):
        path = Path(path)
        raw = os.urandom(32)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        return cls(raw)

    @classmethod
    def load(cls, path):
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise FeedRefused("feed_key_not_owner_only")
        raw = Path(path).read_bytes()
        if len(raw) != 32:
            raise FeedRefused("feed_key_malformed")
        return cls(raw)

    @property
    def public_key(self):
        from cryptography.hazmat.primitives import serialization

        return (
            self._key.public_key()
            .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
            .hex()
        )

    def sign(self, document):
        return self._key.sign(FEED_DOMAIN + _canonical(document).encode()).hex()


def verify_feed(feed, pinned_key=None):
    """Whether a feed's signature is its feed key's, over the document without
    the signature. With `pinned_key` (the key a reader configured out of
    band), the feed must name exactly that key."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        if pinned_key is not None and feed["validator"]["feed_key"] != pinned_key:
            return False
        body = {k: v for k, v in feed.items() if k != "signature"}
        Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(feed["validator"]["feed_key"])
        ).verify(
            bytes.fromhex(feed["signature"]), FEED_DOMAIN + _canonical(body).encode()
        )
    except (InvalidSignature, KeyError, TypeError, ValueError):
        return False
    return True


# --- release records ----------------------------------------------------------------


def record_releases(store, fetch, challenge_id, producer_public_key):
    """Verify every listed training file and record its case ids. `fetch`
    maps a path under `/carbon/v1/training/` to `(status, value)`. Returns
    counts."""
    from .training_pool import TRAINING_PATH, TrainingRefused, verify

    status, listing = fetch(f"{TRAINING_PATH}{challenge_id}")
    if status != 200 or type(listing) is not dict:
        raise FeedRefused("feed_training_unavailable")
    files, added, refused = 0, 0, 0
    for entry in listing.get("files", []):
        name = entry.get("file") if type(entry) is dict else None
        if type(name) is not str:
            continue
        status, value = fetch(f"{TRAINING_PATH}{challenge_id}/{name}")
        try:
            if status != 200:
                raise TrainingRefused("training_unavailable")
            manifest = verify(value, producer_public_key)
            if manifest["challenge_id"] != challenge_id:
                raise TrainingRefused("training_unknown_challenge")
        except TrainingRefused:
            refused += 1
            continue
        files += 1
        added += store.record_published(name, [r["case_id"] for r in value["records"]])
    return {"files": files, "refused": refused, "new_cases": added}


def released_windows(store):
    """`{fingerprint: drawn case ids}` for every window whose drawn cases are
    all published. A hidden duplicate is a copy of a drawn case, so it
    releases with its original."""
    from carbon.battery.seeds import PrivateBatch

    published = store.published_case_ids()
    found = {}
    for fingerprint in store.batch_fingerprints():
        batch = PrivateBatch.from_document(store.batch(fingerprint)["document"])
        duplicates = {dup for dup, _ in batch.duplicates}
        drawn = {case_id for case_id, _ in batch.cases if case_id not in duplicates}
        if drawn and drawn <= published:
            found[fingerprint] = drawn
    return found


# --- the document -------------------------------------------------------------------


def _round(value, precision):
    if value is None:
        return None
    digits = max(0, -round(math.log10(precision)))
    return round(float(value), digits)


def _sections(target, row, released):
    record = row["record"]
    precision = VALUES["released"]["precision"]
    design = target.store.design_report(row["submission_id"])
    design_q = None
    if design is not None and design.get("state") == "MEASURED":
        qs = [
            w["q"]
            for f, w in design["batches"].items()
            if f in released and w.get("status") == "OK" and w.get("q") is not None
        ]
        design_q = sum(qs) / len(qs) if qs else None
    gates = {"eligible": "PASS" if record.get("eligible") else "FAIL"}
    gates.update({str(g): "FAIL" for g in record.get("gate_failures") or []})
    return {
        "accuracy": _round(record.get("score"), precision),
        "design_q": _round(design_q, precision),
        "gates": gates,
        "near_limit": _round(record.get("important_score"), precision),
    }


def showcase(target, incumbent, repository=REPOSITORY):
    """The released incumbent's predictions on the registered public
    showcase task, or None when no incumbent is released. Public inputs only;
    the panel carries the model's identity digest and predicted quantities,
    never its recipe. An inference failure is the showcase's own state."""
    from carbon.battery.pool_store import StateError
    from carbon.battery.value import contract as ev
    from carbon.battery.worker import WorkerFailure
    from carbon.design_search import battery_q3_v8 as v8

    if incumbent is None:
        return None
    path = Path(repository) / SHOWCASE["contract"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHOWCASE["contract_sha256"]:
        raise FeedRefused("feed_showcase_contract_changed")
    contract, contract_digest = ev.load(path)
    if (contract.get("data_scope") or {}).get("classification") != SHOWCASE[
        "data_scope"
    ]:
        raise FeedRefused("feed_showcase_not_public")
    jobs = ev.decision_cases(contract, SHOWCASE["split"])
    inputs = {
        job["case_id"]: {k: job[k] for k in ("c1", "c2", "t_amb_c", "soc0")}
        for job in jobs
    }
    model_id = incumbent["submission_id"]
    head = {
        "schema": SHOWCASE_SCHEMA,
        "task": SHOWCASE,
        "contract_digest": contract_digest,
        "model": {"hotkey": incumbent["hotkey"], "submission_id": model_id},
    }
    try:
        state = target.store.model_state(model_id)
        if state is None:
            return {**head, "state": "UNAVAILABLE", "code": "model_not_retained"}
        predictions = target._quiz_predictions(
            model_id, inputs, "showcase", namespace=SHOWCASE_PREDICTIONS
        )
    except WorkerFailure as failure:
        return {**head, "state": "UNAVAILABLE", "code": failure.code}
    except StateError as refused:
        return {**head, "state": "UNAVAILABLE", "code": refused.code}
    # Each public case's predicted quantities, projected as v8 projects
    # truth (`battery_q3_v8._projection`): what the dashboard's replay feeds
    # Carbon's optimizer. A case the model gave no output for is left out.
    found = {}
    for job in jobs:
        values = v8._projection(
            contract, {"status": "OK", "outputs": predictions[job["case_id"]]}
        )
        if values is not None:
            found[job["case_id"]] = values
    return {
        **head,
        "state": "PREDICTED",
        "model": {**head["model"], "state_digest": state["digest"]},
        "predictions": found,
    }


def canary_hotkeys():
    """The registered canary hotkeys (OWNER-CANARY-LIST-01): excluded from
    every feed field. Empty until the record names them."""
    from .canary import CANARY_HOTKEYS

    return frozenset(CANARY_HOTKEYS)


def build(target, *, key, hotkey, network, device_class="cpu", with_showcase=False):
    """The signed feed for this validator's deployment and one device class,
    stored as a new version when it changed. Returns the feed. Scores of
    another class never appear in it (`rebuild_identity.require_one_class`):
    CPU and GPU are never ranked together."""
    if network not in ("testnet", "mainnet"):
        raise FeedRefused("feed_network_unknown")
    if type(device_class) is not str or not device_class:
        raise FeedRefused("feed_device_class_malformed")
    store = target.store
    identities = target.identities()
    rule = target.rule
    released = released_windows(store)
    canaries = canary_hotkeys()
    excluded = 0
    rows = []
    for row in store.scored_submissions():
        windows = list(row["record"].get("active_batches") or [])
        if not windows or not set(windows) <= set(released):
            continue
        if row["record"].get("device_class", "cpu") != device_class:
            continue
        if row["hotkey"] in canaries:
            excluded += 1
            continue
        rows.append(row)
    submissions = []
    for row in rows:
        submissions.append(
            {
                "hotkey": row["hotkey"],
                "submission_id": row["submission_id"],
                "receipt_block": (row["binding"].get("receipt") or {}).get("block"),
                "windows": sorted(row["record"]["active_batches"]),
                "state": row["state"],
                "device_class": row["record"].get("device_class", "cpu"),
                "sections": _sections(target, row, released),
            }
        )
    shown = {s["submission_id"]: s for s in submissions}
    # Standing: each hotkey's best eligible accuracy (battery: lower is
    # better), earliest first on a tie.
    best = {}
    for s in submissions:
        a = s["sections"]["accuracy"]
        if s["sections"]["gates"]["eligible"] != "PASS" or a is None:
            continue
        held = best.get(s["hotkey"])
        if held is None or a < held["best"]["accuracy"]:
            best[s["hotkey"]] = {
                "hotkey": s["hotkey"],
                "best": {"accuracy": a},
                "best_at_block": s["receipt_block"],
            }
    standing = sorted(
        best.values(), key=lambda b: (b["best"]["accuracy"], b["best_at_block"] or 0)
    )
    for rank, entry in enumerate(standing, start=1):
        entry["rank"] = rank
    incumbent = store.incumbent()
    incumbent_view = (
        {
            "hotkey": shown[incumbent["model_id"]]["hotkey"],
            "submission_id": incumbent["model_id"],
            "sections": shown[incumbent["model_id"]]["sections"],
        }
        if incumbent is not None and incumbent["model_id"] in shown
        else None
    )
    challengers = [
        {
            "hotkey": shown[f["challenger"]]["hotkey"],
            "submission_id": f["challenger"],
            "state": f["state"],
        }
        for f in store.finals_rows()
        if f["challenger"] in shown
    ]
    history = {}
    for s in sorted(submissions, key=lambda s: s["receipt_block"] or 0):
        history.setdefault(s["hotkey"], []).append(
            {"receipt_block": s["receipt_block"], "sections": s["sections"]}
        )
    bank = (rule.get("bank") or {}).get("pool") or {}
    rotation = (rule.get("rotation") or {}).get("every_blocks")
    document = {
        "schema": FEED_SCHEMA,
        "labels": ["DEVELOPMENT"] + (["TESTNET"] if network == "testnet" else []),
        "validator": {"hotkey": hotkey, "feed_key": key.public_key},
        "challenge": {
            "id": identities["challenge"]["id"],
            "version": identities["challenge"]["version"],
            "rule_digest": identities["rule_digest"],
        },
        "device_class": device_class,
        "values": {**VALUES, "showcase_task": SHOWCASE["task_id"]},
        "sections": SECTION_META,
        "release": {
            "predicate": "every case a window drew is retired and published",
            "retire_at": bank.get("retire_at"),
            "rotation_every_blocks": rotation,
            "expected_lag_blocks": (
                None
                if bank.get("retire_at") is None or rotation is None
                else bank["retire_at"] * rotation
            ),
        },
        "released_windows": sorted(released),
        "submissions": submissions,
        "leaderboard": {
            "incumbent": incumbent_view,
            "challengers": challengers,
            "standing": standing,
            "history": history,
        },
        "excluded": {"canary_hotkeys": excluded},
    }
    if with_showcase:
        # Driven by the released incumbent only: no new disclosure.
        document["showcase"] = showcase(target, incumbent_view)
    import datetime

    version = store.record_feed(document)
    generated = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    feed = {**document, "version": version, "generated_at": generated}
    return {**feed, "signature": key.sign(feed)}


def write_feed(path, feed):
    """Write the signed feed atomically for the door to serve."""
    path = Path(path)
    temporary = path.with_name(path.name + ".new")
    if temporary.exists():
        temporary.unlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    with os.fdopen(fd, "w") as handle:
        json.dump(feed, handle, sort_keys=True)
    os.replace(temporary, path)


def read_feed(path, challenge_id):
    """The signed feed at `path` for `challenge_id`, or None: unreadable,
    another Challenge's, or not verified by its own feed key."""
    try:
        feed = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    if (
        type(feed) is not dict
        or feed.get("schema") != FEED_SCHEMA
        or (feed.get("challenge") or {}).get("id") != challenge_id
        or not verify_feed(feed)
    ):
        return None
    return feed


# --- the command line ---------------------------------------------------------------


def _fetch_over_https(url, ca):
    import ssl
    import urllib.error
    import urllib.request

    context = None if ca is None else ssl.create_default_context(cafile=ca)

    def fetch(path):
        try:
            with urllib.request.urlopen(
                url.rstrip("/") + path, timeout=60, context=context
            ) as answer:
                return answer.status, json.loads(answer.read(64 * 2**20))
        except urllib.error.HTTPError as failure:
            return failure.code, None
        except (OSError, ValueError):
            return 0, None

    return fetch


def main(argv=None):
    parser = argparse.ArgumentParser(prog="carbon.challenge_validator.score_feed")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("keygen").add_argument("--out", required=True)
    sub.add_parser("releases").add_argument("--config", required=True)
    built = sub.add_parser("build")
    built.add_argument("--deployment", required=True)
    built.add_argument("--key", required=True)
    built.add_argument("--hotkey", required=True)
    built.add_argument("--network", required=True, choices=("testnet", "mainnet"))
    built.add_argument("--out", help="the signed feed file the door serves")
    built.add_argument("--device-class", default="cpu")
    built.add_argument(
        "--showcase",
        action="store_true",
        help="query the released incumbent on the public showcase task",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "keygen":
            result = {"public_key": FeedKey.create(args.out).public_key}
        elif args.command == "releases":
            from carbon.battery import deployment

            from .answer_key import load_fetch_config

            config = load_fetch_config(args.config)
            target = deployment.validator(
                Path(config["deployment"]), repository=REPOSITORY
            )
            with deployment.writer(target):
                result = record_releases(
                    target.store,
                    _fetch_over_https(config["url"], config.get("ca")),
                    config["challenge_id"],
                    config["producer_public_key"],
                )
        else:
            from carbon.battery import deployment

            target = deployment.validator(Path(args.deployment), repository=REPOSITORY)
            with deployment.writer(target):
                feed = build(
                    target,
                    key=FeedKey.load(args.key),
                    hotkey=args.hotkey,
                    network=args.network,
                    device_class=args.device_class,
                    with_showcase=args.showcase,
                )
            if args.out:
                write_feed(args.out, feed)
            result = {
                "version": feed["version"],
                "released_windows": len(feed["released_windows"]),
                "submissions": len(feed["submissions"]),
                "excluded": feed["excluded"],
            }
    except FeedRefused as refused:
        print(json.dumps({"refused": refused.code}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    # The package module's own main: under `python -m` this file is
    # `__main__`, a second copy whose classes the package's are not.
    from carbon.challenge_validator.score_feed import main as _main

    sys.exit(_main())


__all__ = [
    "VALUES",
    "FeedKey",
    "build",
    "record_releases",
    "released_windows",
    "verify_feed",
]
