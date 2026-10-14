"""S4: DEVELOPMENT capability promotion records and an empty application set.

The owner's promotion bar is undefined. References record provenance, never
prove measurement/sign-off. No nonempty set or promotion can be applied until
a prospectively registered owner policy supplies that missing authority.
Current contracts and all historical pins are unchanged. Pure-data import.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REGISTRY = Path(__file__).with_suffix(".json")
REGISTRY_SCHEMA = "carbon.construction-promotions.v1"
RECORD_SCHEMA = "carbon.construction-capability-promotion.v1"
TARGET = "NEXT_COMBINED_CONTRACT_BASE"
_SHA = re.compile(r"sha256:[0-9a-f]{64}")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]*")
_CAPABILITY = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")


class PromotionRefused(ValueError):
    def __init__(self, code, field=None):
        super().__init__(code)
        self.code, self.field = code, field


def _refuse(code="promotion_record_malformed", field=None):
    raise PromotionRefused(code, field)


def _shape(value, keys, field):
    if type(value) is not dict or set(value) != set(keys):
        _refuse(field=field)


def _sha(value, field):
    if type(value) is not str or _SHA.fullmatch(value) is None:
        _refuse(field=field)


def _reference(value, field):
    _shape(value, {"record", "digest"}, field)
    name = value["record"]
    if (
        type(name) is not str
        or _ID.fullmatch(name) is None
        or name in {"HUMAN_INPUT", "TODO"}
    ):
        _refuse(field=field + "/record")
    _sha(value["digest"], field + "/digest")


def record(value):
    """Validate a proposed record; this returns no promotion authority.

    Source identities are verified against immutable registered composition
    metadata and public expansion history. Evidence/decision blobs are not
    fetched or adjudicated: whose sign-off/which measurements suffice is the
    still-unset promotion bar. A copied receipt cannot approve itself.
    """
    from . import composition_registry as compositions
    from . import expansion_record

    _shape(
        value,
        {
            "schema",
            "challenge",
            "capability",
            "source",
            "evidence",
            "decision",
            "target",
        },
        "/",
    )
    if value["schema"] != RECORD_SCHEMA or value["target"] != TARGET:
        _refuse(field="/schema_or_target")
    if type(value["challenge"]) is not str:
        _refuse(field="/challenge")
    capability = value["capability"]
    if type(capability) is not str or _CAPABILITY.fullmatch(capability) is None:
        _refuse(field="/capability")
    source = value["source"]
    _shape(source, {"base_contract_digest", "composition_digest"}, "/source")
    for name, digest in source.items():
        _sha(digest, "/source/" + name)
    document = compositions.document(source["composition_digest"])
    if (
        document is None
        or document["challenge"] != value["challenge"]
        or document["base_contract"]["digest"] != source["base_contract_digest"]
    ):
        _refuse("promotion_source_unregistered", "/source")
    history = expansion_record.records(value["challenge"])
    matching = [
        row
        for row in history
        if row.get("sequence") == document["base_contract"]["record_sequence"]
        and row.get("contract_digest") == source["base_contract_digest"]
        and expansion_record.digest_of(row.get("contract_document"))
        == source["base_contract_digest"]
    ]
    if len(matching) != 1:
        _refuse("promotion_source_unregistered", "/source/base_contract_digest")
    evidence = value["evidence"]
    if type(evidence) is not list or not evidence:
        _refuse(field="/evidence")
    for ref in evidence:
        _reference(ref, "/evidence")
    if len({(ref["record"], ref["digest"]) for ref in evidence}) != len(evidence):
        _refuse("promotion_evidence_duplicate", "/evidence")
    _reference(value["decision"], "/decision")
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            _refuse("promotion_registry_malformed")
        result[key] = value
    return result


def _constant(_value):
    _refuse("promotion_registry_malformed")


def _empty_set():
    # Read each time. A previous empty result cannot hide a changed registry.
    try:
        value = json.loads(
            REGISTRY.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        _refuse("promotion_registry_unavailable")
    if (
        type(value) is not dict
        or set(value) != {"schema", "scope", "promotion_bar", "promotions"}
        or value["schema"] != REGISTRY_SCHEMA
        or value["scope"] != "DEVELOPMENT"
        or type(value["promotions"]) is not list
    ):
        _refuse("promotion_registry_malformed")
    # No caller/JSON flag, decision-shaped mapping, fixture or string registers
    # the missing policy. An actual future bar needs its own versioned loader.
    if value["promotion_bar"] is not None:
        _refuse("promotion_bar_unregistered", "/promotion_bar")
    if value["promotions"]:
        _refuse("promotion_bar_unset", "/promotions")
    return ()


def promoted():
    """The authenticated registered set; currently exactly empty."""
    return _empty_set()


def promote(value):
    """Refuse adoption while the owner bar is HUMAN_INPUT; never write pins."""
    record(value)
    _empty_set()
    _refuse("promotion_bar_unset", "/promotion_bar")


def base_contract(challenge):
    """Empty promotion is identity, including every capability/lane/bound."""
    from .capability_registry import contract

    _empty_set()
    return contract(challenge)


def composition_document(value):
    """Exact current or historical metadata, with no private L5 arm added."""
    from . import composition_registry as compositions

    _empty_set()
    document = compositions.document(value)
    if document is None:
        _refuse("promotion_source_unregistered", "/source/composition_digest")
    return document


def compile(strategy, composition=None, *, check_budget=True):
    """Operator/library helper; unchanged composed compiler after empty guard.

    This installs no served route or acceptance check. Existing callers own
    their required-health, transport and containment gates. The helper retains
    the compiler's budget default and does not turn metadata into acceptance.
    """
    _empty_set()
    from . import development_composition

    return development_composition.compile(
        strategy, composition, check_budget=check_budget
    )
