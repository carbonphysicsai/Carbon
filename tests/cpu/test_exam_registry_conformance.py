"""X1: a synthetic exam registered ONLY through the registry must pass build -> grade -> crown -> weights -> board.

Owner EXAM-AGNOSTIC (Lead 5851, LAUNCH_PLAN X1-X4; design note reports/SCALE/EXAM_REGISTRY_DESIGN_20261124.md). A family
and version that no code names, ``zz-synthetic 0.1``, is registered only by a host overlay entry and an exam registry
row, each in a temporary file (`version_overlay.install(path)`, `exam_registry.install(path)`), in a fresh interpreter,
before any other module derives a set from the registry. Every site a build, grade, crown, weights and board walk asks about that version is then PROBED: one probe
per site, named with its file and the blind-audit row (reports/SCALE/BLIND_RESTRICTION_AUDIT_20261123.md) it checks.

``KNOWN_GAPS`` is the punch list: the probes that fail today, each with the registry datum its fix moves into the
registry (design note section 2). A probe in it must still FAIL (a fix that makes it pass fails this test until its
line is deleted, so progress is always recorded); a probe not in it must PASS (no regression). Goal (X4): an empty
``KNOWN_GAPS``. Synthetic only: no hidden, sealed or custody material, no key; the weights probe reads the policy and
signs nothing.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
FAMILY, VERSION = "zz-synthetic", "0.1"
#: A second version of the family, whose one difference is a trust interface (`build.trust`); 0.1 offers none.
TRUST_VERSION = "0.3"
#: The synthetic exam's build module, searched as ``carbon.zz_synthetic_build`` only inside the walk.
FIXTURES = REPOSITORY / "tests" / "fixtures" / "exam_registry"
BUILD_MODULE = "carbon.zz_synthetic_build"
#: Its sealed kit and grader (one fixture module for both roles).
SEALED_MODULE = "carbon.zz_synthetic_sealed"
#: The synthetic published-exam file the registry row names.
PUBLISHED = "tests/fixtures/exam_registry/zz_published_exam.json"

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

#: The exam registry row (`challenge_registry/exam_registry.py`): the version's synthetic facts, one per field a head
#: has moved into the registry.
EXAM_ROW = {
    "launch": {
        "state": "launched",
        "qualified_sealed": {
            "record_sha256": "sha256:" + "d" * 64,
            "evaluation_pack_digests": ["sha256:" + "e" * 64],
        },
    },
    "rebuild_gpu_lane_hours": {
        "value": 0.02,
        "measurement_digest": "sha256:" + "a" * 64,
    },
    "solver_seconds_per_design": {"value": 100, "source": "synthetic"},
    "terms": {"version": "zz-terms-v0", "sha256": "b" * 64},
    "entry": {
        "title": "Synthetic exam",
        "portfolio": "launch_pending_readiness",
        "status": "open",
    },
    "verify_set": {"path": "kits/zz/verify_set.json", "sha256": "c" * 64},
    "published": {
        "path": PUBLISHED,
        "sha256": hashlib.sha256((REPOSITORY / PUBLISHED).read_bytes()).hexdigest(),
    },
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
        "build.bundle",
        "BUILD",
        "11",
        "challenge_kit/physical_material.py bundle_material",
    ),
    (
        "build.pack_roles",
        "BUILD",
        "2",
        "challenge_kit/physical_pack.py public_roles / development_bank / physics_contract",
    ),
    (
        "build.trusted_limits",
        "BUILD",
        "2",
        "development_session/bundle_construction_worker.py verify_direct_resource_policy",
    ),
    (
        "build.served",
        "BUILD",
        "11",
        "challenge_validator/direct_receiver.py served_challenges",
    ),
    (
        "build.task_wall",
        "BUILD",
        "39",
        "challenge_kit/task_wall_overrides.py total_wall_seconds",
    ),
    (
        "build.practice_dtype",
        "BUILD",
        "51",
        "development_session/research_service.py _practice_dtype",
    ),
    (
        "build.rebuild_wall",
        "BUILD",
        "24",
        "development_session/bundle_construction_worker.py rebuild_wall_kwargs",
    ),
    (
        "build.trust",
        "BUILD",
        "-",
        "development_session/physical_graph_trust_registry.py REGISTRATIONS",
    ),
    (
        "build.entry",
        "BUILD",
        "-",
        "challenge_registry/registry.py _entries (what a miner can list, describe and select)",
    ),
    (
        "build.campaign",
        "BUILD",
        "-",
        "challenge_registry/campaigns.py _versioned_campaigns",
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
        "build.stage",
        "BUILD",
        "15",
        "development_session/direct_graph_construction_worker.py _v2_stage (the container's Spec)",
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
        "challenge_validator/exam_cap.py registered_cadence",
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
    ("grade.verify_set", "GRADE", "19", "challenge_kit/verify_practice.py registered"),
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
        "scripts/dev/build_weight_policy.py spec_from_rows (a policy built from the launch rows)",
    ),
    ("board.version_key", "BOARD", "3", "dashboard/feed.py board_slug"),
)

#: The punch list (design note section 2): probe -> the registry datum its fix moves into the registry. Each line is
#: deleted by the head that makes its probe pass.
KNOWN_GAPS = {
    "build.rebuild_wall": "a registered raise-only wall range (case-procs 8369a825, rides H2)",
}

_PROBE_PROGRAM = r"""
import inspect, json, sys
from pathlib import Path

import carbon
carbon.__path__.append(sys.argv[5])

overlay_path = Path(sys.argv[1])
family, version = sys.argv[2], sys.argv[3]

from carbon.challenge_kit import version_overlay, version_registry
version_overlay.install(path=overlay_path)
from carbon.challenge_registry import exam_registry
exam_registry.install(path=Path(sys.argv[4]))
from carbon.challenge_kit import family_registry
family_registry.install(path=Path(sys.argv[7]))
from carbon.scoring import family_graders
family_graders.install()


def probe_registry_find():
    assert version_registry.find(family, version) is not None


def probe_registry_overlay():
    assert version_overlay.is_overlay(family, version)


def probe_registry_family():
    from carbon.challenge_kit import family_registry
    assert family_registry.family(family)["kind"] == "zzsynthetic"


def probe_build_material():
    from carbon.challenge_kit import physical_material
    assert physical_material.is_registered(family, version)


def probe_build_kit():
    from carbon.challenge_kit import physical_material
    kit = physical_material.construction_kit(family, version)
    assert (kit["id"], kit["version"]) == (family, version)


def probe_build_bundle():
    from carbon.challenge_kit import physical_material
    material = physical_material.bundle_material(family, version)
    assert material["construction_kit"] == physical_material.construction_kit(family, version)
    assert material["expected_output_shape"] == (8, 1)


def probe_build_pack_roles():
    from carbon.challenge_kit import physical_material, physical_pack
    material = physical_material.bundle_material(family, version)
    roles = physical_pack.public_roles(family, version)
    assert roles["train"] == material["train"]
    assert json.loads(roles["construction_kit"]) == material["construction_kit"]
    assert json.loads(roles["interface"]) == material["interface_document"]
    assert physical_pack.physics_contract(family, version) == material["physics_contract"]
    bank = physical_pack.development_bank(family, version)
    assert (bank["inputs"] == material["practice_inputs"]).all()


def probe_build_trusted_limits():
    from carbon.challenge_kit import physical_material
    from carbon.development_session import bundle_construction_worker
    kit = physical_material.construction_kit(family, version)
    limits = physical_material.construction_limits_document(family, version)
    assert (
        bundle_construction_worker.verify_direct_resource_policy(kit, limits)
        == kit["construction_limits_digest"]
    )


def probe_build_served():
    from carbon.challenge_validator import direct_receiver
    assert {"id": family, "version": version} in direct_receiver.served_challenges()


def probe_build_task_wall():
    from carbon.challenge_kit import physical_material, task_wall_overrides
    assert task_wall_overrides.total_wall_seconds(family, version, 648) == 1234
    policy = physical_material.construction_limits_document(family, version)["reconstruction_resource_policy"]
    assert policy["total_reconstruction_wall_seconds_max"] == 1234


def probe_build_practice_dtype():
    from types import SimpleNamespace
    from carbon.development_session import research_service
    key = SimpleNamespace(challenge_id=family, version=version)
    assert research_service._practice_dtype(key, float64_family=True) == "float32"


def probe_build_rebuild_wall():
    from carbon.development_session import bundle_construction_worker
    limits = {"reconstruction_resource_policy": {"build_wall_seconds_max": 880}}
    assert bundle_construction_worker.rebuild_wall_kwargs(limits) == {"rebuild_wall_seconds": 880}


def probe_build_trust():
    from carbon.challenge_kit import physical_material
    from carbon.development_session import (
        direct_graph_construction_worker,
        physical_graph_adapter_v2,
        physical_graph_trust_registry,
    )
    # a version with no trust outputs needs no trust registration
    assert physical_graph_trust_registry.registered(family, version) is None
    trust_version = sys.argv[6]
    entry = physical_graph_trust_registry.registered(family, trust_version)
    assert (entry["sigma_floor"], entry["epochs"], entry["learning_rate"]) == ((0.0,), 3, 0.002)
    assert physical_graph_adapter_v2.spec_for(family, trust_version).trust_outputs == 1
    kit = physical_material.construction_kit(family, trust_version)
    binding = {
        "challenge_id": family,
        "challenge_version": trust_version,
        "train_digest": kit["train_digest"],
    }
    _, _, files = direct_graph_construction_worker._v2_stage(
        binding,
        physical_material.construction_limits_document(family, trust_version),
        physical_graph_adapter_v2.served_allowlist_bytes(family, trust_version),
        trust=True,
    )
    assert json.loads(files["graph-trust.json"])["version"] == trust_version
    assert b"def derive(" in files[direct_graph_construction_worker.REGISTERED_TRUST_DERIVE + ".py"]


def probe_build_entry():
    from carbon.challenge_registry import registry
    entry, = [e for e in registry.entries() if (e.challenge_id, e.version) == (family, version)]
    assert (entry.title, entry.portfolio) == ("Synthetic exam", "launch_pending_readiness")
    # known and offered as every pool version is: reserved until its own constants are registered and published
    assert entry.status == registry.RESERVED
    try:
        registry._find(family, version)
    except registry.ChallengeNotImplemented:
        pass
    else:
        raise AssertionError("a version with no registered constants was selectable")
    described = entry.describe()
    assert described["construction_kit"]["version"] == version
    assert described["graph_route"]["example"]["recipe"]["challenge"]["id"] == family


def probe_build_campaign():
    from carbon.challenge_registry import campaigns
    built = campaigns._versioned_campaigns()[(family, version)]()
    assert (built.key.challenge_id, built.key.version) == (family, version)
    assert built.construction_kit()["version"] == version
    assert built.construction_bundle_material()["challenge_key"] == built.key
    view = built.research_view()
    assert [output.name for output in view.outputs] == ["y"]
    assert view.components == (("mean", "Mean error"), ("worst", "Worst error"))
    assert built.practice_provenance in campaigns.practice_provenances()


def probe_build_train():
    from carbon.challenge_kit import physical_public_train
    assert physical_public_train._train_name(family, version) == "zz-synthetic-train-v1"
    loaded = physical_public_train.load_public_train(family, version)
    assert loaded["inputs"].shape == (8, 2) and loaded["targets"].shape == (8, 1)


def probe_build_spec():
    from carbon.development_session import physical_graph_adapter_v2
    spec = physical_graph_adapter_v2.spec_for(family, version)
    assert (spec.rows, spec.inputs, spec.outputs) == (8, 2, 1)
    assert spec.adapter_id in physical_graph_adapter_v2.ADAPTER_IDS


def probe_build_program():
    from carbon.development_session import direct_graph_construction_worker
    query = direct_graph_construction_worker.v2_infer_query(family, version)
    assert query["program"] == direct_graph_construction_worker.PHYSICAL_V2_COMPILED_INFER_PROGRAM


def probe_build_stage():
    from carbon.challenge_kit import physical_material
    from carbon.development_session import (
        direct_graph_construction_worker,
        physical_graph_adapter_v2,
    )
    kit = physical_material.construction_kit(family, version)
    binding = {
        "challenge_id": family,
        "challenge_version": version,
        "train_digest": kit["train_digest"],
    }
    spec, _, files = direct_graph_construction_worker._v2_stage(
        binding,
        physical_material.construction_limits_document(family, version),
        physical_graph_adapter_v2.served_allowlist_bytes(family, version),
    )
    assert files["graph-spec.json"] == physical_graph_adapter_v2.staged_spec(spec)


def probe_build_sealed_target():
    assert version_overlay.SEALED_TARGET[family] == "carbon.zz_synthetic_sealed"


def probe_grade_sealed_kit():
    from carbon.scoring import sealed_batch_source
    assert sealed_batch_source._kit(family).__name__ == "carbon.zz_synthetic_sealed"
    assert sealed_batch_source._pool_graded(family, version) is True
    assert sealed_batch_source._adapter(family, {"population": "zz"}, version, None).CHALLENGE == family


def probe_grade_pool_kind():
    from carbon.scoring import pool_version
    assert pool_version.KINDS[family] == "zzsynthetic"


def probe_grade_exam_cap():
    from carbon.challenge_validator import exam_cap
    assert family in exam_cap.registered_challenges()


def probe_grade_cadence():
    from carbon.challenge_validator import exam_cap
    assert exam_cap.registered_cadence()["rebuild_gpu_lane_hours"][family] == 0.02


def probe_grade_speed_gate():
    from carbon.challenge_registry import speed_gate
    assert speed_gate.ceiling_seconds(family, version) == 0.2


def probe_grade_published():
    from carbon.challenge_registry import published_exam
    block = published_exam.for_version(family, version)
    assert block["scoring_version"] == "zz-synthetic-pool-sealed-v1"
    assert (family, version) in published_exam._POOL_VERSIONS


def probe_grade_copy_opacity():
    from carbon.scoring import copy_derivation
    assert copy_derivation.opaque_for(family) == ("case_id",)


def probe_grade_verify_set():
    from carbon.challenge_kit import verify_practice
    assert verify_practice.registered(family, version)


def probe_grade_terms():
    from carbon.challenge_validator import submission_terms
    assert submission_terms.required_version(family, version) == "zz-terms-v0"


def probe_crown_koth_key():
    from carbon.challenge_validator import exam_cap, registry_version
    assert registry_version.known_key(f"{family} {version}", exam_cap.registered_challenges())


def probe_weights_pay_share():
    # a policy built from the launch rows loads and pays the family its equal share (owner G-LEAD-100; none is registered)
    import shutil, tempfile
    from carbon.rewards import winner_decay
    from carbon.rewards.core import Q12
    from scripts.dev import build_weight_policy as builder
    made = builder.dry_run("mainnet-winner-v4", "zz-policy-v1", rows=builder.launch_rows())["document"]
    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder) / "policies"
        shutil.copytree(winner_decay.POLICY_DIR, directory)
        (directory / "zz-policy-v1.json").write_bytes(builder.render(made))
        registry = json.loads((directory / "registry.json").read_bytes())
        registry["versions"]["zz-policy-v1"] = builder.digest(made)
        (directory / "registry.json").write_text(json.dumps(registry))
        policy = winner_decay.load_policy("zz-policy-v1", directory)
    assert set(policy.challenges) == {family, "electric-motor-magnetics"}
    targets = winner_decay.epoch_targets(policy, {family: winner_decay.Winner("king", 10**12)}, 10**12)
    assert targets["winners"] == {"king": Q12 // 2}
    assert policy.qualified_packs(family) == frozenset({"sha256:" + "e" * 64})


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


def _pinned(name):
    raw = (FIXTURES / f"{name}.py").read_bytes().replace(b"\r\n", b"\n")
    return {"module": f"carbon.{name}", "sha256": hashlib.sha256(raw).hexdigest()}


def _trust_block():
    """The trust version's ``build`` field: 0.1's with one trust output and its registration."""
    block = _build_block()
    return {
        **block,
        "graph_spec": {**block["graph_spec"], "trust_outputs": 1},
        "trust": {
            "derive": _pinned("zz_synthetic_trust"),
            "sigma_floor": [0.0],
            "epochs": 3,
            "learning_rate": 0.002,
        },
    }


def _build_block():
    """The version's ``build`` field (`challenge_registry/exam_build.py`): its module, by the sha256 of its file."""
    source = FIXTURES / "zz_synthetic_build.py"
    spec = importlib.util.spec_from_file_location("zz_synthetic_build", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = source.read_bytes().replace(b"\r\n", b"\n")
    return {
        "module": BUILD_MODULE,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "graph_spec": module.graph_spec(),
        "inference_program": "compiled",
        "total_wall_seconds": 1234,
    }


def _family_row():
    """The family registry row (`challenge_kit/family_registry.py`): synthetic, its two modules the synthetic fixture's."""
    raw = (FIXTURES / "zz_synthetic_sealed.py").read_bytes().replace(b"\r\n", b"\n")
    block = {"module": SEALED_MODULE, "sha256": hashlib.sha256(raw).hexdigest()}
    return {
        "kind": "zzsynthetic",
        "opacity": ["case_id"],
        "baseline": {"bounds": {"x": [0.0, 1.0]}, "length_ridge": [2.0, 0.001]},
        "modules": {"sealed_kit": dict(block), "sealed_grader": dict(block)},
    }


def _paid_today():
    """The launch row of the exam the base policy pays, from that policy's own qualification."""
    from carbon.rewards import winner_decay

    raw = (winner_decay.POLICY_DIR / "mainnet-winner-v4.json").read_bytes()
    found = json.loads(raw)["qualified_sealed"]["electric-motor-magnetics"]
    return {"state": "launched", "qualified_sealed": found}


@pytest.fixture(scope="module")
def walk(tmp_path_factory):
    path = tmp_path_factory.mktemp("registry") / "version_overlay.json"
    document = {
        "schema": "carbon.challenge-kit.version-overlay.v1",
        "versions": {
            f"{FAMILY} {version}": {**ENTRY, "version": version}
            for version in (VERSION, TRUST_VERSION)
        },
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    exams = path.with_name("exam_registry.json")
    document = {
        "schema": "carbon.challenge-registry.exam-registry.v1",
        "source": "synthetic",
        "exams": {
            f"{FAMILY} {VERSION}": {**EXAM_ROW, "build": _build_block()},
            f"{FAMILY} {TRUST_VERSION}": {"build": _trust_block()},
            "electric-motor-magnetics 1.8": {"launch": _paid_today()},
        },
    }
    exams.write_text(json.dumps(document), encoding="utf-8")
    families = path.with_name("family_registry.json")
    document = {
        "schema": "carbon.challenge-kit.family-registry.v1",
        "source": "synthetic",
        "families": {FAMILY: _family_row()},
    }
    families.write_text(json.dumps(document), encoding="utf-8")
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            _PROBE_PROGRAM,
            str(path),
            FAMILY,
            VERSION,
            str(exams),
            str(FIXTURES),
            TRUST_VERSION,
            str(families),
        ],
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
