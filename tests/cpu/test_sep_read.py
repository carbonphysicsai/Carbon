"""SEP-READ-01 (S4a) custody read (scripts/dev/exam_reads/sep_read.py): the closed probe set and its class cross-check, the K / O
exports bound to the probe set by ln_harness's own inputs digest, the registered A_gen atom per class against margin_N, the n >= 6
flag rule, DC's nearest_train run in place behind its receipted SUMS, and aggregates only in the output.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

READS = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "exam_reads"
sys.path.insert(0, str(READS))

import sep_read

from carbon.scoring import pool_adapters

NAMES = ["a", "b"]


def _case(a, b, y, klass="inner_band", region="in_train"):
    return {
        "inputs": {"a": a, "b": b},
        "truth": {"y": y},
        "class": klass,
        "class_rule": "S4a-class-rule-v1",
        "region_class": region,
        "source": "PRAC-TEST-01",
    }


def _probe_set(tmp_path, cases, **over):
    tmp_path.mkdir(parents=True, exist_ok=True)
    document = {
        "schema": sep_read.PROBE_SCHEMA,
        "challenge": "electric-motor-magnetics",
        "version": "1.5",
        "input_names": NAMES,
        "u_record": {"id": "U-TEST", "sha256": "c" * 64, "u": {"y": 0.5}},
        "cases": cases,
        **over,
    }
    path = tmp_path / "probe-set.json"
    path.write_text(json.dumps(document))
    return path


def _provenance(tmp_path, names=NAMES):
    path = tmp_path / "train.provenance.json"
    path.write_text(json.dumps({"numeric_interface": {"input_names": names}}))
    return path


def _predict_record(tmp_path, name, document, rows, *, catalog_id, digest=None):
    folder = tmp_path / name
    (folder / catalog_id).mkdir(parents=True)
    buffer = io.BytesIO()
    np.save(buffer, np.asarray(rows, dtype=np.float32), allow_pickle=False)
    (folder / catalog_id / "tuned.npy").write_bytes(buffer.getvalue())
    record = {
        "schema": sep_read.PREDICT_SCHEMA,
        "challenge": {"id": document["challenge"], "version": document["version"]},
        "grid_digest": "sha256:" + "d" * 64,
        "probe_inputs_sha256": digest
        or sep_read.probe_digest(sep_read.probe_array(document)),
        "probe_rows": len(document["cases"]),
        "contenders": [
            {
                "catalog_id": catalog_id,
                "exports": {
                    "tuned": {
                        "file": f"{catalog_id}/tuned.npy",
                        "sha256": "sha256:"
                        + hashlib.sha256(buffer.getvalue()).hexdigest(),
                    }
                },
            }
        ],
        "truths_read": False,
    }
    (folder / "predict-record.json").write_text(json.dumps(record))
    return folder / "predict-record.json"


@pytest.fixture
def fakes(monkeypatch):
    """A binding whose derive returns the raw row's first value as output y, registered A_gen scale 1.0, and a fake nearest_train."""
    monkeypatch.setattr(
        pool_adapters,
        "official_binding",
        lambda kind, version: SimpleNamespace(
            input_names=tuple(NAMES), derive=lambda inputs, raw: {"y": raw[0]}
        ),
    )
    monkeypatch.setattr(sep_read, "agen_scales", lambda challenge, version: {"y": 1.0})
    monkeypatch.setattr(
        sep_read,
        "nearest_train",
        lambda cfg, document: (
            {c["class"]: {"n": 0, "status": "FAKE"} for c in document["cases"]},
            {"train_sha256": "e" * 64, "units": "fake"},
        ),
    )


def _config(tmp_path, cases, kernel_rows, operator_rows, margin=0.05):
    probe = _probe_set(tmp_path, cases)
    document, _ = sep_read.load_probe_set(probe)
    noise = tmp_path / "noise.json"
    noise.write_text(
        json.dumps({"challenges": {"electric-motor-magnetics": {"value": margin}}})
    )
    config = {
        "probe_set": str(probe),
        "kernel": {
            "predict_record": str(
                _predict_record(
                    tmp_path,
                    "k",
                    document,
                    kernel_rows,
                    catalog_id="v2.motor.prior_krr",
                )
            ),
            "catalog_id": "v2.motor.prior_krr",
            "fit": "tuned",
        },
        "operator": {
            "predict_record": str(
                _predict_record(
                    tmp_path, "o", document, operator_rows, catalog_id="v2.motor.fno"
                )
            ),
            "catalog_id": "v2.motor.fno",
            "fit": "tuned",
        },
        "koth_rebuild_noise": str(noise),
        "nearest_train": {
            "payload_dir": str(tmp_path),
            "region": "r.json",
            "region_sha256": "f" * 64,
            "train_npz": "t.npz",
            "train_provenance": str(_provenance(tmp_path)),
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    return path


# --- the probe set ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case, code",
    [
        (
            _case(0.1, 0.2, 1.0, klass="outer_shell", region="in_train"),
            "class_contradicts_region_class:outer_shell",
        ),
        (
            _case(0.1, 0.2, 1.0, klass="inner_band", region="extended_shell"),
            "class_contradicts_region_class:inner_band",
        ),
        (
            _case(0.1, 0.2, 1.0, klass="regime:a", region="regime:b"),
            "class_contradicts_region_class:regime:a",
        ),
        ({**_case(0.1, 0.2, 1.0), "inputs": {"a": 0.1}}, "probe_set_case_inputs"),
        ({**_case(0.1, 0.2, 1.0), "truth": {"z": 1.0}}, "probe_set_case_outputs"),
        ({**_case(0.1, 0.2, 1.0), "extra": 1}, "probe_set_case_shape"),
    ],
)
def test_the_probe_set_is_closed_and_its_class_agrees_with_its_region_class(
    tmp_path, case, code
):
    path = _probe_set(tmp_path, [_case(0.0, 0.0, 1.0), case])
    with pytest.raises(sep_read.SepRefused) as refused:
        sep_read.load_probe_set(path)
    assert refused.value.code == code


def test_a_class_without_a_region_rule_is_accepted_as_labelled(tmp_path):
    document, _ = sep_read.load_probe_set(
        _probe_set(
            tmp_path, [_case(0.0, 0.0, 1.0, klass="neighbour_task", region="in_train")]
        )
    )
    assert document["cases"][0]["class"] == "neighbour_task"


def test_the_probe_columns_must_be_in_trains_order(tmp_path):
    document, _ = sep_read.load_probe_set(_probe_set(tmp_path, [_case(0.0, 0.0, 1.0)]))
    sep_read.check_train_order(document, _provenance(tmp_path))
    with pytest.raises(
        sep_read.SepRefused, match="probe_set_input_order_differs_from_train"
    ):
        sep_read.check_train_order(document, _provenance(tmp_path, ["b", "a"]))


def test_the_probe_npy_carries_ln_harness_own_digest(tmp_path):
    probe = _probe_set(tmp_path, [_case(0.1, 0.2, 1.0), _case(0.3, 0.4, 2.0)])
    out = tmp_path / "probe.npy"
    assert (
        sep_read.main(
            [
                "probe-npy",
                str(probe),
                str(out),
                "--train-provenance",
                str(_provenance(tmp_path)),
            ]
        )
        == 0
    )
    loaded = np.load(out, allow_pickle=False)
    assert loaded.tolist() == [[0.1, 0.2], [0.3, 0.4]]
    assert (
        sep_read.probe_digest(loaded)
        == "sha256:"
        + hashlib.sha256(np.ascontiguousarray(loaded).tobytes()).hexdigest()
    )


# --- the read ---------------------------------------------------------------------------------------------------------


def _six(klass, region, y):
    return [_case(0.1 * i, 0.2, y, klass=klass, region=region) for i in range(6)]


def test_a_class_where_the_kernel_loses_and_the_operator_wins_is_flagged_only_at_n_ge_6(
    tmp_path, fakes
):
    cases = _six("outer_shell", "extended_shell", 1.0) + [
        _case(0.9, 0.9, 1.0) for _ in range(3)
    ]
    kernel = [[3.0]] * 6 + [[1.0]] * 3  # wrong by 2 on the shell, exact inside
    operator = [[1.0]] * 9  # exact everywhere
    result = sep_read.read(_config(tmp_path, cases, kernel, operator))
    shell, inner = result["classes"]["outer_shell"], result["classes"]["inner_band"]
    assert shell["n"] == 6 and shell["status"] == "REPORT"
    assert shell["K"]["accuracy"] == pytest.approx(1 / 3) and shell["O"][
        "accuracy"
    ] == pytest.approx(1.0)
    assert (
        shell["o_minus_k"] == pytest.approx(2 / 3)
        and shell["k_loses_and_o_wins"] is True
    )
    assert shell["K"]["median_err_over_u"] == {
        "y": pytest.approx(4.0)
    }  # |err| 2 over U 0.5
    # n = 3: INDICATIVE, never flagged
    assert inner["status"] == "INDICATIVE" and inner["k_loses_and_o_wins"] is None
    assert result["overall"]["n"] == 9 and result["margin_n"] == 0.05


def test_inside_margin_n_is_not_flagged(tmp_path, fakes):
    cases = _six("outer_shell", "extended_shell", 1.0)
    result = sep_read.read(
        _config(tmp_path, cases, [[1.02]] * 6, [[1.0]] * 6, margin=0.05)
    )
    assert result["classes"]["outer_shell"]["k_loses_and_o_wins"] is False


def test_with_no_registered_scales_there_is_no_accuracy_and_no_flag(
    tmp_path, fakes, monkeypatch
):
    monkeypatch.setattr(sep_read, "agen_scales", lambda challenge, version: None)
    cases = _six("outer_shell", "extended_shell", 1.0)
    result = sep_read.read(_config(tmp_path, cases, [[3.0]] * 6, [[1.0]] * 6))
    row = result["classes"]["outer_shell"]
    assert (
        row["K"]["accuracy"] is None
        and row["k_loses_and_o_wins"] is None
        and "o_minus_k" not in row
    )
    assert row["K"]["median_err_over_u"] == {"y": pytest.approx(4.0)}
    assert result["accuracy"].startswith("no registered A_gen scales")


def test_an_export_for_other_probe_inputs_or_a_changed_file_is_refused(tmp_path, fakes):
    cases = _six("outer_shell", "extended_shell", 1.0)
    path = _config(tmp_path, cases, [[1.0]] * 6, [[1.0]] * 6)
    config = json.loads(path.read_text())
    document, _ = sep_read.load_probe_set(config["probe_set"])
    config["kernel"]["predict_record"] = str(
        _predict_record(
            tmp_path,
            "k2",
            document,
            [[1.0]] * 6,
            catalog_id="v2.motor.prior_krr",
            digest="sha256:" + "0" * 64,
        )
    )
    path.write_text(json.dumps(config))
    with pytest.raises(sep_read.SepRefused, match="predict_record_other_probe_inputs"):
        sep_read.read(path)
    config = json.loads(
        _config(tmp_path / "x", cases, [[1.0]] * 6, [[1.0]] * 6).read_text()
    )
    npy = (
        Path(config["operator"]["predict_record"]).parent / "v2.motor.fno" / "tuned.npy"
    )
    npy.write_bytes(npy.read_bytes()[:-4] + b"\x00\x00\x00\x00")
    (tmp_path / "x" / "config.json").write_text(json.dumps(config))
    with pytest.raises(sep_read.SepRefused, match="prediction_file_changed"):
        sep_read.read(tmp_path / "x" / "config.json")


def test_the_output_holds_aggregates_only(tmp_path, fakes):
    cases = [
        _case(
            0.123456789,
            0.987654321,
            7.654321,
            klass="outer_shell",
            region="extended_shell",
        )
        for _ in range(6)
    ]
    result = sep_read.read(
        _config(tmp_path, cases, [[7.1111111]] * 6, [[7.2222222]] * 6)
    )
    text = json.dumps(result)
    for secret in (
        "0.123456789",
        "0.987654321",
        "7.654321",
        "7.1111111",
        "7.2222222",
        "PRAC-TEST-01",
        "S4a-class-rule-v1",
    ):
        assert secret not in text
    assert set(result["classes"]["outer_shell"]) == {
        "n", "status", "K", "O", "o_minus_k", "k_loses_and_o_wins", "nearest_train",
    }  # fmt: skip


# --- DC's nearest_train, in place -------------------------------------------------------------------------------------


def _payload(tmp_path):
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "nearest_train.py").write_text(
        "SEEN = []\n"
        "def build(cfg):\n"
        "    import json, pathlib\n"
        "    doc = json.loads(next(pathlib.Path(cfg['pool_sources'][0]).glob('pool-source-*.json')).read_text())\n"
        "    SEEN.append(doc['region'])\n"
        "    return {'train_sha256': 'e' * 64, 'units': 'u', 'classes': {doc['region']: {'n': len(doc['designs'])}}}\n"
    )
    digest = hashlib.sha256((payload / "nearest_train.py").read_bytes()).hexdigest()
    (payload / "SHA256SUMS").write_text(f"{digest} *./nearest_train.py\n")
    return payload


def test_nearest_train_runs_dcs_build_in_place_per_class_behind_its_sums(
    tmp_path, monkeypatch
):
    payload = _payload(tmp_path)
    cfg = {
        "payload_dir": str(payload),
        "region": "r",
        "region_sha256": "s",
        "train_npz": "t",
        "train_provenance": "p",
    }
    document, _ = sep_read.load_probe_set(
        _probe_set(
            tmp_path,
            _six("outer_shell", "extended_shell", 1.0) + [_case(0.5, 0.5, 1.0)],
        )
    )
    with pytest.raises(
        sep_read.SepRefused, match="nearest_train_sums_not_the_receipted_ones"
    ):
        sep_read.nearest_train(cfg, document)
    monkeypatch.setattr(
        sep_read,
        "NEAREST_TRAIN_SUMS",
        hashlib.sha256((payload / "SHA256SUMS").read_bytes()).hexdigest(),
    )
    out, train = sep_read.nearest_train(cfg, document)
    assert (
        out == {"outer_shell": {"n": 6}, "inner_band": {"n": 1}}
        and train["train_sha256"] == "e" * 64
    )
    assert not list(
        Path(sep_read.tempfile.gettempdir()).glob("sep-read-*")
    )  # the private copies are gone
    (payload / "nearest_train.py").write_text("def build(cfg):\n    return {}\n")
    with pytest.raises(sep_read.SepRefused, match="nearest_train_file_changed"):
        sep_read.nearest_train(cfg, document)
