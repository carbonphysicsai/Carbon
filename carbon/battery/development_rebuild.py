"""One dispatch for battery's development rebuilds (Levels 1-4).

Every rebuild site asks this module what a development construction's record
is and how it is staged and rebuilt, so a new level is added in one place and
a level's record can never be silently rebuilt as Level 0
(BATTERY-L3-NUMERICS-BUILD-01's lesson). A construction with no development
record is Level 0, and nothing here touches it.

- Level 1: a loss expression (`level1_worker`).
- Level 2: SpecMuon, `specmuon-carbon-v1` (`level2_worker`).
- Level 3: training-time numerics (`level3_worker`).
- Level 4: a graph-only submission (`level4_worker`); every rebuild fails
  closed as Carbon's environment until the security owner accepts the G5
  profile (D3).

Each level's own module stays the authority for its staging; this module
only routes.
"""

from __future__ import annotations

from . import level1_worker, level2_worker, level3_worker, level4_worker

LEVEL1, LEVEL2, LEVEL3, LEVEL4 = "level1", "level2", "level3", "level4"


def record(reconstruction):
    """The development record a construction rebuilds with, or None."""
    found = level4_worker.graph_record(reconstruction)
    if found is None:
        found = level1_worker.expression_record(reconstruction)
    if found is None:
        found = level3_worker.numerics_record(reconstruction)
    if found is None:
        found = level2_worker.spectral_record(reconstruction)
    return found


def kind(found):
    """Which level a development record belongs to."""
    if found is None:
        return None
    if level4_worker.is_graph(found):
        return LEVEL4
    if level3_worker.is_numerics(found):
        return LEVEL3
    if level2_worker.is_spectral(found):
        return LEVEL2
    return LEVEL1


def stage(found, program, files, *, level1_program):
    """`(program, files, trainer)` for a development record staged on a
    Level-0 `program` and `files`. Level 1 has its own program
    (`level1_program()`); Levels 2 and 3 replace the base program's build
    line."""
    level = kind(found)
    if level is None:
        return program, files, None
    if level == LEVEL4:
        return (
            level4_worker.program(program),
            {**files, **level4_worker.staged(found)},
            LEVEL4,
        )
    if level == LEVEL3:
        return (
            level3_worker.program(program),
            {**files, **level3_worker.staged(found)},
            LEVEL3,
        )
    if level == LEVEL2:
        return (
            level2_worker.program(program),
            {**files, **level2_worker.staged(found)},
            LEVEL2,
        )
    return level1_program(), {**files, **level1_worker.staged(found)}, LEVEL1


def rebuild_label(found):
    """The built record's rebuild label: every development level is
    CPU-verified only until the A40 R1 leg passes it."""
    level = kind(found)
    if level is None:
        return None
    return {
        LEVEL1: level1_worker.REBUILD_LABEL,
        LEVEL2: level2_worker.REBUILD_LABEL,
        LEVEL3: level3_worker.REBUILD_LABEL,
        LEVEL4: level4_worker.REBUILD_LABEL,
    }[level]


def build_in_process(recipe, found):
    """The untrained development model, built in this process."""
    level = kind(found)
    if level == LEVEL4:
        return level4_worker.build_in_process(recipe, found)
    if level == LEVEL3:
        return level3_worker.build_in_process(recipe, found)
    if level == LEVEL2:
        return level2_worker.build_in_process(recipe, found)
    return level1_worker.build_in_process(recipe, found)
