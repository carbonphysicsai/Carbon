"""Subset-repeat versions registered OUTSIDE code (new-exam prep #11, host side; v2 ruling 22 Nov 2026 00:12:09Z).

`subset_repeat_evidence` keeps the ONE code table of the versions graded by the keyed subset repeat
(`SUBSET_REPEAT_VERSIONS`, `PRODUCERS`, `STRATA`), and it is a Motor 1.8 producer file, so adding a version there would
move Motor 1.8's producer digest. A version registered from now on declares its subset repeat in its OWN
``version_overlay.json`` entry instead, inside its dispatch block's ``config``:

    "dispatch": {"module": ..., "sha256": ..., "config": {..., "subset_repeat": {
        "producer": "carbon.scoring.<its producer module>",
        "strata": {"<name>": {"source": "cohort" | "coverage_class" | "in_range_outputs" | "menu_task",
                              "selector": <str, or a list of output names for in_range_outputs>,
                              "every": <bool, optional>, "n": <int, required when every>}}}}}

The overlay entry's canonical sha256 is its registration digest (`version_overlay.entry_digest`), which the serving pack
binds, so a changed strata set is a different version identity and the old pack refuses: the same integrity as strata in
a producer file. This module refuses an entry whose canonical digest is not the INSTALLED entry digest. The promise (f, P,
strata names) stays in ``subset_repeat.json``, read by `subset_repeat_evidence.registered_promise` for any version, as
today. A version present in BOTH the 1.8 code table and the overlay refuses (``subset_repeat_version_in_both``).

This module is not in any live version's producer FILES; a version registered from now on lists it
(`NEW_VERSION_PRODUCER_FILES`). Motor 1.8's code tables are read, never changed. Worker-side opt-ins (compiled forward,
task wall) are out of scope here (v2: their own design note).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from carbon.scoring import subset_repeat_evidence as code

#: The producer file a version registered from now on lists for its subset-repeat definitions.
NEW_VERSION_PRODUCER_FILES = ("subset_repeat_registry.py",)
_SOURCES = frozenset({"cohort", "coverage_class", "in_range_outputs", "menu_task"})
_MODULE = re.compile(r"carbon\.scoring(\.[a-z_][a-z0-9_]*)+\Z")


class SubsetRegistryRefused(code.SubsetRepeatRefused):
    """A malformed, unbound or conflicting overlay subset-repeat entry (typed; the version is not served this way)."""


def _refuse(reason):
    raise SubsetRegistryRefused(reason)


def _installed_digest(challenge, version):
    from carbon.challenge_kit import version_overlay

    return version_overlay.entry_digest(challenge, version)


def _stratum(name, spec):
    if not (type(name) is str and name and name != code.SEALED_COHORT):
        _refuse("subset_repeat_overlay_stratum_name")
    if (
        type(spec) is not dict
        or not {"source", "selector"} <= set(spec)
        or set(spec) - {"source", "selector", "every", "n"}
        or spec["source"] not in _SOURCES
    ):
        _refuse("subset_repeat_overlay_stratum")
    selector = spec["selector"]
    if spec["source"] == "in_range_outputs":
        if not (
            type(selector) is list
            and selector
            and all(type(s) is str and s for s in selector)
            and len(set(selector)) == len(selector)
        ):
            _refuse("subset_repeat_overlay_selector")
        selector = tuple(selector)
    elif not (type(selector) is str and selector):
        _refuse("subset_repeat_overlay_selector")
    every = spec.get("every", False)
    n = spec.get("n")
    if (
        type(every) is not bool
        or (n is not None and (type(n) is not int or n < 1))
        or (every and n is None)
    ):
        _refuse("subset_repeat_overlay_stratum")
    return code.Stratum(spec["source"], selector, every, n)


def overlay_versions(path=None, *, installed_digest=None):
    """``{(challenge, version): {"producer": str, "strata": {name: Stratum}}}`` of the overlay entries that declare a
    subset repeat. Refuses (typed) a malformed, unbound or duplicated one; an absent overlay file declares none.
    """
    from carbon.challenge_kit import version_overlay

    source = Path(version_overlay.OVERLAY_PATH if path is None else path)
    if not source.exists():
        return {}
    try:
        document = json.loads(source.read_bytes())
    except (OSError, ValueError):
        _refuse("subset_repeat_overlay_unreadable")
    digest_of = _installed_digest if installed_digest is None else installed_digest
    found = {}
    for name, entry in ((document or {}).get("versions") or {}).items():
        if not isinstance(entry, dict):
            continue
        dispatch = entry.get("dispatch")
        config = dispatch.get("config") if isinstance(dispatch, dict) else None
        declared = config.get("subset_repeat") if isinstance(config, dict) else None
        if declared is None:
            continue
        key = (entry.get("challenge_id"), entry.get("version"))
        if name != f"{key[0]} {key[1]}":
            _refuse("subset_repeat_overlay_name")
        if key in code.SUBSET_REPEAT_VERSIONS:
            _refuse("subset_repeat_version_in_both")
        # an overlay that does not install (or does not add this version) binds nothing
        try:
            bound = digest_of(*key)
        except Exception:  # noqa: BLE001
            bound = None
        if bound != version_overlay.canonical_digest(entry):
            _refuse("subset_repeat_overlay_unbound")
        if (
            type(declared) is not dict
            or set(declared) != {"producer", "strata"}
            or type(declared["producer"]) is not str
            or not _MODULE.fullmatch(declared["producer"])
            or type(declared["strata"]) is not dict
            or not declared["strata"]
        ):
            _refuse("subset_repeat_overlay_entry")
        found[key] = {
            "producer": declared["producer"],
            "strata": {n: _stratum(n, s) for n, s in declared["strata"].items()},
        }
    return found


def versions(path=None, *, installed_digest=None):
    """Every subset-repeat version: the 1.8 code table plus the overlay's (disjoint; a version in both refuses)."""
    return code.SUBSET_REPEAT_VERSIONS | frozenset(
        overlay_versions(path, installed_digest=installed_digest)
    )


def is_subset_version(challenge, version, path=None, *, installed_digest=None) -> bool:
    return (challenge, version) in versions(path, installed_digest=installed_digest)


def producer_module(challenge, version, path=None, *, installed_digest=None):
    """The version's producer module (code table first, then the overlay), or None."""
    if (challenge, version) in code.PRODUCERS:
        return code.PRODUCERS[(challenge, version)]
    found = overlay_versions(path, installed_digest=installed_digest).get(
        (challenge, version)
    )
    return None if found is None else found["producer"]


def definitions(challenge, version, path=None, *, installed_digest=None):
    """The version's strata: Motor 1.8's from code (unchanged), a new version's from its overlay entry, else the typed
    ``subset_repeat_strata_undefined`` refusal (`subset_repeat_evidence.definitions`).
    """
    if (challenge, version) in code.STRATA:
        return code.definitions(challenge, version)
    found = overlay_versions(path, installed_digest=installed_digest).get(
        (challenge, version)
    )
    if found is None:
        return code.definitions(challenge, version)  # raises the typed refusal
    return found["strata"]


__all__ = [
    "NEW_VERSION_PRODUCER_FILES",
    "SubsetRegistryRefused",
    "definitions",
    "is_subset_version",
    "overlay_versions",
    "producer_module",
    "versions",
]
