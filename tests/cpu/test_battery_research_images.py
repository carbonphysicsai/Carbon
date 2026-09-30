"""A battery campaign gets the host's research images, as a Burgers one does.

Owner direction (C-MLP-02): every prebuilt capability is available to every
campaign whenever wanted. For battery that is authored Julia: a runtime that
declares its scope freezes it, an attach re-checks it exactly, and the research
executor's `run_julia` reaches the image. GPU research is refused by name: its
scope binds Burgers material and battery has no GPU practice lane.

Julia is a research tool only. The last tests show that battery's discovery,
recipe compiler, practice, contract digest and submission fields are the same
with and without it, and that the validator-side modules never read it.

Fixtures: image identities, the host doctor, keys and the connection are
stand-ins; the ledger, manifest freeze and research composition are real. This
is engineering evidence only.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_miner_launchpad_runner import HOTKEY, registered

from carbon.battery import campaign as battery
from carbon.battery.challenge import CHALLENGE
from carbon.development_session import julia_analysis as julia
from carbon.development_session.product_campaign import ProductLaunch
from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_image import ResearchImageIdentity
from carbon.development_session.research_ledger import CampaignLedger

REPOSITORY = Path(__file__).resolve().parents[2]
IMPLEMENTATION = "fixture-implementation"
ANALYSIS = ResearchImageIdentity(
    "sha256:" + "a" * 64, "sha256:" + "b" * 64, "sha256:" + "c" * 64
)
IMAGES = [ANALYSIS.parent_image, ANALYSIS.image_id]


def julia_image(tag="d"):
    return julia.JuliaResearchImageIdentity(
        "sha256:" + tag * 64,
        ANALYSIS,
        digest(canonical(julia.runtime_document(ANALYSIS))),
    )


def install(root, image):
    """What the runner's `install_research_images` puts in a campaign root."""
    path = root / "authored-julia-image.json"
    path.unlink(missing_ok=True)
    path.write_bytes(canonical(julia.image_record(image)))
    path.chmod(0o600)


def runtime(image=None):
    value = {"implementation": IMPLEMENTATION, "images": list(IMAGES)}
    if image is not None:
        value["authored_research"] = [julia.authored_julia_scope(image)]
    return value


def launch(declared):
    return ProductLaunch(
        campaign_id="cmp-battery-julia",
        principal="alice",
        miner=registered(),
        runtime=declared,
        budget={},
        agent="none",
        challenge={"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
    )


@pytest.fixture
def host(tmp_path, monkeypatch):
    """Everything prepare_battery touches outside the campaign, as fixtures."""
    import carbon.chain.auth
    import carbon.chain.external_signer
    from carbon.development_session import (
        research_campaign,
        research_image,
        research_tools,
        service,
    )
    from carbon.development_testnet import operator
    from carbon.reconstruction.worker import docker_runtime

    tmp_path.chmod(0o700)
    root = tmp_path / "campaign"
    root.mkdir(mode=0o700)
    public = tmp_path / "miner-public.json"
    public.write_bytes(
        canonical({"netuid": 567, "hotkey": HOTKEY, "key_file": "unused-fixture"})
    )
    public.chmod(0o600)
    monkeypatch.setattr(
        research_campaign, "accepted_implementation", lambda _: IMPLEMENTATION
    )
    monkeypatch.setattr(research_campaign, "verify_current_worker", lambda *_: None)

    async def requester(_):
        return "miner-requester"

    monkeypatch.setattr(research_campaign, "requester", requester)
    monkeypatch.setattr(
        docker_runtime,
        "load_image_identity",
        lambda _: SimpleNamespace(image_id=ANALYSIS.parent_image),
    )
    monkeypatch.setattr(
        docker_runtime, "doctor", lambda **_: SimpleNamespace(eligible=True)
    )
    monkeypatch.setattr(research_image, "load_analysis_image", lambda _: ANALYSIS)
    monkeypatch.setattr(research_image, "verify_image", lambda _: None)
    monkeypatch.setattr(
        operator,
        "load_config",
        lambda _: SimpleNamespace(netuid=567, context=None, publisher_hotkey="pub"),
    )
    monkeypatch.setattr(
        carbon.chain.external_signer, "miner_signer", lambda *_: None
    )
    monkeypatch.setattr(service, "LocalMinerConnection", lambda *_: None)
    # Verification inspects Docker; the record and scope checks stay real.
    monkeypatch.setattr(julia, "verify_julia_image", lambda image: image)
    composed = []

    def compose(**kwargs):
        composed.append(kwargs)
        return SimpleNamespace(tasks=None), None

    monkeypatch.setattr(battery, "compose", compose)
    monkeypatch.setattr(research_tools, "ResearchMinerTools", lambda **kw: kw)

    def args(command, declared=None):
        return SimpleNamespace(
            root=root,
            command=command,
            accepted_revision="fixture",
            image_manifest=public,
            analysis_image_manifest=public,
            operator_config=public,
            miner_public=public,
            agent_policy=None,
            **({} if declared is None else {"product": launch(declared)}),
        )

    def prepare(command, declared=None):
        return asyncio.run(
            battery.prepare_battery(
                args(command, declared),
                ledger=CampaignLedger(root),
                campaign=None,
            )
        )

    return SimpleNamespace(root=root, prepare=prepare, composed=composed)


def test_a_battery_campaign_freezes_its_declared_authored_julia_scope(host):
    image = julia_image()
    install(host.root, image)
    prepared = host.prepare("run", runtime(image))
    frozen = json.loads((host.root / "campaign-manifest.json").read_bytes())
    assert frozen["runtime"] == runtime(image)
    assert prepared.manifest["runtime"] == runtime(image)
    assert host.composed[-1]["julia_image"] == image
    # A resume re-checks the frozen runtime against the same installed image.
    host.prepare("resume")
    assert host.composed[-1]["julia_image"] == image
    # Specimen: the host's record now names another image, so the frozen scope
    # no longer describes what this host would run, and the resume is refused.
    install(host.root, julia_image("e"))
    with pytest.raises(ValueError, match="authored Julia"):
        host.prepare("resume")


def test_anytime_julia_reaches_a_battery_campaign_that_declared_none(host):
    image = julia_image()
    install(host.root, image)
    host.prepare("run", runtime())
    frozen = json.loads((host.root / "campaign-manifest.json").read_bytes())
    assert frozen["runtime"] == runtime()
    assert host.composed[-1]["julia_image"] == image


def test_a_battery_campaign_without_a_host_julia_image_composes_none(host):
    host.prepare("run", runtime())
    assert host.composed[-1]["julia_image"] is None


def test_a_declared_scope_without_the_host_record_is_refused(host):
    with pytest.raises((ValueError, FileNotFoundError)):
        host.prepare("run", runtime(julia_image()))
    assert not (host.root / "campaign-manifest.json").exists()


def test_a_declared_gpu_runtime_is_refused_by_name(host):
    declared = {**runtime(), "gpu_research": [{"schema": "fixture"}]}
    with pytest.raises(ValueError, match="gpu_research"):
        host.prepare("run", declared)
    assert not (host.root / "campaign-manifest.json").exists()


def frozen_manifest(declared):
    from carbon.battery.research import objective
    from carbon.reconstruction.capability_registry import contract_digest

    return {
        "implementation": IMPLEMENTATION,
        "images": list(IMAGES),
        "objective": objective(),
        "contract_digest": contract_digest(CHALLENGE.challenge_id),
        "challenge": {"id": CHALLENGE.challenge_id, "version": CHALLENGE.version},
        "runtime": declared,
    }


def test_an_attach_accepts_exactly_the_frozen_runtime():
    image = julia_image()
    manifest = frozen_manifest(runtime(image))
    # The specimen: the identical runtime and image are accepted.
    battery.check_attached(
        manifest, implementation=IMPLEMENTATION, images=IMAGES, julia_image=image
    )
    battery.check_attached(
        frozen_manifest(runtime()),
        implementation=IMPLEMENTATION,
        images=IMAGES,
        julia_image=image,
    )
    changed = [
        # The host's image changed under a frozen scope.
        (manifest, julia_image("e")),
        # The frozen scope names Julia but the host has none.
        (manifest, None),
        # The frozen runtime gained a composition battery does not have.
        (
            frozen_manifest({**runtime(), "gpu_research": [{"schema": "fixture"}]}),
            image,
        ),
        # A research image was edited into the frozen runtime's images.
        (frozen_manifest({**runtime(), "images": [*IMAGES, image.image_id]}), image),
    ]
    for frozen, host_image in changed:
        with pytest.raises(ValueError, match="runtime|gpu_research"):
            battery.check_attached(
                frozen,
                implementation=IMPLEMENTATION,
                images=IMAGES,
                julia_image=host_image,
            )


def composition(tmp_path, julia_image_=None):
    """A real battery research composition over a real product ledger."""
    import battery_subprocess_runner as runner

    from carbon.battery.research import BatteryPractice, make_battery_research_service
    from carbon.development_session.research_control import CampaignControl

    tmp_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp_path.chmod(0o700)
    root = tmp_path / "campaign"
    ledger = CampaignLedger(root)
    ledger.freeze(
        battery.manifest_document(
            launch(runtime()),
            owner="miner-requester",
            implementation=IMPLEMENTATION,
            images=list(IMAGES),
        )
    )
    ledger.generation = CampaignControl(ledger).acquire()
    practice = BatteryPractice(
        ledger=ledger,
        owner="miner-requester",
        image=SimpleNamespace(image_id=ANALYSIS.parent_image),
        root=REPOSITORY,
        runner=runner.run,
        backend=runner.BACKEND,
    )
    return (
        make_battery_research_service(
            root=root / "research-tasks",
            ledger=ledger,
            owner="miner-requester",
            image=ANALYSIS,
            practice=practice,
            julia_image=julia_image_,
        ),
        ledger,
        practice,
    )


def test_a_battery_composition_gives_run_julia_the_host_image(tmp_path, monkeypatch):
    image = julia_image()
    composed, ledger, _ = composition(tmp_path, image)
    assert composed.executor.julia_image is image
    # What the MCP surface asks before listing and dispatching run_julia.
    julia.authorize_julia(ledger, "miner-requester", composed.executor.julia_image)
    ran = []

    def run_julia(ledger_, **kwargs):
        ran.append(kwargs)
        return {"operation": "julia-fixture", "files": {}}

    monkeypatch.setattr(julia, "run_julia", run_julia)
    result = composed.executor._workspace_action(
        SimpleNamespace(
            action="run_julia",
            arguments_json=canonical(
                {
                    "source": "println(1)",
                    "files": [],
                    "hypothesis": "fixture",
                    "expected_effect": "fixture",
                }
            ).decode(),
        ),
        "task-battery-julia-fixture",
    )
    assert ran[0]["image"] is image
    assert ran[0]["environment"] == julia.DEFAULT_ENVIRONMENT
    assert result["provenance"] == "MINER_SELF_REPORTED"
    composed.tasks.close()
    # Specimen: without a host image the same composition has no Julia to give.
    bare, ledger, _ = composition(tmp_path / "bare")
    assert bare.executor.julia_image is None
    with pytest.raises(ValueError, match="separate authored Julia image"):
        julia.authorize_julia(ledger, "miner-requester", bare.executor.julia_image)
    bare.tasks.close()


def test_julia_leaves_battery_discovery_compiler_and_practice_unchanged(tmp_path):
    from carbon.battery.compile import compile_recipe
    from carbon.battery.research import SCAFFOLD

    with_julia, _, practice_a = composition(tmp_path / "a", julia_image())
    without, _, practice_b = composition(tmp_path / "b")
    for composed, practice in ((with_julia, practice_a), (without, practice_b)):
        assert composed.executor.practice is practice
        assert type(composed.contracts) is type(without.contracts)
    assert canonical(asdict(with_julia.discovery.info.to_ref())) == canonical(
        asdict(without.discovery.info.to_ref())
    )
    assert with_julia.discovery.manifest == without.discovery.manifest
    assert with_julia.contracts.assembly.to_ref() == without.contracts.assembly.to_ref()
    assert repr(compile_recipe(SCAFFOLD)) == repr(compile_recipe(SCAFFOLD))
    with_julia.tasks.close()
    without.tasks.close()


def test_julia_leaves_the_frozen_submission_binding_unchanged():
    """What a battery submission carries - the strategy and the frozen
    contract digest - and what an attach re-checks do not depend on Julia."""
    fields = ("contract_digest", "objective", "control", "selection", "replica_policy")

    def document(declared):
        product = SimpleNamespace(
            campaign_id="cmp-battery-julia",
            agent="none",
            budget={},
            manifest_fields=lambda: {"runtime": declared},
        )
        return battery.manifest_document(
            product, owner="o", implementation=IMPLEMENTATION, images=list(IMAGES)
        )

    with_julia, without = document(runtime(julia_image())), document(runtime())
    assert with_julia["runtime"] != without["runtime"]
    assert {k: with_julia[k] for k in fields} == {k: without[k] for k in fields}
    assert with_julia["images"] == without["images"] == IMAGES


RESEARCH_IMAGE = re.compile(r"julia|gpu_research|authored_research", re.IGNORECASE)
#: The validator side: admission, rebuild (JAX training), screening and the
#: accepted recipe formats. None of it may read a research image.
EVALUATION = (
    "daemon.py",
    "deployment.py",
    "compile.py",
    "training.py",
    "recipes.py",
    "exam.py",
    "contracts.py",
)


@pytest.mark.parametrize("name", EVALUATION)
def test_battery_evaluation_never_reads_a_research_image(name):
    assert not RESEARCH_IMAGE.search((REPOSITORY / "carbon/battery" / name).read_text())


def test_the_research_image_scan_finds_julia_where_it_is_composed():
    # Specimen for the scan above: it does find the research images where the
    # campaign composes them.
    assert RESEARCH_IMAGE.search(
        (REPOSITORY / "carbon/battery/campaign.py").read_text()
    )
