"""G6 LEARNING-CURVE SUBSETS (STRONG_CHECKS_SPEC_20261102, G6): NESTED fractions of a version's PUBLIC TRAIN, by an explicit rule.

    g6_subsets.py --train TRAIN.npz --rule sha256:<version> | seed:<int> | index --count half_up | ceil | floor --out DIR
                  [--stratum-input COLUMN] [--fractions 0.25,0.5,1.0] [--min-rows N]

The rule and the count are rulings (the Validator's), never defaults: both flags are required. THE RULED FORM (Validator 3 Nov
15:46, G6 SUBSET RULE): ``--rule sha256:<version> --count half_up`` (``--stratum-input`` for a version with a registered
stratum, e.g. RB's alloy column):

- ``--rule sha256:<version>``: the TRAIN rows ordered by ``sha256("carbon.g6.subset.v1/<version>/<row_id>")`` (hex, ascending), the
  row_id being the row's 0-based index in the pinned TRAIN file (its sha256 is in the manifest, so the ids are stable); fraction f
  takes the first k(f) of that order.
- ``--count half_up``: k(f) = floor(f * n + 1/2) (round half up).
- ``--stratum-input COLUMN``: STRATIFIED: the order is split by the value of inputs[:, COLUMN] and each stratum takes its own
  first half_up(f * n_stratum) rows of the same global order (so every fraction stays nested, per stratum and overall).

- ``--rule seed:<int>``: one permutation of the TRAIN row indices, ``numpy.random.default_rng(<int>).permutation(n)``; fraction f
  takes its first k(f) entries. ``--rule index``: the first k(f) rows in TRAIN order. Each subset is written in TRAIN row order
  (its indices sorted), so a subset is the same rows whatever order the rule drew them in.
- ``--count ceil``: k(f) = ceil(f * n); ``--count floor``: k(f) = floor(f * n) (the official graph trainer's own count,
  ``physical_graph_trainer_v2.selected_rows``: ``int(rows * train_fraction)``). Exact arithmetic on f's decimal text (``Fraction("0.25")``), so no
  float rounding moves a row (`g6_fit` fits the subset file's own rows, checked byte-equal to TRAIN's rows at its indices).

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
COUNTS = ("half_up", "ceil", "floor")
#: The ruled ordering's key prefix (Validator 15:46).
SHA_KEY = "carbon.g6.subset.v1"
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
    """``("sha256", version)``, ``("seed", int)`` or ``("index", None)``; anything else refuses."""
    _need(type(text) is str, "g6_rule_unknown")
    if text == "index":
        return ("index", None)
    if text.startswith("sha256:"):
        version = text[len("sha256:") :]
        _need(
            bool(version) and "/" not in version and version.strip() == version,
            "g6_rule_unknown",
        )
        return ("sha256", version)
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
    if count == "half_up":
        k = int(exact + Fraction(1, 2))
    elif count == "ceil":
        k = -((-exact.numerator) // exact.denominator)
    else:
        k = int(exact)
    return n if fraction == 1.0 else k


def ordering(rule, n):
    """The rule's ordering of the TRAIN row indices (a permutation of range(n))."""
    import numpy as np

    kind, value = rule
    if kind == "index":
        return np.arange(n)
    if kind == "sha256":
        keys = [
            hashlib.sha256(f"{SHA_KEY}/{value}/{i}".encode()).hexdigest()
            for i in range(n)
        ]
        return np.asarray(sorted(range(n), key=lambda i: keys[i]), dtype=np.int64)
    return np.random.default_rng(value).permutation(n)


def strata_of(arrays, column, n):
    """Each TRAIN row's stratum (the value of inputs[:, column]), or None for no stratification."""
    if column is None:
        return None
    inputs = arrays.get("inputs", arrays.get("X"))
    _need(
        type(column) is int and inputs.ndim == 2 and 0 <= column < inputs.shape[1],
        "g6_stratum_input_invalid",
    )
    return [inputs[i, column].item() for i in range(n)]


def select(order, fraction, n, count, strata):
    """The rows of ``fraction``: the first k(f) of ``order``, or per stratum its own first k(f, n_stratum) of the same order."""
    import numpy as np

    if strata is None:
        return np.sort(order[: row_count(fraction, n, count)])
    chosen = []
    for stratum in sorted(set(strata), key=repr):
        members = [int(i) for i in order if strata[int(i)] == stratum]
        chosen += members[: row_count(fraction, len(members), count)]
    return np.sort(np.asarray(chosen, dtype=np.int64))


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


def make_subsets(
    train_raw, rule_text, count, fractions, *, min_rows=None, stratum_input=None
):
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
    strata = strata_of(arrays, stratum_input, n)
    out, rows = {}, {}
    previous = frozenset()
    for fraction in fractions:
        indices = select(order, fraction, n, count, strata)
        k = len(indices)
        _need(k >= 1, "g6_subset_empty")
        _need(min_rows is None or k >= min_rows, "g6_subset_below_model_minimum")
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
        "stratum_input": stratum_input,
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


def subset_indices(manifest, fraction, n, arrays=None):
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
    strata = None
    if manifest.get("stratum_input") is not None:
        _need(arrays is not None, "g6_manifest_needs_train_for_strata")
        strata = strata_of(arrays, manifest["stratum_input"], n)
    indices = select(order, fraction, n, manifest["count"], strata)
    _need(len(indices) == manifest["subsets"][label]["n"], "g6_manifest_count_differs")
    _need(
        _sha(np.asarray(indices, dtype="<i8").tobytes())
        == manifest["subsets"][label]["indices_sha256"],
        "g6_manifest_indices_differ",
    )
    return order, indices


def write(
    train_path,
    rule_text,
    count,
    fractions,
    out_dir,
    *,
    min_rows=None,
    stratum_input=None,
):
    out_dir = Path(out_dir)
    _need(not out_dir.exists(), "g6_out_exists")
    raw = Path(train_path).read_bytes()
    manifest, files = make_subsets(
        raw, rule_text, count, fractions, min_rows=min_rows, stratum_input=stratum_input
    )
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
    parser.add_argument(
        "--rule",
        required=True,
        help="sha256:<version> (the ruled form), seed:<int> or index",
    )
    parser.add_argument("--stratum-input", type=int)
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
            stratum_input=args.stratum_input,
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
