"""The supported Workbench launcher as processes: check, serve, stop, restart, recover.

Every other host test builds the application in process and replaces
``load_profile``, so none of them runs the command an operator runs. This one
does. ``workbench_host check`` and ``register-draft`` run unmodified in their own
processes; ``serve`` runs in its own process with exactly one substitution, the
external hotkey and testnet runtime, because a real one binds a registered miner.
Profile loading, the grant check, the campaign owner lock, ledger freeze,
controller generation, scientific material selection, the draft registry, staff
tokens, the private-build check, the Julia worker and reconciliation are the
product's own.

The profile, grant and campaign are test-owned synthetic records in a temporary
root. The grant's authority is ``ENGINEERING_FIXTURE_ONLY`` and the profile's
provider key file does not exist, so nothing here can authorize a real provider
account, protected service or public transaction. This is lifecycle evidence for
the launcher, not a deployment, security qualification or scientific result.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import time
from hashlib import sha256
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests/cpu")]

import httpx2 as httpx
import pytest
from test_authored_julia_service import assert_removed
from test_cw1_research_data import case
from test_standard_mcp_cli import FixtureSigner, fixture_connection, private_write

from carbon.development_session.julia_research import julia_burgers_scope
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_admission import (
    MANIFEST,
    PROFILE,
    SCHEMA,
    Admission,
)
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import (
    DEVELOPMENT_CEILINGS,
    DEVELOPMENT_ELAPSED_SECONDS,
    CampaignLedger,
)
from carbon.development_session.research_service import make_research_service
from carbon.miner_mcp import standard_cli
from carbon.reconstruction.worker.docker_runtime import load_image_identity
from carbon.scientific_tasks.workbench import REQUEST, TEMPLATE, wire_digest

HOST = [sys.executable, "-m", "carbon.scientific_tasks.workbench_host"]
BUILD = REPOSITORY / "Business/Carbon_Fit/workbench/tools/build.py"
TOKEN = "launcher-process-staff-token-" + "b" * 24
SCIENCE = "/api/scientific-studies/"
HOST_ROUTES = "/api/workbench-host/"
JOB, DESIGN = "launcher-job", "launcher-design"
SCOPE = {
    **{
        key: "synthetic operator-reviewed public Burgers source"
        for key in (
            "inputs",
            "outputs",
            "units",
            "geometry",
            "conditions",
            "regime",
            "exclusions",
            "query_workload",
            "reference_equation",
            "reference_method",
        )
    },
    "physics_family": TEMPLATE,
    "requested_goal": "Dynamics",
    "rights_scope": "SYNTHETIC_INTERNAL",
}


@pytest.fixture(scope="module")
def worker():
    manifest = os.environ.get("CARBON_JULIA_WORKER_MANIFEST")
    assert manifest, "exact Julia worker image required"
    return Path(manifest).resolve(), load_image_identity(Path(manifest))


def prepare(root: Path, manifest: Path, image, monkeypatch):
    """Write the profile, grant and prepared campaign an operator would hold."""
    import carbon.chain.auth
    from scripts.dev.miner_launchpad.runner import PATH_FIELDS

    monkeypatch.setattr(carbon.chain.auth, "BittensorMessageSigner", FixtureSigner)
    root.chmod(0o700)
    campaign = root / "campaign"
    campaign.mkdir(mode=0o700)
    owner = asyncio.run(standard_cli._requester(fixture_connection(campaign)))
    roles = campaign / "private-roles"
    roles.mkdir(mode=0o700)
    body = canonical([case().public_record()])
    (roles / "research-train-cases.json").write_bytes(body)
    (roles / "private-role-manifest.json").write_bytes(
        canonical({"research-train": {"digest": digest(body)}})
    )
    runtime = {
        "implementation": {"revision": "f" * 40},
        "images": [image.image_id],
        "scientific_tasks": [julia_burgers_scope(image, roles)],
    }
    grant = {
        "schema": SCHEMA,
        "status": "APPROVED",
        "authority": "ENGINEERING_FIXTURE_ONLY",
        "grant_id": "workbench-launcher-fixture",
        "campaign_id": "workbench-launcher-fixture",
        "root": str(campaign),
        "principal": "fixture-operator",
        "miner_identity": "fixture-miner",
        "profile": PROFILE,
        "runtime": runtime,
        "provider": "openai-responses",
        "account_ref": "fixture-no-paid-calls",
        "campaign_count": 1,
        "ceilings": dict(DEVELOPMENT_CEILINGS),
        "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
        "expires_unix": time.time() + DEVELOPMENT_ELAPSED_SECONDS,
        "cleanup": "all-campaign-owned-work; unresolved-reservations-retained",
        "retry_allowance": 0,
    }
    grant_file = root / "grant.json"
    private_write(grant_file, grant)
    admission = Admission.load(grant_file)
    manifest_record = {
        "schema": MANIFEST,
        "campaign_id": grant["campaign_id"],
        "authority": grant["authority"],
        "principal": grant["principal"],
        "owner": owner,
        "runtime": runtime,
        "grant": admission.binding(),
        "ceilings": dict(DEVELOPMENT_CEILINGS),
        "elapsed_seconds": DEVELOPMENT_ELAPSED_SECONDS,
        "implementation": runtime["implementation"],
        "images": runtime["images"],
        **dict.fromkeys(
            (
                "objective",
                "sampling",
                "control",
                "selection",
                "replica_policy",
                "provider",
            ),
            "engineering-fixture-only",
        ),
    }
    ledger = CampaignLedger(campaign, admission=admission)
    ledger.freeze(manifest_record)
    private_write(campaign / "campaign-manifest.json", manifest_record)
    # Prepared through the same selection the attachment makes, so the task store
    # is bound to the material the launcher will actually compose.
    material, practice = standard_cli._science(ledger, owner, image, roles)
    make_research_service(
        root=campaign / "research-tasks",
        ledger=ledger,
        owner=owner,
        image=image,
        public_material=material,
        practice=practice,
    ).tasks.close()
    # Only the worker image manifest exists. The provider key file, miner key and
    # operator config are named but absent: the runtime that would read them is
    # the one substitution, and nothing can be authorized from a missing file.
    paths = {name: str(root / "absent" / (name + ".json")) for name in PATH_FIELDS}
    paths["image_manifest"] = str(manifest)
    profile = root / "profile.json"
    private_write(
        profile,
        {
            "schema": "carbon.launchpad.runner-profile.v1",
            "profile_id": "workbench-launcher-fixture",
            "principal": grant["principal"],
            "grant_file": str(grant_file),
            "account_ref": grant["account_ref"],
            "enabled": True,
            "paths": paths,
            "accepted_revision": runtime["implementation"]["revision"],
        },
    )
    principals = root / "private" / "staff.json"
    principals.parent.mkdir(mode=0o700)
    private_write(
        principals,
        {
            "schema": "carbon.workbench.host-principals.v1",
            "campaign_principal": owner,
            "staff": [
                {
                    "name": "Launcher Test",
                    "token_sha256": sha256(TOKEN.encode()).hexdigest(),
                }
            ],
        },
    )
    return profile, principals, grant_file, owner


def serve_with_fixture_runtime(argv):
    """Child process: the real ``serve`` with only the external runtime replaced."""
    import carbon.chain.auth
    from carbon.development_session import research_tools
    from carbon.scientific_tasks import workbench_host

    carbon.chain.auth.BittensorMessageSigner = FixtureSigner
    research_tools.BittensorMessageSigner = FixtureSigner

    def runtime(profile):
        image = load_image_identity(Path(profile.document["paths"]["image_manifest"]))
        return (
            fixture_connection(profile.root),
            image,
            image,
            profile.root / "private-roles",
        )

    standard_cli._runtime = runtime
    return workbench_host.main(["serve", *argv])


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Launcher:
    def __init__(self, tmp_path, profile, principals, static):
        self.tmp_path = tmp_path
        self.args = [
            "--configuration",
            str(profile),
            "--draft-registry",
            str(tmp_path / "private" / "drafts.json"),
            "--principals",
            str(principals),
            "--static",
            str(static),
        ]
        self.runs = 0

    def start(self, port=None):
        port = port or free_port()
        origin = f"http://127.0.0.1:{port}"
        self.runs += 1
        log = self.tmp_path / f"serve-{self.runs}.log"
        process = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--serve",
                *self.args,
                "--origin",
                origin,
                "--port",
                str(port),
            ],
            cwd=REPOSITORY,
            stdout=log.open("wb"),
            stderr=subprocess.STDOUT,
        )
        return process, origin, log

    @staticmethod
    def wait_serving(process, origin, log, timeout=180):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail(f"launcher exited {process.returncode}: {log.read_text()}")
            try:
                health = httpx.get(origin + HOST_ROUTES + "health", timeout=2)
            except httpx.HTTPError:
                time.sleep(0.25)
                continue
            assert health.status_code == 200, health.text
            assert health.json()["status"] == "SERVING"
            return
        process.kill()
        pytest.fail("launcher never reported SERVING: " + log.read_text())

    @staticmethod
    def stop(process, sig=signal.SIGTERM, timeout=120):
        process.send_signal(sig)
        return process.wait(timeout=timeout)


def study_request(physical):
    binding = {
        "job_id": JOB,
        "design_id": DESIGN,
        "design_revision": 1,
        "physical_sha256": wire_digest(
            {"template_id": TEMPLATE, "physical": physical, "draft_scope": SCOPE}
        ),
    }
    return {
        "schema": REQUEST,
        "operation_id": "study-" + wire_digest(binding),
        "action": "REFERENCE_FEASIBILITY",
        "binding": binding,
        "template_id": TEMPLATE,
        "physical": physical,
        "draft_scope": SCOPE,
        "rights_scope": "SYNTHETIC_INTERNAL",
    }


def test_the_launcher_starts_stops_restarts_and_recovers_as_an_operator_runs_it(
    worker, tmp_path, monkeypatch
):
    from scripts.dev.miner_launchpad.controller import owner_lock

    manifest, image = worker
    profile, principals, grant_file, owner = prepare(
        tmp_path, manifest, image, monkeypatch
    )
    campaign = tmp_path / "campaign"

    # The reviewed private build, produced by the supported command.
    static = (tmp_path / "workbench-private").resolve()
    subprocess.run(
        [
            sys.executable,
            str(BUILD),
            "--private-science",
            "--output-directory",
            str(static),
        ],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    )

    # check: unmodified, in its own process, and it prints no secret or path.
    checked = subprocess.run(
        [*HOST, "check", "--configuration", str(profile)],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr
    assert "ENABLED" in checked.stdout and "reference_feasibility" in checked.stdout
    assert str(tmp_path) not in checked.stdout and TOKEN not in checked.stdout

    # register-draft: unmodified, bound to the grant's exact physical definition.
    draft = tmp_path / "draft.json"
    draft.write_text(
        json.dumps(
            {"job_id": JOB, "design_id": DESIGN, "revision": 1, "draft_scope": SCOPE}
        )
    )
    registered = subprocess.run(
        [
            *HOST,
            "register-draft",
            "--configuration",
            str(profile),
            "--draft-registry",
            str(tmp_path / "private" / "drafts.json"),
            "--draft",
            str(draft),
        ],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        check=False,
    )
    assert registered.returncode == 0, registered.stderr
    assert json.loads(registered.stdout)["registered_drafts"]["revisions"] == 1

    launcher = Launcher(tmp_path, profile, principals, static)
    bearer = {"Authorization": "Bearer " + TOKEN}

    # Start.
    first, origin, log = launcher.start()
    launcher.wait_serving(first, origin, log)
    try:
        # One launcher per campaign: a second start refuses and never binds.
        rival_port = free_port()
        rival, _, rival_log = launcher.start(rival_port)
        assert rival.wait(timeout=120) == 2, rival_log.read_text()
        with pytest.raises(httpx.HTTPError):
            httpx.get(f"http://127.0.0.1:{rival_port}{HOST_ROUTES}health", timeout=2)

        assert httpx.get(origin + HOST_ROUTES + "capabilities").status_code == 401
        report = httpx.get(origin + HOST_ROUTES + "capabilities", headers=bearer)
        assert report.status_code == 200
        assert (
            report.json()["capabilities"]["reference_feasibility"]["status"]
            == "ENABLED"
        )
        page = httpx.get(origin + "/")
        assert (
            page.status_code == 200 and 'data-scientific-service="private"' in page.text
        )

        physical = httpx.get(origin + SCIENCE + "capabilities", headers=bearer).json()[
            "physical"
        ]
        request = study_request(physical)
        started = httpx.post(
            origin + SCIENCE + "start",
            json=request,
            headers={**bearer, "Origin": origin},
            timeout=600,
        )
        assert started.status_code == 200, started.text
        completed = started.json()
        assert completed["status"] == "COMPLETE"
        assert completed["qualification"] == "NOT_QUALIFIED"
        assert completed["official_eligible"] is False
    finally:
        # Asserted after the block, so a failure above is not replaced by this one.
        stopped = launcher.stop(first)
    # Stop: SIGTERM drains, reconciles and exits cleanly.
    assert stopped == 0, log.read_text()

    admission = Admission.load(grant_file)
    ledger = CampaignLedger(campaign, admission=admission)
    with owner_lock(campaign):  # released: the process gave up campaign ownership
        pass
    assert_removed(ledger)
    status = ledger.status(owner=owner)
    assert all(op["state"] != "RESERVED" for op in status["operations"])
    used = status["used"]
    assert used["reference_invocations"] >= 1
    assert used["provider_attempts"] == used["provider_nanodollars"] == 0
    control = CampaignControl(ledger).status()
    # Reconciled rather than merely exited: a process ended by the signal leaves
    # the generation it acquired in RECONCILING.
    assert control["state"] == "INTERRUPTED", control
    generation = control["generation"]

    def replayed_by_a_fresh_process(stop_signal):
        process, origin, log = launcher.start()
        launcher.wait_serving(process, origin, log)
        try:
            for action in ("start", "status", "result"):
                replay = httpx.post(
                    origin + SCIENCE + action,
                    json=request,
                    headers={**bearer, "Origin": origin},
                    timeout=120,
                )
                assert replay.status_code == 200, replay.text
                assert replay.json()["task_id"] == completed["task_id"]
                assert replay.json()["result"] == completed["result"]
        finally:
            code = launcher.stop(process, stop_signal)
        return code, log

    # Restart: a new process takes a new controller generation, returns the saved
    # study from the campaign's own records, and does no new numerical work.
    code, log = replayed_by_a_fresh_process(signal.SIGTERM)
    assert code == 0, log.read_text()
    assert ledger.status(owner=owner)["used"] == used
    control = CampaignControl(ledger).status()
    assert control["state"] == "INTERRUPTED" and control["generation"] > generation

    # Recover from a crash: SIGKILL skips reconciliation, the OS releases the
    # campaign lock, and the same start command serves again with nothing
    # reserved and nothing re-executed.
    code, log = replayed_by_a_fresh_process(signal.SIGKILL)
    assert code == -signal.SIGKILL
    # The specimen for the INTERRUPTED assertions above: a process that did not
    # reconcile really does leave its generation in RECONCILING.
    assert CampaignControl(ledger).status()["state"] == "RECONCILING"
    code, log = replayed_by_a_fresh_process(signal.SIGTERM)
    assert code == 0, log.read_text()
    assert ledger.status(owner=owner)["used"] == used
    assert all(
        op["state"] != "RESERVED" for op in ledger.status(owner=owner)["operations"]
    )
    assert_removed(ledger)
    assert CampaignControl(ledger).status()["state"] == "INTERRUPTED"
    print(
        json.dumps(
            {
                "case": "workbench-launcher-process-lifecycle",
                "image": image.image_id,
                "task_id": completed["task_id"],
                "processes": launcher.runs,
                "used": used,
                "restart_reexecuted": False,
                "scientifically_qualified": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__" and sys.argv[1:2] == ["--serve"]:
    raise SystemExit(serve_with_fixture_runtime(sys.argv[2:]))
