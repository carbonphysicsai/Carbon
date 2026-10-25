"""Pool serving: the practice call is re-aimed at the pool rows, the answers travel as a table."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from carbon.scoring import pool_serving as serving


class _Result:
    def __init__(self, predictions, build="sha256:" + "a" * 64, infer=None):
        self.build = SimpleNamespace(state_digest=build)
        self.inference = SimpleNamespace(
            predictions=predictions, state_digest=infer or build
        )


def _practice(record):
    """A stand-in practice object with the real shape: one `reconstruct_and_infer_public` call, then scoring
    that must never run."""

    def call(identity, strategy):
        from carbon.development_session import bundle_construction_worker as worker

        record["scored"] = False
        result = worker.reconstruct_and_infer_public(
            identity=identity,
            recipe=strategy,
            inputs=np.zeros((5, 2), dtype=np.float32),
            expected_output_shape=(5, 3),
        )
        record["scored"] = True
        return result

    return call


def _fake(seen, predictions_of=lambda rows: np.asarray(rows)[:, :1] * np.ones((1, 3))):
    def fake(**kwargs):
        seen.update(kwargs)
        return _Result(predictions_of(kwargs["inputs"]))

    return fake


def test_the_practice_call_is_aimed_at_the_pool_rows_and_stops_there(monkeypatch):
    from carbon.development_session import bundle_construction_worker as worker

    seen, record = {}, {}
    fake = _fake(seen)
    monkeypatch.setattr(worker, "reconstruct_and_infer_public", fake)
    rows = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]
    raw, state = serving.predict_rows(_practice(record), "id", {"r": 1}, rows)
    assert raw == [[1.0] * 3, [3.0] * 3, [5.0] * 3]
    assert state == "sha256:" + "a" * 64
    assert seen["inputs"].shape == (3, 2) and seen["inputs"].dtype == np.float32
    assert tuple(seen["expected_output_shape"]) == (3, 3)
    assert record["scored"] is False  # the practice scoring after the call never ran
    assert worker.reconstruct_and_infer_public is fake  # the real function is restored


def test_the_real_function_is_restored_after_a_refusal(monkeypatch):
    from carbon.development_session import bundle_construction_worker as worker

    fake = _fake({}, predictions_of=lambda rows: np.full((len(rows), 3), np.nan))
    monkeypatch.setattr(worker, "reconstruct_and_infer_public", fake)
    with pytest.raises(serving.PoolServingRefused) as raised:
        serving.predict_rows(_practice({}), "id", {"r": 1}, [[1.0, 2.0]])
    assert raised.value.code == "predictions_are_not_one_finite_row_per_input"
    assert worker.reconstruct_and_infer_public is fake


def test_rows_of_the_wrong_width_and_a_state_mismatch_are_refused(monkeypatch):
    from carbon.development_session import bundle_construction_worker as worker

    monkeypatch.setattr(worker, "reconstruct_and_infer_public", _fake({}))
    with pytest.raises(serving.PoolServingRefused) as raised:
        serving.predict_rows(_practice({}), "id", {}, [[1.0, 2.0, 3.0]])
    assert raised.value.code == "pool_rows_do_not_match_the_interface_width"
    monkeypatch.setattr(
        worker,
        "reconstruct_and_infer_public",
        lambda **kw: _Result(np.zeros((1, 3)), infer="sha256:" + "b" * 64),
    )
    with pytest.raises(serving.PoolServingRefused) as raised:
        serving.predict_rows(_practice({}), "id", {}, [[1.0, 2.0]])
    assert raised.value.code == "state_differs_between_phases"
    with pytest.raises(serving.PoolServingRefused):
        serving.predict_rows(_practice({}), "id", {}, [])


def test_a_practice_that_never_queries_the_model_is_refused(monkeypatch):
    from carbon.development_session import bundle_construction_worker as worker

    monkeypatch.setattr(worker, "reconstruct_and_infer_public", _fake({}))
    with pytest.raises(serving.PoolServingRefused) as raised:
        serving.predict_rows(lambda identity, strategy: None, "id", {}, [[1.0, 2.0]])
    assert raised.value.code == "the_practice_never_queried_the_model"


def test_the_table_round_trips_and_serves_exact_rows_only(tmp_path):
    names = ["a", "b"]
    rows = [[1.0, 2.0], [3.0, 4.0]]
    raw = [[0.5, 0.25], [0.75, 0.125]]
    path = tmp_path / "t.json"
    serving.write_table(
        path,
        kind="f02",
        version="2.4",
        input_names=names,
        rows=rows,
        raw=raw,
        state_digest="sha256:" + "c" * 64,
        recipe="sha256:" + "d" * 64,
    )
    server = serving.TableServer(serving.load_table(path), names)
    assert server([{"a": 3.0, "b": 4.0}, {"a": 1.0, "b": 2.0}]) == [raw[1], raw[0]]
    assert server.state_digest == "sha256:" + "c" * 64
    with pytest.raises(serving.PoolServingRefused) as raised:
        server([{"a": 1.0, "b": 2.5}])
    assert raised.value.code == "row_not_in_the_prediction_table"
    with pytest.raises(serving.PoolServingRefused):
        serving.TableServer(serving.load_table(path), ["b", "a"])
    path.write_bytes(b'{"schema":"other"}')
    with pytest.raises(serving.PoolServingRefused):
        serving.load_table(path)


def test_the_table_holds_no_pool_material(tmp_path):
    path = tmp_path / "t.json"
    serving.write_table(
        path,
        kind="motor",
        version="1.4",
        input_names=["x"],
        rows=[[1.0]],
        raw=[[2.0]],
        state_digest="s",
        recipe="r",
    )
    text = path.read_text()
    for forbidden in ("truth", "limit", "seed", "agen", "target", "objective"):
        assert forbidden not in text
