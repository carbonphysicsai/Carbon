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
import stat
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
    RECHECK_STEP,
    REINSTALL_STEP,
    REMOTE,
    REMOTE_RECHECK,
    STALE_PROFILE,
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


def one_version_challenge():
    """The first intake Challenge with exactly one intake version, read from
    the registry: a v1 published entry (naming a Challenge only) applies only
    to such a Challenge. Battery was it until it served 1.0 and 2.2; the rule,
    not a name, picks it."""
    every = intake_challenges()
    counts = {}
    for c in every:
        counts[c["id"]] = counts.get(c["id"], 0) + 1
    return next(c for c in every if counts[c["id"]] == 1)


def publish(tmp_path, monkeypatch, entries, schema="v1"):
    """A published list; v1 (entries name a Challenge only) unless `schema`
    is "v2" (each entry names its version)."""
    path = tmp_path / "published_endpoints.json"
    path.write_text(
        json.dumps(
            {
                "schema": f"carbon.launchpad.published-endpoints.{schema}",
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


def unpublished(*configured):
    """Review's warning for each other intake Challenge with no endpoint.

    Battery was once the only intake Challenge; Motor 1.2 has one too, and
    Review says truthfully that Carbon has not published its endpoint
    (Validator, Motor 1.2 landing, 2026-10-20)."""
    named = {challenge["id"] for challenge in configured}
    return [
        {
            "code": "no_evaluation_endpoint",
            "challenge": challenge["id"],
            "version": challenge["version"],
            "message": environment.NO_ENDPOINT.format(title=challenge["title"]),
        }
        for challenge in intake_challenges()
        if challenge["id"] not in named
    ]


def own_review(challenge, receiver=HOTKEY):
    """Review naming the miner's own intake with its receiver hotkey
    (required since LAUNCHPAD-ACCEPT-03)."""
    return {
        "confirm": True,
        "intakes": {challenge["id"]: OWN},
        "receiver_hotkey": receiver,
    }


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
    # The checkout moved since the install: only the installer clears that
    # (review finding, 2026-10-03), so it is the step named.
    assert step.startswith(REINSTALL_STEP) and "CARBON_STATE_DIR=" in step
    # A record that is not the installer's is never read past.
    setup.installation_path.write_text("not json")
    compute = setup.state()["steps"]["compute"]
    assert compute["stale"] == ["the installer's record here is unreadable"]
    assert compute["next_step"].startswith(REINSTALL_STEP)


def test_a_check_at_a_moved_checkout_names_the_installer_not_a_loop(
    tmp_path, state, head
):
    """Review finding, 2026-10-03: after a `git pull` (or an update whose
    build failed once the checkout had moved), Review said to check Compute
    again, but a new check at HEAD is stale again for the same reason while
    the install record names the old revision. The step is the installer's,
    and checking again indeed does not clear it."""
    checks = Reinstalled(REVISION)
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    made = completed(tmp_path, setup)
    write_private(
        setup.installation_path,
        json.dumps(
            {"schema": INSTALLATION_SCHEMA, "revision": REVISION, "images": {}}
        ).encode(),
    )
    assert setup.state()["steps"]["compute"]["checked"] is True
    head["revision"] = checks.revision = NEW  # moved by hand
    compute = setup.state()["steps"]["compute"]
    assert compute["checked"] is False
    assert compute["next_step"].startswith(REINSTALL_STEP)
    setup.compute(
        {
            "choice": LOCAL_CPU,
            "image_manifest": made["worker.json"],
            "analysis_image_manifest": made["analysis.json"],
        }
    )
    with pytest.raises(SetupRefused) as refused:
        setup.review({"confirm": True})
    assert refused.value.code == "compute_check_is_stale"
    assert refused.value.next_step.startswith(REINSTALL_STEP)
    assert "this checkout is at " + NEW[:12] in refused.value.next_step


def test_a_check_that_checking_again_clears_names_setup(tmp_path, state, head):
    """While the checkout is the installed revision, a check made at another
    revision or with other images is cleared by checking again: setup's step,
    not a reinstall."""
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    made = completed(tmp_path, setup)
    record = setup._record()
    record["compute"]["runtime"]["implementation"]["revision"] = NEW
    setup._save(record)
    # The installer built its worker image elsewhere than setup checked.
    installed_worker = tmp_path / "installed-worker.json"
    installed_worker.write_bytes(Path(made["worker.json"]).read_bytes())
    write_private(
        setup.installation_path,
        json.dumps(
            {
                "schema": INSTALLATION_SCHEMA,
                "revision": REVISION,
                "images": {"image_manifest": {"path": str(installed_worker)}},
            }
        ).encode(),
    )
    compute = setup.state()["steps"]["compute"]
    assert compute["stale"] == [
        "Carbon was installed at "
        + REVISION[:12]
        + " and the check was made at "
        + NEW[:12],
        "setup checked another worker image than the one the installer built",
    ]
    assert compute["next_step"] == RECHECK_STEP
    with pytest.raises(SetupRefused) as refused:
        setup.review({"confirm": True})
    assert refused.value.next_step.startswith(RECHECK_STEP + ": ")
    # Checking again, at HEAD and with the installer's own worker image, as
    # setup fills it in, clears both.
    setup.compute(
        {
            "choice": LOCAL_CPU,
            "image_manifest": str(installed_worker),
            "analysis_image_manifest": made["analysis.json"],
        }
    )
    assert "stale" not in setup.state()["steps"]["compute"]
    setup.review({"confirm": True})
    assert profile(setup)["accepted_revision"] == REVISION


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
    direct_target = {
        "intake_url": "http://127.0.0.1:9080",
        "receiver_hotkey": HOTKEY,
    }
    setup.review({"confirm": True, "direct_intake_target": direct_target})
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
    assert cfg["direct_intake_target"] == direct_target
    assert cfg["runtime"]["implementation"]["revision"] == NEW
    compute = setup.state()["steps"]["compute"]
    assert compute["checked"] is True and "set_aside" not in compute
    # The old profile was moved aside, and the new one replaced it.
    assert report["profile_set_aside"] == STALE_PROFILE
    assert "profile_set_aside" not in setup._record()
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


def test_a_set_aside_profile_is_moved_where_no_restart_attaches_it(
    tmp_path, state, head, challenge
):
    """Review finding, 2026-10-03: the controller attaches
    `runner-profile.json` on start whenever it exists, so a remote miner's
    profile at the old accepted revision was attached after an update while
    setup said none was written. It is moved aside, owner-only, and the
    miner's own intake in it is kept for setup to show."""
    checks = Intakes()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    completed(tmp_path, setup)
    setup.review(own_review(challenge))
    written = setup.profile_path.read_bytes()
    record = setup._record()
    record["compute"]["choice"] = REMOTE
    setup._save(record)
    head["revision"] = checks.revision = NEW
    worker, analysis = rebuild(tmp_path, state, NEW)
    report = setup.after_install()
    assert report["compute"] == "set aside"
    assert report["profile_set_aside"] == STALE_PROFILE
    # Nothing is left where the controller looks on start.
    assert not (state / "environment" / "runner-profile.json").exists()
    stale = state / "environment" / STALE_PROFILE
    assert stale.read_bytes() == written
    assert stat.S_IMODE(stale.stat().st_mode) == 0o600
    assert setup.state()["steps"]["review"]["profile_written"] is False
    item = setup.state()["steps"]["evaluation"]["challenges"][0]
    assert item["set_aside_intake"] == OWN
    assert item["set_aside_receiver"] == HOTKEY  # named again with it
    assert "name yours again at Review" in item["note"]
    assert any(
        "set aside with the compute check" in line for line in describe_install(report)
    )
    # Checked again and reviewed with the intake named: a new profile, at
    # the new revision, and the set-aside marker is gone.
    setup.compute(
        {
            "choice": LOCAL_CPU,
            "image_manifest": str(worker),
            "analysis_image_manifest": str(analysis),
        }
    )
    setup.review(own_review(challenge))
    assert profile(setup)["accepted_revision"] == NEW
    assert profile(setup)["intakes"] == {challenge["id"]: OWN}
    assert profile(setup)["receivers"] == {challenge["id"]: HOTKEY}
    assert "profile_set_aside" not in setup._record()
    item = setup.state()["steps"]["evaluation"]["challenges"][0]
    assert "set_aside_intake" not in item


def test_an_update_keeps_the_intake_the_miner_named(tmp_path, state, head, challenge):
    checks = Intakes()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    completed(tmp_path, setup)
    setup.review(own_review(challenge))
    head["revision"] = checks.revision = NEW
    rebuild(tmp_path, state, NEW)
    report = setup.after_install()
    assert report["profile"]["written"] is True
    assert report["profile"]["warnings"] == unpublished(challenge)
    assert profile(setup)["intakes"] == {challenge["id"]: OWN}
    # Its receiver is pinned again (LAUNCHPAD-ACCEPT-03).
    assert profile(setup)["receivers"] == {challenge["id"]: HOTKEY}
    # The named intake is checked again, as at any Review.
    assert checks.calls.count(("intake", OWN)) == 2


def test_a_profile_written_before_intakes_were_recorded_keeps_the_miners_own(
    tmp_path, state, head, challenge
):
    checks = Intakes()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    completed(tmp_path, setup)
    setup.review(own_review(challenge))
    record = setup._record()
    # As a Review before LP-PROD-E recorded it: when, and nothing else.
    record["profile"] = {"written_at": record["profile"]["written_at"]}
    setup._save(record)
    item = setup.state()["steps"]["evaluation"]["challenges"][0]
    assert (item["intake"], item["source"]) == (OWN, "yours")
    # No receiver is recorded for it: setup warns, never refuses.
    assert "Review again in setup to pin it" in item["receiver_hotkey_warning"]
    head["revision"] = checks.revision = NEW
    rebuild(tmp_path, state, NEW)
    report = setup.after_install()
    # Written again unpinned, with a warning, rather than stranded
    # (LAUNCHPAD-ACCEPT-03's working decision).
    assert report["profile"]["written"] is True
    # The miner's own intake names the Challenge, so it serves each of its
    # intake versions (Battery 1.0 and 2.2), each unpinned and said so.
    versions = [c for c in intake_challenges() if c["id"] == challenge["id"]]
    assert [w["code"] for w in report["profile"]["warnings"]] == [
        *(["intake_receiver_not_pinned"] * len(versions)),
        *(w["code"] for w in unpublished(challenge)),
    ]
    assert profile(setup)["intakes"] == {challenge["id"]: OWN}
    assert "receivers" not in profile(setup)


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


# --- an update leaves the miner ready (M1 E2E U54/U67) ---------------------------


class Current(Intakes):
    """Fixture checks whose compute check reads each image ID from its
    manifest, as the real check does, so a profile written now is current."""

    def compute(self, image, analysis):
        runtime = super().compute(image, analysis)
        images = [
            json.loads(Path(path).read_bytes()).get("image_id", fixed)
            for path, fixed in zip((image, analysis), runtime["images"], strict=False)
        ]
        return {**runtime, "images": images + runtime["images"][2:]}


def test_an_update_writes_a_stale_profile_again_though_compute_is_current(
    tmp_path, state, head, challenge
):
    """Compute checked again after the checkout moved, but the profile not
    written again: the next install finds compute current and, before U54,
    left the stale profile for the Control Center to refuse."""
    checks = Current()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    completed(tmp_path, setup)
    setup.review(own_review(challenge))
    head["revision"] = checks.revision = NEW
    worker, analysis = rebuild(tmp_path, state, NEW)
    # Compute checked again in setup, which drops Review's record ("any
    # change needs a new review"); the profile file stays where the Control
    # Center loads it.
    setup.compute(
        {
            "choice": LOCAL_CPU,
            "image_manifest": str(worker),
            "analysis_image_manifest": str(analysis),
        }
    )
    assert profile(setup)["accepted_revision"] == REVISION
    assert "profile" not in setup._record()
    report = setup.after_install()
    assert report["compute"] == "unchanged"
    assert report["profile"]["written"] is True
    assert profile(setup)["accepted_revision"] == NEW
    assert profile(setup)["intakes"] == {challenge["id"]: OWN}
    assert profile(setup)["receivers"] == {challenge["id"]: HOTKEY}
    assert setup.profile_staleness(profile(setup)) == ([], None)


def test_an_update_after_a_refused_recheck_checks_again_with_the_kept_choices(
    tmp_path, state, head, challenge
):
    """An earlier update set compute aside and its check again was refused:
    before U54 the next install said "not set up yet" and stopped, with
    catalog_install refused step_not_checked. The choice and the miner's own
    intake were kept beside the set-aside record and are used again."""

    class Refusing(Intakes):
        def compute(self, image, analysis):
            raise SetupRefused("image_manifest", "worker_image_unverified")

    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Intakes())
    completed(tmp_path, setup)
    setup.review(own_review(challenge))
    head["revision"] = NEW
    rebuild(tmp_path, state, NEW)
    setup.checks = Refusing(NEW)
    assert setup.after_install()["compute"] == "set aside"
    kept = setup._record()["compute_set_aside"]
    assert kept["choice"] == LOCAL_CPU
    assert setup._record()["profile_set_aside"]["intakes"][challenge["id"]] == {
        "url": OWN,
        "source": "yours",
        "receiver": HOTKEY,
    }
    setup.checks = Intakes(NEW)
    report = setup.after_install()
    assert report["compute"] == "checked again"
    assert report["profile"]["written"] is True
    assert setup.state()["steps"]["compute"]["checked"] is True
    assert profile(setup)["accepted_revision"] == NEW
    assert profile(setup)["intakes"] == {challenge["id"]: OWN}
    assert profile(setup)["receivers"] == {challenge["id"]: HOTKEY}
    record = setup._record()
    assert "profile_set_aside" not in record and "compute" in record


def test_one_recheck_call_leaves_the_miner_ready_after_an_update(
    tmp_path, state, head, challenge
):
    """The page's one click (and the MCP door's `carbon_setup_recheck`): the
    same check again and profile write as the installer, for a check the
    installer could not make (here, refused), with the miner's choices."""
    from scripts.dev.miner_launchpad import setup_operations

    class Refusing(Intakes):
        def compute(self, image, analysis):
            raise SetupRefused("image_manifest", "worker_image_unverified")

    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Intakes())
    completed(tmp_path, setup)
    setup.review(own_review(challenge))
    head["revision"] = NEW
    rebuild(tmp_path, state, NEW)
    setup.checks = Refusing(NEW)
    setup.after_install()
    for door in (setup_operations.MCP, setup_operations.HTTP):
        nxt = setup_operations.status(setup, door=door)["next"]
        assert nxt["step"] == "compute"
        assert nxt["recheck"] == setup_operations.call("recheck", door)
    with pytest.raises(SetupRefused) as refused:
        setup.recheck({"confirm": False})
    assert refused.value.code == "recheck_needs_confirmation"
    setup.checks = Current(NEW)
    result = setup.recheck({"confirm": True})
    assert result["update"]["compute"] == "checked again"
    assert result["update"]["profile"]["written"] is True
    assert result["update"]["next_steps"] == []
    assert result["steps"]["compute"]["checked"] is True
    assert result["steps"]["review"]["profile_written"] is True
    assert profile(setup)["accepted_revision"] == NEW
    assert profile(setup)["intakes"] == {challenge["id"]: OWN}
    nxt = setup_operations.status(setup, door=setup_operations.MCP)["next"]
    assert nxt is None or "recheck" not in nxt
    # Nothing left to do: a second call checks nothing and writes nothing.
    calls = len(setup.checks.calls)
    again = setup.recheck({"confirm": True})["update"]
    assert again == {"compute": "unchanged", "next_steps": []}
    assert len(setup.checks.calls) == calls


def test_recheck_leaves_a_remote_setup_and_a_moved_checkout_to_their_owners(
    tmp_path, state, head
):
    from scripts.dev.miner_launchpad import setup_operations

    checks = Reinstalled()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    completed(tmp_path, setup)
    setup.review({"confirm": True})
    record = setup._record()
    record["compute"]["choice"] = REMOTE
    setup._save(record)
    head["revision"] = NEW
    rebuild(tmp_path, state, NEW)
    setup.after_install()
    nxt = setup_operations.status(setup, door=setup_operations.MCP)["next"]
    assert "recheck" not in nxt  # the miner checks their own setup
    calls = len(checks.calls)
    update = setup.recheck({"confirm": True})["update"]
    assert update["next_steps"] == [REMOTE_RECHECK]
    assert len(checks.calls) == calls  # nothing reached
    # The checkout moved since the install: only the installer clears it.
    other, files = tmp_path / "other", tmp_path / "o"
    other.mkdir(mode=0o700)
    files.mkdir()
    setup2 = EnvironmentSetup(other, onboarding=Onboarding(), checks=Reinstalled(NEW))
    completed(files, setup2)
    rebuild(files, other, NEW)
    setup2.after_install()
    head["revision"] = "e" * 40
    with pytest.raises(SetupRefused) as refused:
        setup2.recheck({"confirm": True})
    assert refused.value.code == "carbon_updated_rerun_installer"
    assert refused.value.next_step.startswith(REINSTALL_STEP)


def test_a_stale_check_that_blocks_nothing_reads_done_on_the_step_and_the_list(
    tmp_path, state, head
):
    """M1 E2E R6-2: the compute step read "next" while launches ran, and
    agents could not tell whether it blocked. A stale check under a profile
    that still describes this install reads done, with why and the one
    click; once the profile no longer does, it blocks, and says so."""
    from scripts.dev.miner_launchpad import setup_operations

    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Current())
    made = completed(tmp_path, setup)
    setup.review({"confirm": True})
    # The manifest is written again, naming the same image: the check is
    # stale, the profile (pinned by image ID) is not.
    worker = Path(made["worker.json"])
    worker.write_text(json.dumps({**json.loads(worker.read_bytes()), "note": 1}))
    assert setup.state()["steps"]["compute"]["stale"]
    for door in (setup_operations.MCP, setup_operations.HTTP):
        view = setup_operations.status(setup, door=door)
        row = next(r for r in view["steps"] if r["id"] == "compute")
        assert row["state"] == "done" and "compute" in view["done"]
        assert row["blocks_launch"] is False
        assert row["stale"] == ["the worker image was rebuilt since the check"]
        assert "launches work" in row["note"]
        assert row["recheck"] == setup_operations.call("recheck", door)
        assert view["next"]["step"] == "launch"
        # The step and the list agree, row by row.
        assert view["done"] == [
            r["id"]
            for r in view["steps"]
            if r["blocks_launch"] is False and r["state"] == "done"
        ]
    # The profile no longer loads: now the stale check blocks.
    setup.profile_path.unlink()
    view = setup_operations.status(setup, door=setup_operations.MCP)
    row = next(r for r in view["steps"] if r["id"] == "compute")
    assert row["state"] == "next" and row["blocks_launch"] is True
    assert row["missing"] == ["compute_check_is_stale"]
    assert "compute" not in view["done"]


def test_a_head_git_cannot_read_is_not_a_moved_checkout(tmp_path, state, head):
    """M1 E2E R6-2: judged only on what can be read; a busy checkout whose
    HEAD git could not report sent a running miner to reinstall."""
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    rebuild(tmp_path, state, REVISION)
    setup.after_install()
    assert "stale" not in setup.state()["steps"]["compute"]
    head["revision"] = None
    assert "stale" not in setup.state()["steps"]["compute"]
    head["revision"] = NEW
    assert setup.state()["steps"]["compute"]["next_step"].startswith(REINSTALL_STEP)


def test_recheck_writes_the_profile_a_changed_step_left_unwritten(
    tmp_path, state, head, monkeypatch
):
    """M1 E2E R8-7: after Compute was checked again (which drops Review's
    record), recheck said ready and wrote nothing; Review had to. It writes
    it, and with no profile ever written it says so."""
    from scripts.dev.miner_launchpad import catalog_build, setup_operations

    starts = []
    monkeypatch.setattr(
        catalog_build,
        "start",
        lambda root: starts.append(root) or {"state": "RUNNING"},
    )
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Current())
    made = completed(tmp_path, setup)
    rebuild_path = {
        "choice": LOCAL_CPU,
        "image_manifest": made["worker.json"],
        "analysis_image_manifest": made["analysis.json"],
    }
    rebuild(tmp_path, state, REVISION)
    unwritten = setup_operations.perform(
        setup, "recheck", {"confirm": True}, door=setup_operations.MCP
    )
    assert unwritten["update"]["profile"] == {
        "written": False,
        "code": "profile_not_written",
    }
    assert "review in setup to write your profile" in unwritten["update"]["next_steps"]
    assert starts == []
    setup.review({"confirm": True})
    setup.compute(rebuild_path)
    assert setup.state()["steps"]["review"]["profile_written"] is False
    result = setup_operations.perform(
        setup, "recheck", {"confirm": True}, door=setup_operations.MCP
    )
    assert result["update"]["profile"]["written"] is True
    assert result["steps"]["review"]["profile_written"] is True
    assert starts == [state]


def test_a_challenge_without_an_intake_names_a_field_the_schema_has(
    tmp_path, state, head
):
    """M1 E2E R8-7: the refusal sent an MCP agent to a page label; it names
    `direct_intake_target`, which the review schema now describes."""
    from scripts.dev.miner_launchpad import setup_operations

    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Intakes())
    completed(tmp_path, setup)
    with pytest.raises(SetupRefused) as refused:
        setup.review({"confirm": True, "intakes": {"electric-motor-magnetics": OWN}})
    assert refused.value.code == "challenge_has_no_intake"
    assert refused.value.field == "intakes"
    assert "direct_intake_target" in refused.value.next_step
    for door in (setup_operations.MCP, setup_operations.HTTP):
        properties = setup_operations.schema("review", door)["properties"]
        assert {"intakes", "direct_intake_target"} <= set(properties)


def test_a_moved_checkout_names_the_install_that_needs_updating(
    tmp_path, state, head, monkeypatch
):
    """M1 E2E R8-2: one checkout served two installs; updating the default
    one moved the checkout under the second, whose agents were sent to
    "--update" with no word of which. The step names this setup's own state
    directory, unless it is the default one."""
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    rebuild(tmp_path, state, REVISION)
    setup.after_install()
    head["revision"] = NEW
    step = setup.state()["steps"]["compute"]["next_step"]
    assert step == (
        REINSTALL_STEP
        + " with CARBON_STATE_DIR="
        + str(state)
        + " (this setup's own state directory: another install sharing this "
        "checkout updated it)"
    )
    monkeypatch.setattr(environment, "DEFAULT_STATE_DIR", state)
    assert setup.state()["steps"]["compute"]["next_step"] == REINSTALL_STEP


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
    # Every intake Challenge version published (v2), each at its own endpoint:
    # a receiver serves exactly one version (Motor 1.2 and 1.3 each have one).
    every = intake_challenges()
    urls = [
        URL if i == 0 else f"{URL}/{c['id']}/{c['version']}"
        for i, c in enumerate(every)
    ]
    publish(
        tmp_path,
        monkeypatch,
        [
            entry(c["id"], version=c["version"], intake_url=url)
            for c, url in zip(every, urls, strict=True)
        ],
        schema="v2",
    )
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    before = setup.state()["steps"]["evaluation"]
    assert before["ready"] is True
    assert before["challenges"][0]["source"] == "published"
    result = setup.review({"confirm": True})
    assert result["warnings"] == []
    # Written for exactly each version, never by Challenge id alone.
    written_profile = profile(setup)
    assert "intakes" not in written_profile and "receivers" not in written_profile
    expected = {}
    for c, url in zip(every, urls, strict=True):
        expected.setdefault(c["id"], {})[c["version"]] = [
            {"intake_url": url, "receiver_hotkey": HOTKEY}
        ]
    assert written_profile["version_intakes"] == expected
    items = result["steps"]["evaluation"]["challenges"]
    assert [(i["id"], i["version"], i["intake"]) for i in items] == [
        (c["id"], c["version"], url) for c, url in zip(every, urls, strict=True)
    ]
    written = items[0]
    assert (written["intake"], written["source"]) == (URL, "published")
    assert written["receiver_hotkey"] == HOTKEY
    # Binding (LAUNCHPAD-ACCEPT-03): pinned in the profile from the published
    # entry, without reaching the endpoint, and setup says so.
    assert written["receiver_hotkey_note"] == environment.RECEIVER_NOTE
    assert "binding" in environment.RECEIVER_NOTE
    # Each version's campaign reads its own version's endpoint only.
    from carbon.development_session.intake_targets import for_version

    for c, url in zip(every, urls, strict=True):
        own = for_version(written_profile, c["id"], c["version"])
        assert runner.intakes(own)[c["id"]] == url
        assert runner.receivers(own)[c["id"]] == HOTKEY
    assert runner.validated_profile(dict(written_profile)) == written_profile


def test_with_none_published_review_says_so_and_still_writes(
    tmp_path, state, head, monkeypatch, challenge
):
    publish(tmp_path, monkeypatch, [])
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    result = setup.review({"confirm": True})
    assert result["warnings"] == unpublished()
    assert result["warnings"][0]["challenge"] == challenge["id"]
    assert "intakes" not in profile(setup)
    evaluation = result["steps"]["evaluation"]
    assert evaluation["ready"] is False
    assert "nothing for you to fix" in evaluation["challenges"][0]["note"]
    # Published after Review: setup says to review again. A v2 entry names
    # its version: a v1 entry no longer applies to a Challenge with two.
    publish(
        tmp_path,
        monkeypatch,
        [entry(challenge["id"], version=challenge["version"])],
        schema="v2",
    )
    note = setup.state()["steps"]["evaluation"]["challenges"][0]["note"]
    assert "since your profile was written: review again" in note


def test_the_no_endpoint_note_names_carbon_and_asks_nothing_of_the_miner():
    # Validator (Motor 1.2 landing): Carbon is the party that has not
    # published it; nothing for the miner to fix; their own intake is an
    # alternative, never a remedy.
    note = environment.NO_ENDPOINT.format(title="Motor")
    assert note.startswith("Carbon has not published an evaluation endpoint")
    assert "nothing for you to fix" in note
    assert "once Carbon publishes one" in note
    assert "name a validator intake you run yourself" in note
    assert "update Carbon" not in note and "review again" not in note


def test_a_named_intake_wins_over_the_published_one(
    tmp_path, state, head, monkeypatch, challenge
):
    publish(tmp_path, monkeypatch, [entry(challenge["id"])])
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Intakes())
    completed(tmp_path, setup)
    result = setup.review(own_review(challenge))
    assert profile(setup)["intakes"] == {challenge["id"]: OWN}
    item = result["steps"]["evaluation"]["challenges"][0]
    assert (item["intake"], item["source"]) == (OWN, "yours")
    assert item["receiver_hotkey"] == HOTKEY


# --- LAUNCHPAD-ACCEPT-03: Review pins each intake's receiver -----------------------

OTHER = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"


def test_an_own_intake_needs_its_receiver_and_review_pins_it(
    tmp_path, state, head, challenge
):
    checks = Intakes()
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=checks)
    completed(tmp_path, setup)
    for request, code in (
        ({"intakes": {challenge["id"]: OWN}}, "receiver_hotkey_required"),
        (
            {"intakes": {challenge["id"]: OWN}, "receiver_hotkey": "not-an-address"},
            "receiver_hotkey_invalid",
        ),
        ({"receiver_hotkey": HOTKEY}, "receiver_hotkey_names_one_intake"),
        (
            {"intakes": {challenge["id"]: OWN}, "receivers": {"nowhere": HOTKEY}},
            "receiver_hotkey_needs_its_intake",
        ),
    ):
        with pytest.raises(SetupRefused) as refused:
            setup.review({"confirm": True, **request})
        assert (refused.value.field, refused.value.code) == ("receiver_hotkey", code)
        assert refused.value.next_step
    assert not setup.profile_path.exists()
    assert ("intake", OWN) not in checks.calls  # refused before it was read
    # Named as a map, the same.
    setup.review(
        {
            "confirm": True,
            "intakes": {challenge["id"]: OWN},
            "receivers": {challenge["id"]: HOTKEY},
        }
    )
    assert profile(setup)["receivers"] == {challenge["id"]: HOTKEY}
    assert setup._record()["profile"]["intakes"][challenge["id"]] == {
        "url": OWN,
        "source": "yours",
        "receiver": HOTKEY,
    }


def test_review_refuses_an_intake_reporting_another_receiver(
    tmp_path, state, head, challenge
):
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Intakes())
    completed(tmp_path, setup)
    with pytest.raises(SetupRefused) as refused:
        setup.review(own_review(challenge, OTHER))
    assert (refused.value.field, refused.value.code) == (
        "receiver_hotkey",
        "intake_receiver_mismatch",
    )
    assert refused.value.next_step == environment.RECEIVER_MISMATCH_STEP
    assert not setup.profile_path.exists()


def test_a_legacy_profile_with_an_unpinned_intake_still_validates(
    tmp_path, state, head, challenge
):
    """A profile written before `receivers` validates unchanged, and its
    review pin is the same: the field is an optional addition, and its
    campaign arguments carry no receiver, which is not checked."""
    setup = EnvironmentSetup(state, onboarding=Onboarding(), checks=Reinstalled())
    completed(tmp_path, setup)
    setup.review({"confirm": True})
    legacy = {**profile(setup), "intakes": {challenge["id"]: OWN}}
    legacy.pop("receivers", None)
    assert runner.validated_profile(dict(legacy)) == legacy
    assert runner.review_pin(runner.validated_profile(dict(legacy))) == (
        runner.review_pin(legacy)
    )
    assert runner.campaign_args(legacy, root=tmp_path).receivers == {}
    pinned = {**legacy, "receivers": {challenge["id"]: HOTKEY}}
    assert runner.validated_profile(dict(pinned))["receivers"] == pinned["receivers"]
    for bad in (
        {challenge["id"]: "not-an-address"},
        {"nowhere": HOTKEY},
        [HOTKEY],
    ):
        with pytest.raises(ValueError):
            runner.validated_profile({**legacy, "receivers": bad})
    no_intake = {k: v for k, v in pinned.items() if k != "intakes"}
    with pytest.raises(ValueError, match="beside its intake"):
        runner.validated_profile(no_intake)


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
        "unversioned": [],
    }


def test_the_published_list_is_one_per_challenge_on_this_network(
    tmp_path, monkeypatch, challenge
):
    # v2 entries: each names its version (a v1 entry no longer applies to a
    # Challenge with two intake versions).
    mine = entry(challenge["id"], version=challenge["version"])
    other = {**mine, "network": "finney", "netuid": 1}
    path = publish(tmp_path, monkeypatch, [mine, other], schema="v2")
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
    assert document["schema"] == environment.PUBLISHED_SCHEMA
    assert set(document["entry_fields"]) == environment.PUBLISHED_FIELDS
    assert "version" in environment.PUBLISHED_FIELDS


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
