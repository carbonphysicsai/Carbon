"""Toy published-study shape only; no real label extraction or model fit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from carbon.design_search import tasks
from scripts.dev.score_lab import owner_v3_train as train


def fixture():
    plan = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "Business/research/score-lab-campaign-01/acquisition-v1/acquisition.json"
        ).read_text(encoding="utf-8")
    )
    values = {q: 1.0 for q in train.QUANTITIES}
    raw = json.dumps(
        {
            "schema": "carbon.battery.feasibility02-v2-rescore.v1",
            "cells": {
                "c1=1.25,c2=0.4,sv=4:h1@T5": values,  # exact CAL tuple
                "c1=0.5,c2=0.25,sv=4:h1@T5": values,  # exact EVAL tuple
                "c1=0.49,c2=0.25,sv=4:h1@T5": {
                    **values,
                    "minutes": None,
                },  # disjoint, retained
            },
        }
    ).encode()
    registry = json.dumps(
        {"schema": "carbon.battery.feasibility02-v2-rescore-registry.v1"}
    ).encode()
    base_registry = b"{}"
    kwargs = {
        "plan": plan,
        "expected_plan_digest": tasks.digest(plan),
        "source_digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "registry_digest": "sha256:" + hashlib.sha256(registry).hexdigest(),
        "base_registry_digest": "sha256:" + hashlib.sha256(base_registry).hexdigest(),
    }
    return raw, registry, base_registry, kwargs


def test_construction_role_is_disjoint_and_retains_null_without_imputation():
    raw, registry, base_registry, kwargs = fixture()
    data, receipt = train.prepare(
        raw, registry, base_registry, scope="SYNTHETIC_FIXTURE", **kwargs
    )
    records = [json.loads(line) for line in data.splitlines()]
    assert len(records) == 1 and records[0]["outputs"]["minutes"] is None
    assert records[0]["fixture"] is True
    assert len(receipt["calibration_evaluation_exclusions"]) == 2
    assert receipt["TRAIN_plan_completed_rows_claimed"] == 0
    assert receipt["numerical_evaluation_reference"] is False


def test_toy_source_cannot_be_public_and_changed_bytes_cannot_be_extracted():
    raw, registry, base_registry, kwargs = fixture()
    with pytest.raises(tasks.TaskError, match="registered published"):
        train.prepare(
            raw, registry, base_registry, scope="PUBLIC_DEVELOPMENT", **kwargs
        )
    with pytest.raises(tasks.TaskError, match="bytes differ"):
        train.prepare(
            raw + b" ", registry, base_registry, scope="SYNTHETIC_FIXTURE", **kwargs
        )
