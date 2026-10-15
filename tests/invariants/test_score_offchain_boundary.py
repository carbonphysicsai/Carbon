"""Static score/chain source boundary with a deliberate failing control."""

from pathlib import Path

import pytest

from scripts.dev.score_offchain_audit import PROVEN_SCORE_ROOTS, audit

pytestmark = pytest.mark.invariant
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("module", PROVEN_SCORE_ROOTS)
def test_closed_score_kernel_imports_cannot_reach_chain_or_rewards(module):
    evidence = audit(ROOT, roots=(module,))
    assert evidence["forbidden_reachable"] == []
    assert evidence["missing_local_modules"] == []
    assert evidence["dynamic_import_calls"] == []


def test_guard_fails_if_a_chain_read_is_added_to_scoring_source():
    module = "carbon.scoring.engine"
    source = (ROOT / "carbon/scoring/engine.py").read_text(encoding="utf-8")
    evidence = audit(
        ROOT,
        roots=(module,),
        overrides={
            module: source + "\nfrom carbon.chain import ReadOnlyChainAdapter\n"
        },
    )
    assert "carbon.chain" in evidence["forbidden_reachable"]
    assert evidence["first_forbidden_paths"]["carbon.chain"][0] == module


@pytest.mark.parametrize("ancestor", ("carbon", "carbon.scoring"))
def test_guard_follows_implicit_package_initializers(ancestor):
    module = "carbon.scoring.engine"
    path = ROOT.joinpath(*ancestor.split("."), "__init__.py")
    source = path.read_text(encoding="utf-8")
    evidence = audit(
        ROOT,
        roots=(module,),
        overrides={ancestor: source + "\nimport carbon.chain\n"},
    )
    assert ancestor in evidence["local_modules"]
    assert "carbon.chain" in evidence["forbidden_reachable"]
    assert evidence["first_forbidden_paths"]["carbon.chain"] == [
        module,
        ancestor,
        "carbon.chain",
    ]


@pytest.mark.parametrize(
    "source",
    (
        'from importlib import import_module\nimport_module("carbon.chain")\n',
        'from importlib import import_module as load\nload("carbon.chain")\n',
        'import importlib\nimportlib.import_module("carbon.chain")\n',
        'import importlib as loaders\nloaders.import_module("carbon.chain")\n',
        '__import__("carbon.chain")\n',
    ),
)
def test_dynamic_loader_calls_are_reported_instead_of_claiming_clean(source):
    module = "carbon.scoring.engine"
    evidence = audit(ROOT, roots=(module,), overrides={module: source})
    assert evidence["dynamic_import_calls"] == [f"{module}:{len(source.splitlines())}"]


def test_weight_publisher_transitive_score_reachability_is_reported_as_unknown():
    evidence = audit(ROOT, roots=("carbon.rewards.testnet_winner_publication",))
    assert "carbon.scoring.engine" in evidence["score_root_paths"]
    assert evidence["score_root_paths"]["carbon.scoring.engine"][0] == (
        "carbon.rewards.testnet_winner_publication"
    )


def test_tuning_transitive_chain_reachability_is_reported_as_unknown():
    evidence = audit(ROOT, roots=("carbon.battery.value.score_tuning",))
    assert evidence["first_forbidden_paths"]["carbon.chain"][0] == (
        "carbon.battery.value.score_tuning"
    )
    assert "carbon.chain" in evidence["forbidden_reachable"]
