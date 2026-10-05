"""The CPU carrier lane's registered policy and environment probe (VALIDATOR-11).

Pins:
- `carrier-lane-v1` is registered and digest-pinned, and its declared levels,
  program deadline margin, price and host equal the lane's code; an altered
  or disagreeing document is refused, and the lane will not run without it;
- every run's description records the lane policy's version and digest;
- the environment probe (the Graphite readiness gate's R3) loads the pinned
  image manifest and asks the host doctor, read-only, and reports image
  presence as True, False or unknown, never assumed.

No Docker, network or spend: the doctor and manifest loader are stand-ins.
"""

import hashlib
import json
import shutil
from types import SimpleNamespace

import pytest

from carbon.agent_campaign.graphite import carrier_pods as cp

IMAGE = SimpleNamespace(image_id="sha256:" + "c" * 64)


def test_the_lane_policy_is_registered_and_matches_the_lane():
    document, pinned = cp.lane_policy()
    assert document["version"] == "carrier-lane-v1"
    assert document["lane"] == cp.BACKEND and document["host"] == "operator"
    assert frozenset(document["levels"]) == cp.CARRIER_LEVELS
    assert document["program_deadline_margin_s"] == cp.SETUP_MARGIN_S
    assert document["hourly_usd"] == "0"
    assert "never an environment claim" in document["attribution"]
    assert pinned.startswith("sha256:")


def _copy(tmp_path, change):
    directory = tmp_path / "lanes"
    shutil.copytree(cp.LANE_DIR, directory)
    path = directory / "carrier-lane-v1.json"
    document = json.loads(path.read_text())
    change(document)
    path.write_text(json.dumps(document))
    return directory, document


def test_an_altered_or_disagreeing_policy_is_refused(tmp_path):
    directory, _ = _copy(tmp_path, lambda d: d.update(program_deadline_margin_s=30))
    with pytest.raises(cp.LaneRefused, match="lane_policy_altered"):
        cp.lane_policy(directory)
    # Re-pinned honestly, it still disagrees with the lane's code.
    registry = json.loads((directory / "registry.json").read_text())
    body = json.loads((directory / "carrier-lane-v1.json").read_text())
    registry["versions"]["carrier-lane-v1"] = (
        "sha256:" + hashlib.sha256(cp._canonical(body)).hexdigest()
    )
    (directory / "registry.json").write_text(json.dumps(registry))
    with pytest.raises(cp.LaneRefused, match="lane_policy_disagrees_with_the_lane"):
        cp.lane_policy(directory)


def test_the_lane_runs_only_under_its_policy_and_records_it(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    pods = cp.CarrierPods(tmp_path / "carrier", image=IMAGE)
    _, pinned = cp.lane_policy()
    assert pods.describe()["lane_policy"] == {
        "version": "carrier-lane-v1",
        "digest": pinned,
    }

    def refused(directory=None):
        raise cp.LaneRefused("lane_policy_altered")

    monkeypatch.setattr(cp, "lane_policy", refused)
    with pytest.raises(cp.LaneRefused):
        cp.CarrierPods(tmp_path / "carrier2", image=IMAGE)


def _verdict(eligible, code):
    return SimpleNamespace(eligible=eligible, code=code)


@pytest.mark.parametrize(
    ("verdict", "present", "eligible"),
    [
        (_verdict(True, "worker.doctor.eligible"), True, True),
        (_verdict(False, "worker.doctor.image_unavailable"), False, False),
        (_verdict(False, "worker.doctor.image_binding_mismatch"), True, False),
        (_verdict(False, "worker.doctor.docker_unavailable"), None, False),
        (_verdict(False, "worker.doctor.capacity_or_cgroup_ineligible"), None, False),
    ],
)
def test_the_environment_probe_reports_presence_honestly(verdict, present, eligible):
    seen = {}

    def doctor(*, image_id, image_identity):
        seen.update(image_id=image_id, identity=image_identity)
        return verdict

    result = cp.environment_check("/m.json", doctor=doctor, load=lambda path: IMAGE)
    assert seen == {"image_id": IMAGE.image_id, "identity": IMAGE}
    assert result["manifest_loaded"] is True
    assert result["image_present"] is present
    assert result["eligible"] is eligible and result["doctor_eligible"] is eligible
    assert result["doctor_code"] == verdict.code
    assert result["lane_policy"] == "carrier-lane-v1"


def test_an_unreadable_manifest_is_not_eligible():
    def load(path):
        raise ValueError("unreadable")

    result = cp.environment_check("/m.json", load=load, doctor=None)
    assert result["manifest_loaded"] is False and result["eligible"] is False
    assert result["image_present"] is None
    assert result["doctor_code"] == "lane.manifest_unreadable"


def test_the_check_command_exits_on_eligibility(monkeypatch, capsys):
    monkeypatch.setattr(cp, "environment_check", lambda manifest: {"eligible": True})
    assert cp.main(["check", "--image-manifest", "/m.json"]) == 0
    monkeypatch.setattr(cp, "environment_check", lambda manifest: {"eligible": False})
    assert cp.main(["check", "--image-manifest", "/m.json"]) == 1
    capsys.readouterr()
