"""The calibration grade runs a graph route v2 version's inference under its longer rebuild wall, as the official
route does (Cooling 1.6: 648 s > the 600 s default)."""

from carbon.challenge_validator import calibration_grade as cg
from carbon.development_session import bundle_construction_worker as worker


class _Result:
    predictions = ((1.0,),)


def _infer(monkeypatch, **extra):
    seen = {}

    def fake(*_a, **kwargs):
        seen.update(kwargs)
        return _Result()

    monkeypatch.setattr(worker, "_infer_state", fake)
    infer = cg.worker_infer(
        ledger=None,
        owner="o",
        identity="i",
        inference_image=None,
        recipe=None,
        binding=None,
        state=b"",
        state_digest="sha256:" + "0" * 64,
        expected_output_shape=(1, 1),
        expected_output_dtype="<f8",
        allowlist_bytes=b"",
        seconds=648,
        **extra,
    )
    infer([[0.0]])
    return seen


def test_the_rebuild_wall_reaches_the_inference_step(monkeypatch):
    seen = _infer(monkeypatch, rebuild_wall_seconds=648)
    assert seen["seconds"] == 648 and seen["rebuild_wall_seconds"] == 648


def test_a_version_without_a_rebuild_wall_passes_none(monkeypatch):
    assert "rebuild_wall_seconds" not in _infer(monkeypatch)


def test_the_run_derives_the_wall_from_the_versions_resource_policy():
    from carbon.challenge_kit.version_registry import REBUILD_LIMIT_SECONDS

    long_policy = {
        "reconstruction_resource_policy": {
            "build_wall_seconds_max": REBUILD_LIMIT_SECONDS
        }
    }
    assert worker.rebuild_wall_kwargs(long_policy) == {
        "rebuild_wall_seconds": REBUILD_LIMIT_SECONDS
    }
    assert REBUILD_LIMIT_SECONDS == 648
    default = {"reconstruction_resource_policy": {"build_wall_seconds_max": 600}}
    assert worker.rebuild_wall_kwargs(default) == {}
