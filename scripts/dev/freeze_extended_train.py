"""Freeze one extended public TRAIN (Motor 1.8 / Cooling 1.8) from its typed-OK added reference records.

    python3 -I scripts/dev/freeze_extended_train.py NAME OUT_DIR RECORDS.jsonl [RECORDS.jsonl ...]
    python3 -I scripts/dev/freeze_extended_train.py NAME OUT_DIR --encoded      (Cooling: from the frozen native twin)

NAME is a key of `physical_public_train.EXTENDED` or `FRESH_LAMBDA` (Motor 1.8: ALL its records, the re-solved
TRAIN rows with their train-NNNN ids included; the TRAIN 150 torque must be byte-equal, else it refuses). A native TRAIN is assembled with `assemble_extended_source` (the
Challenge's native TRAIN lines byte-equal, then the added records: typed-OK only, allow-listed fields, predicted outputs
only, ordered by their inputs, renumbered) and derived with `derive_extended_public_train`. An encoded TRAIN is derived
from its native twin, which must already be pinned in this checkout. Writes OUT_DIR/NAME.{source.jsonl,npz,
provenance.json} (never overwrites) and prints the pins to copy into EXTENDED (rows + sha256s) - nothing else: no input or
output value. The added records come from the custody merge; a non-OK row is refused, never silently dropped.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from carbon.challenge_kit import physical_public_train as ppt


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _write(path, raw):
    if path.exists():
        raise SystemExit(f"refused: {path.name} exists; never overwrite")
    path.write_bytes(raw)


def main(argv):
    if len(argv) < 3:
        raise SystemExit(__doc__)
    name, out = argv[0], Path(argv[1])
    fresh = name in ppt.FRESH_LAMBDA
    spec = ppt.FRESH_LAMBDA[name] if fresh else ppt.EXTENDED.get(name)
    if spec is None:
        raise SystemExit(f"refused: {name!r} is not an extended or fresh TRAIN")
    if fresh:
        spec = {**spec, "encoded_from": None}
    out.mkdir(parents=True, exist_ok=True)
    pins = {"name": name}
    if argv[2:] == ["--encoded"]:
        if spec["encoded_from"] is None:
            raise SystemExit("refused: --encoded needs an encoded TRAIN name")
        native = ppt.load_extended_train(spec["encoded_from"], spec["challenge"])
        raw, provenance = ppt.derive_extended_encoded_public_train(name, native)
    else:
        if spec["encoded_from"] is not None:
            raise SystemExit("refused: an encoded TRAIN takes --encoded, not records")
        records = []
        for path in argv[2:]:
            for line in Path(path).read_text(encoding="utf-8").splitlines():
                if line.strip():
                    records.append(json.loads(line))
        if (
            fresh
        ):  # Motor 1.8: every row from record-now; TRAIN 150 torque byte-equal or REFUSE
            source = ppt.assemble_motor18_source(records)
            raw, provenance = ppt.derive_motor18_public_train(name, source)
        else:
            source = ppt.assemble_extended_source(spec["challenge"], records)
            raw, provenance = ppt.derive_extended_public_train(name, source)
        _write(out / f"{name}.source.jsonl", source)
        pins["source_sha256"] = _sha(source)
    provenance_raw = (json.dumps(provenance, indent=1, sort_keys=True) + "\n").encode()
    _write(out / f"{name}.npz", raw)
    _write(out / f"{name}.provenance.json", provenance_raw)
    pins.update(
        rows=len(provenance["case_ids"]),
        train_sha256=_sha(raw),
        provenance_sha256=_sha(provenance_raw),
    )
    print(json.dumps(pins, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
