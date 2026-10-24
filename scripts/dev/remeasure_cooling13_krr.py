"""Re-measure Cooling 1.3's practice baseline by the practice dual v2 ($0, local, CPU).

The baseline is the registered learned-krr-v1 in its 1.3-native bundle
(docs/development/evidence/cooling13-native-krr-baseline-v1). Its earlier record was
measured by the first practice dual (the development bank, v1 legs); practice now shows the
exam's own v2 legs on the practice grid (`practice_dual.feedback_v2`), so the "beat this"
line is re-measured by exactly that code and the record rewritten:

    python scripts/dev/remeasure_cooling13_krr.py --out RECORD.json

Needs torch (the bundle trains a torch KRR on CPU). The record cites the code head it ran
at (the commit that holds this script), the environment, the strategy (the recipe digest)
and the practice bank's digest. Aggregates only: the practice dual document carries leg
values and failed gate names, never per-case values.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import platform
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "docs/development/evidence/cooling13-native-krr-baseline-v1"
CHALLENGE = ("chip-cold-plate", "1.3")
RECIPE_DIGEST = (
    "sha256:ffde968a02665765afb346307b9ce1935bde838d67a3c2ace5273521778629d1"
)
SCHEMA = "carbon.practice-baseline-record.v1"


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _build_module(directory: Path):
    with tarfile.open(
        fileobj=io.BytesIO((PACKET / "source.tar.gz").read_bytes())
    ) as tar:
        (member,) = [
            m for m in tar.getmembers() if m.name.endswith("carbon_candidate/build.py")
        ]
        path = directory / "build.py"
        path.write_bytes(tar.extractfile(member).read())
    spec = importlib.util.spec_from_file_location("cooling13_native_krr_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measure():
    import torch

    from carbon.challenge_kit import physical_public_train
    from carbon.cold_plate import output_encoding
    from carbon.scoring import physical_dual_pack as physical
    from carbon.scoring import practice_dual, practice_grid

    recipe = json.loads((PACKET / "recipe.json").read_bytes())
    if _sha(_canonical(recipe)) != RECIPE_DIGEST:
        raise SystemExit("the packet's recipe is not the receipted one")
    train = physical_public_train.load_public_train("chip-cold-plate")
    with tempfile.TemporaryDirectory() as tmp:
        module = _build_module(Path(tmp))
        model = module.build(
            np.asarray(train["inputs"], float),
            output_encoding.encode_targets(np.asarray(train["targets"], float)),
            seed=0,
            configuration=recipe["procedure"]["configuration"],
            train_use={"cases": "all"},
        )

    def predict(inputs):
        x = np.asarray([[float(v) for v in row.values()] for row in inputs], float)
        return model["apply"](model["parameters"], torch.from_numpy(x)).numpy().tolist()

    document = practice_dual.feedback_v2("cooling", CHALLENGE[1], predict)
    bank = practice_grid.practice_bank("cooling", CHALLENGE[1])
    return document, physical.bank_digest(bank)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    document, bank_digest = measure()
    if document.get("available") is not True or document.get("total") is None:
        raise SystemExit("the baseline did not score: " + json.dumps(document)[:300])
    import torch

    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    record = {
        "schema": SCHEMA,
        "evidence": "DEVELOPMENT",
        "label": "practice baseline on the public bank",
        "challenge": {"id": CHALLENGE[0], "version": CHALLENGE[1]},
        "model": "learned-krr-v1 (1.3-native bundle)",
        "measurement": (
            "carbon.scoring.cooling_encoded_dual_pack via practice_dual.feedback_v2"
        ),
        "bundle_digest": _sha(
            _canonical(json.loads((PACKET / "bundle.json").read_bytes()))
        ),
        "strategy_digest": RECIPE_DIGEST,
        "bank_digest": bank_digest,
        "code_head": head,
        "n_cases": document.get("n_cases"),
        "environment": {
            "numpy": np.__version__,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
        },
        "practice_dual": document,
        "score": document["total"],
        "qualification": False,
    }
    args.out.write_bytes(json.dumps(record, indent=1, sort_keys=True).encode() + b"\n")
    print(json.dumps({"score": record["score"], "code_head": head}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
