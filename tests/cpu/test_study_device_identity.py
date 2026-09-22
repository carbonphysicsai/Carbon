"""Naming the device that produced a digest, where nothing else in the image can.

Stage A attributes results to individual devices in one chassis. `nvidia-smi` is
absent from the pinned image and JAX exposes only an index and a model name, so
the study reads the UUID through `libnvidia-ml`. The property under test is what
happens when that fails: an unnameable device must stop the run, because a result
recorded against "device 0" is attributed to an index whose mapping to hardware
is preserved nowhere.
"""

import pytest

from scripts.dev.gpu_determinism_study import device_identity


@pytest.fixture(autouse=True)
def no_driver_library(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CPU host, which is also what a pod with no device attached looks like."""
    monkeypatch.setattr(device_identity, "_library", lambda: None)
    monkeypatch.delenv("STUDY_DEVICE_UUID", raising=False)


def test_no_readable_driver_yields_no_devices_rather_than_a_placeholder() -> None:
    assert device_identity.device_uuids() == []


def test_an_unnameable_device_refuses(capsys: pytest.CaptureFixture) -> None:
    assert device_identity.main(["device_identity.py"]) == 1
    assert "refusal rather than a warning" in capsys.readouterr().err


def test_an_operator_supplied_identity_is_accepted_and_marked_as_such(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Stating the identity from outside is allowed; passing it off as read is not."""
    monkeypatch.setenv("STUDY_DEVICE_UUID", "GPU-0000")
    assert device_identity.main(["device_identity.py"]) == 0
    out = capsys.readouterr().out
    assert "GPU-0000" in out
    assert '"source": "override"' in out


def test_an_absent_index_refuses_rather_than_falling_back_to_another_device(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(
        device_identity,
        "device_uuids",
        lambda: [{"index": 0, "uuid": "GPU-a", "name": "L40S"}],
    )
    assert device_identity.main(["device_identity.py", "1"]) == 1
    assert "no device at index 1" in capsys.readouterr().err


def test_the_requested_index_is_the_one_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(
        device_identity,
        "device_uuids",
        lambda: [
            {"index": 0, "uuid": "GPU-a", "name": "L40S"},
            {"index": 1, "uuid": "GPU-b", "name": "L40S"},
        ],
    )
    assert device_identity.main(["device_identity.py", "1"]) == 0
    out = capsys.readouterr().out
    assert "GPU-b" in out
    assert "GPU-a" not in out
