"""G6 LEARNING-CURVE SUBSETS (STRONG_CHECKS_SPEC_20261102, G6): NESTED fractions of a version's PUBLIC TRAIN, by an explicit rule.

    g6_subsets.py --train TRAIN.npz --rule seed:<int> | index --count ceil | floor --out DIR [--fractions 0.25,0.5,1.0]
                  [--min-rows N]

The rule and the count are rulings (the Validator's), never defaults: both flags are required.

- ``--rule seed:<int>``: one permutation of the TRAIN row indices, ``numpy.random.default_rng(<int>).permutation(n)``; fraction f
  takes its first k(f) entries. ``--rule index``: the first k(f) rows in TRAIN order. Each subset is written in TRAIN row order
  (its indices sorted), so a subset is the same rows whatever order the rule drew them in.
- ``--count ceil``: k(f) = ceil(f * n); ``--count floor``: k(f) = floor(f * n) (the official graph trainer's own count,
  ``physical_graph_trainer_v2.selected_rows``: ``int(rows * train_fraction)``). Exact arithmetic on f's decimal text (``Fraction("0.25")``), so no
  float rounding moves a row (`g6_fit` checks the trainer's own draw against the subset before it fits).

Every fraction is a prefix of ONE ordering, so 25 % is inside 50 % is inside 100 % by construction. The 100 % subset is TRAIN
itself, byte-identical (copied, never re-saved). Each smaller subset is an npz with TRAIN's own array names, dtypes and column
order, written with a fixed zip timestamp so its sha256 is a function of the rows alone.

Writes ``DIR/train@frac:<f>.npz`` per fraction and ``DIR/g6-subsets.json``: {schema, rule, count, fractions, n_train, train
sha256, per fraction {n, sha256, file, indices_sha256}, the ordering's sha256}. Refuses an unknown rule or count, a fraction set
other than exactly {0.25, 0.5, 1.0} unless ``--fractions`` names it, a set without 1.0, a non-nested or empty subset, and any
subset with fewer rows than ``--min-rows`` (the model's declared minimum, when the caller gives one). It reads only the public
TRAIN; it fits nothing and grades nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import zipfile
from fractions import Fraction
from pathlib import Path

SCHEMA = "carbon.exam-reads.g6-subsets.v1"
DEFAULT_FRACTIONS = (0.25, 0.5, 1.0)
COUNTS = ("ceil", "floor")
MANIFEST = "g6-subsets.json"
#: The zip member timestamp of every written subset (zip's epoch), so equal rows give equal bytes.
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


class SubsetsRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise SubsetsRefused(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def frac_label(fraction):
    """The canonical text of a fraction (``repr`` of the float: ``0.25``, ``0.5``, ``1.0``), used in roles and file names."""
    return repr(float(fraction))


def parse_rule(text):
    """``("seed", int)`` or ``("index", None)``; anything else refuses."""
    _need(type(text) is str, "g6_rule_unknown")
    if text == "index":
        return ("index", None)
    kind, _, value = text.partition(":")
    _need(kind == "seed" and value.lstrip("-").isdigit(), "g6_rule_unknown")
    seed = int(value)
    _need(seed >= 0 and str(seed) == value, "g6_rule_unknown")
    return ("seed", seed)


def parse_fractions(text):
    """The fractions, ascending, each canonical, in (0, 1], distinct, 1.0 included."""
    parts = text.split(",")
    _need(all(p.strip() == p and p for p in parts), "g6_fractions_malformed")
    try:
        values = [float(p) for p in parts]
    except ValueError:
        raise SubsetsRefused("g6_fractions_malformed") from None
    _need(
        all(frac_label(v) == p for v, p in zip(values, parts, strict=True)),
        "g6_fractions_not_canonical",
    )
    _need(all(0.0 < v <= 1.0 for v in values), "g6_fraction_out_of_range")
    _need(len(set(values)) == len(values), "g6_fractions_repeat")
    _need(1.0 in values, "g6_fractions_need_1.0")
    return tuple(sorted(values))


def row_count(fraction, n, count):
    """k(f) by exact rational arithmetic: ceil or floor of f * n."""
    _need(count in COUNTS, "g6_count_unknown")
    exact = Fraction(frac_label(fraction)) * n
    k = -((-exact.numerator) // exact.denominator) if count == "ceil" else int(exact)
    return n if fraction == 1.0 else k


def ordering(rule, n):
    """The rule's ordering of the TRAIN row indices (a permutation of range(n))."""
    import numpy as np

    kind, seed = rule
    if kind == "index":
        return np.arange(n)
    return np.random.default_rng(seed).permutation(n)


def load_train(raw):
    """TRAIN's arrays by name, in file order (the repo layout ``inputs`` / ``targets``; ``X`` / ``Y`` accepted)."""
    import numpy as np

    try:
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            names = list(archive.files)
            arrays = {name: archive[name].copy() for name in names}
    except (OSError, ValueError, zipfile.BadZipFile):
        raise SubsetsRefused("g6_train_not_an_npz") from None
    _need(
        set(names) in ({"inputs", "targets"}, {"X", "Y"}),
        "g6_train_needs_inputs_targets_or_X_Y",
    )
    lengths = {len(a) for a in arrays.values()}
    _need(
        len(lengths) == 1 and all(a.ndim >= 1 for a in arrays.values()),
        "g6_train_row_counts_differ",
    )
    n = lengths.pop()
    _need(n >= 1, "g6_train_empty")
    return names, arrays, n


def npz_bytes(names, arrays):
    """An npz of ``arrays`` (``np.savez``'s layout: one ``<name>.npy`` member each, stored) with a fixed member timestamp."""
    import numpy as np

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in names:
            info = zipfile.ZipInfo(name + ".npy", date_time=ZIP_TIME)
            with archive.open(info, "w", force_zip64=True) as member:
                np.lib.format.write_array(
                    member, np.ascontiguousarray(arrays[name]), allow_pickle=False
                )
    return buffer.getvalue()


def make_subsets(train_raw, rule_text, count, fractions, *, min_rows=None):
    """``(manifest_without_files, {fraction: bytes})``: the nested subsets of TRAIN (see the module docstring)."""
    import numpy as np

    rule = parse_rule(rule_text)
    _need(count in COUNTS, "g6_count_unknown")
    _need(
        min_rows is None or (type(min_rows) is int and min_rows >= 1),
        "g6_min_rows_invalid",
    )
    names, arrays, n = load_train(train_raw)
    order = ordering(rule, n)
    out, rows = {}, {}
    previous = frozenset()
    for fraction in fractions:
        k = row_count(fraction, n, count)
        _need(k >= 1, "g6_subset_empty")
        _need(min_rows is None or k >= min_rows, "g6_subset_below_model_minimum")
        indices = np.sort(order[:k])
        chosen = frozenset(int(i) for i in indices)
        _need(previous <= chosen, "g6_subsets_not_nested")
        previous = chosen
        if fraction == 1.0:
            _need(k == n, "g6_full_fraction_is_not_train")
            raw = train_raw
        else:
            raw = npz_bytes(names, {name: arrays[name][indices] for name in names})
        out[fraction] = raw
        rows[fraction] = {
            "n": k,
            "sha256": _sha(raw),
            "indices_sha256": _sha(np.asarray(indices, dtype="<i8").tobytes()),
        }
    manifest = {
        "schema": SCHEMA,
        "rule": rule_text,
        "count": count,
        "fractions": [frac_label(f) for f in fractions],
        "n_train": n,
        "train_sha256": _sha(train_raw),
        "ordering_sha256": _sha(np.asarray(order, dtype="<i8").tobytes()),
        "subsets": {frac_label(f): rows[f] for f in fractions},
        "nested": "every fraction is a prefix of one ordering of the TRAIN rows",
        "row_order": "TRAIN order within each subset",
        "scratch_only": True,
    }
    return manifest, out


def subset_indices(manifest, fraction, n):
    """The TRAIN row indices of ``fraction``'s subset, re-derived from the manifest's rule and count and checked against its
    recorded ``indices_sha256`` (so a reader never trusts a file name)."""
    import numpy as np

    label = frac_label(fraction)
    _need(label in manifest["subsets"], "g6_fraction_not_in_manifest")
    _need(manifest["n_train"] == n, "g6_manifest_train_rows_differ")
    order = ordering(parse_rule(manifest["rule"]), n)
    _need(
        _sha(np.asarray(order, dtype="<i8").tobytes()) == manifest["ordering_sha256"],
        "g6_manifest_ordering_differs",
    )
    k = row_count(fraction, n, manifest["count"])
    _need(k == manifest["subsets"][label]["n"], "g6_manifest_count_differs")
    indices = np.sort(order[:k])
    _need(
        _sha(np.asarray(indices, dtype="<i8").tobytes())
        == manifest["subsets"][label]["indices_sha256"],
        "g6_manifest_indices_differ",
    )
    return order, indices


def write(train_path, rule_text, count, fractions, out_dir, *, min_rows=None):
    out_dir = Path(out_dir)
    _need(not out_dir.exists(), "g6_out_exists")
    raw = Path(train_path).read_bytes()
    manifest, files = make_subsets(raw, rule_text, count, fractions, min_rows=min_rows)
    out_dir.mkdir(parents=True)
    for fraction, data in files.items():
        name = f"train@frac:{frac_label(fraction)}.npz".replace(":", "_")
        if fraction == 1.0:
            shutil.copyfile(train_path, out_dir / name)
            _need(
                _sha((out_dir / name).read_bytes()) == manifest["train_sha256"],
                "g6_train_copy_differs",
            )
        else:
            (out_dir / name).write_bytes(data)
        manifest["subsets"][frac_label(fraction)]["file"] = name
    text = json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    (out_dir / MANIFEST).write_bytes(text.encode())
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--rule", required=True, help="seed:<int> or index")
    parser.add_argument("--count", required=True, choices=COUNTS)
    parser.add_argument("--fractions", help="comma list, ascending, with 1.0")
    parser.add_argument("--min-rows", type=int)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        fractions = (
            DEFAULT_FRACTIONS
            if args.fractions is None
            else parse_fractions(args.fractions)
        )
        manifest = write(
            args.train,
            args.rule,
            args.count,
            fractions,
            args.out,
            min_rows=args.min_rows,
        )
    except SubsetsRefused as refused:
        print(f"REFUSED: {refused.code}", file=sys.stderr)
        return 2
    print(_sha((args.out / MANIFEST).read_bytes()), MANIFEST)
    for label, row in manifest["subsets"].items():
        print(row["sha256"], row["file"], f"n={row['n']}", f"frac={label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
