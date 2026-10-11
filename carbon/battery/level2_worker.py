"""What Carbon stages for a Level-2 rebuild: SpecMuon (`specmuon-carbon-v1`)
and pool selection (`training_data.pool_selection`, battery-l2-v2).

- **SpecMuon.** A construction whose reconstruction turns `muon_spectral` on
  trains with `carbon.battery.level2_specmuon` wrapping battery's Muon. The
  worker gets, beside a Level-0 rebuild's files, Carbon's SpecMuon module and
  the Level-2 trainer.
- **Pool selection.** A construction with a `pool_selection` trains on the
  subset Carbon drew from the named pool version (`carbon.battery.pools`).
  The worker gets the drawn case ids (`battery-pool-selection.json`; TRAIN
  case ids are public) and restricts the staged TRAIN v1 to them before the
  fit. Nothing else changes: the trainer is Level 0's unless SpecMuon is on.

Nothing the strategy supplied is executed.

**Off is Level 0.** A recipe with neither has no record and rebuilds through
Level 0's program, files and trainer. A SpecMuon-only record is v1's record,
byte for byte.

**CPU only for now** (`CPU_ONLY_DEV`): the per-step SVD is a
GPU-nondeterminism risk until the A40 R1 leg passes it. Any other device is
refused as an environment failure, never the candidate's.
"""

from __future__ import annotations

from pathlib import Path

SPECTRAL = "optimizer.muon_spectral"
POOL = "training_data.pool_selection"
SCHEMA = "carbon.battery.level2-spectral.v1"
#: A record with a pool selection (and SpecMuon or not).
SCHEMA_V2 = "carbon.battery.level2.v2"
POOL_FILE = "battery-pool-selection.json"
LANE = "CPU_ONLY_DEV"
REBUILD_LABEL = "rebuild: CPU-verified only"
STAGED_MODULES = {
    "battery-level2-specmuon.py": ("battery", "level2_specmuon.py"),
    "battery-level2-training.py": ("battery", "level2_training.py"),
}
_BUILD = 'model = recipes.build(recipe["family"], recipe["settings"])\n'
_LEVEL2_BUILD = r"""for staged, module in (
    ("battery-level2-specmuon.py", "level2_specmuon.py"),
    ("battery-level2-training.py", "level2_training.py"),
):
    shutil.copyfile(work / staged, lab / module)
import jax as _jax  # noqa: E402

if _jax.default_backend() != "cpu":  # CPU_ONLY_DEV: Carbon's lane, not the candidate's
    raise ImportError("level2_cpu_only_dev")
from carbon_battery_lab import level2_training  # noqa: E402

model = level2_training.build(recipe["family"], recipe["settings"])
"""


#: Where the Level-2 pool restriction goes: before the OCV table is read,
#: after TRAIN v1 is loaded.
_POOL_ANCHOR = 'table = json.loads((work / "ocv-table.json").read_text())\n'
_POOL_RESTRICT = r"""_pool = json.loads((work / "battery-pool-selection.json").read_text())
_wanted = set(_pool["case_ids"])
_index = [i for i, c in enumerate(train.case_ids) if c in _wanted]
if len(_index) != len(_wanted) or len(_index) != _pool["cases"]:
    raise SystemExit("battery-pool-selection does not match TRAIN v1")
train = train.take(_index)
"""


def spectral_record(reconstruction):
    """The SpecMuon record of a development construction, or None."""
    if type(reconstruction) is not dict:
        return None
    found = reconstruction.get(SPECTRAL) or {}
    if not found.get("muon_spectral"):
        return None
    return {"schema": SCHEMA, "interpretation": found["interpretation"], "lane": LANE}


def level2_record(reconstruction):
    """The Level-2 record of a development construction, or None: v1's
    SpecMuon record when there is no pool selection (byte for byte), else a
    v2 record carrying the drawn subset and SpecMuon's record or None."""
    spectral = spectral_record(reconstruction)
    pool = (reconstruction or {}).get(POOL) if type(reconstruction) is dict else None
    if not pool:
        return spectral
    return {
        "schema": SCHEMA_V2,
        "spectral": spectral,
        "pool": {
            "pool_version": pool["pool_version"],
            "cases": pool["cases"],
            "case_ids": list(pool["case_ids"]),
            "case_ids_digest": pool["case_ids_digest"],
        },
        "lane": LANE if spectral else "LEVEL0_LANE",
    }


def is_spectral(record):
    return type(record) is dict and record.get("schema") == SCHEMA


def is_level2(record):
    return type(record) is dict and record.get("schema") in (SCHEMA, SCHEMA_V2)


def _spectral_of(record):
    if is_spectral(record):
        return record
    return record.get("spectral") if type(record) is dict else None


def program(base, record=None):
    """`base` with the Level-2 changes: the pool restriction after TRAIN v1 is
    loaded, when `record` selects a pool, and the Level-2 build line when
    SpecMuon is on (a v1 SpecMuon record, or `record` None, as before)."""
    import textwrap

    if record is not None and record.get("schema") == SCHEMA_V2:
        if base.count(_POOL_ANCHOR) != 1:
            raise RuntimeError("the program's TRAIN load moved")
        base = base.replace(_POOL_ANCHOR, _POOL_RESTRICT + _POOL_ANCHOR)
        if record.get("spectral") is None:
            return base
    for indent in ("    ", ""):
        line = indent + _BUILD
        if base.count(line) == 1:
            return base.replace(line, textwrap.indent(_LEVEL2_BUILD, indent))
    raise RuntimeError("the program's build line moved")


def build_in_process(recipe, record):
    if _spectral_of(record) is None:
        from carbon.battery import recipes

        return recipes.build(recipe.family, recipe.settings)
    import jax

    if jax.default_backend() != "cpu":
        raise ImportError("level2_cpu_only_dev")
    from carbon.battery import level2_training

    return level2_training.build(recipe.family, recipe.settings)


def training_data(record, train):
    """The TRAIN a Level-2 record trains on: the drawn pool subset, else
    `train` itself."""
    if type(record) is dict and record.get("schema") == SCHEMA_V2:
        from carbon.battery import pools

        return pools.subset(train, record["pool"]["case_ids"])
    return train


def staged(record):
    import json

    carbon = Path(__file__).resolve().parents[1]
    files = {}
    if _spectral_of(record) is not None:
        files.update(
            {
                name: (carbon / folder / module).read_bytes()
                for name, (folder, module) in STAGED_MODULES.items()
            }
        )
    if type(record) is dict and record.get("schema") == SCHEMA_V2:
        pool = record["pool"]
        files[POOL_FILE] = json.dumps(
            {"cases": pool["cases"], "case_ids": pool["case_ids"]},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    return files
