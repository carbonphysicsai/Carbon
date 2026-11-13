"""Dev-pack v2 (Validator 2026-10-23): a development pack graded by the sealed v2 grader.

For the graph-route-v2 versions listed here, the development pack's bank is the Challenge's
practice grid (`practice_grid.practice_bank`: the full exposed public bank shaped as the exam's
grid, with public-seeded probes interleaved) and the development adapter is the sealed v2
grader under its own development evaluation version (``<kind>-dual-development-grid-v2``).
One code path with the exam: the same critical-fidelity D = min(V, C) and physics-half legs.

Existing versions are untouched (their banks, evaluation versions and producer identities).
The kit of a grid version is unchanged, so a recipe or artifact bound to it stays valid. This
module reads only the registry and public material; it is a new version, pre-publish.
"""

from __future__ import annotations

#: (challenge id, version) -> the practice-grid kind that names its grader and bank.
GRID_KINDS = {
    ("f08-ribbed-bracket", "1.5"): "f08",
    ("f08-ribbed-bracket", "1.6"): "f08",
    ("f08-ribbed-bracket", "1.7"): "f08",
    ("f02", "2.4"): "f02",
    ("f02", "2.5"): "f02",
    ("electric-motor-magnetics", "1.4"): "motor",
    ("electric-motor-magnetics", "1.5"): "motor",
    ("electric-motor-magnetics", "1.6"): "motor",
    ("chip-cold-plate", "1.4"): "cooling",
    ("chip-cold-plate", "1.5"): "cooling",
    ("chip-cold-plate", "1.6"): "cooling",
    ("chip-cold-plate", "1.7"): "cooling",
}


#: Overlay versions' dev grids (add-only, `register`): (challenge id, version) -> (bank(version), adapter(version)).
#: A version registered by the worker image's GRID_KINDS is never in it.
_REGISTERED = {}
#: The kind name `kind` answers for a registered overlay version.
REGISTERED_KIND = "registered"


def register(challenge_id, version, *, bank, adapter):
    """Register an overlay version's development bank and adapter (its dispatch calls this; add-only: the same pair
    again is a no-op, a different one or an image version refuses)."""
    key = (challenge_id, version)
    if key in GRID_KINDS:
        raise ValueError(f"{key!r} is a worker-image dev-grid version")
    known = _REGISTERED.setdefault(key, (bank, adapter))
    if known != (bank, adapter):
        raise ValueError(f"{key!r} already has a different dev grid")


def _dispatched(key):
    """Apply an armed overlay dispatch for ``key`` (importing its Challenge's sealed module runs it), so a registered
    version is known before its sealed module happens to be imported."""
    try:
        from carbon.challenge_kit import version_overlay
    except ImportError:
        return
    if key in getattr(version_overlay, "_ARMED", {}):
        import importlib

        importlib.import_module(version_overlay.SEALED_TARGET[key[0]])


def kind(challenge_id, version):
    """The practice-grid kind of a dev-grid version, or None."""
    key = (challenge_id, version)
    if key in GRID_KINDS:
        return GRID_KINDS[key]
    if key not in _REGISTERED:
        _dispatched(key)
    return REGISTERED_KIND if key in _REGISTERED else None


def adapter(challenge_id, version):
    """The sealed v2 grader as the development adapter of a dev-grid version, under its
    development evaluation version, or None for any other version."""
    chosen = kind(challenge_id, version)
    if chosen is None:
        return None
    if chosen == REGISTERED_KIND:
        return _REGISTERED[(challenge_id, version)][1](version)
    from carbon.challenge_kit import version_registry
    from carbon.scoring import physical_dual_pack as physical
    from carbon.scoring import practice_grid

    if chosen == "motor":
        from carbon.scoring import motor_dev_grid

        return motor_dev_grid.adapter(version)
    evaluation, case_id = version_registry.entry(
        challenge_id, version
    ).development_evaluation
    sealed = practice_grid.adapter(chosen, version)
    # ``sealed`` is the sealed module itself or a Variant of it for this version.
    module = getattr(sealed, "_module", sealed)
    return physical.Variant(module, version, evaluation, case_id)


def bank(challenge_id, version):
    """The development bank of a dev-grid version: the practice grid with probes."""
    from carbon.scoring import practice_grid

    if kind(challenge_id, version) == REGISTERED_KIND:
        return _REGISTERED[(challenge_id, version)][0](version)
    if kind(challenge_id, version) == "motor":
        from carbon.scoring import motor_dev_grid

        return motor_dev_grid.bank(version)
    return practice_grid.practice_bank(kind(challenge_id, version), version)
