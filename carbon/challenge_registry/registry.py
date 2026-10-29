"""Challenge entries, resolution and discovery documents.

Each entry names one Challenge and version, its lifecycle status and its
execution profiles. An IMPLEMENTED entry also carries an adapter that
describes the Challenge from its executable registrations:
- the construction contract and its capabilities;
- the public material allow-list;
- the exam semantics;
- the permitted feedback;
- an example validated by the same admission a submission meets.

RESERVED entries are launch Challenges whose interface exists only as a name
and a tracking issue. They say so, and refuse selection. DEFERRED entries are
portfolio candidates kept for history. RETIRED entries were once selectable and
are no longer on the research path; their code stays in the repository as
reference, they stay listed, and selecting one is refused.

A description separates *implemented* (Carbon has the code) from *usable
here* (this host, as the operator configured it, can run the profile now).
Usability is observed from the host: a present module, a configured image or
an installed runtime. It is never assumed, and never declared by the caller's
wish.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field

from carbon.reconstruction.capability_registry import is_development_variant

CATALOG_SCHEMA = "carbon.challenge-catalog.v1"
#: A launch-portfolio Challenge registered before its readiness record: it is
#: listed and runs, but is not `launch` until a readiness record (pilot
#: evidence) is committed for it (`test_challenge_readiness`). Gate6 on the
#: composite, 2026-10-21: F08 1.4 and F02 2.3 had none, and a record is
#: evidence, never boilerplate.
LAUNCH_PENDING_READINESS = "launch_pending_readiness"
#: The host fact a torch-cpu execution profile requires: the configured
#: trusted worker image is the PyTorch CPU worker (installed with --pytorch).
TORCH_CPU_WORKER = "torch_cpu_worker_image"
DESCRIPTION_SCHEMA = "carbon.challenge-description.v1"

IMPLEMENTED, RESERVED, DEFERRED, RETIRED = (
    "IMPLEMENTED",
    "RESERVED",
    "DEFERRED",
    "RETIRED",
)
CAPABILITY_REQUEST = (
    "Ask with the research workspace action capability_request "
    "{request:{purpose,operation,hypothesis,public_evidence,reason,"
    "expected_benefit,estimated_cost,minimal_safe_design,verification}} and an "
    "optional capability (a registry id). A request is recorded as demand; it "
    "grants nothing."
)


class ResolutionError(LookupError):
    """A selection Carbon refuses, with a stable code and the next step."""

    code = "challenge_resolution_failed"
    next_action = "List challenges and select an implemented, usable one."

    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail

    def public(self):
        return {
            "code": self.code,
            "detail": self.detail,
            "next_action": self.next_action,
        }


class UnknownChallenge(ResolutionError):
    code = "challenge_unknown"


class UnsupportedVersion(ResolutionError):
    code = "challenge_version_unsupported"
    next_action = "Select a version the catalog lists for this Challenge."


class ChallengeNotImplemented(ResolutionError):
    code = "challenge_not_implemented"
    next_action = (
        "This launch Challenge is reserved; follow its tracking issue. "
        + CAPABILITY_REQUEST
    )


class ChallengeDeferred(ResolutionError):
    code = "challenge_deferred"
    next_action = "Deferred portfolio candidate; not selectable in this version."


class ChallengeRetired(ResolutionError):
    code = "challenge_retired"
    next_action = (
        "Retired from the research path; its code is kept for reference only. "
        "Select an implemented Challenge from the catalog."
    )


class DevelopmentVariantNotServed(ResolutionError):
    """A development-only contract variant (OWNER-GRAPHITE-TEST-WAVE-03 §1),
    named as a Challenge or a version. Only Carbon's development runners read
    one; it is never listed, described or selected here."""

    code = "development_variant_not_served"
    next_action = "Select an implemented Challenge from the catalog."


class ProfileUnavailable(ResolutionError):
    code = "execution_profile_unavailable"
    next_action = (
        "Select a profile the description lists as usable here, or ask the "
        "operator to configure the missing host requirement."
    )


@dataclass(frozen=True)
class ExecutionProfile:
    """One way a Challenge's research runs, and what the host must supply."""

    name: str
    summary: str
    backend: str
    #: Named host facts (`HostFacts`) this profile needs, all of them.
    requirements: tuple[str, ...]


@dataclass(frozen=True)
class HostFacts:
    """What this host can run, observed rather than declared.

    `configured` holds operator-configured facts (a verified trusted worker
    image, a configured evaluation deployment); `observe()` adds the ones the
    host itself can answer.
    """

    facts: frozenset = frozenset()

    @staticmethod
    def observe(configured=()):
        found = set(configured)
        for module, fact in (("jax", "jax"), ("optax", "optax"), ("pybamm", "pybamm")):
            if importlib.util.find_spec(module) is not None:
                found.add(fact)
        if shutil.which("docker") is not None:
            found.add("docker_cli")
        return HostFacts(frozenset(found))

    def missing(self, profile):
        return [r for r in profile.requirements if r not in self.facts]


@dataclass(frozen=True)
class Entry:
    challenge_id: str
    version: str | None
    title: str
    status: str
    portfolio: str
    tracking: str | None
    profiles: tuple[ExecutionProfile, ...] = ()
    #: () -> the Challenge's own description (IMPLEMENTED only).
    describe: Callable | None = field(default=None, compare=False)
    #: (strategy) -> (compiled, guarded reconstruction recipe/profile).
    compile_strategy: Callable | None = field(default=None, compare=False)

    def summary(self, host):
        profiles = []
        for profile in self.profiles:
            missing = host.missing(profile)
            profiles.append(
                {
                    "profile": profile.name,
                    "summary": profile.summary,
                    "backend": profile.backend,
                    "requirements": list(profile.requirements),
                    "implemented": self.status == IMPLEMENTED,
                    "usable_here": self.status == IMPLEMENTED and not missing,
                    "missing_here": missing,
                }
            )
        return {
            "challenge_id": self.challenge_id,
            "version": self.version,
            "title": self.title,
            "status": self.status,
            "portfolio": self.portfolio,
            "tracking": self.tracking,
            "profiles": profiles,
        }


CPU_RESEARCH = "cpu_research"
#: Practice on the miner's own GPU, for speed only (C-MLP-03 slice 3).
GPU_RESEARCH = "gpu_research"


def _burgers():
    from .burgers import describe

    return describe()


def _battery():
    from .battery import describe

    return describe()


def _cold_plate():
    from .cold_plate import describe

    return describe()


def _cold_plate_catalog():
    from .cold_plate import describe_catalog

    return describe_catalog("1.2")


def _cold_plate_catalog_encoded():
    from .cold_plate import describe_catalog

    return describe_catalog("1.3")


def _motor():
    from .motor import describe

    return describe()


def _motor_catalog():
    from .motor import describe_catalog

    return describe_catalog()


def _motor_catalog_v7():
    from .motor import describe_catalog

    return describe_catalog("1.3")


def _motor_describe_catalog(version):
    from .motor import describe_catalog

    return describe_catalog(version)


def _cold_plate_describe_catalog(version):
    from .cold_plate import describe_catalog

    return describe_catalog(version)


def _direct_describe(challenge):
    def describe(version):
        from carbon.direct_campaign.spec import SPECS

        from .direct import describe as direct_describe

        return direct_describe(SPECS[challenge], version)

    return describe


def _f08_direct():
    from carbon.direct_campaign.spec import F08

    from .direct import describe

    return describe(F08, "1.4")


def _f02_direct():
    from carbon.direct_campaign.spec import F02

    from .direct import describe

    return describe(F02, "2.3")


def _battery_catalog_direct():
    from carbon.direct_campaign.spec import BATTERY_CATALOG

    from .direct import describe

    return describe(BATTERY_CATALOG, "2.2")


def _with_graph_route(described, challenge_id, version):
    """A graph route v2 version's description: its predecessor's, plus the
    graph training adapter v2 it serves and a ready graph recipe template
    (`development_session.graph_adapters`)."""
    from carbon.challenge_kit import version_registry
    from carbon.development_session import graph_adapters

    block = graph_adapters.adapter_block(challenge_id, version)
    described = dict(described)
    described["graph_route"] = {
        "adapter": block,
        "predecessor": version_registry.entry(challenge_id, version).predecessor,
        "summary": (
            "Your own graph, trained by Carbon's graph training adapter v2: "
            "per-output loss weights, ensembles whose members each train on a "
            "chosen subset of the outputs (combined per output), any number of "
            "members within the build's resource limits, and training settings "
            "bounded only by structure."
        ),
        "example": {
            "recipe": graph_adapters.graph_recipe(
                challenge_id,
                version,
                configuration=graph_adapters.configuration_example(
                    challenge_id, version
                ),
            ),
            "note": (
                "Stage your graph in your workspace and put its submission_digest "
                "in source; every configuration field is optional."
            ),
        },
    }
    described["examples"] = [
        *described.get("examples", []),
        {"recipe": described["graph_route"]["example"]["recipe"]},
    ]
    return described


def _graph_route(predecessor_describe, challenge_id, version):
    def describe():
        return _with_graph_route(predecessor_describe(version), challenge_id, version)

    return describe


def _compile_burgers(strategy):
    from carbon.development_session.research_catalog import compile_recipe

    return compile_recipe(strategy)


def _compile_battery(strategy):
    from carbon.battery.compile import compile_recipe

    return compile_recipe(strategy)


def _compile_cold_plate(strategy):
    from carbon.cold_plate.compile import compile_recipe

    return compile_recipe(strategy)


def _compile_motor(strategy):
    from carbon.motor.compile import compile_recipe

    return compile_recipe(strategy)


def _pool_status(challenge_id, version):
    """A pool-graded version is offered (IMPLEMENTED) only once its owner constants are registered and published;
    until then it is RESERVED, and the page, which offers by status only, does not offer it. Each version flips in
    the same change that registers its constants (`scoring/pool_constants.json`, `published_exam._REGISTERED_POOL`;
    tests/cpu/test_pool_reserved_status.py ties the two)."""
    from . import published_exam

    registered = published_exam.registered_pool(challenge_id, version) is not None
    return IMPLEMENTED if registered else RESERVED


def _entries():
    from carbon.reconstruction.capability_registry import (
        BATTERY_CHALLENGE,
        BATTERY_CONTRACT,
        BURGERS_CHALLENGE,
        BURGERS_CONTRACT,
        COLD_PLATE_CHALLENGE,
        COLD_PLATE_CONTRACT,
        MOTOR_CHALLENGE,
        MOTOR_CONTRACT,
    )

    carrier = ("docker_cli", "trusted_worker_image", "jax", "optax")
    #: A torch-cpu practice builds on the separate pinned PyTorch CPU worker
    #: (`gpu_practice.direct_parent_backend`): installed with --pytorch.
    torch_carrier = carrier + (TORCH_CPU_WORKER,)
    # One shared GPU practice profile for every catalog version (shared GPU
    # path, S3, `development_session.catalog_gpu`): its tested backbones'
    # GPU builds on the miner's own GPU, speed only, never official.
    catalog_gpu = ExecutionProfile(
        GPU_RESEARCH,
        "Practice of Carbon's tested catalog backbones' GPU builds on the "
        "miner's own GPU, in the isolated C-03 worker, for speed only; "
        "measured on GPU, not official, and CPU and GPU results can differ",
        "torch-cuda/isolated-carrier",
        torch_carrier + ("gpu_worker_image", "host_device_record"),
    )
    return (
        Entry(
            BURGERS_CHALLENGE,
            BURGERS_CONTRACT.version,
            "Burgers dynamics (DEVELOPMENT autoresearch, retired)",
            RETIRED,
            "historical_development",
            None,
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "JAX CPU practice in the isolated research carrier",
                    "jax-cpu/isolated-carrier",
                    carrier,
                ),
            ),
            _burgers,
            _compile_burgers,
        ),
        Entry(
            BATTERY_CHALLENGE,
            BATTERY_CONTRACT.version,
            "Battery fast charge and ageing (DEVELOPMENT, out of the launch set)",
            IMPLEMENTED,
            # Not a launch Challenge (OWNER-BATTERY-OUT-OF-LAUNCH-01, 2026-10-23; services wound
            # down by OWNER-WIND-DOWN-BATTERY-01): its code, tests and recorded campaigns stay,
            # and a miner is NOT offered it (see OFFERED_PORTFOLIOS). Returning it to the launch
            # portfolio is a new owner decision.
            "historical_development",
            "carbonphysicsai/Carbon#341",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "JAX or PyTorch CPU practice in the isolated research "
                    "carrier; exact Carbon recipe and training bytes staged",
                    "jax-cpu/isolated-carrier",
                    carrier,
                ),
                ExecutionProfile(
                    GPU_RESEARCH,
                    "JAX practice on the miner's own GPU in the isolated "
                    "carrier, for speed only; the validator rebuilds on its "
                    "own pinned backend",
                    "jax-cuda/isolated-carrier",
                    carrier + ("gpu_worker_image", "host_device_record"),
                ),
            ),
            _battery,
            _compile_battery,
        ),
        Entry(
            COLD_PLATE_CHALLENGE,
            COLD_PLATE_CONTRACT.version,
            "AI-chip liquid cold plate (DEVELOPMENT periodic cell)",
            IMPLEMENTED,
            "launch",
            "carbonphysicsai/Carbon#342",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "NumPy KRR practice in the isolated CPU research carrier; "
                    "exact public TRAIN and recipe bytes staged",
                    "numpy-cpu/isolated-carrier",
                    carrier,
                ),
            ),
            _cold_plate,
            _compile_cold_plate,
        ),
        Entry(
            MOTOR_CHALLENGE,
            MOTOR_CONTRACT.version,
            "Electric-motor magnetics (DEVELOPMENT periodic cross-section)",
            IMPLEMENTED,
            "launch",
            "carbonphysicsai/Carbon#344",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "NumPy KRR practice in the isolated CPU research carrier; "
                    "exact public TRAIN and recipe bytes staged",
                    "numpy-cpu/isolated-carrier",
                    carrier,
                ),
            ),
            _motor,
            _compile_motor,
        ),
        # The backbone-catalog version (OWNER-BACKBONE-CATALOG-01): Carbon's
        # tested backbones by catalog id on the direct recipe path; the
        # Level 0 strategy compiler stays 1.0's.
        Entry(
            MOTOR_CHALLENGE,
            "1.2",
            "Electric-motor magnetics (DEVELOPMENT periodic cross-section, backbone catalog)",
            IMPLEMENTED,
            "launch",
            "carbonphysicsai/Carbon#344",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch practice of Carbon's tested catalog backbones in the "
                    "isolated C-03 CPU worker; exact public TRAIN and bundle bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _motor_catalog,
            None,
        ),
        # Motor 1.3: 1.2 plus allowlist v7, each Challenge's catalog version
        # (Validator, 2026-10-20). 1.2 is unchanged.
        Entry(
            MOTOR_CHALLENGE,
            "1.3",
            "Electric-motor magnetics (DEVELOPMENT periodic cross-section, backbone "
            "catalog, allowlist v7)",
            IMPLEMENTED,
            "launch",
            "carbonphysicsai/Carbon#344",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch practice of Carbon's tested catalog backbones in the "
                    "isolated C-03 CPU worker; exact public TRAIN and bundle bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _motor_catalog_v7,
            None,
        ),
        # Graph route v2 (`challenge_kit.version_registry`): the predecessor
        # plus Carbon's graph training adapter v2; the predecessor is unchanged.
        Entry(
            MOTOR_CHALLENGE,
            "1.4",
            "Electric-motor magnetics (DEVELOPMENT periodic cross-section, backbone "
            "catalog and graph training adapter v2, allowlist v7)",
            IMPLEMENTED,
            "launch",
            "carbonphysicsai/Carbon#344",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch CPU practice of Carbon's tested catalog backbones, or "
                    "JAX CPU practice of your own graph by Carbon's graph training "
                    "adapter v2, in the isolated C-03 CPU worker; exact public TRAIN "
                    "and recipe bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _graph_route(_motor_describe_catalog, MOTOR_CHALLENGE, "1.4"),
            None,
        ),
        # Pool grade (`scoring.pool_exam`): 1.4's construction and kit material; the exam is the pool grader's.
        Entry(
            MOTOR_CHALLENGE,
            "1.5",
            "Electric-motor magnetics (DEVELOPMENT periodic cross-section, pool-graded exam, backbone catalog and graph training adapter v2, allowlist v8)",
            _pool_status(MOTOR_CHALLENGE, "1.5"),
            "launch",
            "carbonphysicsai/Carbon#344",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch CPU practice of Carbon's tested catalog backbones, or "
                    "JAX CPU practice of your own graph by Carbon's graph training "
                    "adapter v2, in the isolated C-03 CPU worker; exact public TRAIN "
                    "and recipe bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _graph_route(_motor_describe_catalog, MOTOR_CHALLENGE, "1.5"),
            None,
        ),
        # Cooling 1.2, Cooling's catalog version (allowlist v7 and the backbone
        # catalog, as Motor 1.2/1.3): Carbon's tested backbones by catalog id
        # on the direct recipe path; the Level 0 strategy compiler stays 1.0's.
        # Its catalog is empty until a Cooling entry is tested.
        Entry(
            COLD_PLATE_CHALLENGE,
            "1.2",
            "AI-chip liquid cold plate (DEVELOPMENT periodic cell, backbone catalog, "
            "allowlist v7)",
            IMPLEMENTED,
            "launch",
            "carbonphysicsai/Carbon#342",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch practice of Carbon's tested catalog backbones in the "
                    "isolated C-03 CPU worker; exact public TRAIN and bundle bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _cold_plate_catalog,
            None,
        ),
        # Cooling 1.3: 1.2 with the law-safe output encoding (Validator
        # ruling G1, 2026-10-22), so a catalog recipe can pass the mandatory
        # peak_bounds_profile law; its catalog is empty until an entry is
        # pair-tested on 1.3.
        Entry(
            COLD_PLATE_CHALLENGE,
            "1.3",
            "AI-chip liquid cold plate (DEVELOPMENT periodic cell, backbone catalog, "
            "allowlist v7, law-safe output encoding)",
            IMPLEMENTED,
            "launch",
            "carbonphysicsai/Carbon#342",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch practice of Carbon's tested catalog backbones in the "
                    "isolated C-03 CPU worker; exact public TRAIN and bundle bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                # The shared GPU practice profile every catalog version
                # declares (S3); 1.3 predates it on its own branch.
                catalog_gpu,
            ),
            _cold_plate_catalog_encoded,
            None,
        ),
        # Graph route v2 (`challenge_kit.version_registry`): the predecessor
        # plus Carbon's graph training adapter v2; the predecessor is unchanged.
        Entry(
            COLD_PLATE_CHALLENGE,
            "1.4",
            "AI-chip liquid cold plate (DEVELOPMENT periodic cell, backbone catalog, "
            "graph training adapter v2, allowlist v7, law-safe output encoding)",
            IMPLEMENTED,
            "launch",
            "carbonphysicsai/Carbon#342",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch CPU practice of Carbon's tested catalog backbones, or "
                    "JAX CPU practice of your own graph by Carbon's graph training "
                    "adapter v2, in the isolated C-03 CPU worker; exact public TRAIN "
                    "and recipe bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _graph_route(_cold_plate_describe_catalog, COLD_PLATE_CHALLENGE, "1.4"),
            None,
        ),
        # Pool grade (`scoring.pool_exam`): 1.4's construction and kit material; the exam is the pool grader's.
        Entry(
            COLD_PLATE_CHALLENGE,
            "1.5",
            "AI-chip liquid cold plate (DEVELOPMENT periodic cell, pool-graded exam, backbone catalog, graph training adapter v2, allowlist v8, law-safe output encoding)",
            _pool_status(COLD_PLATE_CHALLENGE, "1.5"),
            "launch",
            "carbonphysicsai/Carbon#342",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch CPU practice of Carbon's tested catalog backbones, or "
                    "JAX CPU practice of your own graph by Carbon's graph training "
                    "adapter v2, in the isolated C-03 CPU worker; exact public TRAIN "
                    "and recipe bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _graph_route(_cold_plate_describe_catalog, COLD_PLATE_CHALLENGE, "1.5"),
            None,
        ),
        # OWNER-COOLING-HOTSPOT-GATE-DROP-01; unpicked constants keep it RESERVED.
        Entry(
            COLD_PLATE_CHALLENGE,
            "1.6",
            "AI-chip liquid cold plate (DEVELOPMENT periodic cell, pool-graded exam, hotspot response correction, backbone catalog, graph training adapter v2, allowlist v8, law-safe output encoding)",
            _pool_status(COLD_PLATE_CHALLENGE, "1.6"),
            "launch",
            "carbonphysicsai/Carbon#342",
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch CPU practice of Carbon's tested catalog backbones, or "
                    "JAX CPU practice of your own graph by Carbon's graph training "
                    "adapter v2, in the isolated C-03 CPU worker; exact public TRAIN "
                    "and recipe bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _graph_route(_cold_plate_describe_catalog, COLD_PLATE_CHALLENGE, "1.6"),
            None,
        ),
        # F08 (Ribbed Bracket) 1.4 and F02 (Burst Thermal) 2.3, direct-recipe
        # only (`carbon.direct_campaign`): Carbon's tested backbones by catalog
        # id, or a graph trained by Carbon's registered graph training adapter;
        # no Level 0 strategy compiler. Each catalog is empty until an entry is
        # tested, and until then the campaign refuses to start.
        Entry(
            "f08-ribbed-bracket",
            "1.4",
            "Ribbed Bracket (F08, DEVELOPMENT, backbone catalog and graph training "
            "adapter, allowlist v7)",
            IMPLEMENTED,
            LAUNCH_PENDING_READINESS,
            None,
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch CPU practice of Carbon's tested catalog backbones, or "
                    "of a graph by Carbon's graph training adapter, in the isolated "
                    "C-03 CPU worker; exact public TRAIN and recipe bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _f08_direct,
            None,
        ),
        # Graph route v2 (`challenge_kit.version_registry`): the predecessor
        # plus Carbon's graph training adapter v2; the predecessor is unchanged.
        Entry(
            "f08-ribbed-bracket",
            "1.5",
            "Ribbed Bracket (F08, DEVELOPMENT, backbone catalog and graph training "
            "adapter v2, allowlist v7)",
            IMPLEMENTED,
            LAUNCH_PENDING_READINESS,
            None,
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch CPU practice of Carbon's tested catalog backbones, or "
                    "JAX CPU practice of your own graph by Carbon's graph training "
                    "adapter v2, in the isolated C-03 CPU worker; exact public TRAIN "
                    "and recipe bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _graph_route(
                _direct_describe("f08-ribbed-bracket"), "f08-ribbed-bracket", "1.5"
            ),
            None,
        ),
        # Pool grade (`scoring.pool_exam`): 1.5's construction and kit material; the
        # exam is the pool grader's. Its constants are not yet registered (HUMAN_INPUT).
        Entry(
            "f08-ribbed-bracket",
            "1.6",
            "Ribbed Bracket (F08, DEVELOPMENT, pool-graded exam, backbone catalog and "
            "graph training adapter v2, allowlist v8)",
            _pool_status("f08-ribbed-bracket", "1.6"),
            LAUNCH_PENDING_READINESS,
            None,
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch CPU practice of Carbon's tested catalog backbones, or "
                    "JAX CPU practice of your own graph by Carbon's graph training "
                    "adapter v2, in the isolated C-03 CPU worker; exact public TRAIN "
                    "and recipe bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _graph_route(
                _direct_describe("f08-ribbed-bracket"), "f08-ribbed-bracket", "1.6"
            ),
            None,
        ),
        Entry(
            "f08-ribbed-bracket",
            "1.7",
            "Ribbed Bracket (F08, DEVELOPMENT, pool-graded exam, backbone catalog and "
            "graph training adapter v2, allowlist v8)",
            _pool_status("f08-ribbed-bracket", "1.7"),
            LAUNCH_PENDING_READINESS,
            None,
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch CPU practice of Carbon's tested catalog backbones, or "
                    "JAX CPU practice of your own graph by Carbon's graph training "
                    "adapter v2, in the isolated C-03 CPU worker; exact public TRAIN "
                    "and recipe bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _graph_route(
                _direct_describe("f08-ribbed-bracket"), "f08-ribbed-bracket", "1.7"
            ),
            None,
        ),
        Entry(
            "f02",
            "2.3",
            "Burst Thermal (F02, DEVELOPMENT, backbone catalog and graph training "
            "adapter, allowlist v7)",
            IMPLEMENTED,
            LAUNCH_PENDING_READINESS,
            None,
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch CPU practice of Carbon's tested catalog backbones, or "
                    "of a graph by Carbon's graph training adapter, in the isolated "
                    "C-03 CPU worker; exact public TRAIN and recipe bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _f02_direct,
            None,
        ),
        # Battery 2.2 is not served (OWNER-BATTERY-OUT-OF-LAUNCH-01).
        # Graph route v2 (`challenge_kit.version_registry`): the predecessor
        # plus Carbon's graph training adapter v2; the predecessor is unchanged.
        Entry(
            "f02",
            "2.4",
            "Burst Thermal (F02, DEVELOPMENT, backbone catalog and graph training "
            "adapter v2, allowlist v7)",
            IMPLEMENTED,
            LAUNCH_PENDING_READINESS,
            None,
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch CPU practice of Carbon's tested catalog backbones, or "
                    "JAX CPU practice of your own graph by Carbon's graph training "
                    "adapter v2, in the isolated C-03 CPU worker; exact public TRAIN "
                    "and recipe bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _graph_route(_direct_describe("f02"), "f02", "2.4"),
            None,
        ),
        # Pool grade (`scoring.pool_exam`): 2.4's construction; the exam is the pool grader's.
        Entry(
            "f02",
            "2.5",
            "Burst Thermal (F02, DEVELOPMENT, pool-graded exam, backbone catalog and graph training adapter v2, allowlist v8)",
            _pool_status("f02", "2.5"),
            LAUNCH_PENDING_READINESS,
            None,
            (
                ExecutionProfile(
                    CPU_RESEARCH,
                    "PyTorch CPU practice of Carbon's tested catalog backbones, or "
                    "JAX CPU practice of your own graph by Carbon's graph training "
                    "adapter v2, in the isolated C-03 CPU worker; exact public TRAIN "
                    "and recipe bytes staged",
                    "torch-cpu/isolated-carrier",
                    torch_carrier,
                ),
                catalog_gpu,
            ),
            _graph_route(_direct_describe("f02"), "f02", "2.5"),
            None,
        ),
        Entry(
            "photonic-coupler",
            None,
            "Photonic coupler (reserved)",
            RESERVED,
            "launch",
            "carbonphysicsai/Carbon#345",
        ),
        Entry(
            "power-magnetics",
            None,
            "Power magnetics (deferred portfolio candidate)",
            DEFERRED,
            "deferred",
            "carbonphysicsai/Carbon#343",
        ),
        Entry(
            "airfoil",
            None,
            "Airfoils (deferred portfolio candidate)",
            DEFERRED,
            "deferred",
            "carbonphysicsai/Carbon#346",
        ),
    )


def entries():
    return _entries()


def compiler_for(challenge_id):
    """The exact Challenge compiler, with no fallback to another Challenge."""
    matches = [entry for entry in _entries() if entry.challenge_id == challenge_id]
    if not matches or matches[0].compile_strategy is None:
        raise LookupError(f"no compiler for Challenge {challenge_id!r}")
    return matches[0].compile_strategy


def _matching_entries(challenge_id, version):
    if type(challenge_id) is not str:
        raise UnknownChallenge("a challenge id string is required")
    if is_development_variant(challenge_id) or is_development_variant(version):
        raise DevelopmentVariantNotServed("a development-only variant is never served")
    matches = [e for e in _entries() if e.challenge_id == challenge_id]
    if not matches:
        raise UnknownChallenge(f"no Challenge {challenge_id!r} is registered")
    return matches


def _unsupported_version(challenge_id, version, matches):
    versions = ", ".join(str(e.version) for e in matches)
    return UnsupportedVersion(
        f"{challenge_id} is registered at version {versions}, not {version!r}"
    )


def published_description(challenge_id, version):
    """The existing public exam block for an exact registered identity.

    Publication is independent of execution readiness. This metadata supplies
    no profile, host capability or admission; `_find` still owns those refusals.
    """
    from carbon.challenge_registry import published_exam

    matches = _matching_entries(challenge_id, version)
    exact = [e for e in matches if e.version == version]
    if not exact:
        raise _unsupported_version(challenge_id, version, matches)
    entry = exact[0]
    return _json(
        {
            "challenge_id": entry.challenge_id,
            "version": entry.version,
            "published_exam": published_exam.for_version(
                entry.challenge_id, entry.version
            ),
        }
    )


def _find(challenge_id, version):
    matches = _matching_entries(challenge_id, version)
    # A Challenge may register several versions; the exact one is served.
    exact = [e for e in matches if e.version == version]
    entry = exact[0] if exact else matches[0]
    if entry.status == RETIRED:
        raise ChallengeRetired(f"{challenge_id} is retired from the research path")
    if entry.status == DEFERRED:
        raise ChallengeDeferred(f"{challenge_id} is a deferred portfolio candidate")
    if entry.status == RESERVED:
        raise ChallengeNotImplemented(
            f"{challenge_id} is a reserved launch Challenge ({entry.tracking})"
        )
    if version != entry.version:
        raise _unsupported_version(challenge_id, version, matches)
    return entry


def resolve(challenge_id, version, profile, *, host=None):
    """The entry for an exact (id, version, profile) usable on `host`.

    With `host=None` only implementation is checked: that is what a record
    or a validator needs. A door that is about to run work passes the host.
    """
    entry = _find(challenge_id, version)
    chosen = [p for p in entry.profiles if p.name == profile]
    if not chosen:
        raise ProfileUnavailable(f"{challenge_id} has no execution profile {profile!r}")
    if host is not None:
        missing = host.missing(chosen[0])
        if missing:
            raise ProfileUnavailable(
                f"{profile} is implemented but not usable here: "
                + ", ".join(missing)
                + " missing"
            )
    return entry, chosen[0]


#: The portfolios whose IMPLEMENTED Challenges a miner is offered: the Challenges page, the launch
#: wizard and the MCP list all follow this one rule. Anything else that is implemented (Battery,
#: out of the launch set) is kept for history and reference and is not offered.
OFFERED_PORTFOLIOS = ("launch", LAUNCH_PENDING_READINESS)


def is_offered(summary) -> bool:
    """Whether a catalog entry (an `Entry.summary` dict) is OFFERED to a miner.

    An implemented Challenge outside the offered portfolios is not offered; one that is not
    implemented (RESERVED, DEFERRED, RETIRED) is listed with its status and never reads as READY.
    """
    return (
        summary["status"] != IMPLEMENTED or summary["portfolio"] in OFFERED_PORTFOLIOS
    )


def offered_catalog(host=None):
    """`catalog` for a miner's eyes: the entries `is_offered` refuses are left out."""
    document = catalog(host)
    document["challenges"] = [c for c in document["challenges"] if is_offered(c)]
    return document


def catalog(host=None):
    """Every registered Challenge, including the ones that cannot be selected."""
    host = host if host is not None else HostFacts.observe()
    return _json(
        {
            "schema": CATALOG_SCHEMA,
            "challenges": [e.summary(host) for e in _entries()],
            "selection": (
                "Select by exact challenge_id and version plus a profile. There is "
                "no default Challenge and no fallback."
            ),
            "authority": "discovery grants no authority",
        }
    )


def describe(challenge_id, version, *, host=None):
    """One Challenge's full description, or a typed refusal."""
    from carbon.challenge_kit.standard import public_provisions
    from carbon.challenge_registry import published_exam

    entry = _find(challenge_id, version)
    host = host if host is not None else HostFacts.observe()
    return _json(
        {
            "schema": DESCRIPTION_SCHEMA,
            **entry.summary(host),
            **entry.describe(),
            "provisions": public_provisions(entry.challenge_id),
            "published_exam": published_exam.for_version(
                entry.challenge_id, entry.version
            ),
            "how_to_request_unsupported": CAPABILITY_REQUEST,
        }
    )


def _json(document):
    """Plain, finite JSON: what every door can carry unchanged."""
    return json.loads(json.dumps(document, allow_nan=False))
