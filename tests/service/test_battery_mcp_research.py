"""Battery through Carbon's shared MCP research workflow, end to end.

An agent works through the same operations every Challenge uses:
1. it discovers the battery Challenge, its interface and its public material;
2. it validates, compiles and estimates recipes;
3. it runs a real practice trial;
4. it freezes the practiced recipe and submits it;
5. Carbon rebuilds the recipe and scores it on committed private pools.

Real here:
- the signed gateway and research adapter;
- the durable task provider and the campaign ledger;
- recipe compilation and JAX training on public TRAIN;
- exam scoring, the seed journal and the shadow pool.

Fixtures here:
- chain registration and signing, as in the Burgers interoperability tests;
- the practice runner, a subprocess stand-in for the Docker carrier. Its
  backend is reported as `SUBPROCESS_TEST_ONLY_NOT_ISOLATED`.

This is interoperability and engineering evidence, not scientific or
security qualification.
"""

from __future__ import annotations

import asyncio
import base64
import itertools
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPOSITORY), str(REPOSITORY / "tests" / "cpu")]

from test_standard_mcp_cli import (
    CAMPAIGN,
    FixtureSigner,
    fixture_connection,
    private_write,
)

from carbon import research
from carbon.battery import seeds
from carbon.battery.challenge import CHALLENGE, INPUTS
from carbon.battery.research import (
    EVALUATION_FEEDBACK_FIELDS,
    SCAFFOLD,
    objective,
)
from carbon.development_session.research_control import CampaignControl
from carbon.development_session.research_ledger import (
    PRODUCT,
    CampaignLedger,
)
from carbon.miner_mcp import standard_cli
from carbon.miner_mcp.standard import (
    ResearchToolAdapter,
    ResearchToolRequest,
)
from carbon.reconstruction import capability_registry as registry

EVIDENCE = REPOSITORY / "docs/development/evidence/exam-design-2026-09-24"
BATTERY = registry.BATTERY_CHALLENGE


def strategy(backbone, **parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": BATTERY,
        "backbone": backbone,
        "parameters": parameters,
    }


KNN = strategy("knn", neighbours=6)
SMALL_MLP = strategy("mlp", steps=120, width=32, depth=2)


def battery_campaign(root, monkeypatch):
    """A registration-admitted product campaign bound to battery."""
    from test_miner_launchpad_runner import registered

    import carbon.chain.auth
    from carbon.development_session import research_tools
    from scripts.dev.miner_launchpad.runner import PATH_FIELDS

    monkeypatch.setattr(carbon.chain.auth, "BittensorMessageSigner", FixtureSigner)
    monkeypatch.setattr(research_tools, "BittensorMessageSigner", FixtureSigner)
    root.chmod(0o700)
    campaigns = root / "campaigns"
    campaigns.mkdir(mode=0o700)
    campaign = campaigns / CAMPAIGN
    campaign.mkdir(mode=0o700)
    connection = fixture_connection(campaign)
    # The fixture clock is frozen, which caps a whole test at one rate window
    # (32 transmissions). Advance it 50 ms per transmission instead: inside the
    # snapshot's freshness window, and never faster than the real rate limit.
    from test_c08_authenticated_miner_mcp import NOW

    ticks = itertools.count(NOW, 50_000_000)
    connection.service.gateway.clock_ns = lambda: next(ticks)
    owner = asyncio.run(standard_cli._requester(connection))
    runtime = {
        "implementation": {"revision": "f" * 40},
        "images": ["fixture-cpu", "fixture-analysis"],
    }
    manifest = {
        "schema": PRODUCT,
        "authority": "C-MLP-02-D11",
        "campaign_id": "cmp-" + CAMPAIGN,
        "principal": "operator-alice",
        "owner": owner,
        "runtime": runtime,
        "admission": registered().record(),
        "agent": "none",
        "challenge": {"id": BATTERY, "version": CHALLENGE.version},
        "contract_digest": registry.contract_digest(BATTERY),
        "implementation": runtime["implementation"],
        "images": runtime["images"],
        "objective": objective(),
        "sampling": {"practice": "fixture"},
        "control": SCAFFOLD,
        "selection": {"rule": "fixture"},
        "replica_policy": {"reconstructions_per_submission": 1},
        "provider": {"agent": "none", "model_calls": 0},
    }
    ledger = CampaignLedger(campaign)
    ledger.freeze(manifest)
    private_write(campaign / "campaign-manifest.json", manifest)
    profile = {
        "schema": "carbon.launchpad.runner-profile.v2",
        "profile_id": "fixture-profile",
        "principal": "operator-alice",
        "enabled": True,
        "paths": {name: str(root / (name + ".json")) for name in PATH_FIELDS},
        "accepted_revision": runtime["implementation"]["revision"],
        "campaigns_root": str(campaigns),
        "runtime": runtime,
    }
    path = root / "profile.json"
    private_write(path, profile)
    return path, ledger, owner, connection, manifest


def adapter_for(path, ledger, owner, connection):
    import battery_subprocess_runner as runner

    from carbon.battery.campaign import compose
    from carbon.development_session.research_tools import ResearchMinerTools

    profile = standard_cli.load_profile(path, CAMPAIGN)
    control = CampaignControl(ledger)
    ledger.generation = control.acquire()
    composition, wrapper = compose(
        ledger=ledger,
        owner=owner,
        image=SimpleNamespace(image_id="fixture-cpu"),
        analysis=SimpleNamespace(image_id="fixture-analysis"),
        connection=connection,
        runner=runner.run,
        backend=runner.BACKEND,
    )
    sdk = ResearchMinerTools(
        connection=standard_cli._AdmittedConnection(
            connection, profile, ledger, control
        ),
        wrapper=wrapper,
        composition=composition,
        ledger=ledger,
        owner=owner,
    )
    return composition, wrapper, ResearchToolAdapter(sdk, principal=owner)


async def call(adapter, operation, number, **arguments):
    result = await adapter.call(
        ResearchToolRequest(operation, f"battery-e2e-{number:04d}-op", arguments)
    )
    return result.payload


def reply(payload):
    assert payload["reply"]["status"] == "OK", payload["reply"]
    return payload["reply"]["result"]


async def workspace(adapter, number, action, arguments):
    payload = await call(
        adapter,
        "start_research_task",
        number,
        kind="workspace",
        strategy=None,
        action=action,
        arguments=arguments,
        hypothesis="Read public battery material",
        expected_effect="Named public files in my workspace",
    )
    return payload["public_result"]["result"]


async def practice(adapter, number, recipe):
    started = await adapter.start_task(
        ResearchToolRequest(
            "start_research_task",
            f"battery-e2e-{number:04d}-op",
            {
                "kind": "practice",
                "strategy": recipe,
                "action": None,
                "arguments": None,
                "hypothesis": "A small recipe learns the public TRAIN set",
                "expected_effect": "Eligible on public PRACTICE with a finite score",
            },
        )
    )
    task = started.payload["terminal_task"]["task_id"]["value"]
    for _ in range(600):
        current = await adapter.observe_task(task)
        if current.payload["terminal_task"]["state"] in {"SUCCEEDED", "FAILED"}:
            return current.payload
        await asyncio.sleep(0.25)
    raise AssertionError("practice did not finish")


def deployment_config(root, repository_refs):
    """An operator's evaluation deployment over committed private batches.

    The batches are four 100-case batches of the campaign's retained private
    screening references, each with two hidden repeats, committed to a fresh
    journal under a fresh root before any submission exists.
    """
    folder = root / "evaluation"
    folder.mkdir(mode=0o700)
    private_root = seeds.PrivateRoot.create(folder / "root.bin")
    journal = seeds.SeedJournal(folder / "journal.jsonl")
    journal.commit_root(private_root, seeds.seed_pin("sha256:g", "sha256:s"))
    documents = []
    for b in range(4):
        role = f"pscreen-B0{b}"
        ids = sorted(c for c in repository_refs if c.startswith(role + "-"))[:98]
        cases = [
            (c, tuple(sorted((k, repository_refs[c]["inputs"][k]) for k in INPUTS)))
            for c in ids
        ]
        repeats = [(f"{role}-r{j}", ids[j * 40]) for j in range(2)]
        inputs = dict(cases)
        cases += [(d, inputs[o]) for d, o in repeats]
        batch = seeds.PrivateBatch(role, tuple(cases), tuple(repeats))
        journal.commit(batch, pool_version=0)
        documents.append(batch.document())
    private_write(folder / "batches.json", documents)
    references = folder / "references.jsonl"
    references.write_text(
        "".join(json.dumps(r) + "\n" for r in repository_refs.values())
    )
    references.chmod(0o600)
    config = {
        "schema": "carbon.battery.evaluation-deployment.v1",
        "private_root": str(folder / "root.bin"),
        "journal": str(folder / "journal.jsonl"),
        "batches": str(folder / "batches.json"),
        "references": str(references),
        "results": str(folder / "results.jsonl"),
    }
    private_write(folder / "deployment.json", config)
    return folder / "deployment.json", documents


@pytest.fixture(scope="module")
def screening_refs():
    refs = {}
    for line in (
        (EVIDENCE / "refs-b/out/battery_refs/records.jsonl").read_text().splitlines()
    ):
        record = json.loads(line)
        if not record.get("refined") and record["case_id"].startswith("pscreen-"):
            refs[record["case_id"]] = record
    return refs


def test_an_agent_researches_and_submits_battery_through_mcp(
    tmp_path, monkeypatch, screening_refs
):
    from carbon.battery import campaign as battery_campaign_module
    from carbon.development_session.research_campaign import (
        OperationRefused,
        freeze_candidate,
        freeze_refusal,
        submit_frozen,
    )

    path, ledger, owner, connection, manifest = battery_campaign(tmp_path, monkeypatch)
    composition, _wrapper, adapter = adapter_for(path, ledger, owner, connection)

    async def scenario():
        try:
            # Discovery: the composition serves battery and only battery.
            info = reply(await call(adapter, "get_challenge_info", 1))
            assert info["challenge_key"]["challenge_id"] == BATTERY
            manifest_reply = reply(await call(adapter, "get_interaction_manifest", 2))
            assert manifest_reply["challenge_key"]["challenge_id"] == BATTERY
            scaffold = reply(await call(adapter, "get_mock_scaffold", 3))
            assert scaffold["strategy_template"] == SCAFFOLD

            # Validate, compile and estimate: nothing charged.
            assert reply(await call(adapter, "dry_validate", 4, strategy=KNN))["valid"]
            compiled = reply(
                await call(adapter, "compile_strategy", 5, strategy=SMALL_MLP)
            )
            assert compiled["accepted"] is True
            burgers = dict(SMALL_MLP, backbone="fno")
            refused = reply(
                await call(adapter, "compile_strategy", 6, strategy=burgers)
            )
            assert refused["accepted"] is False  # no Burgers fallback
            reply(await call(adapter, "inspect_resources", 7, strategy=SMALL_MLP))
            reply(
                await call(
                    adapter, "forecast_resources", 8, strategy=SMALL_MLP, seconds=600
                )
            )
            assert ledger.status(owner=owner)["used"]["research_trials"] == 0

            # Public material through the shared workspace action.
            objective_doc = await workspace(
                adapter, 9, "public_material", {"name": "objective"}
            )
            assert objective_doc["document"]["challenge"]["id"] == BATTERY
            train = await workspace(
                adapter, 10, "public_material", {"name": "training_data"}
            )
            assert set(train["files"]) == {
                "battery-train-v1.jsonl.gz",
                "battery-ocv-table.json",
            }
            practice_files = await workspace(
                adapter, 11, "public_material", {"name": "practice_data"}
            )
            assert practice_files["cases"] == 200
            verdict = await workspace(
                adapter, 12, "check_design", {"design": {"strategy": SMALL_MLP}}
            )
            assert verdict["verdict"] == "submittable"
            assert verdict["contract"]["challenge"] == BATTERY

            # Practice: real JAX training on TRAIN, scored by Carbon on PRACTICE.
            learned = await practice(adapter, 13, SMALL_MLP)
            assert learned["terminal_task"]["state"] == "SUCCEEDED"
            feedback = learned["public_result"]["result"]
            assert feedback["provenance"] == "BATTERY_PUBLIC_PRACTICE"
            assert feedback["backend"]["kind"] == "SUBPROCESS_TEST_ONLY_NOT_ISOLATED"
            assert feedback["summary"]["n_cases"] == 200
            assert feedback["summary"]["n_failed_infra"] == 0
            assert feedback["final_exam"] is False
            # Cancelling finished work is answered, and changes nothing.
            task = learned["terminal_task"]["task_id"]["value"]
            again = await adapter.cancel_task(task)
            assert again.payload["terminal_task"]["state"] == "SUCCEEDED"
            neighbours = await practice(adapter, 14, KNN)
            assert neighbours["public_result"]["result"]["summary"]["eligible"] is True
            assert ledger.status(owner=owner)["used"]["research_trials"] == 2

            # Freeze needs a practice of the same recipe.
            root = ledger.root
            assert freeze_refusal(root, strategy("knn", neighbours=3)) == (
                "practice_result_required"
            )
            assert freeze_refusal(root, KNN) is None

            # Submission: refused, not scored, until an operator configures it.
            prepared = SimpleNamespace(
                ledger=ledger,
                owner=owner,
                agent="none",
                manifest=manifest,
                challenge=CHALLENGE,
                args=SimpleNamespace(),
            )
            await freeze_candidate(prepared, strategy=KNN, reason="practiced")
            with pytest.raises(OperationRefused) as unavailable:
                await submit_frozen(prepared)
            assert unavailable.value.code == "evaluation_unavailable"
            assert not (root / "epoch-1" / "permitted-final-feedback.json").exists()

            config, documents = deployment_config(tmp_path, screening_refs)
            prepared.args.battery_evaluation = str(config)
            monkeypatch.setattr(battery_campaign_module, "_DEPLOYMENTS", {})
            submitted = await submit_frozen(prepared)
            outcome = submitted["feedback"]["outcome"]
            assert outcome["status"] == "SCORED"
            public = outcome["result"]
            assert set(public) == set(EVALUATION_FEEDBACK_FIELDS)
            assert public["eligible"] is True and public["reward"] is False
            assert public["reconstruction"] == {
                "backend": "DIRECT_TRUSTED_PROCESS",
                "validator_path": False,
            }
            # Nothing private reached the miner: no private case, input or seed.
            text = json.dumps(submitted)
            for document in documents:
                for case in document["cases"]:
                    assert case["case_id"] not in text
            assert '"seed"' not in text
        finally:
            await adapter.shutdown_tasks()
            composition.tasks.close()

    asyncio.run(scenario())


def test_the_battery_gateway_refuses_another_challenges_request(tmp_path, monkeypatch):
    """A Burgers request never reaches battery code, and the reverse."""
    from carbon.development_session.profile import CHALLENGE as BURGERS
    from carbon.transport.models import message

    path, ledger, owner, connection, _ = battery_campaign(tmp_path, monkeypatch)
    composition, wrapper, adapter = adapter_for(path, ledger, owner, connection)
    try:

        def signed(key, request):
            snapshot = asyncio.run(connection.check_registration())
            call_ = research.ServiceCall(
                research.RESEARCH_NAMESPACE, "get_challenge_info", request
            )
            body = message(
                connection.chain_context,
                snapshot.snapshot_id,
                key,
                session="carbon-autoresearch",
                request="cross-challenge-" + key.challenge_id[:8],
                tool=research.RESEARCH_NAMESPACE,
                fields={
                    "call_base64": base64.b64encode(
                        research.canonical_bytes(call_)
                    ).decode("ascii")
                },
            )
            return body, FixtureSigner(None).sign(body)

        body, headers = signed(BURGERS, research.GetChallengeInfoRequest(BURGERS))
        with pytest.raises(Exception):  # noqa: B017 - refused before any provider
            asyncio.run(wrapper.call(body, headers))
        # The Burgers gateway refuses battery in the same way.
        from carbon.miner_mcp.research import AuthenticatedResearchService

        burgers_wrapper = AuthenticatedResearchService(
            connection.service.gateway, {owner: composition.service}
        )
        body, headers = signed(CHALLENGE, research.GetChallengeInfoRequest(CHALLENGE))
        with pytest.raises(Exception):  # noqa: B017
            asyncio.run(burgers_wrapper.call(body, headers))
    finally:
        asyncio.run(adapter.shutdown_tasks())
        composition.tasks.close()
