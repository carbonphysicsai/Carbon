"""The custody driver's own checks (offline): pins, evidence verification, exclusive write. The container run itself is the receiver's
`paired_inference.infer_frozen_pair` and needs the pod."""

import base64
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "infer_pair",
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "dev"
    / "part_feedback_attack"
    / "infer_pair.py",
)
infer_pair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(infer_pair)

RECIPE = "sha256:" + "a" * 64
STATE = "sha256:" + "b" * 64


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _original(raw):
    return {"sha256": _sha(raw), "raw_base64": base64.b64encode(raw).decode()}


def _evidence(primary=b"[[1.0]]", repeat=None, **over):
    repeat = primary if repeat is None else repeat
    document = {
        "schema": infer_pair.PAIR_SCHEMA,
        "recipe_digest": RECIPE,
        "state_digest": STATE,
        "inputs_digest": "sha256:" + "c" * 64,
        "logical_prediction_rows_per_operation": 1,
        "primary": {"originals": {"predictions.json": _original(primary)}},
        "repeat": {"originals": {"predictions.json": _original(repeat)}},
    }
    document.update(over)
    return document


def _refused(call):
    with pytest.raises(infer_pair.PairRefused) as caught:
        call()
    return caught.value.code


def test_verified_evidence_summarises_digests_only():
    summary = infer_pair.verify_evidence(
        _evidence(),
        recipe_digest=RECIPE,
        state_digest=STATE,
        predictions_sha256=_sha(b"[[1.0]]"),
    )
    assert summary["predictions_sha256"] == _sha(b"[[1.0]]")
    assert set(summary) == {
        "recipe_digest",
        "state_digest",
        "inputs_digest",
        "predictions_sha256",
        "rows",
    }


def test_wrong_state_or_recipe_in_the_evidence_is_refused():
    kw = {"recipe_digest": RECIPE, "state_digest": STATE}
    assert (
        _refused(
            lambda: infer_pair.verify_evidence(
                _evidence(state_digest="sha256:" + "d" * 64), **kw
            )
        )
        == "pair_state_digest_differs"
    )
    assert (
        _refused(
            lambda: infer_pair.verify_evidence(
                _evidence(recipe_digest="sha256:" + "d" * 64), **kw
            )
        )
        == "pair_recipe_digest_differs"
    )
    assert (
        _refused(lambda: infer_pair.verify_evidence(_evidence(schema="other"), **kw))
        == "pair_schema"
    )


def test_primary_must_equal_repeat_bit_for_bit():
    code = _refused(
        lambda: infer_pair.verify_evidence(
            _evidence(repeat=b"[[1.0000001]]"), recipe_digest=RECIPE, state_digest=STATE
        )
    )
    assert code == "pair_primary_differs_from_repeat"


def test_changed_original_is_refused():
    evidence = _evidence()
    evidence["primary"]["originals"]["predictions.json"]["sha256"] = (
        "sha256:" + "0" * 64
    )
    code = _refused(
        lambda: infer_pair.verify_evidence(
            evidence, recipe_digest=RECIPE, state_digest=STATE
        )
    )
    assert code == "pair_primary_changed"


def test_predictions_that_do_not_reproduce_are_refused():
    code = _refused(
        lambda: infer_pair.verify_evidence(
            _evidence(),
            recipe_digest=RECIPE,
            state_digest=STATE,
            predictions_sha256=_sha(b"[[2.0]]"),
        )
    )
    assert code == "predictions_do_not_reproduce"


@pytest.mark.parametrize(
    "bad", ["", "sha256:abc", "sha256:" + "G" * 64, "x" * 71, None, 3]
)
def test_pins_must_be_full_digests(bad):
    assert _refused(lambda: infer_pair.check_digest_pin("expect_state", bad)).endswith(
        "must_be_a_sha256_digest"
    )
    infer_pair.check_digest_pin("expect_state", STATE)


def test_pair_file_is_written_once_and_never_overwritten(tmp_path):
    target = tmp_path / "inference-pair.json"
    digest = infer_pair.write_once(target, _evidence())
    assert digest == _sha(target.read_bytes())
    assert json.loads(target.read_bytes())["schema"] == infer_pair.PAIR_SCHEMA
    with pytest.raises(FileExistsError):
        infer_pair.write_once(target, _evidence())


def test_written_pair_is_readable_by_the_binding_reader(tmp_path):
    """The file this driver writes is what `pool_binding` reads as a baseline."""
    spec = importlib.util.spec_from_file_location(
        "pool_binding_for_pair", Path(infer_pair.__file__).with_name("pool_binding.py")
    )
    binding = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(binding)
    evidence = _evidence(primary=b"[[1.0, 2.0]]")
    values, summary = binding._pair_predictions(
        evidence, evidence["inputs_digest"], RECIPE, STATE
    )
    assert values == [[1.0, 2.0]] and summary["state_digest"] == STATE


def test_published_manifest_with_schema_key_loads(tmp_path, monkeypatch):
    import sys
    import types

    seen = {}

    class Identity:
        def __init__(self, **kw):
            seen.update(kw)

    module = types.ModuleType("carbon.reconstruction.worker.model")
    module.WorkerImageIdentity = Identity
    monkeypatch.setitem(sys.modules, "carbon.reconstruction.worker.model", module)
    path = tmp_path / "image.json"
    path.write_text(json.dumps({"schema": "x", "image_id": "sha256:1"}))
    infer_pair.load_image(path)
    assert seen == {"image_id": "sha256:1"}
    path.write_text("[]")
    assert _refused(lambda: infer_pair.load_image(path)) == "judge_image_unreadable"
