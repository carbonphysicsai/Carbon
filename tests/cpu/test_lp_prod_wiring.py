"""Cross-workstream wiring of the Launchpad production work (OWNER-LAUNCHPAD-PROD-01).

Integration of slices A to G found handoffs that were never wired. These
tests hold the Python side of the repairs; the page's side is driven in Node
by tests/cpu/control_center_page_check.cjs (test_control_center_live_page):

- C -> F: the Control Center prints its one-click session link only once the
  page declares it reads the fragment; the page now does;
- E -> B: the MCP setup tools carry what setup says an install changed: a
  stale compute check with why and the step that clears it, where each
  Challenge's candidates are evaluated, an intake an update set aside (to
  name again at Review), and Review's warnings;
- D -> A: a new battery campaign of Carbon's agent freezes the v2 research
  tools rule in its run plan, so its tools, its reads and its first
  observation follow it; a plan frozen earlier names no rule and keeps the
  historical tools, reads and observation byte for byte; a miner's MCP
  session attached to either campaign is described the tools it froze.

No chain, provider, signer, container or intake is reached: the checks are
the existing fixtures, and the checkout's revision is patched.
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

# --- C -> F: the session link ------------------------------------------------------


def test_the_page_declares_it_reads_the_session_link():
    """LP-PROD-C D14: the link is printed only once the page's own head says
    it reads `#token=` once and removes it. The page served now does."""
    from scripts.dev.miner_launchpad import controller

    assert controller.session_link_supported()
    page = Path(controller.__file__).with_name("index.html").read_text()
    head = page.split("</head>", 1)[0]
    assert controller.SESSION_LINK_DECLARATION.search(head)
    # The pasted token stays the fallback, under the label the installer's
    # hint and the miner know.
    assert '<label for="token">Local session token</label>' in page


# --- E -> B: what setup says an install changed, at the MCP door --------------------


@pytest.fixture
def head(monkeypatch):
    """The checkout's revision, as setup reads it."""
    from test_miner_launchpad_environment_setup import REVISION

    from scripts.dev.miner_launchpad import environment_setup as environment

    current = {"revision": REVISION}
    monkeypatch.setattr(
        environment, "checkout_revision", lambda repo=None: current["revision"]
    )
    return current


def _door(setup):
    """Setup's MCP door over `setup`, as `carbon-mcp` installs it."""
    from carbon.miner_mcp.mcp_setup import SetupDoor
    from carbon.miner_mcp.open_tier import create_open_tier_server

    server = create_open_tier_server()
    SetupDoor(server, setup).install()
    return server


def _call(server, name, arguments=None):
    result = asyncio.run(server.call_tool(name, arguments or {}))
    assert not result.is_error, result
    return result.structured_content


def _setup(tmp_path, name, checks):
    from test_miner_launchpad_environment_setup import Onboarding, completed

    from scripts.dev.miner_launchpad.environment_setup import EnvironmentSetup

    base = tmp_path / name
    (base / "state").mkdir(parents=True, mode=0o700)
    setup = EnvironmentSetup(base / "state", onboarding=Onboarding(), checks=checks)
    made = completed(base, setup)
    return base, setup, made


def test_status_names_a_stale_compute_check_and_the_installers_update(tmp_path, head):
    """A checkout moved after the install: checking again would be stale
    again, so status says why and that the installer's update clears it,
    rather than sending an agent round the compute check."""
    from test_miner_setup_after_install import NEW, REVISION, Reinstalled

    from carbon.miner_mcp.mcp_setup import STATUS
    from scripts.dev.miner_launchpad import environment_setup as environment

    _, setup, _ = _setup(tmp_path, "stale", Reinstalled(REVISION))
    environment.write_private(
        setup.installation_path,
        json.dumps(
            {
                "schema": environment.INSTALLATION_SCHEMA,
                "revision": REVISION,
                "images": {},
            }
        ).encode(),
    )
    server = _door(setup)
    assert _call(server, STATUS)["payload"]["next"]["step"] == "review"
    head["revision"] = NEW
    status = _call(server, STATUS)["payload"]
    compute = setup.state()["steps"]["compute"]
    row = next(r for r in status["steps"] if r["id"] == "compute")
    assert row["missing"] == ["compute_check_is_stale"]
    entry = status["next"]
    assert entry["step"] == "compute" and entry["missing"] == ["compute_check_is_stale"]
    assert entry["stale"] == compute["stale"] and entry["stale"]
    assert entry["next_step"] == environment.REINSTALL_STEP == compute["next_step"]
    # The specimen: a check that is not stale carries neither.
    head["revision"] = REVISION
    assert "stale" not in _call(server, STATUS)["payload"]["next"]


def test_status_and_review_say_where_candidates_are_evaluated(
    tmp_path, head, monkeypatch
):
    """None published: status carries setup's own evaluation state, Review
    names the Challenge as its intake option, and Review's result warns that
    the profile cannot submit there. Published: status names Carbon's
    endpoint and its receiver, for reference."""
    from test_miner_setup_after_install import URL, Reinstalled, entry, publish

    from carbon.miner_mcp.mcp_setup import STATUS
    from scripts.dev.miner_launchpad import environment_setup as environment

    challenges = environment.intake_challenges()
    challenge = challenges[0]
    publish(tmp_path, monkeypatch, [])
    _, setup, _ = _setup(tmp_path, "none", Reinstalled())
    server = _door(setup)
    status = _call(server, STATUS)["payload"]
    assert status["evaluation"] == json.loads(
        json.dumps(setup.state()["steps"]["evaluation"])
    )
    assert status["evaluation"]["ready"] is False
    item = status["evaluation"]["challenges"][0]
    assert (item["id"], item["intake"]) == (challenge["id"], None)
    assert item["note"] == environment.NO_ENDPOINT.format(title=challenge["title"])
    assert status["next"]["step"] == "review"
    assert status["next"]["options"] == {"intakes": [c["id"] for c in challenges]}
    reviewed = _call(server, "carbon_setup_review", {"confirm": True})["payload"]
    assert reviewed["warnings"] == [
        {
            "code": "no_evaluation_endpoint",
            "challenge": c["id"],
            "message": environment.NO_ENDPOINT.format(title=c["title"]),
        }
        for c in challenges
    ]
    # Launch is next, and status still says where nothing can be submitted.
    after = _call(server, STATUS)["payload"]
    assert after["next"]["step"] == "launch"
    assert after["evaluation"]["ready"] is False

    publish(tmp_path, monkeypatch, [entry(challenge["id"])])
    _, setup, _ = _setup(tmp_path, "published", Reinstalled())
    server = _door(setup)
    _call(server, "carbon_setup_review", {"confirm": True})
    item = _call(server, STATUS)["payload"]["evaluation"]["challenges"][0]
    assert (item["intake"], item["source"]) == (URL, "published")
    assert item["receiver_hotkey_note"] == environment.RECEIVER_NOTE


def test_an_intake_set_aside_by_an_update_is_named_again_through_status(
    tmp_path, head, monkeypatch
):
    """An update set a remote miner's compute check and profile aside and
    kept their own intake: status shows the set-aside check, then offers the
    intake at Review as `name_again`, and Review sent it keeps it."""
    from test_miner_setup_after_install import (
        HOTKEY,
        NEW,
        OWN,
        Intakes,
        own_review,
        profile,
        publish,
        rebuild,
    )

    from carbon.miner_mcp.mcp_setup import STATUS
    from scripts.dev.miner_launchpad import environment_setup as environment

    challenge = environment.intake_challenges()[0]
    publish(tmp_path, monkeypatch, [])
    checks = Intakes()
    base, setup, _ = _setup(tmp_path, "set-aside", checks)
    setup.review(own_review(challenge))
    record = setup._record()
    record["compute"]["choice"] = environment.REMOTE
    setup._save(record)
    head["revision"] = checks.revision = NEW
    worker, analysis = rebuild(base, base / "state", NEW)
    setup.after_install()
    server = _door(setup)
    status = _call(server, STATUS)["payload"]
    assert status["next"]["step"] == "compute"
    assert status["next"]["set_aside"] == (
        setup.state()["steps"]["compute"]["set_aside"]["reasons"]
    )
    assert status["evaluation"]["challenges"][0]["set_aside_intake"] == OWN
    # Checked again on this machine: Review is next, with the intake to keep.
    _call(
        server,
        "carbon_setup_compute",
        {
            "choice": environment.LOCAL_CPU,
            "image_manifest": str(worker),
            "analysis_image_manifest": str(analysis),
        },
    )
    entry = _call(server, STATUS)["payload"]["next"]
    assert entry["step"] == "review"
    assert entry["options"]["name_again"] == {challenge["id"]: OWN}
    # With the receiver its Review pinned (LAUNCHPAD-ACCEPT-03).
    assert entry["options"]["receivers_again"] == {challenge["id"]: HOTKEY}
    _call(
        server,
        "carbon_setup_review",
        {
            "confirm": True,
            "intakes": entry["options"]["name_again"],
            "receivers": entry["options"]["receivers_again"],
        },
    )
    assert profile(setup)["intakes"] == {challenge["id"]: OWN}
    assert profile(setup)["receivers"] == {challenge["id"]: HOTKEY}
    item = _call(server, STATUS)["payload"]["evaluation"]["challenges"][0]
    assert (item["intake"], item["source"]) == (OWN, "yours")
    assert "set_aside_intake" not in item


def test_both_doors_pin_an_own_intakes_receiver_the_same(tmp_path, head, monkeypatch):
    """LAUNCHPAD-ACCEPT-03, door parity: Review over MCP and over the
    browser's door take the same receiver fields, refuse the same codes with
    the same field and next step, and pin the same receiver."""
    from mcp.server.mcpserver.exceptions import ToolError
    from test_miner_setup_after_install import HOTKEY, OWN, Intakes, profile, publish

    from scripts.dev.miner_launchpad import environment_setup as environment
    from scripts.dev.miner_launchpad.setup_operations import HTTP, MCP, perform, schema

    challenge = environment.intake_challenges()[0]
    publish(tmp_path, monkeypatch, [])
    for door in (HTTP, MCP):
        fields = schema("review", door)["properties"]
        assert {"intakes", "receiver_hotkey", "receivers"} <= set(fields)
    other = "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
    for code, request in (
        ("receiver_hotkey_required", {}),
        ("intake_receiver_mismatch", {"receiver_hotkey": other}),
    ):
        request = {"confirm": True, "intakes": {challenge["id"]: OWN}, **request}
        _, setup, _ = _setup(tmp_path, "browser-" + code, Intakes())
        with pytest.raises(environment.SetupRefused) as browser:
            perform(setup, "review", request, door=HTTP)
        _, setup, _ = _setup(tmp_path, "mcp-" + code, Intakes())
        with pytest.raises(ToolError) as raised:
            asyncio.run(_door(setup).call_tool("carbon_setup_review", request))
        message = str(raised.value)
        answered = json.loads(message[message.index("{") :])
        assert answered == {
            "error": code,
            "field": "receiver_hotkey",
            "next_step": browser.value.next_step,
        }
        assert browser.value.code == code and browser.value.field == "receiver_hotkey"
    _, setup, _ = _setup(tmp_path, "mcp-pinned", Intakes())
    _call(
        _door(setup),
        "carbon_setup_review",
        {"confirm": True, "intakes": {challenge["id"]: OWN}, "receiver_hotkey": HOTKEY},
    )
    assert profile(setup)["receivers"] == {challenge["id"]: HOTKEY}


# --- D -> A: the research tools rule, frozen for new battery campaigns ---------------


BUDGET = {"ceilings": {"provider_attempts": 10, "provider_nanodollars": 10**9}}


def _read(plan, path, body):
    """One read_file through the research executor of a campaign whose run
    plan is `plan`."""
    from test_lp_prod_research_tools import ledger

    from carbon.development_session.profile import canonical
    from carbon.development_session.research_tasks import PublicResearchExecutor

    executor = PublicResearchExecutor(
        ledger=ledger(path, provider=plan),
        owner="alice",
        image=SimpleNamespace(),
        public_material=lambda *a: None,
        practice=lambda *a: None,
    )
    executor.workspace.put("notes.txt", body)
    spec = SimpleNamespace(
        action="read_file",
        arguments_json=canonical(
            {"count": 4096, "name": "notes.txt", "offset": 0}
        ).decode(),
    )
    return executor._workspace_action(spec, "rtsk_" + "4" * 64)


def test_a_new_battery_plan_freezes_the_tools_rule_and_an_old_one_replays(tmp_path):
    from test_lp_prod_research_tools import (
        HISTORICAL_TOOLS_DIGEST,
        battery_composition,
    )

    from carbon.battery import campaign
    from carbon.development_session.profile import canonical, digest
    from carbon.development_session.research_tools import (
        ARGUMENT_NORMALISATION_V2,
        TOOLS,
        TOOLS_RULE,
        TOOLS_V2,
        ResearchMinerTools,
        frozen_tools_rule,
        tools_for_sdk,
    )

    plan = campaign.provider_plan("autonomous", BUDGET)
    assert plan["research_tools"] == TOOLS_RULE
    assert frozen_tools_rule({"provider": plan}) == TOOLS_RULE
    # A plan frozen before this change: the same plan with no rule.
    old = {key: value for key, value in plan.items() if key != "research_tools"}
    assert frozen_tools_rule({"provider": old}) is None
    # A miner-driven plan is unchanged: Carbon's agent does not run there.
    # Since AGENT-DOOR-USABILITY-01 it freezes argument-normalisation.v2.
    assert campaign.provider_plan("none", None) == {
        "agent": "none",
        "model_calls": 0,
        "argument_normalisation": ARGUMENT_NORMALISATION_V2,
    }

    body = b"loss = 0.25\nstep = 42\n" * 8
    for name, frozen in (("new", plan), ("old", old)):
        meter, composition, prepared = battery_composition(tmp_path / name, frozen)
        try:
            sdk = ResearchMinerTools(
                connection=None,
                wrapper=None,
                composition=composition,
                ledger=meter,
                owner="alice",
            )
            observation = campaign.agent_observation(prepared, 1, None)
            assert observation["run_plan"] == json.loads(json.dumps(frozen))
            if frozen is plan:
                # The v2 tools, and the research environment, wake up.
                assert tools_for_sdk(sdk) is TOOLS_V2
                assert observation["research_environment"]["rule"] == TOOLS_RULE
            else:
                # Replays as it was frozen: the historical tools, byte for
                # byte, and the observation without the environment.
                assert tools_for_sdk(sdk) is TOOLS
                assert digest(canonical(TOOLS)) == HISTORICAL_TOOLS_DIGEST
                assert "research_environment" not in observation
                assert observation["unsupported_capabilities"]["read_with"] == (
                    "workspace public_material {name: capabilities} or roadmap {}"
                )
        finally:
            composition.tasks.close()
    # Reads follow the frozen rule: text once under v2, base64 alone before.
    new_read = _read(plan, tmp_path / "read-new", body)
    assert (new_read["content_utf8"], new_read["content_base64"]) == (
        body.decode(),
        None,
    )
    old_read = _read(old, tmp_path / "read-old", body)
    assert set(old_read) == {"name", "digest", "bytes", "offset", "content_base64"}
    assert base64.b64decode(old_read["content_base64"]) == body


def test_an_mcp_session_is_described_the_tools_its_campaign_froze(tmp_path):
    """Review repair: a miner's MCP session attached to a new battery campaign
    of Carbon's agent (allowed on a paused one, LP-PROD-C D12) was described
    the historical tools - read_file `count<=4096`, base64 - while its reads
    returned the v2 rule's text once, up to 8192. `sdk_tools` now follows the
    rule the campaign froze, with or without authored Julia; a campaign
    frozen before the rule is still described by `TOOLS`, byte for byte."""
    from test_lp_prod_research_tools import battery_composition

    from carbon.battery import campaign
    from carbon.development_session.research_tools import (
        PREFIX,
        TOOLS,
        TOOLS_V2,
        ResearchMinerTools,
    )
    from carbon.miner_mcp.standard import ResearchToolAdapter
    from carbon.miner_mcp.standard_server import _create_server

    plan = campaign.provider_plan("autonomous", BUDGET)
    old = {key: value for key, value in plan.items() if key != "research_tools"}
    for name, frozen, tools, read in (
        ("new", plan, TOOLS_V2, "count: 1 to 8192"),
        ("old", old, TOOLS, "count<=4096"),
    ):
        meter, composition, _ = battery_composition(tmp_path / name, frozen)
        try:
            sdk = ResearchMinerTools(
                connection=None,
                wrapper=None,
                composition=composition,
                ledger=meter,
                owner="alice",
            )
            adapter = ResearchToolAdapter(sdk, principal="alice")
            assert adapter.authored_julia_available is False
            assert adapter.sdk_tools is tools, name
            listed = {
                tool.name: tool.description
                for tool in asyncio.run(_create_server(adapter).list_tools())
            }
            described = listed[PREFIX + "start_research_task"]
            assert read in described, name
            assert ("content_utf8" in described) is (tools is TOOLS_V2), name
        finally:
            composition.tasks.close()
