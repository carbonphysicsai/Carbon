"""Demand records and the public roadmap.

Claims tested: demand counts distinct miners per research-only capability, so
repeating a request cannot inflate it; nothing but a research-only registry id
can be counted; unrecognized text and raw principals are never stored; the
roadmap partitions the registry and says "not collected" rather than zero when
a host keeps no demand; and the whole path runs through the real workspace
executor. Each absence is paired with the same check finding what is present.
"""

import pytest

from carbon.development_session.capability_demand import (
    DemandStore,
    demanded,
    public_roadmap,
)
from carbon.development_session.design_check import check_design
from carbon.reconstruction.capability_registry import REGISTRY

LION, PRECISION = "optimizer.lion", "inference.precision"


def store(tmp_path):
    return DemandStore(tmp_path / "demand.sqlite")


def test_each_miner_counts_once_per_capability(tmp_path):
    demand = store(tmp_path)
    for _ in range(5):
        demand.record("miner-a", [LION])
    assert demand.counts()["by_capability"] == {LION: 1}
    # Specimen: a second miner does count.
    demand.record("miner-b", [LION, PRECISION])
    assert demand.counts()["by_capability"] == {LION: 2, PRECISION: 1}


@pytest.mark.parametrize(
    "capability",
    [
        "architecture.heads",  # rebuildable already
        "model_family.pretrained_weights",  # excluded
        "optimizer.made_up",  # not a registry id
    ],
)
def test_only_a_research_only_registry_id_can_be_counted(tmp_path, capability):
    demand = store(tmp_path)
    assert demand.record("miner-a", [capability]) == []
    assert demand.counts()["by_capability"] == {}
    assert demand.record("miner-a", [LION]) == [LION]


def test_malformed_demand_is_refused(tmp_path):
    demand = store(tmp_path)
    for bad in ("optimizer.lion", [1], None):
        with pytest.raises(ValueError):
            demand.record("miner-a", bad)
    with pytest.raises(ValueError):
        demand.record("", [LION])


def test_neither_unrecognized_text_nor_a_raw_principal_is_stored(tmp_path):
    marker = "MINER-PRIVATE-NOTE-9c21"
    owner = "5FminerHotkeyExample"
    demand = store(tmp_path)
    ids, unrecognized = demanded(
        check_design(
            {
                "strategy": {
                    "schema_version": "1.0",
                    "challenge_id": "burgers-dynamics-v1",
                    "backbone": "fno",
                    "parameters": {marker: 1},
                },
                "capabilities": [marker, LION],
            }
        )
    )
    demand.record(owner, ids, unrecognized=unrecognized)
    stored = (tmp_path / "demand.sqlite").read_bytes()
    assert marker.encode() not in stored
    assert owner.encode() not in stored
    # Specimen: the store does hold what it records, readable in the same bytes.
    assert LION.encode() in stored
    assert demand.counts() == {"by_capability": {LION: 1}, "unrecognized": 1}
    assert (tmp_path / "demand.sqlite").stat().st_mode & 0o777 == 0o600


def test_the_roadmap_partitions_the_registry():
    roadmap = public_roadmap()
    sections = roadmap["available"], roadmap["roadmap"], roadmap["not_planned"]
    ids = [item["id"] for section in sections for item in section]
    assert sorted(ids) == sorted(c.capability_id for c in REGISTRY)
    by_id = {item["id"]: item for item in roadmap["roadmap"]}
    assert by_id[PRECISION]["blocked_on"] == "owner_decision"
    assert by_id[PRECISION]["trigger"] == "new_comparison_or_resource_regime"
    assert by_id[LION]["trigger"] is None


def test_no_store_means_not_collected_never_zero(tmp_path):
    uncollected = public_roadmap()
    assert uncollected["demand"] == "not collected on this host"
    assert uncollected["unrecognized"] is None
    assert {item["demand"] for item in uncollected["roadmap"]} == {None}
    # Specimen: with a store, nobody asking is a real zero.
    demand = store(tmp_path)
    demand.record("miner-a", [LION])
    collected = {i["id"]: i["demand"] for i in public_roadmap(demand)["roadmap"]}
    assert collected[LION] == 1 and collected[PRECISION] == 0


def test_demand_and_roadmap_run_through_the_real_workspace_executor(tmp_path):
    from test_cw1_research_tasks import compose, request

    from carbon import research

    f, p, e = compose(tmp_path)
    e.demand = store(tmp_path)

    def run(action, args, index):
        task = p.start_research_task(request(f, action, args, index)).task
        done = p.run_queued_task(task.task_id)
        return done, e.public_result(done)

    design = {
        "strategy": {
            "schema_version": "1.0",
            "challenge_id": "burgers-dynamics-v1",
            "backbone": "unet1d",
            "parameters": {},
        },
        "capabilities": [LION],
    }
    _, checked = run("check_design", {"design": design}, 0)
    assert checked["result"]["verdict"] == "not_yet_rebuildable"
    fields = {
        "purpose": "p",
        "operation": "o",
        "hypothesis": "h",
        "public_evidence": "e",
        "reason": "missing_adapter",
        "expected_benefit": "b",
        "estimated_cost": "c",
        "minimal_safe_design": "d",
        "verification": "v",
    }
    run("capability_request", {"request": {**fields, "capability": PRECISION}}, 1)
    _, roadmap = run("roadmap", {}, 2)
    demand = {i["id"]: i["demand"] for i in roadmap["result"]["roadmap"]}
    assert demand[LION] == 1
    assert demand["model_family.unet1d"] == 1
    assert demand[PRECISION] == 1
    # A request naming something that is not a registry id is refused.
    refused, _ = run(
        "capability_request", {"request": {**fields, "capability": "made.up"}}, 3
    )
    assert refused.state is not research.ResearchTaskState.SUCCEEDED
    p.close()
