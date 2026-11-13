"""The one registered source of each Challenge's KOTH rule (KOTH-TAKEOVER-RULE-01).

`scripts/validator_host_classes/koth_rebuild_noise.json` holds each Challenge's registered rebuild noise,
`{value, measurement_digest}`, once its measurement record has been reviewed.
A Challenge absent from it has none: the comparator then decides UNAVAILABLE
and the private-exam ladder steps at eta. The KOTH comparator and the Ladder
both read this file, so the margin and the feedback step can never disagree.
Changing it is a reviewed, reserved change (rewards and what miners see).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from carbon.challenge_validator import registry_version
from carbon.challenge_validator.bank_promotion import COMPARATOR_SCHEMA
from carbon.challenge_validator.interface import is_digest

#: The registered margins live OUTSIDE `carbon/` (beside the host-class records): the worker image's source digest is the
#: git listing of the build inputs, `carbon/` among them, so a margin write inside it would move the image id and with it
#: every pack, copy and binding. Only the host reads this file; nothing in a worker container does.
REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "koth_rebuild_noise.json"
)
SCHEMA = "carbon.koth.rebuild-noise-registry.v1"
#: The registered crown FLOORS of exams whose pack carries none (Motor 1.8: V2C's option B, 13 Nov), host-read data beside
#: the margins for the same reason (a measured number is registered without touching any code).
FLOORS = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "crown_floor.json"
)
FLOOR_SCHEMA = "carbon.crown.floor-registry.v1"
_FLOOR_ENTRY = {
    "challenge",
    "version",
    "epoch",
    "evaluation_pack_digest",
    "value",
    "measurement_digest",
    "rebuild_noise_measurement_digest",
    "crown_margin_measurement_digest",
}


class RegistryInvalid(ValueError):
    """The registry file is not exactly the registered shape."""


def _load(path=REGISTRY):
    document = json.loads(Path(path).read_bytes())
    if (
        type(document) is not dict
        or set(document) != {"schema", "challenges"}
        or document["schema"] != SCHEMA
        or type(document["challenges"]) is not dict
    ):
        raise RegistryInvalid("koth_registry_invalid")
    from carbon.challenge_validator.exam_cap import registered_challenges

    known = registered_challenges()
    for challenge, noise in document["challenges"].items():
        if (
            # A plain lookup would silently ignore a misspelled id: refuse it ("<id> <version>" is a versioned entry).
            not registry_version.known_key(challenge, known)
            or type(noise) is not dict
            or set(noise) - {"control"} != {"value", "measurement_digest"}
            or type(noise["value"]) not in (int, float)
            or not math.isfinite(noise["value"])
            # Never 0: an all-equal measurement registers the total's resolution.
            or not noise["value"] > 0
            or not is_digest(noise["measurement_digest"])
            or ("control" in noise and not _control_ok(noise["control"]))
        ):
            raise RegistryInvalid("koth_registry_invalid")
    return document["challenges"]


CONTROL_BASES = ("bit_identical", "within_noise")


def _control_ok(control):
    """The control the recal registered beside a Challenge's noise (Validator V7 rulings, codex-queue/reports/VALIDATOR_V7_RULINGS_20261029.md): a panel
    member that trains on the GPU, its reference total and grade fingerprint, how it is compared, and the evaluation
    pack (or pack-set key) they were measured on: a control runs only on that exam, since a rotation changes both.
    """
    return (
        type(control) is dict
        and set(control)
        == {
            "entry_id",
            "reference_total",
            "reference_fingerprint",
            "control_basis",
            "evaluation_pack_digest",
        }
        and is_digest(control["entry_id"])
        and is_digest(control["evaluation_pack_digest"])
        and type(control["reference_total"]) in (int, float)
        and math.isfinite(control["reference_total"])
        and is_digest(control["reference_fingerprint"])
        and control["control_basis"] in CONTROL_BASES
    )


def rebuild_noise(challenge_id, *, path=REGISTRY, version=None):
    """The Challenge's registered `{value, measurement_digest}`, or None. A version's own entry
    (``"<id> <version>"``) is read first, then the Challenge id (`registry_version`)."""
    noise = registry_version.find(_load(path), challenge_id, version)
    return None if noise is None else {k: v for k, v in noise.items() if k != "control"}


def control(challenge_id, *, path=REGISTRY, version=None):
    """The Challenge's registered control `{entry_id, reference_total, reference_fingerprint, control_basis,
    evaluation_pack_digest}`, or None: with none, a beyond-tolerance repeat is FAILED_INFRA, as before (fail closed).
    """
    noise = registry_version.find(_load(path), challenge_id, version)
    found = None if noise is None else noise.get("control")
    return None if found is None else dict(found)


def _load_floors(path=FLOORS):
    """The registered floors, one per exact (challenge, version, epoch, evaluation pack digest); the shape is closed."""
    document = json.loads(Path(path).read_bytes())
    if (
        type(document) is not dict
        or set(document) != {"schema", "floors"}
        or document["schema"] != FLOOR_SCHEMA
        or type(document["floors"]) is not list
    ):
        raise RegistryInvalid("crown_floor_registry_invalid")
    from carbon.challenge_validator.exam_cap import registered_challenges

    known = registered_challenges()
    seen = set()
    for entry in document["floors"]:
        if (
            type(entry) is not dict
            or set(entry) != _FLOOR_ENTRY
            # a misspelled id would silently match nothing: refuse it (as the noise registry does)
            or entry["challenge"] not in known
            or not all(type(entry[k]) is str and entry[k] for k in ("version", "epoch"))
            or not all(
                is_digest(entry[k])
                for k in (
                    "evaluation_pack_digest",
                    "measurement_digest",
                    "rebuild_noise_measurement_digest",
                    "crown_margin_measurement_digest",
                )
            )
            or type(entry["value"]) not in (int, float)
            or not math.isfinite(entry["value"])
            or not 0 <= entry["value"] <= 1
        ):
            raise RegistryInvalid("crown_floor_registry_invalid")
        key = (
            entry["challenge"],
            entry["version"],
            entry["epoch"],
            entry["evaluation_pack_digest"],
        )
        if key in seen:
            raise RegistryInvalid("crown_floor_registry_invalid")
        seen.add(key)
    return document["floors"]


def registered_floor(
    challenge_id, exam, *, path=FLOORS, noise_path=REGISTRY, margin_path=None
):
    """The crown floor registered for exactly this exam, or None (UNAVAILABLE downstream, never a default).

    ``exam`` is ``{"version", "epoch", "evaluation_pack_digest"}``: the version and menu epoch being graded and the digest
    of the exact sealed evaluation pack. A floor is the baseline's total on THAT exam at THAT epoch, so another pack, epoch
    or version finds nothing. Each entry also names the rebuild-noise and crown-margin measurements it was registered
    beside: a floor is found only while the Challenge's registered noise and margin are those very measurements, so a
    crown can never be decided on a floor measured on 1.8 against a noise or margin that was not (V2C must-have 5).
    """
    if exam is None:
        return None
    from carbon.challenge_validator import crown_average

    rule = crown_average.load_rule(
        crown_average.REGISTRY if margin_path is None else margin_path
    )
    # the noise and margin of THIS version (its own entry, else the Challenge's: `registry_version`)
    version = exam["version"]
    noise = rebuild_noise(challenge_id, path=noise_path, version=version)
    margin_digest = rule.margin_digest_for(challenge_id, version)
    if (
        noise is None
        or margin_digest is None
        or rule.margin_for(challenge_id, version) is None
    ):
        return None
    for entry in _load_floors(path):
        if (
            entry["challenge"],
            entry["version"],
            entry["epoch"],
            entry["evaluation_pack_digest"],
        ) == (
            challenge_id,
            exam["version"],
            exam["epoch"],
            exam["evaluation_pack_digest"],
        ):
            if (
                entry["rebuild_noise_measurement_digest"] != noise["measurement_digest"]
                or entry["crown_margin_measurement_digest"] != margin_digest
            ):
                return None
            return float(entry["value"])
    return None


def _refuse_practice(*documents):
    """A practice document is feedback on the public bank, never a grade: its pack or
    definition cannot make a comparator (practice dual v2, Validator condition)."""
    for document in documents:
        if type(document) is dict and (
            document.get("scope") == "PUBLIC_PRACTICE_FEEDBACK"
            or document.get("population") == "PRACTICE_PUBLIC_BANK"
        ):
            raise RegistryInvalid("practice_is_not_a_grade")


def comparator(
    challenge_id,
    score_pack,
    accuracy_definition,
    *,
    path=REGISTRY,
    exam=None,
    floors=FLOORS,
    margins=None,
    version=None,
):
    """The DEVELOPMENT comparator for one Challenge and its selected pack:
    the pack's score digest, its leg-minimum source entries (never contenders)
    and the registered rebuild noise (None means UNAVAILABLE).

    ``exam`` is ``{"version", "epoch", "evaluation_pack_digest"}`` of the exam being graded, or None (the default: the
    floor then comes from the pack alone, exactly as before). With it, a floor registered for exactly that exam
    (`registered_floor`) stands in when the pack carries none; the pack's own floor always wins.
    """
    from carbon.scoring.physical_dual_pack import minimum_source_entry_ids

    _refuse_practice(score_pack, accuracy_definition)
    return {
        "schema": COMPARATOR_SCHEMA,
        "scope": "DEVELOPMENT",
        "challenge": challenge_id,
        "score_pack_digest": score_pack["pack_digest"],
        "rebuild_noise": rebuild_noise(challenge_id, path=path, version=version),
        "ties": "incumbent_keeps",
        "minimum_source_entry_ids": minimum_source_entry_ids(accuracy_definition),
        "baseline_total": baseline_total(
            score_pack,
            registered_floor(
                challenge_id, exam, path=floors, noise_path=path, margin_path=margins
            ),
        ),
    }


def comparator_for_set(
    challenge_id, score_packs, accuracy_definitions, *, path=REGISTRY, version=None
):
    """The DEVELOPMENT comparator for a Challenge version's whole pack set: the
    score digest of the set's packs, the union of their leg-minimum source
    entries, and the baseline graded on the same set (the equal-weight mean of
    each batch's baseline total; one batch without one makes it None, which is
    UNAVAILABLE downstream, never a partial mean)."""
    from carbon.challenge_validator.interface import digest
    from carbon.scoring.physical_dual_pack import minimum_source_entry_ids

    if (
        type(score_packs) not in (list, tuple)
        or not score_packs
        or len(score_packs) != len(accuracy_definitions)
    ):
        raise ValueError("a score pack and accuracy definition for every batch")
    _refuse_practice(*score_packs, *accuracy_definitions)
    totals = [baseline_total(pack) for pack in score_packs]
    sources = sorted(
        {
            entry
            for definition in accuracy_definitions
            for entry in minimum_source_entry_ids(definition)
        }
    )
    return {
        "schema": COMPARATOR_SCHEMA,
        "scope": "DEVELOPMENT",
        "challenge": challenge_id,
        "score_pack_digest": digest(
            sorted(pack["pack_digest"] for pack in score_packs)
        ),
        "rebuild_noise": rebuild_noise(challenge_id, path=path, version=version),
        "ties": "incumbent_keeps",
        "minimum_source_entry_ids": sources,
        "baseline_total": (
            None if any(t is None for t in totals) else math.fsum(totals) / len(totals)
        ),
    }


def baseline_total(score_pack, registered=None):
    """The crown floor: Carbon's baseline, the unpaid starting king the first crown must beat by the margin
    (OWNER-FIRST-CROWN-BEATS-BASELINE-01).

    ``registered`` is a floor registered for this exact exam (`registered_floor`), or None. The pack's own total (below)
    always wins; a registered floor that disagrees with it is a refusal, never a pick; with no pack total the registered
    floor stands in; with neither the result is None (UNAVAILABLE downstream, never a default).

    Normally the total of a model sitting exactly on the pack's leg minimums (None when the pack has no minimums). A pack
    that carries ``baseline_floor_total`` (OWNER-EXAM-VALUE-PICKS-01, option B) uses THAT instead: the floor is separate
    from the minimums, which stay untouched; it can never sit below the minimums-derived total (a refusal). Absent, this is
    exactly what it always was."""
    own = _pack_floor(score_pack)
    if registered is None:
        return own
    if own is None:
        return float(registered)
    if not math.isclose(own, registered, rel_tol=0, abs_tol=1e-12):
        raise RegistryInvalid("registered_floor_differs_from_the_packs_own")
    return own


def _pack_floor(score_pack):
    """The pack's own crown floor: its ``baseline_floor_total`` or, with none, the minimums-derived total."""
    derived = minimums_total(score_pack)
    if "baseline_floor_total" not in score_pack:
        return derived
    floor = score_pack["baseline_floor_total"]
    if (
        type(floor) not in (int, float)
        or isinstance(floor, bool)
        or not math.isfinite(floor)
        or not 0 <= floor <= 1
        or (derived is not None and floor < derived - 1e-12)
    ):
        raise RegistryInvalid("baseline_floor_invalid")
    return float(floor)


def minimums_total(score_pack):
    """The total of a model sitting exactly on the pack's leg minimums, or None when the pack has no minimums."""
    legs = score_pack["legs"]
    a, d = legs["A"]["minimum"], legs["D"]["minimum"]
    if a is None or d is None:
        return None
    w = score_pack["value_weight"]
    if score_pack["combination"] == "weighted_arithmetic_mean":
        return (1 - w) * a + w * d
    if a == 0 or d == 0:
        return 0.0
    return min(a, d) * math.exp((1 - w) * math.log(a) + w * math.log(d))
