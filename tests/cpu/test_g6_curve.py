"""G6 LEARNING CURVE (`g6_subsets`, `g6_fit`, the ``@frac`` roles of `checks_report`, G6 in `g_reports`).

Claims: the subsets are nested by construction, deterministic to the byte, the 100 % subset is TRAIN itself, and an unknown
rule / count, a malformed or 1.0-less fraction set, a subset below the declared minimum and an existing output are refused;
the fit driver writes rows of the QUERY's shape for both contenders at every fraction, with the subset and rows sha256 in each
record and the record's sha256 in its contender entry; the default model goes through the official graph route v2 build at
seed 0 on exactly the subset's rows (POSIX, a tiny fixture recipe); ``@frac`` roles grade like any contender but never enter
the panel, and check (1K)'s member roles are unchanged; G6 is MEASURED from them with A per class and fraction, the
monotonicity flags and the default - shortcut gap; without them G6 is the old NOT_RUN. Every value is synthetic.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "scripts" / "dev" / "exam_reads")
)

import checks_kit
import checks_report as report
import g6_fit
import g6_subsets as subsets
import g_reports
import q3_q8_whatif as reads
import test_checks_report as fake

from carbon.scoring import pool_version

posix = pytest.mark.skipif(os.name != "posix", reason="isolated build programs")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _train_npz(n=10, d=3, m=2, seed=0):
    rng = np.random.default_rng(seed)
    buffer = io.BytesIO()
    np.savez(buffer, inputs=rng.uniform(0, 1, (n, d)), targets=rng.normal(0, 1, (n, m)))
    return buffer.getvalue()


def _arrays(raw):
    with np.load(io.BytesIO(raw), allow_pickle=False) as z:
        return z["inputs"].copy(), z["targets"].copy()


def _write_train(tmp_path, raw):
    path = tmp_path / "train.npz"
    path.write_bytes(raw)
    return path


# ---------------------------------------------------------------- subsets


def test_the_subsets_are_nested_deterministic_and_the_full_one_is_train(tmp_path):
    raw = _train_npz()
    path = _write_train(tmp_path, raw)
    manifest = subsets.write(path, "seed:7", "ceil", (0.25, 0.5, 1.0), tmp_path / "a")
    again = subsets.write(path, "seed:7", "ceil", (0.25, 0.5, 1.0), tmp_path / "b")
    assert (tmp_path / "a" / subsets.MANIFEST).read_bytes() == (
        tmp_path / "b" / subsets.MANIFEST
    ).read_bytes()
    assert [manifest["subsets"][f]["n"] for f in ("0.25", "0.5", "1.0")] == [3, 5, 10]
    assert manifest["train_sha256"] == _sha(raw) and manifest["n_train"] == 10
    full = (tmp_path / "a" / manifest["subsets"]["1.0"]["file"]).read_bytes()
    assert full == raw
    x, y = _arrays(raw)
    order = np.random.default_rng(7).permutation(10)
    previous = set()
    for label, k in (("0.25", 3), ("0.5", 5)):
        row = manifest["subsets"][label]
        data = (tmp_path / "a" / row["file"]).read_bytes()
        assert _sha(data) == row["sha256"] == again["subsets"][label]["sha256"]
        sx, sy = _arrays(data)
        indices = np.sort(order[:k])
        np.testing.assert_array_equal(sx, x[indices])
        np.testing.assert_array_equal(sy, y[indices])
        assert previous <= set(indices.tolist())
        previous = set(indices.tolist())
        _order, derived = subsets.subset_indices(manifest, float(label), 10)
        np.testing.assert_array_equal(derived, indices)


def test_the_index_rule_takes_the_first_rows_and_floor_counts_down(tmp_path):
    raw = _train_npz()
    manifest = subsets.write(
        _write_train(tmp_path, raw), "index", "floor", (0.25, 0.5, 1.0), tmp_path / "o"
    )
    assert [manifest["subsets"][f]["n"] for f in ("0.25", "0.5", "1.0")] == [2, 5, 10]
    sx, _ = _arrays((tmp_path / "o" / manifest["subsets"]["0.25"]["file"]).read_bytes())
    np.testing.assert_array_equal(sx, _arrays(raw)[0][:2])


@pytest.mark.parametrize(
    "rule, count, code",
    [
        ("random", "ceil", "g6_rule_unknown"),
        ("seed:-1", "ceil", "g6_rule_unknown"),
        ("seed:x", "ceil", "g6_rule_unknown"),
        ("seed:07", "ceil", "g6_rule_unknown"),
        ("seed:1", "round", "g6_count_unknown"),
    ],
)
def test_an_unknown_rule_or_count_is_refused(tmp_path, rule, count, code):
    with pytest.raises(subsets.SubsetsRefused, match=code):
        subsets.make_subsets(_train_npz(), rule, count, (0.25, 0.5, 1.0))


@pytest.mark.parametrize(
    "text, code",
    [
        ("0.25,0.5", "g6_fractions_need_1.0"),
        (".25,0.5,1.0", "g6_fractions_not_canonical"),
        ("0.25,0.25,1.0", "g6_fractions_repeat"),
        ("0.25,1.5", "g6_fraction_out_of_range"),
        ("a,1.0", "g6_fractions_malformed"),
    ],
)
def test_a_malformed_fraction_set_is_refused(text, code):
    with pytest.raises(subsets.SubsetsRefused, match=code):
        subsets.parse_fractions(text)


def test_only_the_named_default_set_is_taken_without_the_flag(tmp_path):
    assert subsets.DEFAULT_FRACTIONS == (0.25, 0.5, 1.0)
    assert subsets.parse_fractions("0.1,0.5,1.0") == (0.1, 0.5, 1.0)
    path = _write_train(tmp_path, _train_npz())
    assert (
        subsets.main(
            [
                "--train",
                str(path),
                "--rule",
                "index",
                "--count",
                "ceil",
                "--out",
                str(tmp_path / "o"),
            ]
        )
        == 0
    )
    doc = json.loads((tmp_path / "o" / subsets.MANIFEST).read_text())
    assert doc["fractions"] == ["0.25", "0.5", "1.0"]
    # the rule is a ruling: no default
    with pytest.raises(SystemExit):
        subsets.main(["--train", str(path), "--count", "ceil", "--out", "x"])


def test_a_subset_below_the_declared_minimum_and_an_existing_output_are_refused(
    tmp_path,
):
    with pytest.raises(subsets.SubsetsRefused, match="g6_subset_below_model_minimum"):
        subsets.make_subsets(_train_npz(), "seed:1", "ceil", (0.25, 1.0), min_rows=4)
    path = _write_train(tmp_path, _train_npz())
    (tmp_path / "o").mkdir()
    with pytest.raises(subsets.SubsetsRefused, match="g6_out_exists"):
        subsets.write(path, "seed:1", "ceil", (0.25, 1.0), tmp_path / "o")


# ---------------------------------------------------------------- the fit driver (the shortcut; the default without a recipe)


def _fit_args(tmp_path, query_path, query_sha, **over):
    return Namespace(**{**_fit_defaults(tmp_path, query_path, query_sha), **over})


def _fit_defaults(tmp_path, query_path, query_sha):
    return {
        "subsets": tmp_path / "subsets",
        "train": tmp_path / "train.npz",
        "query": query_path,
        "query_sha256": query_sha,
        "member": "knn",
        "shortcut_role": "knn",
        "shortcut_catalog_id": "shortcut_panel:knn",
        "shortcut_fit": "default",
        "recipe": None,
        "submission_dir": None,
        "default_catalog_id": None,
        "out": tmp_path / "fit",
    }


def test_the_fit_driver_writes_rows_and_records_for_every_fraction(tmp_path):
    raw = _train_npz(n=24)
    subsets.write(
        _write_train(tmp_path, raw),
        "seed:3",
        "ceil",
        (0.25, 0.5, 1.0),
        tmp_path / "subsets",
    )
    query = np.random.default_rng(1).uniform(0, 1, (5, 3))
    buffer = io.BytesIO()
    np.save(buffer, query)
    (tmp_path / "query.npy").write_bytes(buffer.getvalue())
    fragment = g6_fit.run(
        _fit_args(tmp_path, tmp_path / "query.npy", _sha(buffer.getvalue()))
    )
    manifest = json.loads((tmp_path / "subsets" / subsets.MANIFEST).read_text())
    roles = [c["role"] for c in fragment["contenders"]]
    assert roles == ["knn@frac:0.25", "knn@frac:0.5", "knn@frac:1.0"]
    assert [e["role"] for e in fragment["not_run"]] == [
        "default_model@frac:0.25",
        "default_model@frac:0.5",
        "default_model@frac:1.0",
    ]
    assert {e["code"] for e in fragment["not_run"]} == {"default_subset_build_unavailable"}
    for entry in fragment["contenders"]:
        assert set(entry) == report.CONTENDER_KEYS
        data = Path(entry["rows_npy"]).read_bytes()
        assert _sha(data) == entry["sha256"]
        assert np.load(io.BytesIO(data)).shape == (5, 2)
        safe = entry["role"].replace(":", "_")
        record_raw = (tmp_path / "fit" / "records" / f"{safe}.json").read_bytes()
        assert entry["record_sha256"] == "sha256:" + _sha(record_raw)
        record = json.loads(record_raw)
        label = record["fraction"]
        assert record["subset"]["sha256"] == manifest["subsets"][label]["sha256"]
        assert record["rows_sha256"] == entry["sha256"] and record["seed"] == 0
        assert record["fit"]["n_train"] == manifest["subsets"][label]["n"]
    with pytest.raises(subsets.SubsetsRefused, match="g6_out_exists"):
        g6_fit.run(_fit_args(tmp_path, tmp_path / "query.npy", _sha(buffer.getvalue())))
    with pytest.raises(subsets.SubsetsRefused, match="g6_query_sha256_differs"):
        g6_fit.run(
            _fit_args(tmp_path, tmp_path / "query.npy", "0" * 64, out=tmp_path / "x")
        )


@posix
def test_the_default_model_is_the_official_graph_build_on_the_subset_rows(
    tmp_path, monkeypatch
):
    import test_graph_route_v2 as graph

    from carbon.development_session import physical_graph_adapter_v2 as adapter

    key = (graph.F08, "1.5")
    spec = adapter.SPECS[key]
    recipe, raw_manifest, files, _ = graph._case(key, {"training": {"steps": 8}})
    raw_train, inputs, targets = graph._train(key)
    manifest = subsets.write(
        _write_train(tmp_path, raw_train),
        "sha256:1.5",
        "half_up",
        (0.25, 0.5, 1.0),
        tmp_path / "s",
    )
    query = np.asarray(inputs[:3], dtype=np.float64)
    recipe_bytes = bytes(recipe.canonical_bytes)
    from carbon.development_session import physical_graph_trainer_v2 as trainer

    used = []
    real_train = trainer.train
    monkeypatch.setattr(
        trainer,
        "train",
        lambda prepared, x, y, settings, **kw: used.append(
            (x.copy(), y.copy(), settings)
        )
        or real_train(prepared, x, y, settings, **kw),
    )
    for label in manifest["fractions"]:
        data = (tmp_path / "s" / manifest["subsets"][label]["file"]).read_bytes()
        rows, record = g6_fit.default_rows(
            recipe.canonical_bytes,
            raw_manifest,
            files,
            raw_train,
            manifest,
            float(label),
            data,
            query,
        )
        assert record["status"] == "FITTED", record
        assert rows.shape == (3, spec.outputs) and np.isfinite(rows).all()
        k = manifest["subsets"][label]["n"]
        assert record["fit"]["train_cases"] == record["train_cases"] == k
        # the recipe is the published one, unchanged (train_fraction 1.0)
        assert bytes(recipe.canonical_bytes) == recipe_bytes
        assert record["recipe_digest"] == recipe.digest
        # the rows the trainer saw are exactly the ruled subset's
        x, y, settings = used[-1]
        assert settings["train_fraction"] == 1.0
        _o, indices = subsets.subset_indices(manifest, float(label), spec.rows)
        assert x.tobytes() == inputs[indices].tobytes()
        assert y.tobytes() == targets[indices].tobytes()
        if label == "1.0":
            model = adapter.build_validated_graph(
                recipe,
                raw_manifest,
                files,
                allowlist_bytes=adapter.served_allowlist_bytes(*key),
                train_cases=spec.rows,
            )
            model.fit(inputs, targets, seed=0)
            np.testing.assert_array_equal(
                rows,
                np.asarray(
                    model.predict(np.asarray(query, spec.dtype), isolated=True),
                    dtype=np.float64,
                ),
            )

    # a subset smaller than the recipe's batch is NOT_RUN, as the official path refuses a batch over its TRAIN rows
    tiny = subsets.write(
        _write_train(tmp_path, raw_train),
        "sha256:1.5",
        "half_up",
        (0.02, 1.0),
        tmp_path / "tiny",
    )
    data = (tmp_path / "tiny" / tiny["subsets"]["0.02"]["file"]).read_bytes()
    assert tiny["subsets"]["0.02"]["n"] < 8
    rows, record = g6_fit.default_rows(
        recipe.canonical_bytes, raw_manifest, files, raw_train, tiny, 0.02, data, query
    )
    assert rows is None and record == {
        "status": "NOT_RUN",
        "code": "g6_batch_exceeds_subset",
    }


# ---------------------------------------------------------------- @frac roles, the checks run and G6


def test_frac_roles_validate_without_widening_the_existing_roles():
    assert report.frac_role("default_model@frac:0.25") == ("default_model", 0.25)
    assert report.frac_role("gp@frac:1.0") == ("gp", 1.0)
    assert report.frac_role("king_replay:k1@frac:0.5") == ("king_replay:k1", 0.5)
    for bad in (
        "gp@frac:.25",
        "gp@frac:1.5",
        "gp@frac:0",
        "tuned_operator@frac:0.5",
        "gp@frac:0.5@frac:0.5",
        "gp",
        None,
    ):
        assert report.frac_role(bad) is None
    assert not report._role_ok("gp@frac:0.5")
    assert not checks_kit._member_role_ok("gp@frac:0.5")


@pytest.fixture
def stubbed(tmp_path, monkeypatch):
    monkeypatch.setattr(reads, "Regrader", fake._StubRegrader)
    monkeypatch.setattr(
        pool_version, "registered_policies", lambda *a, **k: fake.POLICIES
    )
    monkeypatch.setattr(
        reads,
        "_class_source",
        lambda source: (
            fake._klass,
            {"base": {"x": 0, "y": 0}},
            frozenset({report.IN_TRAIN, fake.OUTER}),
            {"rule_sha256": "r", "region_sha256": "g", "plan_params_sha256": "p"},
        ),
    )
    config = {"challenge": "c", "version": "v", "margin_n": 0.03}
    (tmp_path / "config.json").write_text(json.dumps(config))
    return config, tmp_path / "config.json"


#: Synthetic curves (the stub predicts truth + v x U): the default's error falls with data, the shortcut's plateaus.
FRAC_VALUES = {
    "default_model@frac:0.25": 3.0,
    "default_model@frac:0.5": 2.0,
    "default_model@frac:1.0": 1.0,
    "gp@frac:0.25": 2.0,
    "gp@frac:0.5": 2.0,
    "gp@frac:1.0": 2.0,
}


def _run(config, config_path, tmp_path, with_frac):
    path = fake._inputs(tmp_path)
    doc = json.loads(path.read_text())
    if with_frac:
        doc["contenders"] += [
            fake._contender(tmp_path, role, v) for role, v in FRAC_VALUES.items()
        ]
    path.write_text(json.dumps(doc))
    sink = {}
    checks = report.run_report(config, config_path, path, keep=sink)
    g = g_reports.build(
        checks,
        sink,
        {"g2_threshold": None, "g3_floor_n": None, "g8_practice_inputs": None},
    )
    return checks, g


def test_g6_is_measured_from_the_frac_contenders(stubbed, tmp_path):
    config, config_path = stubbed
    plain, _ = _run(config, config_path, tmp_path / "a", with_frac=False)
    checks, g = _run(config, config_path, tmp_path / "b", with_frac=True)
    # the @frac contenders never enter the panel: best shortcut and check (1) are unchanged
    for a, b in zip(plain["classes"], checks["classes"], strict=True):
        assert a["best_shortcut"] == b["best_shortcut"] == "gp"
    assert set(checks["checks"]["1_shortcuts_out_of_range"][fake.OUTER]) == {
        "engineer_shortcut",
        "gp",
    }
    assert checks["checks"]["3_default"] == plain["checks"]["3_default"]
    g6 = g["G6_learning_curve"]
    assert g6["status"] == "MEASURED"
    assert g6["contenders"] == {
        "default_model": ["0.25", "0.5", "1.0"],
        "gp": ["0.25", "0.5", "1.0"],
    }
    assert set(g6["by_class"]) == {report.IN_TRAIN, fake.OUTER}
    for row in g6["by_class"].values():
        default = row["curves"]["default_model"]
        shortcut = row["curves"]["gp"]
        a = [default["fractions"][f]["A"]["value"] for f in ("0.25", "0.5", "1.0")]
        assert a[0] < a[1] < a[2]
        assert default["fractions"]["0.25"]["A"]["ci95"] is not None
        assert default["fractions"]["0.25"]["D"] is None
        assert default["a_rises_with_fraction"] is True
        assert default["a_strictly_rises_with_fraction"] is True
        assert shortcut["a_rises_with_fraction"] is True
        assert shortcut["a_strictly_rises_with_fraction"] is False
        assert set(default["err_over_u_median_falls_with_fraction"].values()) == {True}
        assert default["fractions"]["1.0"]["err_over_u"]["f"][
            "median"
        ] == pytest.approx(1.0)
        gaps = row["gap_default_minus_shortcut"]["gp"]
        assert gaps["0.25"]["gap"]["value"] < 0 < gaps["1.0"]["gap"]["value"]
        assert gaps["1.0"]["gap_paired"]["paired"] is True
        assert gaps["1.0"]["gap_paired"]["value"] == pytest.approx(
            gaps["1.0"]["gap"]["value"]
        )
    assert "owner" in g6["bars"]


def test_without_frac_contenders_g6_is_the_old_not_run(stubbed, tmp_path):
    config, config_path = stubbed
    _checks, g = _run(config, config_path, tmp_path, with_frac=False)
    assert g["G6_learning_curve"] == {
        "status": "NOT_RUN",
        "needs": "default-model and best-shortcut rows trained on 25 / 50 / 100 % of TRAIN",
    }


# ---------------------------------------------------------------- the ruled form (Validator 3 Nov 15:46)


def test_the_ruled_order_is_the_sha256_of_the_versioned_row_key():
    import hashlib

    order = subsets.ordering(("sha256", "9.9-test"), 12)
    keys = [
        hashlib.sha256(f"carbon.g6.subset.v1/9.9-test/{i}".encode()).hexdigest()
        for i in range(12)
    ]
    assert list(order) == sorted(range(12), key=lambda i: keys[i])
    assert list(subsets.ordering(("sha256", "9.8-test"), 12)) != list(
        order
    )  # the version keys it


@pytest.mark.parametrize(
    ("fraction", "n", "k"),
    [(0.25, 10, 3), (0.25, 6, 2), (0.5, 7, 4), (0.25, 2, 1), (0.25, 1, 0), (1.0, 7, 7)],
)
def test_half_up_rounds_a_half_up(fraction, n, k):
    # 0.25 * 10 = 2.5 -> 3; 0.25 * 6 = 1.5 -> 2; 0.5 * 7 = 3.5 -> 4; 0.25 * 2 = 0.5 -> 1; 0.25 * 1 = 0.25 -> 0
    assert subsets.row_count(fraction, n, "half_up") == k


def test_the_ruled_form_is_nested_and_stratified_per_stratum(tmp_path):
    rng = np.random.default_rng(1)
    inputs = rng.uniform(0, 1, (21, 3))
    inputs[:, 0] = (
        [0.0] * 9 + [1.0] * 8 + [2.0] * 4
    )  # three strata of 9, 8 and 4 rows (synthetic)
    buffer = io.BytesIO()
    np.savez(buffer, inputs=inputs, targets=rng.normal(0, 1, (21, 2)))
    raw = buffer.getvalue()
    manifest, _files = subsets.make_subsets(
        raw, "sha256:9.9-test", "half_up", (0.25, 0.5, 1.0), stratum_input=0
    )
    assert manifest["rule"] == "sha256:9.9-test" and manifest["stratum_input"] == 0
    # per stratum half-up: 25 % -> 2 + 2 + 1 = 5; 50 % -> 5 + 4 + 2 = 11; 100 % -> 21
    assert [manifest["subsets"][label]["n"] for label in ("0.25", "0.5", "1.0")] == [
        5,
        11,
        21,
    ]
    order = subsets.ordering(("sha256", "9.9-test"), 21)
    strata = list(inputs[:, 0])
    small = {int(i) for i in subsets.select(order, 0.25, 21, "half_up", strata)}
    half = {int(i) for i in subsets.select(order, 0.5, 21, "half_up", strata)}
    assert small <= half
    for stratum, quarter in ((0.0, 2), (1.0, 2), (2.0, 1)):
        members = [int(i) for i in order if strata[int(i)] == stratum]
        assert {i for i in small if strata[i] == stratum} == set(members[:quarter])
    # the manifest re-derives the same rows from TRAIN's arrays (strata need them)
    _order, derived = subsets.subset_indices(
        manifest, 0.25, 21, arrays={"inputs": inputs}
    )
    assert {int(i) for i in derived} == small
    with pytest.raises(
        subsets.SubsetsRefused, match="g6_manifest_needs_train_for_strata"
    ):
        subsets.subset_indices(manifest, 0.25, 21)
    with pytest.raises(subsets.SubsetsRefused, match="g6_stratum_input_invalid"):
        subsets.make_subsets(
            raw, "sha256:9.9-test", "half_up", (0.25, 1.0), stratum_input=7
        )
    for bad in ("sha256:", "sha256:a/b", "sha256: x"):
        with pytest.raises(subsets.SubsetsRefused, match="g6_rule_unknown"):
            subsets.parse_rule(bad)
