"""X1: a synthetic exam registered ONLY through the registry must pass build -> grade -> crown -> weights -> board.

Owner EXAM-AGNOSTIC (Lead 5851, LAUNCH_PLAN X1-X4; design note reports/SCALE/EXAM_REGISTRY_DESIGN_20261124.md). A family
and version that no code names, ``zz-synthetic 0.1``, is registered only by a host overlay entry written to a temporary
file (`version_overlay.install(path)`), in a fresh interpreter, before any other module derives a set from the
registry. Every site a build, grade, crown, weights and board walk asks about that version is then PROBED: one probe
per site, named with its file and the blind-audit row (reports/SCALE/BLIND_RESTRICTION_AUDIT_20261123.md) it checks.

``KNOWN_GAPS`` is the punch list: the probes that fail today, each with the registry datum its fix moves into the
registry (design note section 2). A probe in it must still FAIL (a fix that makes it pass fails this test until its
line is deleted, so progress is always recorded); a probe not in it must PASS (no regression). Goal (X4): an empty
``KNOWN_GAPS``. Synthetic only: no hidden, sealed or custody material, no key; the weights probe reads the policy and
signs nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
FAMILY, VERSION = "zz-synthetic", "0.1"

#: The overlay entry: every field a registered version carries, every value synthetic (no code names any of them).
ENTRY = {
    "challenge_id": FAMILY,
    "version": VERSION,
    "train": "zz-synthetic-train-v1",
    "allowlist": "v8",
    "step_caps": False,
    "pack_version": "zz-synthetic-normal-construction-development-1",
    "development_evaluation": None,
    "sealed_evaluation": "zz-synthetic-pool-sealed-v1",
    "campaign": "catalog",
    "catalog": True,
    "graph_adapter": "v2",
    "catalog_entries_from": [],
    "predecessor": None,
    "rebuild_wall_seconds": 648,
}

#: (probe id, stage, audit row, site): the walk in order. The probe bodies are in `_PROBE_PROGRAM`.
PROBES = (
    ("registry.find", "REGISTRY", "-", "challenge_kit/version_registry.py find"),
    (
        "registry.overlay",
        "REGISTRY",
        "-",
        "challenge_kit/version_overlay.py is_overlay",
    ),
    (
        "registry.family",
        "REGISTRY",
        "7",
        "challenge_kit/family_registry.py family (door-code H1)",
    ),
    ("build.material", "BUILD", "11", "challenge_kit/physical_material.py REGISTERED"),
    (
        "build.kit",
        "BUILD",
        "2 / 11",
        "challenge_kit/physical_material.py construction_kit",
    ),
    (
        "build.train",
        "BUILD",
        "18",
        "challenge_kit/physical_public_train.py _train_name",
    ),
    (
        "build.spec",
        "BUILD",
        "15",
        "development_session/physical_graph_adapter_v2.py spec_for",
    ),
    (
        "build.program",
        "BUILD",
        "16",
        "development_session/direct_graph_construction_worker.py v2_infer_query",
    ),
    (
        "build.sealed_target",
        "BUILD",
        "6",
        "challenge_kit/version_overlay.py SEALED_TARGET",
    ),
    ("grade.sealed_kit", "GRADE", "7", "scoring/sealed_batch_source.py _kit"),
    ("grade.pool_kind", "GRADE", "9", "scoring/pool_version.py KINDS"),
    (
        "grade.exam_cap",
        "GRADE",
        "12",
        "challenge_validator/exam_cap.py registered_challenges",
    ),
    (
        "grade.cadence",
        "GRADE",
        "12",
        "challenge_validator/exam_cadence.json rebuild_gpu_lane_hours",
    ),
    (
        "grade.speed_gate",
        "GRADE",
        "14",
        "challenge_registry/speed_gate.py ceiling_seconds",
    ),
    (
        "grade.published",
        "GRADE",
        "17",
        "challenge_registry/published_exam.py _BY_VERSION",
    ),
    (
        "grade.copy_opacity",
        "GRADE",
        "8",
        "scoring/copy_derivation.py OPAQUE_BY_CHALLENGE",
    ),
    ("grade.verify_set", "GRADE", "19", "challenge_kit/verify_practice.py REGISTRY"),
    (
        "grade.terms",
        "GRADE",
        "20",
        "challenge_validator/submission_terms.py required_version",
    ),
    (
        "crown.koth_key",
        "CROWN",
        "13",
        "challenge_validator/registry_version.py known_key",
    ),
    (
        "weights.pay_share",
        "WEIGHTS",
        "21",
        "rewards/winner_decay.py load_policy().challenges",
    ),
    ("board.version_key", "BOARD", "3", "dashboard/feed.py board_slug"),
)

#: The punch list (design note section 2): probe -> the registry datum its fix moves into the registry. Each line is
#: deleted by the head that makes its probe pass.
KNOWN_GAPS = {
    "registry.family": "family_registry.json + reader (door-code #1, H1)",
    "build.material": "physical_material.REGISTERED derived from the registry's physical families",
    "build.kit": "family / version public_module",
    "build.train": "family train_loader (TRAIN name served by the registry)",
    "build.spec": "graph Spec derived from the version entry",
    "build.program": "version inference_program (eager / compiled / per-case)",
    "build.sealed_target": "family sealed_target in version_overlay.json (image move, H2)",
    "grade.sealed_kit": "family kit / sealed grader / bank modules (H1 wrap)",
    "grade.pool_kind": "family pool_kind + register_kind (H1)",
    "grade.exam_cap": "exam_cap family list from the registry",
    "grade.cadence": "cadence row per family (measured t_c)",
    "grade.speed_gate": "per-version solver seconds row, typed refusal when missing",
    "grade.published": "published block derived from the version's sealed evaluation + pool rows",
    "grade.copy_opacity": "family copy_opacity (through H1, a shared producer file)",
    "grade.verify_set": "version verify_set (path + receipted sha)",
    "grade.terms": "version terms (version string + digest; G-LEAD-50: no terms, no submission)",
    "crown.koth_key": "koth rows keyed by the registry (door-code #15)",
    "weights.pay_share": "paying families from the registry (owner economics line, not code)",
}

_PROBE_PROGRAM = r"""
import inspect, json, sys
from pathlib import Path

overlay_path = Path(sys.argv[1])
family, version = sys.argv[2], sys.argv[3]

from carbon.challenge_kit import version_overlay, version_registry
version_overlay.install(path=overlay_path)


def probe_registry_find():
    assert version_registry.find(family, version) is not None


def probe_registry_overlay():
    assert version_overlay.is_overlay(family, version)


def probe_registry_family():
    from carbon.challenge_kit import family_registry
    assert family_registry.family(family) is not None


def probe_build_material():
    from carbon.challenge_kit import physical_material
    assert physical_material.is_registered(family, version)


def probe_build_kit():
    from carbon.challenge_kit import physical_material
    physical_material.construction_kit(family, version)


def probe_build_train():
    from carbon.challenge_kit import physical_public_train
    assert physical_public_train._train_name(family, version) is not None


def probe_build_spec():
    from carbon.development_session import physical_graph_adapter_v2
    physical_graph_adapter_v2.spec_for(family, version)


def probe_build_program():
    from carbon.development_session import direct_graph_construction_worker
    direct_graph_construction_worker.v2_infer_query(family, version)


def probe_build_sealed_target():
    assert family in version_overlay.SEALED_TARGET


def probe_grade_sealed_kit():
    from carbon.scoring import sealed_batch_source
    assert sealed_batch_source._kit(family) is not None


def probe_grade_pool_kind():
    from carbon.scoring import pool_version
    assert family in pool_version.KINDS


def probe_grade_exam_cap():
    from carbon.challenge_validator import exam_cap
    assert family in exam_cap.registered_challenges()


def probe_grade_cadence():
    from carbon.challenge_validator import exam_cap
    document = json.loads(exam_cap.REGISTRY.read_bytes())
    assert family in document["rebuild_gpu_lane_hours"]


def probe_grade_speed_gate():
    from carbon.challenge_registry import speed_gate
    speed_gate.ceiling_seconds(family)


def probe_grade_published():
    from carbon.challenge_registry import published_exam
    assert (family, version) in published_exam._BY_VERSION


def probe_grade_copy_opacity():
    from carbon.scoring import copy_derivation
    assert family in copy_derivation.OPAQUE_BY_CHALLENGE


def probe_grade_verify_set():
    from carbon.challenge_kit import verify_practice
    assert (family, version) in verify_practice.REGISTRY


def probe_grade_terms():
    from carbon.challenge_validator import submission_terms
    assert submission_terms.required_version(family, version) is not None


def probe_crown_koth_key():
    from carbon.challenge_validator import exam_cap, registry_version
    assert registry_version.known_key(f"{family} {version}", exam_cap.registered_challenges())


def probe_weights_pay_share():
    from carbon.rewards import winner_decay
    assert family in winner_decay.load_policy().challenges


def probe_board_version_key():
    from carbon.dashboard import feed
    assert "version" in inspect.signature(feed.board_slug).parameters


results = {}
for name, function in list(globals().items()):
    if not name.startswith("probe_"):
        continue
    key = name[len("probe_"):].replace("_", ".", 1)
    try:
        function()
        results[key] = {"ok": True}
    except BaseException as failure:  # a probe's own failure, of any kind, is its result
        results[key] = {"ok": False, "error": type(failure).__name__ + ": " + str(failure)[:300]}
print(json.dumps(results, sort_keys=True))
"""


@pytest.fixture(scope="module")
def walk(tmp_path_factory):
    path = tmp_path_factory.mktemp("registry") / "version_overlay.json"
    document = {
        "schema": "carbon.challenge-kit.version-overlay.v1",
        "versions": {f"{FAMILY} {VERSION}": ENTRY},
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-c", _PROBE_PROGRAM, str(path), FAMILY, VERSION],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=600,
        check=True,
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_every_probe_ran_and_the_punch_list_names_only_probes(walk):
    names = [probe for probe, *_ in PROBES]
    assert len(names) == len(set(names))
    assert set(walk) == set(names)
    assert set(KNOWN_GAPS) <= set(names)


@pytest.mark.parametrize("probe", [probe for probe, *_ in PROBES])
def test_the_registered_synthetic_exam_passes_the_site(walk, probe):
    result = walk[probe]
    if probe in KNOWN_GAPS:
        assert not result[
            "ok"
        ], f"{probe} now PASSES: delete its KNOWN_GAPS line (the punch list shrinks)"
        pytest.xfail(f"punch list: {KNOWN_GAPS[probe]} ({result.get('error')})")
    assert result["ok"], f"{probe} regressed: {result.get('error')}"
