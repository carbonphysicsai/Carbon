"""Registered hunt themes for the Level 5 opportunity hunt (GRAPHITE-L5-HUNT-01).

A theme is a short, committed text that steers a Constructor session toward one kind of
construction and asks it to report what it could not build. It is opt-in
(`phase3 run --theme ID`): a brief recorded without a theme keeps its digest, so every
earlier session replays byte for byte. A theme widens nothing: the level's domain, the
grant and every boundary are unchanged, and a wish a theme asks for is stored as data by
the capability log (`capability_log`), never granted.

The owner's priority is models that learn the real physics, so the themes are
physics-informed construction. The wording stays neutral about the Challenge: it names
no figure, threshold or hidden material, and each text is checked by the brief's own
protected-material refusal.

DEVELOPMENT only. It claims no qualification and adopts no capability.
"""

from __future__ import annotations

THEME_SCHEMA = "carbon.graphite.hunt-theme.v1"

#: What every themed report must say, whatever the theme.
REPORT_REQUIREMENT = (
    "End your session with a short report: for the physics you tried to build in, which "
    "freedom that this level does not offer would have let you build it. File one WISH "
    "line for each such freedom (what it is, what it needs, the gain you expect, and the "
    "evidence you saw). Say plainly when a freedom you wanted is already available."
)

THEMES = {
    "physics-law-losses": {
        "levels": (1, 2),
        "text": (
            "Theme: physics-law losses and constraints. Propose recipes whose loss or "
            "constraint terms encode the laws the data obeys: conservation of what is "
            "conserved, physical bounds on outputs, and monotonic trends the "
            "mechanism guarantees. Use only what this level's domain lists; where a law "
            "cannot be expressed here, name it in a WISH line instead of approximating it "
            "silently."
        ),
    },
    "physics-structure": {
        "levels": (3, 4),
        "text": (
            "Theme: structure that respects the physics. Propose recipes whose structure "
            "or numerics respect known properties of the system: symmetries, positivity "
            "and boundedness of outputs, smoothness, and the right behaviour at limits. "
            "Use only what this level's domain lists; where a structure cannot be "
            "expressed here, name it in a WISH line."
        ),
    },
    "open": {
        "levels": (1, 2, 3, 4),
        "text": (
            "Theme: open. Propose whatever construction you judge most likely to make a "
            "model learn the real physics rather than fit the practice data, within this "
            "level's domain, and name in WISH lines what the level stopped you from "
            "trying."
        ),
    },
}


class UnknownTheme(ValueError):
    """A theme id that is not registered."""


def theme_block(theme_id, level):
    """The brief block for theme `theme_id` at construction `level`, or `UnknownTheme`.
    A theme is advice for the levels it names; a level it does not name is refused so
    a run is never briefed with a theme its level cannot act on."""
    entry = THEMES.get(theme_id) if type(theme_id) is str else None
    if entry is None:
        raise UnknownTheme("unregistered_hunt_theme")
    if level not in entry["levels"]:
        raise UnknownTheme("hunt_theme_not_for_this_level")
    return {
        "schema": THEME_SCHEMA,
        "id": theme_id,
        "level": level,
        "text": entry["text"],
        "report_requirement": REPORT_REQUIREMENT,
        "effect": "advice only: the level's domain, grant and boundaries are unchanged",
    }
