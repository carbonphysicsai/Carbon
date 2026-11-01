"""The learning-necessity reference is the in-pack learned baseline, run exactly as the pack runs it (Validator ruling,
1 Nov 15:30 CST).

Claims: the adapter's predictions are bit-equal to the pack's own ``pool_baseline.fit`` given the same TRAIN, for F02 2.5,
Motor 1.5 and Cooling 1.6, with the same (length, ridge) choice; for F02 and Motor the harness's TRAIN is the pack's
bit for bit; the three grids are the superseded 6-role grids with the reference replaced by the in-pack contender and
the catalog prior KRR kept, right after it, as "physics-prior KRR" (the superseded digests are reproduced from the new
files); the new kind resolves and runs through the harness and its custody step; a pin that is not the files on disk, a
malformed in-pack contender or a setting refuses before anything trains; and the adapter itself imports nothing sealed,
while a run reads only public repository files and imports no module the pack's own entry point does not.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

TOOLS = Path(__file__).resolve().parents[2] / "scripts/dev/learning_necessity"
sys.path.insert(0, str(TOOLS))

import ln_harness as h
import ln_inpack_baseline as ib

from carbon.scoring import pool_baseline

ROOT = Path(__file__).resolve().parents[2]
#: (Challenge, registered version, the pack's kind)
PACKS = (
    ("f02", "2.5", "f02"),
    ("electric-motor-magnetics", "1.5", "motor"),
    ("chip-cold-plate", "1.6", "cooling"),
)
#: (grid file, Challenge, version, catalog prefix, the superseded 6-role grid's digest)
GRIDS = (
    (
        "ln_grid_f02_2_5.json",
        "f02",
        "2.5",
        "v2.f02.",
        "sha256:7d8545aa4d24ef2a9f0914191f56a5e60184aee12ad38b3f42c5df4d55a0434a",
    ),
    (
        "ln_grid_motor_1_7.json",
        "electric-motor-magnetics",
        "1.7",
        "v2.motor.",
        "sha256:898fe6cfd29034279958c6ac1d91c44ea9b6db67cb34d4c514a5a1a009e4ebe9",
    ),
    (
        "ln_grid_cooling_1_8.json",
        "chip-cold-plate",
        "1.8",
        "v2.cooling.",
        "sha256:167edec626b34e6be4925a1e51c777231762a4083f17a0f606accf3079b9d0b7",
    ),
)
ROLES = [
    "reference (in-pack learned baseline)",
    "physics-prior KRR",
    "operator: FNO",
    "second operator",
    "MLP",
    "graph",
    "transformer",
]


def _read(name):
    return json.loads((TOOLS / name).read_text(encoding="utf-8"))


def _rows(kind, version, inputs):
    """TRAIN's inputs plus a deterministic sweep of the declared box (off-TRAIN rows)."""
    bounds = np.asarray(list(pool_baseline.declared_bounds(kind, version).values()))
    low, span = bounds[:, 0], bounds[:, 1] - bounds[:, 0]
    steps = np.linspace(0.0, 1.0, 7)[:, None]
    crossed = np.where(np.arange(len(low)) % 2, steps, 1.0 - steps)
    return np.vstack([inputs, low + steps * span, low + crossed * span])


@pytest.mark.parametrize(("challenge", "version", "kind"), PACKS)
def test_the_adapter_is_bit_equal_to_the_packs_own_baseline(challenge, version, kind):
    pack_predict, pack_choice = pool_baseline.fit(kind, version)
    own_train = pool_baseline._train
    inputs, targets = pool_baseline._train(kind, version)
    product = ib.builder(challenge, version)(
        inputs, targets, seed=0, configuration={}, train_use={}
    )
    assert pool_baseline._train is own_train  # the seam is restored
    assert product["inpack_choice"] == pack_choice
    rows = _rows(kind, version, inputs)
    mine = h.predict(product, rows)
    theirs = np.asarray(pack_predict(rows.tolist()), dtype=np.float64)
    assert mine.shape == theirs.shape == (len(rows), targets.shape[1])
    assert np.array_equal(mine, theirs)


@pytest.mark.parametrize(
    ("challenge", "version", "kind"), [p for p in PACKS if p[2] != "cooling"]
)
def test_the_harness_train_is_the_packs_train_for_f02_and_motor(
    challenge, version, kind
):
    x, y = h.load_train(challenge, version)
    inputs, targets = pool_baseline._train(kind, version)
    assert np.array_equal(np.asarray(x, float), inputs)
    assert np.array_equal(np.asarray(y, float), targets)


@pytest.mark.parametrize(("name", "challenge", "version", "prefix", "old"), GRIDS)
def test_each_grid_has_the_seven_roles_and_reproduces_the_superseded_one(
    name, challenge, version, prefix, old
):
    grid = _read(name)
    assert grid["schema"] == h.GRID_SCHEMA == "carbon.ln-grid.v2"
    assert grid["status"] == "PROPOSED_NOT_RULED"  # the grid digest is the Validator's
    assert grid["challenge"] == {"id": challenge, "version": version}
    assert [c["role"] for c in grid["contenders"]] == ROLES
    reference, prior = grid["contenders"][:2]
    assert reference == {
        "role": ROLES[0],
        "kind": "inpack_baseline",
        "settings": None,
        "implementation_digest": ib.implementation_digest(),
    }
    assert prior == {
        "role": "physics-prior KRR",
        "candidates": [prefix + "prior_krr"],
        "settings": None,
    }
    # the superseded grid is these bytes with the old reference back in place: the other five roles, k, fold seed and
    # seed are verbatim
    superseded = copy.deepcopy(grid)
    superseded["schema"] = "carbon.ln-grid.v1"
    superseded["contenders"] = [
        {**prior, "role": "reference (learned baseline)"},
        *grid["contenders"][2:],
    ]
    assert h.digest(superseded) == old
    raw = (TOOLS / name).read_bytes()
    assert raw == (json.dumps(grid, indent=1, sort_keys=True) + "\n").encode()
    assert h.load_grid(TOOLS / name, h.digest(grid)) == grid


def _tiny_grid(tmp_path, challenge, version, pin=None):
    grid = {
        "schema": h.GRID_SCHEMA,
        "status": "PROPOSED_NOT_RULED",
        "challenge": {"id": challenge, "version": version},
        "k": 2,
        "fold_seed": 0,
        "seed": 0,
        "contenders": [
            {
                "role": ROLES[0],
                "kind": "inpack_baseline",
                "settings": None,
                "implementation_digest": pin or ib.implementation_digest(),
            }
        ],
    }
    path = tmp_path / "grid.json"
    path.write_text(json.dumps(grid), encoding="utf-8")
    return path, h.digest(grid)


@pytest.mark.parametrize(
    ("challenge", "version", "kind"), [p for p in PACKS if p[2] != "cooling"]
)
def test_the_in_pack_kind_runs_through_the_harness_and_its_custody_step(
    tmp_path, challenge, version, kind
):
    x, _y = h.load_train(challenge, version)
    probe = _rows(kind, version, np.asarray(x, float)[:5]).astype(np.float32)
    probe_path = tmp_path / "probe.npy"
    np.save(probe_path, probe)
    path, digest = _tiny_grid(tmp_path, challenge, version)
    record = h.run(
        path,
        digest,
        version,
        probe_path,
        tmp_path / "desk",
        challenge_id=challenge,
        log=lambda *_: None,
    )
    (only,) = record["contenders"]
    assert only["catalog_id"] == "inpack.learned_baseline" and only["tuned"] is False
    assert only["implementation_digest"] == ib.implementation_digest()
    pack_predict, pack_choice = pool_baseline.fit(kind, version)
    assert only["inpack_choice"] == {"default": pack_choice}
    exported = np.load(tmp_path / "desk" / only["exports"]["default"]["file"])
    expected = np.asarray(pack_predict(probe.tolist()), dtype=np.float64)
    assert np.array_equal(exported, expected.astype(np.float32))
    assert record["contenders_expected"] == ["inpack.learned_baseline"]
    assert h.for_runtime(h.resolve_entries(_read_grid(path), challenge, version), "jax")
    custody = h.predict_from_record(
        tmp_path / "desk" / "record.json",
        digest,
        version,
        probe_path,
        tmp_path / "custody",
        challenge_id=challenge,
        log=lambda *_: None,
    )
    (again,) = custody["contenders"]
    assert again["implementation_digest"] == ib.implementation_digest()
    assert np.array_equal(
        np.load(tmp_path / "custody" / again["exports"]["default"]["file"]), exported
    )


def _read_grid(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _never(*_args, **_kwargs):
    raise AssertionError("a refused run must not train anything")


def test_a_pin_that_is_not_the_files_on_disk_refuses_before_anything_trains(tmp_path):
    path, digest = _tiny_grid(tmp_path, "f02", "2.5", pin="sha256:" + "0" * 64)
    with pytest.raises(h.Refused, match="inpack_baseline_implementation_differs"):
        h.run(
            path,
            digest,
            "2.5",
            None,
            tmp_path / "out",
            builders={"inpack.learned_baseline": _never},
        )
    assert not (tmp_path / "out").exists()


def test_a_malformed_or_repeated_in_pack_contender_is_refused(tmp_path):
    path, _digest = _tiny_grid(tmp_path, "f02", "2.5")
    base = _read_grid(path)
    good = base["contenders"][0]
    for contender, code in (
        ({**good, "settings": []}, "grid_inpack_contender_invalid"),
        ({**good, "kind": "catalog"}, "grid_inpack_contender_invalid"),
        (
            {**good, "implementation_digest": "sha256:xyz"},
            "grid_inpack_contender_invalid",
        ),
        ({**good, "candidates": ["v2.f02.prior_krr"]}, "grid_inpack_contender_invalid"),
    ):
        grid = {**base, "contenders": [contender]}
        path.write_text(json.dumps(grid), encoding="utf-8")
        with pytest.raises(h.Refused, match=code):
            h.load_grid(path, h.digest(grid))
    grid = {**base, "contenders": [good, good]}
    path.write_text(json.dumps(grid), encoding="utf-8")
    with pytest.raises(h.Refused, match="grid_inpack_contender_repeated"):
        h.load_grid(path, h.digest(grid))
    with pytest.raises(h.Refused, match="inpack_baseline_not_registered"):
        h.inpack_item("f08-ribbed-bracket")


def test_the_adapter_takes_no_setting_and_a_record_must_carry_its_pin(tmp_path):
    x, y = h.load_train("f02", "2.5")
    build = ib.builder("f02", "2.5")
    with pytest.raises(ib.Refused, match="inpack_baseline_takes_no_setting"):
        build(x, y, seed=0, configuration={"length": 1.0}, train_use={})
    with pytest.raises(ib.Refused, match="inpack_baseline_takes_no_setting"):
        build(x, y, seed=0, configuration={}, train_use={"steps": 1})
    path, digest = _tiny_grid(tmp_path, "f02", "2.5")
    h.run(path, digest, "2.5", None, tmp_path / "pod", log=lambda *_: None)
    record = _read_grid(tmp_path / "pod" / "record.json")
    record["contenders"][0]["implementation_digest"] = "sha256:" + "1" * 64
    forged = tmp_path / "forged.json"
    forged.write_text(json.dumps(record), encoding="utf-8")
    probe = tmp_path / "probe.npy"
    np.save(probe, np.asarray(x, np.float32)[:3])
    with pytest.raises(h.Refused, match="inpack_baseline_implementation_differs"):
        h.predict_from_record(
            forged,
            digest,
            "2.5",
            probe,
            tmp_path / "c",
            builders={"inpack.learned_baseline": _never},
        )


#: Module-name parts the adapter module itself must never import (sealed material, pools, exams, custody, the validator).
FORBIDDEN = (
    "sealed",
    "pool_",
    "custody",
    ".exam",
    "challenge_validator",
    "score_feed",
    "ledger",
)
#: What a run may read besides code: committed public material under these repository directories.
PUBLIC_DIRS = ("carbon", "docs/development/evidence")
#: ...and these exact committed public files: the version registry reads the validator host-class version overlay
#: (from the image move on main), a tracked repository file with no sealed content.
PUBLIC_FILES = ("scripts/validator_host_classes/version_overlay.json",)
_RUN = """
import json, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
opened = []
sys.addaudithook(lambda event, args: opened.append(str(args[0])) if event == "open" else None)
import numpy as np
mode = sys.argv[3]
if mode == "import":
    import ln_inpack_baseline as ib
    ib.implementation_digest()
else:
    from carbon.scoring import pool_baseline
    for challenge, version, kind in (("electric-motor-magnetics", "1.5", "motor"), ("f02", "2.5", "f02")):
        if mode == "pack":
            pool_baseline.fit(kind, version)
        else:
            import ln_inpack_baseline as ib
            x, y = pool_baseline._train(kind, version)
            ib.builder(challenge, version)(x, y, seed=0, configuration={}, train_use={})
data = [p for p in opened if not p.endswith((".py", ".pyc", ".pyd", ".dll", ".so"))]
print(json.dumps({"modules": sorted(sys.modules), "opened": data}))
"""


def _closure(mode):
    result = subprocess.run(
        [sys.executable, "-c", _RUN, str(TOOLS), str(ROOT), mode],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.splitlines()[-1])


def _sealed_named(modules):
    return {m for m in modules if any(part in m for part in FORBIDDEN)}


def test_the_adapter_imports_nothing_sealed_and_a_run_reads_only_public_repository_files():
    alone = _closure("import")
    assert "ln_inpack_baseline" in alone["modules"]
    assert _sealed_named(alone["modules"]) == set()
    pack, mine = _closure("pack"), _closure("adapter")
    # running the pack's own entry point imports its grading modules (some named for the sealed pool they also grade);
    # the adapter adds none of its own
    assert _sealed_named(mine["modules"]) <= _sealed_named(pack["modules"])
    for path in mine["opened"]:
        resolved = Path(path).resolve()
        if not resolved.is_relative_to(ROOT):
            assert "site-packages" in resolved.parts or resolved.is_relative_to(
                Path(sys.base_prefix).resolve()
            ), path
            continue
        relative = resolved.relative_to(ROOT).as_posix()
        assert relative.startswith(PUBLIC_DIRS) or relative in PUBLIC_FILES, relative
        assert not any(
            part in relative for part in ("custody", "sealed", "private", "store")
        ), relative
