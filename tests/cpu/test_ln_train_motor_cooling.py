"""The learning-necessity harness for Motor 1.7 and Cooling 1.8 (Validator ruling, 1 Nov ~15:10 CST).

Claims: each grid is the F02 grid verbatim (roles, candidate order, settings, k, fold seed, seed) with only its Challenge,
version and catalog prefix changed, stays PROPOSED_NOT_RULED, loads under its own digest, names catalog ids that exist,
and resolves with no substitution against the newest registered version's listing; the loader returns a registered
version's public TRAIN through `physical_public_train` (Cooling's encoded TRAIN where the version declares it), refuses
an unknown Challenge and a version the registry does not hold (Motor 1.7 and Cooling 1.8 until they register) rather
than guess its TRAIN, and its import closure touches no sealed, pool, exam, custody or validator module; and
`ln_harness.load_train` reaches it for exactly these two Challenges, with F02 unchanged.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

TOOLS = Path(__file__).resolve().parents[2] / "scripts/dev/learning_necessity"
sys.path.insert(0, str(TOOLS))

import ln_harness as h
import ln_train_motor_cooling as lt

from carbon.backbone_catalog import listing
from carbon.challenge_kit import physical_public_train, version_registry

F02 = TOOLS / "ln_grid_f02_2_5.json"
#: (grid file, Challenge, version, catalog prefix, the newest registered version on main)
GRIDS = (
    ("ln_grid_motor_1_7.json", "electric-motor-magnetics", "1.7", "v2.motor.", "1.5"),
    ("ln_grid_cooling_1_8.json", "chip-cold-plate", "1.8", "v2.cooling.", "1.6"),
)


def _read(name):
    return json.loads((TOOLS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(("name", "challenge", "version", "prefix", "_"), GRIDS)
def test_each_grid_is_the_f02_grid_with_only_its_challenge_and_prefix_changed(
    name, challenge, version, prefix, _
):
    grid, f02 = _read(name), _read(F02.name)
    assert grid["challenge"] == {"id": challenge, "version": version}
    assert grid["status"] == "PROPOSED_NOT_RULED"  # the grid digest is the Validator's
    for key in ("schema", "k", "fold_seed", "seed"):
        assert grid[key] == f02[key]
    assert [c["role"] for c in grid["contenders"]] == [
        c["role"] for c in f02["contenders"]
    ]
    for mine, theirs in zip(grid["contenders"], f02["contenders"], strict=True):
        assert mine["settings"] == theirs["settings"]
        if "kind" in theirs:  # the in-pack reference names no catalog entry
            assert mine == theirs
            continue
        assert mine["candidates"] == [
            prefix + c.removeprefix("v2.f02.") for c in theirs["candidates"]
        ]
    # the same bytes the F02 file is written with, so a digest is reproducible
    raw = (TOOLS / name).read_bytes()
    assert raw == (json.dumps(grid, indent=1, sort_keys=True) + "\n").encode()
    assert h.load_grid(TOOLS / name, h.digest(grid)) == grid


@pytest.mark.parametrize(("name", "challenge", "_", "prefix", "registered"), GRIDS)
def test_each_grid_names_catalog_ids_and_resolves_on_the_registered_listing(
    name, challenge, _, prefix, registered
):
    grid = _read(name)
    ids = {e["catalog_id"] for e in listing.load()["entries"]}
    for each in grid["contenders"]:
        assert all(c in ids for c in each.get("candidates", []))
    entries = h.resolve_entries(grid, challenge, registered)
    assert [item["catalog_id"] for _, item, _ in entries] == [
        "inpack.learned_baseline"
    ] + [
        prefix + suffix
        for suffix in (
            "prior_krr",
            "neuralop.FNO",
            "lno.LNO1d",
            "physicsnemo.FullyConnected",
            "jno.mgno2d",
            "jno.transolver",
        )
    ]
    for each, item, substituted in entries:
        assert substituted is None
        assert len(h.check_settings(each, item)) == (
            0 if each["settings"] is None else 8
        )


@pytest.mark.parametrize(
    ("challenge", "version", "train"),
    [
        ("electric-motor-magnetics", "1.5", version_registry.MOTOR_TRAIN),
        ("chip-cold-plate", "1.2", version_registry.COOLING_TRAIN),
        ("chip-cold-plate", "1.6", version_registry.COOLING_TRAIN_ENCODED),
    ],
)
def test_a_registered_version_loads_its_own_declared_public_train(
    challenge, version, train
):
    assert lt.train_name(challenge, version) == train
    x, y = h.load_train(challenge, version)
    data = physical_public_train.load_public_train(challenge, version)
    assert np.array_equal(x, data["inputs"]) and np.array_equal(y, data["targets"])
    assert len(x) == len(y) > 0


def test_an_unregistered_version_or_another_challenge_is_refused():
    # Motor 1.7 and Cooling 1.8 load once their registration lands, never by a guessed TRAIN
    for challenge, version in (
        ("electric-motor-magnetics", "1.7"),
        ("chip-cold-plate", "1.8"),
        ("chip-cold-plate", "9.9"),
    ):
        if version_registry.find(challenge, version) is not None:
            continue
        with pytest.raises(lt.Refused, match="version_not_registered"):
            h.load_train(challenge, version)
    with pytest.raises(lt.Refused, match="train_not_registered_for_this_challenge"):
        lt.load_train("f08-ribbed-bracket", "1.7")
    with pytest.raises(h.Refused, match="train_not_registered_for_this_challenge"):
        h.load_train("f08-ribbed-bracket", "1.7")


def test_f02_still_loads_its_own_train_unchanged():
    from carbon.challenge_kit import f02_train

    x, y = h.load_train("f02", "2.5")
    data = f02_train.load_public_train("2.5")
    assert np.array_equal(x, data["inputs"]) and np.array_equal(y, data["targets"])


#: Module-name parts the public-TRAIN loader must never import (sealed material, pools, exams, custody, the validator).
FORBIDDEN = (
    "sealed",
    "pool_",
    "custody",
    ".exam",
    "challenge_validator",
    "score_feed",
    "ledger",
)


def test_the_loader_import_closure_touches_no_sealed_module():
    code = (
        "import json, sys; sys.path.insert(0, sys.argv[1]); import ln_train_motor_cooling as lt;"
        "lt.load_train('electric-motor-magnetics', '1.5'); lt.load_train('chip-cold-plate', '1.6');"
        "print(json.dumps(sorted(sys.modules)))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(TOOLS)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    loaded = json.loads(result.stdout)
    assert "ln_train_motor_cooling" in loaded
    assert [m for m in loaded if any(part in m for part in FORBIDDEN)] == []
