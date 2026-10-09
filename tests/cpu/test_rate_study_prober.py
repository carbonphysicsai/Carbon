"""SUBMISSION-RATE-STUDY-01's scripted prober and G-sealed probe tool (run
sheet D.2, D.3).

Claims tested:
- deterministic: two runs against the same synthetic route propose the same
  sequence;
- never a repeat: 144 informative answers give 144 distinct strategies (the
  route never rescores a repeat, plan O7c);
- S-revealed climbs a synthetic batch score; S-sealed reads the allow-list
  state only, and a revealed view without its score is refused;
- WINDOW_USED / UNAVAILABLE visit nothing, so the same proposal comes back;
- the probe tool on the prober's own history proposes what the prober would,
  and ignores a session's own off-ladder designs;
- every proposal compiles under battery's construction contract;
- the module reads nothing: no file, network, clock or randomness.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from carbon.agent_campaign.graphite import study_prober as sp

MODULE = Path(sp.__file__)


def synthetic_batch_score(strategy):
    """A bowl over the ladder: best at steps 15000, width 512, depth 4."""
    p = strategy["parameters"]
    target = {"steps": 15000, "width": 512, "depth": 4, "learning_rate": 0.002}
    return sum(
        (sp.COORDINATES[i][1].index(p[name]) - sp.COORDINATES[i][1].index(target[name]))
        ** 2
        for i, (name, _ladder) in enumerate(sp.COORDINATES)
        if name in target
    )


def run(mode, n, view_of):
    prober = sp.Prober(mode)
    proposals = []
    for _ in range(n):
        strategy = prober.propose()
        proposals.append(strategy)
        prober.observe(view_of(strategy))
    return prober, proposals


def revealed(strategy):
    return {"state": "SCORED", "batch_score": float(synthetic_batch_score(strategy))}


def sealed(strategy):
    return {"state": "SCORED", "refusal_codes": [], "digest": "sha256:" + "0" * 64}


@pytest.mark.parametrize(
    ("mode", "view"), [(sp.SEALED, sealed), (sp.REVEALED, revealed)]
)
def test_deterministic_and_never_a_repeat(mode, view):
    _, a = run(mode, 144, view)
    _, b = run(mode, 144, view)
    assert a == b
    digests = [sp.strategy_digest(s) for s in a]
    assert len(set(digests)) == 144
    assert a[0] == sp.strategy(sp.START)


def test_revealed_climbs_the_batch_score():
    prober, _ = run(sp.REVEALED, 60, revealed)
    scores = [-sp.objective(sp.REVEALED, e["view"]) for e in prober.history]
    assert min(scores) == 0.0 < scores[0]


def test_sealed_reads_the_state_only():
    assert sp.objective(sp.SEALED, {"state": "SCORED", "batch_score": 9.0}) == 1.0
    assert sp.objective(sp.SEALED, {"state": "NOT_SCORED"}) == 0.0
    with pytest.raises(sp.ProberRefused) as refused:
        sp.objective(sp.REVEALED, {"state": "SCORED"})
    assert refused.value.code == "revealed_view_without_batch_score"
    for bad in (None, {}, {"state": "LEAKED"}):
        with pytest.raises(sp.ProberRefused):
            sp.objective(sp.SEALED, bad)


@pytest.mark.parametrize("state", sp.NO_INFORMATION)
def test_no_information_repeats_the_proposal(state):
    prober = sp.Prober(sp.REVEALED)
    first = prober.propose()
    assert prober.observe({"state": state}) is None
    assert prober.propose() == first


def test_the_probe_tool_replays_the_prober_and_ignores_own_designs():
    prober, _ = run(sp.REVEALED, 30, revealed)
    assert sp.next_probe(sp.REVEALED, prober.history) == prober.propose()
    own = {
        "strategy": {
            "schema_version": "1.0",
            "challenge_id": sp.CHALLENGE_ID,
            "backbone": "deeponet",
            "parameters": {"steps": 6000, "width": 128, "deeponet_depth": 3},
        },
        "view": {"state": "SCORED", "batch_score": -100.0},
    }
    mixed = prober.history[:10] + [own] + prober.history[10:]
    assert sp.next_probe(sp.REVEALED, mixed) == prober.propose()
    assert sp.next_probe(sp.REVEALED, []) == sp.strategy(sp.START)
    for bad in (None, [{"strategy": {}}], [1]):
        with pytest.raises(sp.ProberRefused):
            sp.next_probe(sp.REVEALED, bad)


def test_every_proposal_compiles():
    from carbon.battery.compile import compile_recipe

    _, proposals = run(sp.REVEALED, 40, revealed)
    for strategy in proposals:
        compile_recipe(strategy)


def test_the_module_reads_nothing():
    tree = ast.parse(MODULE.read_text())
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported <= {"__future__", "hashlib", "json", "math", "annotations"}
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "open" not in calls
