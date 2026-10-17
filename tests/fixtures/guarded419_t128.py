"""Synthetic T128 raw delivery; never for runtime or prerequisite substitution.

The default factory is deliberately UNADMITTED: no fabricated CAL15 evidence.
The full factory requires the real CAL owner's nominal synthetic evidence/pins.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from carbon.design_search import tasks
from scripts.dev.score_lab import guarded419_t128 as t128

_spec = importlib.util.spec_from_file_location(
    "guarded419_t9_fixture_for_t128", Path(__file__).with_name("guarded419_t9.py")
)
t9_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(t9_fixture)


def record(job):
    row = t9_fixture.record(job)
    row["schema"] = t128.RECORD
    row["reference_identity"] = t128.observer(job["reference_role"])
    return row


def refresh_delivery(delivery, records):
    raw = b"".join((json.dumps(row, sort_keys=True) + "\n").encode() for row in records)
    binding = delivery["binding"]
    chunk = {
        "id": "synthetic-t128",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "source_commit": binding["execution_source"],
        "source_files": binding["source_files"],
        "rows": [{"line": i, "job_id": r["case_id"]} for i, r in enumerate(records, 1)],
    }
    manifest = t128.delivery_manifest(binding, [chunk])
    delivery.update(
        manifest=manifest,
        raw_chunks={chunk["id"]: raw},
        expected_manifest_digest=tasks.digest(manifest),
    )
    return delivery


def make_unadmitted_delivery(tmp_path, *, all_rows=False):
    """Real synthetic G0/T9 authentication, missing CAL15 by construction."""
    prior = t9_fixture.make_delivery(tmp_path / "t9")
    files = {p: "b" * 64 for p in t128.REQUIRED_SOURCES}
    files.update(prior["binding"]["source_files"])
    files[t128.INPUT_FILE] = t128.INPUT_FILE_SHA
    binding = t128.execution_binding(
        source_commit="c" * 40,
        source_files=files,
        prerequisites={
            "t9": {
                "binding_digest": prior["expected_binding_digest"],
                "manifest_digest": prior["expected_manifest_digest"],
            },
            "cal15": {
                "binding_digest": "sha256:" + "d" * 64,
                "manifest_digest": "sha256:" + "e" * 64,
            },
        },
        dispatch_id="SYNTHETIC_T128_NOT_RELEASED",
        scope="SYNTHETIC_FIXTURE",
    )
    selected = t128.jobs()[9:] if all_rows else [t128.jobs()[9], t128.jobs()[13]]
    return refresh_delivery(
        {
            "binding": binding,
            "expected_binding_digest": tasks.digest(binding),
            "t9_delivery": prior,
            "calibration_evidence": None,
        },
        [record(j) for j in selected],
    )


def make_delivery(tmp_path, *, calibration_evidence, calibration_pins):
    """Requires actual CAL adapter's synthetic nominal object; no fake PASS."""
    delivery = make_unadmitted_delivery(tmp_path, all_rows=True)
    binding = delivery["binding"]
    binding["prerequisites"]["cal15"] = dict(calibration_pins)
    delivery["expected_binding_digest"] = tasks.digest(binding)
    delivery["calibration_evidence"] = calibration_evidence
    rows = [
        json.loads(line)
        for line in delivery["raw_chunks"]["synthetic-t128"].splitlines()
    ]
    return refresh_delivery(delivery, rows)
