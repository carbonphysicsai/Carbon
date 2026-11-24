"""The catalog entry of a version registered by data: what a miner can list, describe and select (owner G-LEAD-61).

An ``exam_registry.json`` row may carry ``entry``: ``{title, portfolio, status}``. With a build row (`exam_build`) it is the
version's catalog `registry.Entry`, written from its own served material:

- ``status`` "open": offered exactly as every pool version is, so RESERVED until its owner constants are registered and
  published, and IMPLEMENTED from then on (`registry._pool_status`);
- ``status`` "retired": listed as RETIRED and never selected or described as open, whatever its constants say. Its rows,
  record and other versions are untouched: retiring one is this one word.

A version the code serves keeps its own code entry (a row for it is refused); a refused row has no entry, so the version is
unknown to the catalog, never a nearby one. Nothing here opens a door: serving, intake and grading have their own rules.
"""

from __future__ import annotations

import logging

from . import exam_build, exam_registry

_LOG = logging.getLogger(__name__)
#: ``{(challenge id, version): reason}`` of every entry row that gives no entry.
REFUSED: dict = {}
PROFILE_SUMMARY = (
    "JAX CPU practice of your own graph by Carbon's graph training adapter v2, in the isolated C-03 CPU worker; exact "
    "public TRAIN and recipe bytes staged"
)


def _refuse(key, reason) -> None:
    if REFUSED.get(key) != reason:
        REFUSED[key] = reason
        _LOG.warning("exam registry entry row %r refused: %s", key, reason)


def rows() -> dict:
    """``{(challenge id, version): entry row}`` of every version a build row serves and an entry row names."""
    found = {}
    for key in exam_registry.keys("entry"):
        if exam_build.code_serves(*key):
            _refuse(key, "entry_version_is_code_served")
            continue
        try:
            if exam_build.block(*key) is None:
                raise exam_build.ExamBuildRefused("entry_has_no_build_row")
        except exam_build.ExamBuildRefused as refused:
            _refuse(key, str(refused))
            continue
        found[key] = exam_registry.field(*key, "entry")
    return found


def describe(challenge_id: str, version: str) -> dict:
    """The version's description, from its build module and its graph training adapter: served facts only."""
    from carbon.challenge_kit import version_registry

    module = exam_build.module(challenge_id, version)
    entry = version_registry.entry(challenge_id, version)
    train = module.load_public_train(challenge_id, version)
    return {
        "identity": f"carbon.{challenge_id}.{version}",
        "interface": module.interface_document(challenge_id, version),
        "construction_kit": module.construction_kit(challenge_id, version),
        "construction_limits": module.construction_limits_document(
            challenge_id, version
        ),
        "public_material": {
            "train": {"name": entry.train, "cases": len(train["case_ids"])},
        },
        "examples": [],
        "examples_note": (
            "The graph route's example recipe needs your own staged graph; no catalog entry is offered on this version."
        ),
        "unsupported": [
            {
                "id": "source.bundle",
                "status": "closed",
                "blocker": "miner source bundles stay closed",
                "summary": "A miner-authored source bundle is not served.",
            }
        ],
    }
