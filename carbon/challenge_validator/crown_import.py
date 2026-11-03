"""A sitting king's crown-average MEASUREMENT, made on a non-serving spare and filed on the live receiver (Validator 06:56,
condition C10 of the crown switch-on).

Re-measuring a king takes N rebuilds (40-75 min). The live door cannot stop that long, and a hand import of a mean is not
allowed. So the spare receiver, at the SAME revision and images with copies of the king's entry and pack, re-measures the
king (`lean_recipe_retention.remeasure_incumbent_pack`) and writes a measurement record (`write_record`). The live receiver,
stopped for seconds under the same lock gate as the origin rebind, verifies the record against ITS OWN configuration, store
and key (`import_record`) and files the mean through the same `PoolStore.record_crown_average` the re-measure uses.

What the record binds, every field checked on import (a differing field refuses with ``crown_import_<field>_differs`` and
files nothing):
- ``submission_id``: the live store's incumbent; ``evaluation_key``: the key it was measured under;
- ``entry``: the king's retained entry id and the digest of its retained entry directory (every file's relative path and sha256);
- ``binding``: the receiver's identity (`BOUND_KEYS` of its write-once receiver binding: implementation, worker and
  inference images, construction parents, GPU images and devices, evaluation pack digest, Challenge). The
  ``implementation`` (the code revision) is compared apart (Validator 07:37 / 07:46): a record measured at another
  revision imports only when the operator names that measured revision in full (``--accept-measured-revision``), and
  the acceptance is logged and returned; every other binding field must be equal;
- ``key_id``: HMAC-SHA256 of a fixed label under K_crown (proves the same K_crown; the key never leaves either host);
- ``rule``: the crown-average rule's version, seed range, N and registered margin for the Challenge;
- ``private``: the filed private body itself (seeds, N, margin, then the totals and their mean, or the statuses of an unstable
  king). On import the seeds are DERIVED again with the live K_crown and must equal the record's; a mean must be
  ``fsum(totals) / N``.
- ``record_mac``: HMAC-SHA256 under K_crown over the whole record (`record_mac`), so nothing in it, an edited total with a
  matching mean included, files without the key. ``write_record`` with ``outcome`` None (``--record-only``) records a
  measurement the spare filed earlier, with no rebuild.

The record and the filed body are private (seeds and totals never leave the validator host); the file is written 0600.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
from pathlib import Path

from carbon.challenge_validator import crown_average

SCHEMA = "carbon.challenge-validator.crown-measurement-import.v1"
KEY_ID_LABEL = b"carbon.crown.key-id.v1\x00"
#: The record MAC's domain (Validator 07:28 condition 1): HMAC-SHA256 under K_crown over the canonical record without its
#: ``record_mac``, so no field (an edited total with a matching mean included) changes without K_crown.
RECORD_MAC_DOMAIN = b"carbon.crown.measurement-record-mac.v1\x00"
#: The receiver-binding fields a measurement depends on (direct_receiver's write-once ``receiver-binding.json``). The hotkey
#: and the chain context are left out: a spare is the same model on the same images, not the same door.
BOUND_KEYS = (
    "schema",
    "implementation",
    "parent",
    "inference_image",
    "construction_parents",
    "gpu_construction_device",
    "evaluation_pack_digest",
    "graph_gpu_image",
    "graph_gpu_ops_digest",
    "graph_gpu_device",
    "challenge",
    "measure_query",
    "material_cache_bytes",
)
#: The re-measure outcomes a record may carry: a mean (KING_MEASURED) or an unstable king (KING_UNSTABLE).
FILED = (crown_average.KING_MEASURED, crown_average.KING_UNSTABLE)


class ImportRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def bound(receiver_binding):
    """The measurement-relevant part of a receiver binding (`BOUND_KEYS` present in it)."""
    return {k: receiver_binding[k] for k in BOUND_KEYS if k in receiver_binding}


def key_id(key):
    """K_crown's public identity: HMAC-SHA256 of `KEY_ID_LABEL` under it (hex)."""
    if type(key) is not bytes or not key:
        raise ImportRefused("crown_import_key_unavailable")
    return hmac.new(key, KEY_ID_LABEL, hashlib.sha256).hexdigest()


def record_mac(key, record):
    """HMAC-SHA256 under K_crown over `RECORD_MAC_DOMAIN` and the canonical record without ``record_mac`` (hex)."""
    body = {k: v for k, v in record.items() if k != "record_mac"}
    return hmac.new(
        key, RECORD_MAC_DOMAIN + _canonical(body).encode(), hashlib.sha256
    ).hexdigest()


def rule_identity(rule, challenge_id):
    return {
        "version": rule.version,
        "seed_range": rule.seed_range,
        "n": rule.n_for(challenge_id),
        "margin": rule.margin_for(challenge_id),
        "margin_digest": rule.margin_digest_for(challenge_id),
    }


def entry_digest(directory):
    """sha256 over every regular file of the retained entry directory: its relative path and its bytes' sha256, sorted.
    A symlink or any other kind of entry refuses."""
    root = Path(directory)
    if not root.is_dir() or root.is_symlink():
        raise ImportRefused("crown_import_entry_unavailable")
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ImportRefused("crown_import_entry_link")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ImportRefused("crown_import_entry_unavailable")
        files.append(
            [
                path.relative_to(root).as_posix(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            ]
        )
    return "sha256:" + hashlib.sha256(_canonical(files).encode()).hexdigest()


def filed_private(store, submission_id, evaluation_key):
    """The private body ``record_crown_average`` filed for this king and key, or None."""
    op = store._bank_operation("crown_average.v1", submission_id, evaluation_key)
    with store.db() as db:
        row = db.execute(
            "SELECT kind,state,body FROM operations WHERE op_id=?", (op,)
        ).fetchone()
    if row is None or row[:2] != ("crown_average.v1", "RECORDED"):
        return None
    found = json.loads(row[2])
    if (
        found.get("submission_id") != submission_id
        or found.get("evaluation_key") != evaluation_key
    ):
        return None
    return found.get("private")


def _record(
    *, active, challenge_id, submission_id, evaluation_key, entry, binding, private
):
    record = {
        "schema": SCHEMA,
        "submission_id": submission_id,
        "evaluation_key": evaluation_key,
        "entry": entry,
        "binding": bound(binding),
        "key_id": key_id(active._key),
        "rule": rule_identity(active.rule, challenge_id),
        "private": private,
    }
    record["record_mac"] = record_mac(active._key, record)
    return record


def write_record(
    path,
    *,
    outcome,
    active,
    store,
    challenge_id,
    submission_id,
    evaluation_key,
    entry_id,
    entry_directory,
    receiver_binding,
):
    """After a spare re-measure that filed (`FILED` outcomes), write its measurement record to ``path`` (new file, 0600).
    Any other outcome writes nothing and refuses. ``outcome`` None is the write-only mode (`--record-only`): the spare
    re-measured earlier and filed; the record is written from that filed body, with no rebuild.
    """
    if outcome is not None and outcome not in FILED:
        raise ImportRefused("crown_import_nothing_filed")
    private = filed_private(store, submission_id, evaluation_key)
    if private is None:
        raise ImportRefused("crown_import_nothing_filed")
    record = _record(
        active=active,
        challenge_id=challenge_id,
        submission_id=submission_id,
        evaluation_key=evaluation_key,
        entry={"id": entry_id, "digest": entry_digest(entry_directory)},
        binding=receiver_binding,
        private=private,
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(_canonical(record) + "\n")
    return record


def _check_private(private, *, active, challenge_id, submission_id, rule):
    if type(private) is not dict:
        raise ImportRefused("crown_import_private_invalid")
    n = rule["n"]
    seeds = crown_average.derive_seeds(
        active._key, challenge_id, submission_id, n, active.rule.seed_range
    )
    if private.get("seeds") != seeds:
        raise ImportRefused("crown_import_seeds_differs")
    if private.get("n") != n or private.get("margin") != rule["margin"]:
        raise ImportRefused("crown_import_rule_differs")
    if "totals" in private or "mean" in private:
        totals = private.get("totals")
        if (
            type(totals) is not list
            or len(totals) != n
            or not all(type(t) in (int, float) and math.isfinite(t) for t in totals)
            or private.get("mean") != math.fsum(totals) / n
            or set(private) != {"seeds", "n", "margin", "totals", "mean"}
        ):
            raise ImportRefused("crown_import_mean_differs")
    elif set(private) != {"seeds", "n", "margin", "statuses"} or not (
        type(private["statuses"]) is list and len(private["statuses"]) == n
    ):
        raise ImportRefused("crown_import_private_invalid")


def import_record(
    path,
    *,
    active,
    store,
    challenge_id,
    evaluation_key,
    entry_id,
    entry_directory,
    receiver_binding,
    accept_measured_revision=None,
):
    """Verify the spare's measurement record at ``path`` against THIS receiver and file its private body. Returns
    ``{"state": "CROWN_MEASUREMENT_IMPORTED", "submission_id", "evaluation_key"}`` (plus ``accepted_measured_revision``
    when a record from another revision was accepted); a differing field refuses (`ImportRefused`) with nothing filed.
    Filing the same record twice is a no-op."""
    if active is None:
        raise ImportRefused("crown_import_rule_not_installed")
    try:
        record = json.loads(Path(path).read_bytes())
    except (OSError, ValueError) as error:
        raise ImportRefused("crown_import_record_unreadable") from error
    names = {
        "schema",
        "submission_id",
        "evaluation_key",
        "entry",
        "binding",
        "key_id",
        "rule",
        "private",
        "record_mac",
    }
    if type(record) is not dict or set(record) != names or record["schema"] != SCHEMA:
        raise ImportRefused("crown_import_record_invalid")
    if record["key_id"] != key_id(active._key):
        raise ImportRefused("crown_import_key_id_differs")
    if type(record["record_mac"]) is not str or not hmac.compare_digest(
        record["record_mac"], record_mac(active._key, record)
    ):
        raise ImportRefused("crown_import_record_mac_differs")
    submission_id = record["submission_id"]
    king = store.incumbent()
    if king is None or king.get("model_id") != submission_id:
        raise ImportRefused("crown_import_submission_id_differs")
    if record["evaluation_key"] != evaluation_key:
        raise ImportRefused("crown_import_evaluation_key_differs")
    if record["entry"] != {"id": entry_id, "digest": entry_digest(entry_directory)}:
        raise ImportRefused("crown_import_entry_differs")
    measured, live = dict(record["binding"]), bound(receiver_binding)
    measured_impl, live_impl = measured.pop("implementation", None), live.pop(
        "implementation", None
    )
    if measured != live:
        raise ImportRefused("crown_import_binding_differs")
    accepted = None
    if measured_impl != live_impl:
        revision = (measured_impl or {}).get("revision")
        if (
            type(accept_measured_revision) is not str
            or len(accept_measured_revision) != 40
            or accept_measured_revision != revision
        ):
            raise ImportRefused("crown_import_implementation_differs")
        accepted = revision
    rule = rule_identity(active.rule, challenge_id)
    if record["rule"] != rule:
        raise ImportRefused("crown_import_rule_differs")
    _check_private(
        record["private"],
        active=active,
        challenge_id=challenge_id,
        submission_id=submission_id,
        rule=rule,
    )
    from carbon.battery.pool_store import StateError

    try:
        store.record_crown_average(submission_id, evaluation_key, record["private"])
    except (
        StateError
    ) as error:  # a different record already filed for this king and key
        raise ImportRefused("crown_import_record_changed") from error
    result = {
        "state": "CROWN_MEASUREMENT_IMPORTED",
        "submission_id": submission_id,
        "evaluation_key": evaluation_key,
    }
    if accepted is not None:
        import logging

        logging.getLogger(__name__).warning(
            "crown measurement imported across revisions: measured at %s, filed at %s",
            accepted,
            (live_impl or {}).get("revision"),
        )
        result["accepted_measured_revision"] = accepted
    return result
