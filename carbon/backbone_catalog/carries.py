"""The cross-version pair rule for catalog entries (VALIDATOR_RC26_PAIR_STATE_RULING section 1;
V8_RULINGS section 12 item 3).

A version may offer another version's receipted entries (`version_registry`'s `catalog_entries_from`) only when the
two versions differ by identity alone. Each entry's pair-identity receipt binds the TRAIN and interface digests of the
version it was tested on; a successor whose interface document differs only in its own version label builds the same
model from the same inputs, so the receipt carries. Anything else is a refusal, never a silent carry:

- the two versions name the same TRAIN artifact;
- their public interface documents differ in no field but `/challenge/version` (a Challenge whose interface does not
  name its version differs in none: its digests are equal and the rule has nothing to show).

The diff is recomputed here from the served public documents every time, so a later change to either interface moves
the answer. It is an input-identity diff of the kit documents, not a diff of built states: the ruling allows no host
reruns. `scripts/dev/catalog_carry_report.py` writes the per-entry record.
"""

from __future__ import annotations

import functools

from .entries import CatalogRefused

#: The interface fields that may differ between a version and the version it carries entries from.
ALLOWED_INTERFACE_DIFF = frozenset({"/challenge/version"})


def _flat(value, prefix=""):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            out.update(_flat(item, f"{prefix}/{key}"))
        return out
    if isinstance(value, list):
        out = {}
        for index, item in enumerate(value):
            out.update(_flat(item, f"{prefix}[{index}]"))
        return out
    return {prefix: value}


def interface_document(challenge_id, version):
    from carbon.challenge_kit import physical_material

    return physical_material._public(challenge_id).interface_document(
        challenge_id, version
    )


def interface_diff(challenge_id, from_version, to_version):
    """The sorted paths at which the two versions' public interface documents differ."""
    left = _flat(interface_document(challenge_id, from_version))
    right = _flat(interface_document(challenge_id, to_version))
    return sorted(k for k in set(left) | set(right) if left.get(k) != right.get(k))


@functools.cache
def require_identity_only(challenge_id, version):
    """Refuse (`CatalogRefused`) unless every version ``version`` offers entries from differs from it by identity
    alone. Returns the per-version diffs for the record."""
    from carbon.challenge_kit.version_registry import find

    declared = find(challenge_id, version)
    found = {}
    for from_version in declared.catalog_entries_from if declared is not None else ():
        if from_version == version:
            continue
        source = find(challenge_id, from_version)
        if source is None or source.train != declared.train:
            raise CatalogRefused(
                "catalog_entry_unknown", f"carry from {from_version}: train differs"
            )
        diff = interface_diff(challenge_id, from_version, version)
        if not set(diff) <= ALLOWED_INTERFACE_DIFF:
            raise CatalogRefused(
                "catalog_entry_unknown",
                f"carry from {from_version}: interface differs beyond identity",
            )
        found[from_version] = diff
    return found


__all__ = ["ALLOWED_INTERFACE_DIFF", "interface_diff", "require_identity_only"]
