"""The F08 1.4 / F02 2.3 direct campaigns leave Motor and Cooling as they were.

Their research parts are fingerprinted with the values computed on the base
these campaigns were built on (97205feca); the practice provenances and
backends a freeze and a correction read are exactly the base's plus the two
new Challenges' own (the version-keyed campaigns of Challenges with no
id-level campaign)."""

from __future__ import annotations

import hashlib
import json

import pytest

from carbon import measurement
from carbon.challenge_registry import campaigns
from carbon.cold_plate import research as cooling
from carbon.motor import research as motor

#: (module, version, catalog version) -> fingerprint on 97205feca.
PINNED = {
    (motor, "1.0", False): (
        "sha256:ced58f072aeb696f88b55aea955570f862a85dfa2b44a0daaadfd8d221dc5753"
    ),
    (motor, "1.2", True): (
        "sha256:000cecc65f20cd9aa18b6c3983d13bde5bd01fc70a865793a1b9d79e24a1684c"
    ),
    (motor, "1.3", True): (
        "sha256:fd2acb67499c4dd4759640ff404f1ebb015318fdbe13a7b7dd8d5e606fc94914"
    ),
    (cooling, "1.0", False): (
        "sha256:e4b9ab4b90f4a164753c279dc3e35715a68b3855d534d24de43c40bd219e2235"
    ),
    (cooling, "1.2", True): (
        "sha256:fede2240818dcc5c2526a63364f4eddb88e8740e8844115e0171f923664be25e"
    ),
}
BASE_PROVENANCES = frozenset(
    {"BATTERY_PUBLIC_PRACTICE", "COLD_PLATE_PUBLIC_PRACTICE", "MOTOR_PUBLIC_PRACTICE"}
)
BASE_BACKENDS = frozenset({"jax", "numpy", "pytorch"})


def fingerprint(parts, *, catalog):
    """The parts' contract, population, sampling and measurement identities and
    their documents. A catalog version's catalog-derived documents are left
    out: they move whenever a tested entry is added, by design."""
    value = {
        "key": [parts.key.challenge_id, parts.key.version],
        "assembly": parts.contracts.assembly.to_ref().content_digest,
        "catalog": parts.contracts.catalog.to_ref(
            candidate_assembly=parts.contracts.assembly
        ).content_digest,
        "population": parts.population.to_ref().content_digest,
        "sampling": parts.sampling.to_ref().content_digest,
        "measurement": measurement.measurement_ref(parts.measurements).content_digest,
        "score": parts.score_document,
        "practice_scope": parts.practice_scope,
        "disclosure": parts.disclosure.decode(),
        "implementation_files": sorted(p.name for p in parts.implementation_files),
    }
    if not catalog:
        value.update(
            strategy_schema=parts.strategy_schema,
            scaffold_catalog=parts.scaffold_catalog,
            scaffold_strategy=parts.scaffold_strategy,
        )
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    "module, version, catalog",
    list(PINNED),
    ids=lambda v: getattr(v, "__name__", str(v)),
)
def test_motor_and_cooling_research_parts_are_unchanged(module, version, catalog):
    parts = module.challenge_parts(version)
    assert fingerprint(parts, catalog=catalog) == PINNED[(module, version, catalog)]


def test_the_provenances_and_backends_are_the_bases_plus_the_new_challenges():
    assert campaigns.practice_provenances() == BASE_PROVENANCES | {
        "F08_PUBLIC_PRACTICE",
        "F02_PUBLIC_PRACTICE",
    }
    assert campaigns.implemented_backends() == BASE_BACKENDS | {"torch_cpu"}
    # The id-level campaigns alone still give exactly the base's sets: Motor's
    # and Cooling's catalog versions reuse their id-level provenance and add
    # nothing.
    ids = campaigns._campaigns()
    assert (
        frozenset(build().practice_provenance for build in ids.values())
        == BASE_PROVENANCES
    )
    assert (
        frozenset(b for build in ids.values() for b in build().backends)
        == BASE_BACKENDS
    )
    for (challenge_id, _), build in campaigns._versioned_campaigns().items():
        if challenge_id in ids:
            assert (
                build().practice_provenance == ids[challenge_id]().practice_provenance
            )


def test_the_research_campaign_reads_the_same_sets():
    from carbon.development_session.research_campaign import practice_provenances

    assert practice_provenances() == (
        frozenset({"REAL_JAX_PUBLIC_PRACTICE"}) | campaigns.practice_provenances()
    )
