"""A synthetic Motor 1.8 COUNTED bank grade on the GRAPH route (13 Nov): the canary's own path at the canary's shape.

`test_graph_pool_counted_e2e` runs graph custody -> the counted bank grade (`retention._counted_bank_grade`: the source-free
regrade, graph custody v5, the dual producer, the score engine, the binding, ExamCap) on a Motor 1.5 pool bank. This runs the same
chain on the REAL Motor 1.8 builders with the 2564 x 240 bank of `test_motor18_grade_pad_proof` (retained predictions 12.6 MB,
worker evidence 16.8 MB as base64: the sizes that stopped the canary at the custody cap and then at the graded originals'
parse), and runs it twice, with the bank's non-truth reference columns padded with 0 and with a finite sentinel, asserting the
computed score, the gate verdicts and the cap row identical (V2C's pad-proof, condition 2).

STAND-INS: those of `test_motor18_grade_pad_proof` (the exam's registered policies are the Motor 1.5 pool version's; the model, the
pair and the single-call seconds are fixtures). The retained ORIGIN carries the full-bank outputs here, where production's origin
is the 154-row practice query, so its ordinary retention runs under the bank bound; the counted grade itself is NOT wrapped.
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import test_graph_pool_counted_e2e as graph_e2e
from test_motor18_grade_pad_proof import SENTINEL, build_case

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.scoring import inference_pair_evidence, pair_read_bound
from scripts.dev.score_lab import public_unbound_custody as custody

ROWS, WIDTH = 2564, 240


@pytest.fixture
def one_point_eight(monkeypatch):
    monkeypatch.setattr(graph_e2e, "VERSION", "1.8")


def counted_grade(tmp_path, monkeypatch, pad):
    case = build_case(tmp_path / "pack", monkeypatch, pad)
    with custody.raised_json_bytes(pair_read_bound.pair_bytes(ROWS, WIDTH)):
        fixture = graph_e2e._setup(case, tmp_path, monkeypatch)
    result = graph_e2e._grade(fixture, counted=True)
    regrade = next(
        p
        for p in fixture.base.iterdir()
        if p.is_dir()
        and p.name != graph_e2e.TASK
        and not p.name.endswith(".evaluation")
    )
    evaluation = fixture.base / (regrade.name + ".evaluation")
    binding = json.loads((evaluation / "private-evaluation-binding.json").read_bytes())
    scored = {
        k: v
        for k, v in binding["scoring"]["models"][0].items()
        if k != "artifact_digest"
    }
    return case, fixture, result, scored


def test_the_counted_graph_grade_reaches_a_computed_score_at_the_canarys_shape(
    one_point_eight, tmp_path, monkeypatch
):
    case, fixture, result, scored = counted_grade(tmp_path, monkeypatch, 0.0)
    assert case["bank"]["references"].shape == (ROWS, 4 * 60)
    assert len(fixture.artifacts["predictions.json"]) > 12_000_000
    assert len(fixture.artifacts["worker-evidence.json"]) > 16_000_000
    assert result["private_evaluation_state"] == "BOUND_DEVELOPMENT_ONLY", result
    assert result["official_eligible"] is False
    assert scored["status"] == "SCORED_DEVELOPMENT_CANDIDATE"
    assert type(scored["score"]) is float and 0.0 < scored["score"] <= 1.0
    assert set(scored["gates"].values()) == {"PASS"}
    assert graph_e2e._cap_rows(fixture) == [
        (
            graph_e2e.TASK,
            "GRADED",
            "COUNTED",
            "SCORED_DEVELOPMENT_CANDIDATE",
            graph_e2e.OWNER,
            7,
        )
    ]


def test_the_counted_graph_grade_is_identical_whatever_the_pad(
    one_point_eight, tmp_path, monkeypatch
):
    """The pad-proof: nothing the counted grade decides depends on the bank's non-truth reference columns."""
    first = counted_grade(tmp_path / "zero", monkeypatch, 0.0)
    second = counted_grade(tmp_path / "sentinel", monkeypatch, SENTINEL)
    zero_case, _fz, zero_result, zero_scored = first
    pad_case, _fp, pad_result, pad_scored = second
    # the two packs really differ in the pad: the bank, and so the reference rows the producer binds
    assert zero_case["references"] != pad_case["references"]
    assert (zero_case["bank"]["references"][:, 60:] == 0.0).any()
    assert (pad_case["bank"]["references"][:, 60:] == SENTINEL).any()
    assert zero_scored == pad_scored
    for key in (
        "private_evaluation_state",
        "ladder_feedback_state",
        "official_eligible",
        "score_state",
    ):
        assert zero_result[key] == pad_result[key]
    assert graph_e2e._cap_rows(first[1]) == graph_e2e._cap_rows(second[1])


def test_the_binding_reads_under_the_banks_ceiling_only_where_the_bank_is_that_big(
    monkeypatch,
):
    """`_sized_pair_ceiling` raises the pair/original ceiling to the graded query's bound for a block outside `produce`."""
    before = inference_pair_evidence._MAX_BYTES
    big = pair_read_bound.pair_bytes(ROWS, WIDTH)
    monkeypatch.setattr(retention, "_pair_read_limit", lambda adapter, artifacts: big)
    with retention._sized_pair_ceiling(None, {}):
        assert inference_pair_evidence._MAX_BYTES == big
    assert inference_pair_evidence._MAX_BYTES == before
    # a bank within PAIR_READ_BYTES (every other live version) changes nothing
    monkeypatch.setattr(
        retention,
        "_pair_read_limit",
        lambda adapter, artifacts: retention.PAIR_READ_BYTES,
    )
    assert isinstance(retention._sized_pair_ceiling(None, {}), contextlib.nullcontext)
