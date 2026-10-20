"""Step-2 batch (STEP2_BATCH_VERSIONS_20261020): each new Challenge version's
exam pack carries the same content as its predecessor apart from the
version binding, and every version is named explicitly (no default)."""

from __future__ import annotations

import numpy as np
import pytest

from carbon.challenge_kit import f02_public, f02_train, f08_public, f08_train
from carbon.challenge_kit import physical_pack as pp

F08, F02 = f08_train.CHALLENGE_ID, f02_train.CHALLENGE_ID
NEW = {
    ("electric-motor-magnetics", "1.1"): "motor-normal-construction-development-2",
    ("chip-cold-plate", "1.1"): "cooling-normal-construction-development-2",
    (F08, "1.2"): "f08-normal-construction-development-3",
    (F02, "2.1"): "f02-normal-construction-development-3",
    (
        "battery-fastcharge-ageing-development-v1",
        "2.0",
    ): "battery-normal-construction-development-3",
}


def _same_bank(a, b):
    return (
        a["case_ids"] == b["case_ids"]
        and a["cohorts"] == b["cohorts"]
        and np.array_equal(a["inputs"], b["inputs"])
        and np.array_equal(a["references"], b["references"])
        and a["reference_records"] == b["reference_records"]
        and a["solver_evidence"] == b["solver_evidence"]
        and a["decision_coverage"] == b["decision_coverage"]
    )


def test_every_new_version_has_its_own_explicit_pack_version():
    for key, pack_version in NEW.items():
        assert pp.PACK_VERSIONS[key] == pack_version
    # Distinct from every existing version's pack.
    assert len(set(pp.PACK_VERSIONS.values())) == len(pp.PACK_VERSIONS)


def test_f08_1_2_is_1_1_apart_from_the_binding():
    assert _same_bank(pp.development_bank(F08, "1.1"), pp.development_bank(F08, "1.2"))
    v11, v12 = (f08_train.load_public_train(v) for v in ("1.1", "1.2"))
    assert v11["train"] == v12["train"]
    k11, k12 = (f08_public.construction_kit(F08, v) for v in ("1.1", "1.2"))
    assert k11["train_digest"] == k12["train_digest"]
    assert (
        k12["version"] == "1.2" and k11["interface_digest"] != k12["interface_digest"]
    )


def test_f02_2_1_is_2_0_apart_from_the_binding():
    assert _same_bank(pp.development_bank(F02, "2.0"), pp.development_bank(F02, "2.1"))
    t20, t21 = (f02_train.load_public_train(v) for v in ("2.0", "2.1"))
    assert t20["train"] == t21["train"]
    assert t20["train_peak_std_c"] == t21["train_peak_std_c"]
    k21 = f02_public.construction_kit(F02, "2.1")
    assert (
        k21["train_digest"] == f02_public.construction_kit(F02, "2.0")["train_digest"]
    )
    assert k21["version"] == "2.1"


def test_there_is_no_default_version():
    with pytest.raises(TypeError):
        f02_train.load_public_train()
    with pytest.raises(TypeError):
        f08_train.load_public_train()
    with pytest.raises(ValueError):
        f02_train.load_public_train("2.2")
    with pytest.raises(SystemExit):
        pp.main(["out", "--challenge", F02])  # --version is required
    with pytest.raises(SystemExit):
        pp.main(["out", "--challenge", F02, "--version", "9.9"])


def test_an_unregistered_version_writes_no_pack(tmp_path):
    with pytest.raises(ValueError):
        pp.write_public_pack(tmp_path / "x", F02, "2.2")
