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
    ("f02", "2.4"): "f02",
    ("electric-motor-magnetics", "1.4"): "motor",
    ("chip-cold-plate", "1.4"): "cooling",
}


def kind(challenge_id, version):
    """The practice-grid kind of a dev-grid version, or None."""
    return GRID_KINDS.get((challenge_id, version))


def adapter(challenge_id, version):
    """The sealed v2 grader as the development adapter of a dev-grid version, under its
    development evaluation version, or None for any other version."""
    chosen = kind(challenge_id, version)
    if chosen is None:
        return None
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

    if kind(challenge_id, version) == "motor":
        from carbon.scoring import motor_dev_grid

        return motor_dev_grid.bank(version)
    return practice_grid.practice_bank(kind(challenge_id, version), version)
