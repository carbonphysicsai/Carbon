"""Every surface that ranks, compares or shows battery scores (TORCH-GPU-01).

The Test Lead (2026-10-06): before any GPU-class score exists, every surface
that ranks or compares battery scores is partitioned by device class (a mixed
set is refused or split), and every surface that only shows a score labels it
with its class. The surfaces and their rule are tabled in #692. These tests
hold each one, with a mutation for each guard:
- display: the operator status carries the device class beside the
  incumbent. The miner's outcome (and the Launchpad's projection of it) is
  not changed: adding a field to the miner disclosure allow-list is the
  owner's (OWNER-BATTERY-3B-AND-EXPOSURE-01; HUMAN_INPUT), and under the
  mainnet-parity sealed rule a miner is shown no score at all;
- the tuning set and EV experiment panels refuse a mixed panel;
- a Graphite proposal is never compared with a baseline of another class,
  nor with one whose class was never recorded;
- weights are the validator's incumbent (no ranking), and which device class
  may earn them is the owner's (HUMAN_INPUT), so that surface is not changed.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from carbon.battery import rebuild_identity as ri

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tests" / "cpu"))
sys.path.insert(0, str(REPOSITORY))

from test_battery_validator_daemon import (
    backend,  # noqa: F401 - fixture
    make,
    refs,  # noqa: F401 - fixture
    run,
    submission,
)

A40 = "NVIDIA A40"


def bundle(device_kind=None):
    fit = {"params_sha256": "x"}
    if device_kind is not None:
        fit.update(backend="pytorch", device="cuda", device_kind=device_kind)
    return {"reconstruction": {"backend": "ISOLATED_CARRIER"}, "fit": fit}


def _calls(path, function, name):
    """Whether `function` in `path` calls `name` (an attribute or a name)."""
    tree = ast.parse((REPOSITORY / path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function:
            for call in ast.walk(node):
                if isinstance(call, ast.Call):
                    target = call.func
                    found = getattr(target, "attr", None) or getattr(target, "id", None)
                    if found == name:
                        return True
    return False


# --- display surfaces carry the label ---------------------------------------------


def test_the_operator_status_labels_the_incumbents_device_class(
    tmp_path, refs, backend  # noqa: F811 - fixtures
):
    validator = make(tmp_path, refs, backend)
    run(validator, submission("hk1"))
    assert validator.status()["incumbent"]["device_class"] == "cpu"


def test_the_miner_disclosure_allow_list_is_unchanged():
    """HUMAN_INPUT: the device class is not added to what a miner sees."""
    from carbon.battery.daemon import SCREENING_FEEDBACK_FIELDS
    from scripts.dev.miner_launchpad import projection

    assert "device_class" not in SCREENING_FEEDBACK_FIELDS
    assert "device_class" not in projection._SCREENING_FIELDS


# --- ranking surfaces refuse a mixed set ------------------------------------------


def test_a_panel_of_one_device_class_is_scored_and_a_mixed_one_refused():
    assert ri.bundles_class([bundle(), bundle()]) == "cpu"
    assert ri.bundles_class([bundle(A40), bundle(A40)]) == "gpu:" + A40
    with pytest.raises(ri.DeviceClassMixed):
        ri.bundles_class([bundle(), bundle(A40)])


def test_dropping_a_bundles_device_kind_is_caught_as_a_mixed_panel():
    """Mutation: a GPU bundle that loses its device kind reads as CPU, so a
    panel that also holds an intact GPU bundle is refused."""
    gpu = bundle(A40)
    dropped = {
        **gpu,
        "fit": {k: v for k, v in gpu["fit"].items() if k != "device_kind"},
    }
    with pytest.raises(ri.DeviceClassMixed):
        ri.bundles_class([dropped, bundle(A40)])


@pytest.mark.parametrize(
    "path, function",
    [
        ("carbon/challenge_validator/tuning.py", "score"),
        ("carbon/battery/value/experiment.py", "evaluate"),
    ],
)
def test_the_tuning_set_and_ev_panels_run_the_guard(path, function):
    assert _calls(path, function, "bundles_class"), (path, function)


def test_a_graphite_comparison_needs_one_recorded_class():
    from carbon.agent_campaign.graphite.experiment import _rebuilt

    pod_gpu = {
        "rebuild": ri.from_runtime({"backend": "gpu", "devices": [{"kind": A40}]})
    }
    pod_cpu = {"rebuild": ri.from_runtime({"backend": "cpu", "devices": []})}
    assert ri.comparable(pod_gpu, dict(pod_gpu))
    assert not ri.comparable(pod_gpu, pod_cpu)
    # A baseline made before the field existed may have run on a GPU pod: it
    # reads as unrecorded and is compared with nothing, not even its kind.
    legacy = _rebuilt({"status": "SCORED"})
    assert ri.device_class(legacy) == ri.UNRECORDED
    assert not ri.comparable(legacy, pod_gpu)
    assert not ri.comparable(legacy, _rebuilt({"status": "SCORED"}))
    # A runtime naming no backend, or several kinds, is unrecorded too.
    mixed = {"backend": "gpu", "devices": [{"kind": A40}, {"kind": "NVIDIA H100"}]}
    assert ri.from_runtime(mixed)["device_class"] == ri.UNRECORDED
    assert ri.from_runtime(None)["device_class"] == ri.UNRECORDED
    # A synthetic dry-run pod rebuilds nothing: it is its own class, compared
    # only with other synthetic records.
    synthetic = {"rebuild": ri.from_runtime({"synthetic": True})}
    assert ri.device_class(synthetic) == ri.SYNTHETIC
    assert ri.comparable(synthetic, dict(synthetic))
    assert not ri.comparable(synthetic, pod_cpu)


def test_graphite_records_the_class_and_guards_the_baseline_comparison():
    source = (REPOSITORY / "carbon/agent_campaign/graphite/experiment.py").read_text()
    assert '"rebuild": ri.from_runtime(_object(files.get("runtime.json")))' in source
    assert "elif not ri.comparable(_rebuilt(baseline), record):" in source
    assert '"outcome": "DEVICE_CLASS_DIFFERS"' in source
    # Delivery promotes only an IMPROVEMENT, so a refused comparison is never
    # delivered.
    delivery = (REPOSITORY / "carbon/agent_campaign/graphite/delivery.py").read_text()
    assert '.get("outcome") == "IMPROVEMENT"' in delivery


# --- weights: unchanged, owner-reserved -------------------------------------------


def test_weights_follow_the_incumbent_and_are_not_partitioned_here():
    """HUMAN_INPUT: which device class may earn weight is the owner's. The
    winner is the validator's incumbent, never a ranking, so no mixed
    comparison happens here; nominations and finals refuse mixed classes."""
    source = (REPOSITORY / "carbon/rewards/winner_eligibility.py").read_text()
    assert "store.incumbent()" in source
    assert "device_class" not in source
