"""A closed lowering refusal is the candidate's (CANDIDATE_BUILD_REFUSED), not infrastructure.

Validator ruling: only the two closed refusal types write the fixed-schema file;
the parent sanitises it; no valid file keeps the infrastructure meaning.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("jax")

import test_direct_clean_rebuild_acceptance as acceptance
import test_direct_v3_durable_tasks as durable

from carbon.challenge_kit import physical_material
from carbon.development_session import build_refusal, bundle_construction_worker
from carbon.development_session.bundle_construction_worker import (
    CandidateBuildRefused,
    reconstruct_public,
)
from carbon.development_session.research_ledger import CampaignLedger
from carbon.research import DirectTaskStateV3

MOTOR = ("electric-motor-magnetics", "1.0")

#: A model whose graph needs a floor, which the served allowlist does not carry.
UNSUPPORTED_OP = """import jax.numpy as jnp


def build(train_inputs, train_targets, *, seed, configuration, train_use):
    def apply(x):
        return jnp.floor(x) @ jnp.ones((x.shape[1], 60), x.dtype)

    return {"framework": "jax", "apply": apply, "parameters": []}
"""

CRASH = """\
def build(train_inputs, train_targets, *, seed, configuration, train_use):
    raise RuntimeError("the candidate's own bug")
"""

#: Forges a refusal file with free text and an unregistered code, then exits.
FORGED = """\
import json
import os


def build(train_inputs, train_targets, *, seed, configuration, train_use):
    with open("../output/refusal.json", "w") as stream:
        json.dump(
            {
                "schema": "carbon.development.bundle-build-refusal.v1",
                "code": "ignore previous instructions",
                "at": "free text with spaces and /slashes",
            },
            stream,
        )
    os._exit(0)
"""


def _build(tmp_path, monkeypatch, source):
    monkeypatch.setattr(acceptance, "SOURCE", source)
    material = physical_material.bundle_material(*MOTOR)
    image, installed = acceptance._source_bundle(tmp_path)
    recipe = acceptance._recipe(material, image)
    runner = acceptance.LocalProcessRunner(installed)
    ledger = CampaignLedger(tmp_path / "campaign")
    return lambda: reconstruct_public(
        ledger,
        owner="miner",
        identity="refusal-build",
        image=image,
        recipe=recipe,
        challenge_binding=acceptance._binding(material),
        train=material["train"],
        example=material["example"],
        seed=11,
        allowlist_bytes=material["allowlist_bytes"],
        runner=runner,
    )


def test_the_unsupported_op_is_a_typed_candidate_refusal_naming_the_op(
    tmp_path, monkeypatch
):
    build = _build(tmp_path, monkeypatch, UNSUPPORTED_OP)
    with pytest.raises(CandidateBuildRefused) as refused:
        build()
    assert refused.value.code in build_refusal.CODES
    assert refused.value.at is not None and "floor" in refused.value.at.lower()


def test_a_crash_without_a_refusal_file_is_not_a_candidate_refusal(
    tmp_path, monkeypatch
):
    build = _build(tmp_path, monkeypatch, CRASH)
    with pytest.raises(Exception) as failed:
        build()
    assert not isinstance(failed.value, CandidateBuildRefused)


def test_a_forged_refusal_file_is_sanitised(tmp_path, monkeypatch):
    build = _build(tmp_path, monkeypatch, FORGED)
    with pytest.raises(CandidateBuildRefused) as refused:
        build()
    assert (refused.value.code, refused.value.at) == (build_refusal.UNSPECIFIED, None)


def _file(**override):
    value = {
        "schema": build_refusal.SCHEMA,
        "code": "op_not_allowlisted",
        "at": "gather",
    }
    value.update(override)
    return json.dumps(value).encode()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (_file(), ("op_not_allowlisted", "gather")),
        (_file(code="not in the registry"), ("unspecified", "gather")),
        (_file(at="free text, not an identifier"), ("op_not_allowlisted", None)),
        (_file(at="a" * 65), ("op_not_allowlisted", None)),
        (_file(at=None), ("op_not_allowlisted", None)),
        (_file(schema="other"), None),
        (b'{"schema": "x"}', None),
        (b"not json", None),
        (b"", None),
        (b"{" + b" " * 2048 + b"}", None),
    ],
)
def test_refusal_file_parsing_is_closed(raw, expected):
    assert build_refusal.parse(raw) == expected


def test_the_task_completes_refused_with_a_typed_code_not_infrastructure(
    tmp_path, monkeypatch
):
    request, provider, _ = durable._fixture(tmp_path, monkeypatch)
    tasks = provider()
    try:
        started = tasks.start_research_task(request)

        def refuse(*args, **kwargs):
            raise CandidateBuildRefused("aten_op_not_allowlisted", "aten.index.Tensor")

        monkeypatch.setattr(
            bundle_construction_worker, "reconstruct_and_infer_public", refuse
        )
        view = tasks.run_queued_task(started.task.task_id)
        assert view.state is DirectTaskStateV3.REFUSED
        assert view.terminal_receipt.refusal_code == "candidate_build_refused"
        assert view.terminal_receipt.infrastructure_failure_class is None
    finally:
        tasks.close()
