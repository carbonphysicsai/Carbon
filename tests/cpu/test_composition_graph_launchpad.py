"""Composition-bound CLI, G4 and frozen transport; no host/chain authority.

Only the private in-process check fixture permits positive wiring controls.
The default unknown-check child refuses in test_composition_required_checks.
"""

import asyncio
import copy
import json

import pytest
import test_launchpad_level4_parts as transport
from composition_check_fixtures import accepted_fixture_checks
from test_battery_composed_graph import PARTS, graph_input, loss_graph_input, strategy

from carbon.battery import campaign, intake_client
from carbon.battery.level4_parts import Level4Parts, split
from carbon.development_ladder import operate
from carbon.development_session import construction_level as cl
from carbon.development_session.research_campaign import OperationRefused
from carbon.level4 import staging
from carbon.reconstruction import development_composition as dc
from carbon.reconstruction import development_level_cli as cli

__all__ = ["accepted_fixture_checks", "graph_input", "loss_graph_input"]


def binding():
    return cl.with_target(
        cl.resolve_composition(strategy()["challenge_id"]), transport.URL
    )


def envelope(value):
    raw, files = staging.from_workspace(value[1], value[0])
    return staging.envelope(raw, files)


def test_authenticated_cli_directory_and_real_ladder_parts_keep_every_document(
    tmp_path, monkeypatch, graph_input, accepted_fixture_checks
):
    found = binding()
    requested = strategy(composition_graphs=graph_input[0], **PARTS)
    raw, files = staging.from_workspace(graph_input[1], graph_input[0])
    directory = tmp_path / "lowered"
    staging.write_directory(directory, raw, files)
    request = {
        "op": "level4",
        "challenge": found["challenge"],
        "composition_digest": found["digest"],
        "strategy": requested,
        "directory": str(directory),
    }
    checked = cli.answer(request)
    assert checked["ok"] and checked["variant_digest"] == found["digest"]
    assert staging.from_envelope(checked["envelope"]) == (graph_input[0], raw, files)
    parts = Level4Parts(tmp_path / "parts", [transport.HOTKEY])
    chunks = split(json.dumps(checked["envelope"]).encode("utf-8"))
    held = {}
    with pytest.raises(ValueError, match="level4_envelope_incomplete"):
        operate.compile_variant(requested, found["digest"], parts, held)
    assert not held
    for i, chunk in enumerate(chunks):
        parts.put(transport.HOTKEY, graph_input[0], i, len(chunks), chunk)
    compiled = operate.compile_variant(requested, found["digest"], parts, held)
    assert compiled.development == dc.compile(requested).development
    assert held[graph_input[0]] == (raw, files)
    for change in ("batch", "missing", "digest"):
        changed = copy.deepcopy(request)
        if change == "batch":
            changed["strategy"]["parameters"]["batch_size"] = 256
        elif change == "missing":
            changed["directory"] = str(tmp_path / "absent")
        else:
            changed["composition_digest"] = "sha256:" + "0" * 64
        refused = cli.answer(changed)
        assert refused["ok"] is False, change


def test_actual_dual_loss_graph_refusal_survives_composition_cli(
    tmp_path, loss_graph_input, accepted_fixture_checks
):
    found = binding()
    raw, files = staging.from_workspace(loss_graph_input[1], loss_graph_input[0])
    directory = tmp_path / "dual"
    staging.write_directory(directory, raw, files)
    result = cli.answer(
        {
            "op": "level4",
            "challenge": found["challenge"],
            "composition_digest": found["digest"],
            "strategy": strategy(
                composition_graphs=loss_graph_input[0],
                loss_expressions=PARTS["loss_expressions"],
            ),
            "directory": str(directory),
        }
    )
    assert result["code"] == "construction_rebuild_unavailable"
    assert {i["path"] for i in result["issues"]} == {
        "/parameters/loss_expressions",
        "/parameters/composition_graphs",
    }


@pytest.mark.parametrize("label", [None, 0, 1, 4])
def test_campaign_routes_actual_frozen_graph_with_any_descriptive_label(
    tmp_path, monkeypatch, graph_input, label
):
    found = binding()
    record = {
        "contract_digest": found["digest"],
        "construction_level": {**found, "level": label},
        "strategy": strategy(composition_graphs=graph_input[0], muon_spectral=True),
    }
    folder = tmp_path / "epoch-1"
    folder.mkdir()
    cl.write_envelope(folder, envelope(graph_input))
    frozen = (folder / cl.LEVEL4_ENVELOPE).read_bytes()
    monkeypatch.setattr(
        intake_client,
        "read_intake",
        lambda *a, **kw: transport._facts(found, transport.PART_TOOLS),
    )
    sent = []

    def submit(*args, **kwargs):
        sent.append(kwargs)
        return 200, {"submission_id": "sub-1", "state": "SCORED"}, "sub-1"

    monkeypatch.setattr(campaign, "submit_through_intake", submit)
    asyncio.run(
        campaign._evaluate_through_intake(
            transport._prepared(tmp_path, found), 1, record, transport.URL
        )
    )
    assert len(sent) == 1 and sent[0]["level4_envelope"] == frozen
    assert sent[0]["strategy"] == record["strategy"]
    # Loss of required transport or malformed signed envelope stops before send.
    sent.clear()
    monkeypatch.setattr(
        intake_client, "read_intake", lambda *a, **kw: transport._facts(found)
    )
    with pytest.raises(OperationRefused, match="level4_envelope_transport_unavailable"):
        asyncio.run(
            campaign._evaluate_through_intake(
                transport._prepared(tmp_path, found), 1, record, transport.URL
            )
        )
    assert not sent
    (folder / cl.LEVEL4_ENVELOPE).write_bytes(b"{}")
    with pytest.raises(OperationRefused):
        asyncio.run(
            campaign._evaluate_through_intake(
                transport._prepared(tmp_path, found), 1, record, transport.URL
            )
        )
    assert not sent


def test_nongraph_composition_needs_no_graph_transport_and_unbound_never_sends(
    tmp_path, monkeypatch
):
    found = binding()
    record = {
        "contract_digest": found["digest"],
        "construction_level": found,
        "strategy": strategy(muon_spectral=True),
    }
    monkeypatch.setattr(
        campaign, "_level4_envelope", lambda *a: pytest.fail("nongraph envelope read")
    )
    monkeypatch.setattr(
        campaign, "_carries_level4", lambda *a: pytest.fail("nongraph transport read")
    )
    sent = []

    def submit(*args, **kwargs):
        sent.append(kwargs)
        return 200, {"submission_id": "sub-1", "state": "SCORED"}, "sub-1"

    monkeypatch.setattr(campaign, "submit_through_intake", submit)
    asyncio.run(
        campaign._evaluate_through_intake(
            transport._prepared(tmp_path, found), 1, record, transport.URL
        )
    )
    assert sent[0]["level4_envelope"] is None
    sent.clear()
    record["contract_digest"] = "sha256:" + "0" * 64
    with pytest.raises(OperationRefused, match="level_not_registered"):
        asyncio.run(
            campaign._evaluate_through_intake(
                transport._prepared(tmp_path, found), 1, record, transport.URL
            )
        )
    assert not sent
