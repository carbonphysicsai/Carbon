"""A setup check describes one install; the evaluation endpoint is filled in
(LP-PROD-E).

Observed live 2026-10-03: after a reinstall at a new revision, setup still
showed compute as checked, at the old revision and images, and Review wrote a
runner profile with the old accepted revision. These tests hold the repair:
- the compute check pins each image manifest it verified; one rebuilt or
  removed since, or a check made before pinning, shows as unchecked and
  Review refuses it with why;
- once the installer has recorded an install, a check made at another
  revision, or with other images, is refused the same way;
- `after_install` sets a stale check aside, checks this machine's compute
  again with the new images, writes the profile again with the miner's own
  intakes, and leaves the miner's remote setup to them;
- Review writes the evaluation endpoint Carbon publishes for each Challenge,
  without reaching it, and says plainly when none is published;
- the published list is closed: a malformed one publishes nothing.

No chain, provider, image or intake is contacted: the checks are fixtures and
the checkout's revision is patched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_miner_launchpad_environment_setup import (
    HOTKEY,
    REVISION,
    RUNTIME,
    Checks,
    Onboarding,
    completed,
)

from scripts.dev.miner_launchpad import environment_setup as environment
from scripts.dev.miner_launchpad import installed, runner
from scripts.dev.miner_launchpad.environment_setup import (
    INSTALLATION_SCHEMA,
    LOCAL_CPU,
    LOCAL_GPU,
    REMOTE,
    REMOTE_RECHECK,
    STALE_UNPINNED,
    EnvironmentSetup,
    SetupRefused,
    describe_install,
    intake_challenges,
    main,
    published_endpoints,
    service_unit,
    write_private,
)

NEW = "f" * 40
URL = "https://intake.example.org"
OWN = "https://my-validator.example.org"


class Reinstalled(Checks):
    """Fixture checks whose compute check reads `revision` as the checkout's."""

    def __init__(self, revision=REVISION):
        super().__init__()
        self.revision = revision

    def compute(self, image, analysis):
        self.calls.append(("compute", image, analysis))
        implementation = {**RUNTIME["implementation"], "revision": self.revision}
        return {**RUNTIME, "implementation": implementation}


class Intakes(Reinstalled):
    """Fixture checks that also read a validator intake's public facts."""

    def intake(self, url, campaign=None):
        self.calls.append(("intake", url))
        return {"receiver": HOTKEY, "snapshot": "fixture"}


@pytest.fixture
def state(tmp_path):
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    return root


@pytest.fixture
def head(monkeypatch):
    """The checkout's revision, as setup reads it."""
    current = {"revision": REVISION}
    monkeypatch.setattr(
        environment, "checkout_revision", lambda repo=None: current["revision"]
    )
    return current


@pytest.fixture
def challenge():
    return intake_challenges()[0]


def publish(tmp_path, monkeypatch, entries):
    path = tmp_path / "published_endpoints.json"
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.launchpad.published-endpoints.v1",
                "about": "fixture",
                "endpoints": entries,
            }
        )
    )
    monkeypatch.setattr(environment, "PUBLISHED_ENDPOINTS", path)
    return path


def entry(challenge_id, **changes):
    return {
        "network": "testnet",
        "netuid": 567,
        "challenge": challenge_id,
        "intake_url": URL,
        "receiver_hotkey": HOTKEY,
        **changes,
    }


def rebuild(tmp_path, state, revision):
    """What the installer does at `revision`: the images rebuilt in place,
    and recorded."""
    home = tmp_path / "miner"
    home.mkdir(mode=0o700, exist_ok=True)
    worker, analysis = home / "worker.json", home / "analysis.json"
    worker.write_text(json.dumps({"image_id": "sha256:" + revision[0] * 64}))
    analysis.write_text(json.dumps({"image_id": "sha256:" + revision[1] * 64}))
    installed.write(state, image_manifest=worker, analysis_image_manifest=analysis)
    return worker, analysis


def profile(setup):
    return runner.validated_profile(json.loads(setup.profile_path.read_bytes()))


# --- the compute check pins what it checked -----------------------------------


def test_a_rebuilt_image_makes_the_check_stale_and_review_refuses_it(
    tmp_path, state, head
):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    made = completed(tmp_path, setup)
    pinned = setup._record()["compute"]["manifests"]
    assert set(pinned) == {"image_manifest", "analysis_image_manifest"}
    assert setup.state()["steps"]["compute"]["checked"] is True
    Path(made["worker.json"]).write_text('{"image_id": "sha256:rebuilt"}')
    compute = setup.state()["steps"]["compute"]
    assert compute["checked"] is False
    assert compute["stale"] == ["the worker image was rebuilt since the check"]
    assert setup.state()["steps"]["review"]["ready"] is False
    with pytest.raises(SetupRefused) as refused:
        setup.review({"confirm": True})
    assert (refused.value.field, refused.value.code) == (
        "compute",
        "compute_check_is_stale",
    )
    assert "rebuilt since the check" in refused.value.next_step
    assert not setup.profile_path.exists()
    # Checking compute again pins the new manifest, and Review writes.
    setup.compute(
        {
            "choice": LOCAL_CPU,
            "image_manifest": made["worker.json"],
            "analysis_image_manifest": made["analysis.json"],
        }
    )
    setup.review({"confirm": True})
    assert profile(setup)["accepted_revision"] == REVISION


def test_a_removed_image_and_a_check_from_before_pinning_are_stale(
    tmp_path, state, head
):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    made = completed(tmp_path, setup)
    Path(made["analysis.json"]).unlink()
    assert setup.state()["steps"]["compute"]["stale"] == [
        "the analysis image is gone since the check"
    ]
    record = setup._record()
    del record["compute"]["manifests"]
    setup._save(record)
    assert setup.state()["steps"]["compute"]["stale"] == [STALE_UNPINNED]
    with pytest.raises(SetupRefused, match="compute_check_is_stale"):
        setup.review({"confirm": True})


def test_once_installed_a_check_at_another_revision_is_refused(tmp_path, state, head):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    setup.review({"confirm": True})
    # The installer recorded another revision than the check's.
    write_private(
        setup.installation_path,
        json.dumps(
            {"schema": INSTALLATION_SCHEMA, "revision": NEW, "images": {}}
        ).encode(),
    )
    with pytest.raises(SetupRefused) as refused:
        setup.review({"confirm": True})
    step = refused.value.next_step
    assert "Carbon was installed at " + NEW[:12] in step
    assert "this checkout is at " + REVISION[:12] in step
    # A record that is not the installer's is never read past.
    setup.installation_path.write_text("not json")
    assert setup.state()["steps"]["compute"]["stale"] == [
        "the installer's record here is unreadable"
    ]


# --- after the installer ---------------------------------------------------------


def test_a_reinstall_sets_the_old_check_aside_and_writes_the_profile_again(
    tmp_path, state, head, capsys
):
    """The observed failure, repaired: the reinstall's own step re-checks
    this machine's compute with the new images and rewrites the profile with
    the new accepted revision."""
    checks = Reinstalled(REVISION)
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    completed(tmp_path, setup)
    setup.review({"confirm": True})
    assert profile(setup)["accepted_revision"] == REVISION

    head["revision"] = checks.revision = NEW
    worker, analysis = rebuild(tmp_path, state, NEW)
    report = setup.after_install()
    assert report["revision"] == {"from": REVISION, "to": NEW}
    assert report["images"]["image_manifest"] == {
        "from": RUNTIME["images"][0],
        "to": "sha256:" + "f" * 64,
    }
    assert report["compute"] == "checked again"
    assert "the worker image was rebuilt since the check" in report["reasons"]
    assert report["profile"]["written"] is True
    assert report["profile"]["accepted_revision"] == NEW
    assert checks.calls[-1] == ("compute", worker, analysis)
    cfg = profile(setup)
    assert cfg["accepted_revision"] == NEW
    assert cfg["runtime"]["implementation"]["revision"] == NEW
    compute = setup.state()["steps"]["compute"]
    assert compute["checked"] is True and "set_aside" not in compute
    lines = describe_install(report)
    assert "  Carbon: " + REVISION[:12] + " -> " + NEW[:12] in lines
    assert "  Compute: checked again with the new images." in lines

    # Run again at the same revision: nothing changed, nothing re-checked.
    calls = len(checks.calls)
    again = setup.after_install()
    assert again["compute"] == "unchanged"
    assert again["revision"] == {"from": NEW, "to": NEW}
    assert len(checks.calls) == calls
    assert setup.state()["steps"]["review"]["profile_written"] is True


def test_a_refused_recheck_leaves_compute_unchecked_and_no_profile_marker(
    tmp_path, state, head
):
    class Refusing(Reinstalled):
        def compute(self, image, analysis):
            raise SetupRefused("image_manifest", "worker_image_unverified")

    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    setup.review({"confirm": True})
    head["revision"] = NEW
    rebuild(tmp_path, state, NEW)
    setup.checks = Refusing(NEW)
    report = setup.after_install()
    assert report["compute"] == "set aside"
    assert report["recheck"] == {
        "code": "worker_image_unverified",
        "field": "image_manifest",
    }
    compute = setup.state()["steps"]["compute"]
    assert compute["checked"] is False
    assert "rebuilt since the check" in " ".join(compute["set_aside"]["reasons"])
    assert setup.state()["steps"]["review"]["profile_written"] is False
    with pytest.raises(SetupRefused) as refused:
        setup.review({"confirm": True})
    assert (refused.value.field, refused.value.code) == ("compute", "step_not_checked")


def test_an_update_leaves_the_miners_remote_setup_to_them(tmp_path, state, head):
    checks = Reinstalled()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    completed(tmp_path, setup)
    record = setup._record()
    record["compute"]["choice"] = REMOTE
    setup._save(record)
    head["revision"] = NEW
    rebuild(tmp_path, state, NEW)
    calls = len(checks.calls)
    report = setup.after_install()
    assert report["compute"] == "set aside"
    assert report["next_steps"] == [REMOTE_RECHECK]
    assert len(checks.calls) == calls  # nothing reached
    assert "compute" not in setup._record()


def test_an_update_keeps_the_intake_the_miner_named(tmp_path, state, head, challenge):
    checks = Intakes()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    completed(tmp_path, setup)
    setup.review({"confirm": True, "intakes": {challenge["id"]: OWN}})
    head["revision"] = checks.revision = NEW
    rebuild(tmp_path, state, NEW)
    report = setup.after_install()
    assert report["profile"]["written"] is True
    assert profile(setup)["intakes"] == {challenge["id"]: OWN}
    # The named intake is checked again, as at any Review.
    assert checks.calls.count(("intake", OWN)) == 2


def test_a_profile_written_before_intakes_were_recorded_keeps_the_miners_own(
    tmp_path, state, head, challenge
):
    checks = Intakes()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    completed(tmp_path, setup)
    setup.review({"confirm": True, "intakes": {challenge["id"]: OWN}})
    record = setup._record()
    # As a Review before LP-PROD-E recorded it: when, and nothing else.
    record["profile"] = {"written_at": record["profile"]["written_at"]}
    setup._save(record)
    item = setup.state()["steps"]["evaluation"]["challenges"][0]
    assert (item["intake"], item["source"]) == (OWN, "yours")
    head["revision"] = checks.revision = NEW
    rebuild(tmp_path, state, NEW)
    assert setup.after_install()["profile"]["written"] is True
    assert profile(setup)["intakes"] == {challenge["id"]: OWN}


def test_an_update_names_the_gpu_worker_build_when_none_is_built(
    tmp_path, state, head, monkeypatch
):
    monkeypatch.setattr(environment, "REPO", tmp_path)
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    record = setup._record()
    record["compute"]["choice"] = LOCAL_GPU
    setup._save(record)
    head["revision"] = NEW
    rebuild(tmp_path, state, NEW)
    report = setup.after_install()
    assert report["compute"] == "set aside"
    assert report["next_steps"][0].startswith("build the GPU worker (")
    assert report["next_steps"][0].endswith("then check Compute again in setup")


def test_after_install_needs_the_installed_images(state, head):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    with pytest.raises(SetupRefused) as refused:
        setup.after_install()
    assert refused.value.code == "installed_images_not_recorded"


def test_the_installer_command_reports_a_first_install(
    tmp_path, state, head, capsys, monkeypatch
):
    monkeypatch.setattr(environment, "REPO", tmp_path)  # no GPU worker built
    rebuild(tmp_path, state, NEW)
    assert main(["after-install", "--state-dir", str(state)]) == 0
    out = capsys.readouterr().out
    assert "  Carbon: " + REVISION[:12] in out
    assert "Compute: not set up yet" in out
    stamp = json.loads((state / "environment" / "installation.json").read_bytes())
    assert stamp["revision"] == REVISION
    assert set(stamp["images"]) == {"image_manifest", "analysis_image_manifest"}
    assert main(["gpu-installed", "--state-dir", str(state)]) == 0
    assert capsys.readouterr().out == "no\n"


# --- the evaluation endpoint -------------------------------------------------------


def test_review_writes_the_published_endpoint_without_reaching_it(
    tmp_path, state, head, monkeypatch, challenge
):
    """`Checks` has no intake check: a published endpoint is written without
    one, and checked by the intake client at submit."""
    publish(tmp_path, monkeypatch, [entry(challenge["id"])])
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    before = setup.state()["steps"]["evaluation"]
    assert before["ready"] is True
    assert before["challenges"][0]["source"] == "published"
    result = setup.review({"confirm": True})
    assert result["warnings"] == []
    assert profile(setup)["intakes"] == {challenge["id"]: URL}
    written = result["steps"]["evaluation"]["challenges"][0]
    assert (written["intake"], written["source"]) == (URL, "published")
    assert written["receiver_hotkey"] == HOTKEY


def test_with_none_published_review_says_so_and_still_writes(
    tmp_path, state, head, monkeypatch, challenge
):
    publish(tmp_path, monkeypatch, [])
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    result = setup.review({"confirm": True})
    assert result["warnings"] == [
        {
            "code": "no_evaluation_endpoint",
            "challenge": challenge["id"],
            "message": environment.NO_ENDPOINT.format(title=challenge["title"]),
        }
    ]
    assert "intakes" not in profile(setup)
    evaluation = result["steps"]["evaluation"]
    assert evaluation["ready"] is False
    assert "cannot submit" in evaluation["challenges"][0]["note"]
    # Published after Review: setup says to review again.
    publish(tmp_path, monkeypatch, [entry(challenge["id"])])
    note = setup.state()["steps"]["evaluation"]["challenges"][0]["note"]
    assert "since your profile was written: review again" in note


def test_a_named_intake_wins_over_the_published_one(
    tmp_path, state, head, monkeypatch, challenge
):
    publish(tmp_path, monkeypatch, [entry(challenge["id"])])
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Intakes())
    completed(tmp_path, setup)
    result = setup.review({"confirm": True, "intakes": {challenge["id"]: OWN}})
    assert profile(setup)["intakes"] == {challenge["id"]: OWN}
    item = result["steps"]["evaluation"]["challenges"][0]
    assert (item["intake"], item["source"]) == (OWN, "yours")


@pytest.mark.parametrize(
    "change",
    [
        {"intake_url": "http://intake.example.org"},
        {"intake_url": "http://127.0.0.1:8443"},
        {"receiver_hotkey": "not-an-address"},
        {"netuid": "567"},
        {"extra": True},
    ],
)
def test_a_malformed_published_list_publishes_nothing(
    tmp_path, monkeypatch, challenge, change
):
    path = publish(tmp_path, monkeypatch, [entry(challenge["id"], **change)])
    assert published_endpoints(path) == {
        "endpoints": {},
        "problem": "published_endpoints_unreadable",
    }


def test_the_published_list_is_one_per_challenge_on_this_network(
    tmp_path, monkeypatch, challenge
):
    other = entry(challenge["id"], network="finney", netuid=1)
    path = publish(tmp_path, monkeypatch, [entry(challenge["id"]), other])
    assert list(published_endpoints(path)["endpoints"]) == [challenge["id"]]
    path = publish(tmp_path, monkeypatch, [entry(challenge["id"])] * 2)
    assert published_endpoints(path)["problem"] == "published_endpoints_unreadable"
    path.unlink()
    path.symlink_to(Path(__file__))
    assert published_endpoints(path)["problem"] == "published_endpoints_unreadable"


def test_the_repository_publishes_a_well_formed_list():
    found = published_endpoints()
    assert found["problem"] is None
    document = json.loads(environment.PUBLISHED_ENDPOINTS.read_bytes())
    assert set(document["entry_fields"]) == environment.PUBLISHED_FIELDS


def test_a_malformed_published_list_is_a_review_warning(
    tmp_path, state, head, monkeypatch
):
    path = tmp_path / "published_endpoints.json"
    path.write_text("[")
    monkeypatch.setattr(environment, "PUBLISHED_ENDPOINTS", path)
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    result = setup.review({"confirm": True})
    assert result["warnings"][0]["code"] == "published_endpoints_unreadable"
    assert result["steps"]["evaluation"]["problem"] == "published_endpoints_unreadable"


# --- the service unit --------------------------------------------------------------


def test_the_service_unit_runs_this_checkout_on_loopback_with_private_output():
    text = service_unit(
        Path("/srv/miner/.carbon/state"), 8788, Path("/srv/miner/carbon")
    )
    assert (
        "ExecStart=/srv/miner/carbon/.venv/bin/carbon-control-center "
        "--state-dir /srv/miner/.carbon/state --port 8788"
    ) in text
    assert "UMask=0077" in text
    assert "StandardOutput=append:/srv/miner/.carbon/state/control-center.log" in text
    assert "WantedBy=default.target" in text


@pytest.mark.parametrize(
    ("state_dir", "port"),
    [
        ("relative/state", 8788),
        ("/srv/my state", 8788),
        ("/srv/%h/state", 8788),
        ("/srv/$USER/state", 8788),
        ("/srv/miner/state\nExecStartPre=/bin/false", 8788),
        ("/srv/miner/state", 80),
        ("/srv/miner/state", "8788"),
    ],
)
def test_the_service_unit_refuses_what_systemd_would_expand(state_dir, port, capsys):
    with pytest.raises(ValueError):
        service_unit(Path(state_dir), port, Path("/srv/miner/carbon"))
    if type(port) is int and port == 8788 and "\n" not in state_dir:
        assert main(["service-unit", "--state-dir", state_dir, "--port", "8788"]) == 2
        assert "service unit refused" in capsys.readouterr().err
