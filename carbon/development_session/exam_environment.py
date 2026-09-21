"""What a validator runs the exam under, published for miners to read.

A miner submits a declarative training strategy, not a trained checkpoint. The
validator reconstructs it and trains from scratch, so what the miner used to
arrive at the design does not matter - but what the design will be *run on* when
it is graded does, and they are entitled to know it before they submit.

That makes this a disclosure by Carbon rather than a constraint on miners.
Nothing here describes, restricts or grades the miner's own research hardware,
and reading it is not a step a miner has to complete before researching.

Every value is read from the constants the reconstruction path actually runs
under, never restated here as a literal. A number copied into a second place
drifts from the first, and a published exam environment that has quietly drifted
from the real one is worse than none: a miner would be reading a document
Carbon no longer honours. The prose authority is
`docs/development/VALIDATOR_EXAM_ENVIRONMENT.md`, which this projects.

Declared is not qualified. The backend profile's support status is owned by
MQ-008 under R0/R1/R2 at gate G4 and is unresolved; this reports that status and
does not resolve, soften or route around it. Nothing here is a tolerance, an
acceptance, or a claim that reconstruction reproduces across hosts - and the one
place it is known not to is disclosed below rather than omitted.
"""

from __future__ import annotations

from carbon.reconstruction import profile as reconstruction_profile
from carbon.reconstruction.worker import model as worker

SCHEMA = "carbon.public-validator-exam-environment.v1"

#: The authority this projects. Named so a reader can go to the source.
AUTHORITY = "docs/development/VALIDATOR_EXAM_ENVIRONMENT.md"

#: Declared by the authority document, not computed here.
#:
#: The one value in this module that is a literal rather than read from the
#: runtime, and deliberately so on both counts. There is no registry of
#: qualified backends to read: support is carried per R1 identity, and
#: comparison reports `BACKEND_UNSUPPORTED` while it is not `SUPPORTED`.
#: Deriving a status from the absence of a registry would be inventing one, so
#: the declared value is reported and attributed to the document above.
#:
#: It is also not imported from `carbon.reproducibility`, whose enum spells the
#: same word. B-E1 holds that a completed package does not reach into that one,
#: and borrowing a name for a value this module does not compute would buy
#: nothing and cross that boundary for decoration.
#: See `tests/invariants/test_be1_reproducibility_boundaries.py`.
DECLARED_SUPPORT = "UNRESOLVED"


def _containment() -> dict[str, object]:
    """The containment the worker is built to apply, as facts not promises."""
    return {
        "network": "none",
        "root_filesystem": "read-only",
        "capabilities": "all dropped",
        "user": f"{worker.WORKER_UID}:{worker.WORKER_GID}",
        "no_new_privileges": True,
        "seccomp": "docker-default",
        "restart_policy": "none",
        "worker_image": "PINNED_AND_BOUND_INTO_EVERY_LAUNCH",
    }


def _envelope() -> dict[str, object]:
    return {
        # Per launch. Until C-CORE-19 the cpuset was the literal "0,1", so two
        # reconstructions could never run at once on any host - both demanded
        # those exact cores. The cpuset is now resolved from the host, so a
        # validator working through a queue is no longer serialised by a string
        # literal. The per-launch quota below is unchanged.
        "concurrency_per_launch": 1,
        "concurrent_launches_possible": True,
        "cpu_count": worker.CPU_COUNT,
        "cpu_allocation": "QUOTA_FIXED_CPUSET_RESOLVED_FROM_HOST",
        "memory_bytes": worker.MEMORY_BYTES,
        "swap_bytes": worker.SWAP_BYTES,
        "pids_limit": worker.PIDS_LIMIT,
        "scratch_bytes": worker.SCRATCH_BYTES,
        "scratch_inodes": worker.SCRATCH_INODES,
        "output_bytes": worker.OUTPUT_BYTES,
        "output_members": worker.OUTPUT_MEMBERS,
        "productive_deadline_seconds": worker.PRODUCTIVE_DEADLINE_SECONDS,
        "graceful_cancellation_seconds": worker.GRACEFUL_CANCELLATION_SECONDS,
        "cleanup_confirmation_seconds": worker.CLEANUP_CONFIRMATION_SECONDS,
    }


def exam_environment() -> dict[str, object]:
    """The public, read-only description of the validator's exam environment.

    Safe for any audience: it carries pinned versions, a resource envelope and
    containment facts, and no seed, draw, case, protected material, credential
    or private path. There is nothing here a miner could use to reconstruct
    hidden evaluation state, because none of it is derived from any.
    """
    return {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "disclosure": "PUBLIC_READ_ONLY",
        "backend_profile": {
            "profile_id": worker.PROFILE_ID,
            "profile_version": worker.PROFILE_VERSION,
            "scope": worker.SCOPE,
            "backend": "jax-cpu",
            "environment_id": reconstruction_profile.ENVIRONMENT_ID,
            "environment_version": reconstruction_profile.ENVIRONMENT_VERSION,
            "environment_digest": reconstruction_profile.ENVIRONMENT_DIGEST,
        },
        "qualification": {
            "declared": True,
            "qualified": False,
            "backend_support": DECLARED_SUPPORT,
            "owner": "MQ-008 under R0/R1/R2 at gate G4, owned by SCI and SRE",
            "basis": "Declaring an environment is not qualifying it. Until MQ-008 qualifies a profile, comparison returns BACKEND_UNSUPPORTED.",
        },
        "pinned_dependencies": [
            {"name": name, "version": version, "identity": identity}
            for name, version, identity in reconstruction_profile.DEPENDENCY_SPECS
        ],
        "platform": {"operating_system": "linux", "architecture": "x86_64"},
        "precision": {
            "parameter_dtype": "float32",
            "complex_dtype": "complex64",
            "x64_enabled": False,
            "matmul_precision": "highest",
        },
        "resource_envelope": _envelope(),
        "containment": _containment(),
        "interfaces": {
            "input_digest": reconstruction_profile.INPUT_INTERFACE_DIGEST,
            "output_digest": reconstruction_profile.OUTPUT_INTERFACE_DIGEST,
        },
        "submission": {
            "accepted": "DECLARATIVE_TRAINING_STRATEGY",
            "not_accepted": [
                "TRAINED_CHECKPOINT",
                "MINER_COMPUTED_SCORE",
                "MINER_HARDWARE_CLAIM",
                "MINER_RESEARCH_RESULT_AS_EVIDENCE",
            ],
            "basis": "The validator reconstructs and trains the submitted strategy from scratch under this environment.",
        },
        # The point of publishing this, stated where a miner will read it.
        "miner_research_hardware": {
            "constrained_by_this_contract": False,
            "must_match_validator": False,
            "provider_prescribed": False,
            "basis": "A miner may research on any compute they choose, matching or not. This describes the exam, not an eligibility test. A validator likewise may run this environment with any provider.",
        },
        # Disclosed rather than omitted. A miner reading an exam environment is
        # entitled to know what it does and does not fix.
        "known_limitations": [
            {
                "id": "CPU_INSTRUCTION_SET_DIVERGENCE",
                "statement": "The pinned set does not determine the numerical result on its own. Under identical recorded identities, AVX2, AVX and SSE4_2 produced three distinct sets of weights, and every identity Carbon records was the same across all three.",
                "consequence": "Two validators running exactly this declared environment on different machines may compute different weights, and nothing in the record would distinguish them.",
                "status": "DISCLOSED_UNRESOLVED_OWNER_QUESTION",
                "evidence": ".agent/evidence/wave_c/c-core-19-cpu-determinism-across-configurations.md",
            }
        ],
        "not_established": [
            "SCIENTIFIC_QUALIFICATION_OF_THIS_ENVIRONMENT",
            "CROSS_HOST_REPRODUCIBILITY",
            "ANY_TOLERANCE_OR_ACCEPTANCE_THRESHOLD",
            "GPU_BACKEND_COVERAGE",
        ],
        # Measured under N2 and reported because it bears on what a miner can
        # infer from the envelope above: varying usable cores (1, 2, 4, 8) and
        # the memory ceiling (2, 4, 8 GiB), and running two simultaneous
        # reconstructions on disjoint cpusets, left the trained weights
        # byte-identical across eighteen runs. Sizing is therefore a cost and
        # throughput question on that evidence, not a reproducibility one - on
        # one host, one backbone, at two steps, which is the whole of it.
        "resource_sizing": {
            "affects_numerical_result": False,
            "basis": "N2: eighteen runs across core counts, memory ceilings and two simultaneous disjoint-cpuset runs produced byte-identical weights.",
            "scope_limit": "One host, one backbone, two training steps. Not a cross-host or general claim.",
            "evidence": ".agent/evidence/wave_c/c-core-19-host-resource-allocation.md",
        },
    }
