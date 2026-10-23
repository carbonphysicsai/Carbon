"""Private exam-seeded probe points for the physics half (Validator spec
VALIDATOR_EXAM_PHYSICS_HALF_V1_20261023): extra model inputs inside a Challenge
validity region, from which A_law and A_response read the model laws and local
sensitivities. They need no solver run: the references for A_response are fitted
exponents registered in the accuracy definition.

A probe set is deterministic from the sealed batch itself (``seed``), so the
signed batch is unchanged: the bank is rebuilt from the batch document and gets the
same probes every time, and the probe inputs stay as private as the batch is. The
model is queried on the cells and the probes together in the one registered query;
probe rows are bank rows with no reference (``reference_present`` False) in the
``PROBE_COHORT`` cohort, so the shared pipeline carries them like Battery's
unreferenced rows.

Layout per base point ``k``: the base, then for every input ``i`` the point moved
by ``+delta`` and ``-delta`` of that input's span (a 1% default). Pure
arithmetic; DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import hashlib

PROBE_COHORT = "probe_response"
DELTA = 0.01
PROBE_STATUS = "PROBE"


class ProbeRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def seed(canonical_document: bytes, challenge: str) -> bytes:
    """The probe seed: derived from the private batch document."""
    return hashlib.sha256(
        b"carbon.exam-probes/1\n"
        + challenge.encode("ascii")
        + b"\n"
        + canonical_document
    ).digest()


def _uniform(seed_bytes: bytes, counter: int) -> float:
    digest = hashlib.sha256(seed_bytes + counter.to_bytes(8, "big")).digest()
    return int.from_bytes(digest[:8], "big") / 2.0**64


def draw_valid(seed_bytes, bounds, valid, count, *, delta=DELTA, max_tries=100_000):
    """``count`` base points uniform in ``bounds`` whose every +-delta neighbour
    also satisfies ``valid`` (the Challenge validity predicate). Raises
    ``ProbeRefused`` rather than returning fewer."""
    spans = [hi - lo for lo, hi in bounds]
    points, counter = [], 0
    while len(points) < count:
        if counter >= max_tries * count:
            raise ProbeRefused("probe_validity_region_unreachable")
        point = [
            lo + _uniform(seed_bytes, counter + i) * span
            for i, ((lo, _), span) in enumerate(zip(bounds, spans, strict=True))
        ]
        counter += len(bounds)
        neighbours = [point]
        for i, span in enumerate(spans):
            for sign in (1, -1):
                moved = list(point)
                moved[i] += sign * delta * span
                neighbours.append(moved)
        if all(
            all(lo <= v <= hi for v, (lo, hi) in zip(p, bounds, strict=True))
            and valid(p)
            for p in neighbours
        ):
            points.append(point)
    return points


def response_rows(points, bounds, *, delta=DELTA):
    """The probe rows for ``points``: ``[(case_id, record, x)]``."""
    spans = [hi - lo for lo, hi in bounds]
    rows = []
    for k, base in enumerate(points):
        rows.append(
            (
                f"probe-{k:02d}-base",
                {"status": PROBE_STATUS, "probe": {"base": k, "dim": None, "sign": 0}},
                list(base),
            )
        )
        for i, span in enumerate(spans):
            for sign, tag in ((1, "p"), (-1, "m")):
                moved = list(base)
                moved[i] += sign * delta * span
                rows.append(
                    (
                        f"probe-{k:02d}-d{i}{tag}",
                        {
                            "status": PROBE_STATUS,
                            "probe": {"base": k, "dim": i, "sign": sign},
                        },
                        moved,
                    )
                )
    return rows


def groups(rows):
    """Group probe bank rows (each with ``record["probe"]`` and an index) into
    bases: ``[{"base": index, "dims": {i: (plus index, minus index)}}]``. ``rows``
    is ``[(index, probe record)]``."""
    bases = {}
    for index, probe in rows:
        entry = bases.setdefault(probe["base"], {"base": None, "dims": {}})
        if probe["dim"] is None:
            entry["base"] = index
        else:
            slot = entry["dims"].setdefault(probe["dim"], [None, None])
            slot[0 if probe["sign"] > 0 else 1] = index
    result = []
    for k in sorted(bases):
        entry = bases[k]
        if entry["base"] is None or any(
            None in pair for pair in entry["dims"].values()
        ):
            raise ProbeRefused("probe_group_incomplete")
        result.append(
            {
                "base": entry["base"],
                "dims": {d: tuple(p) for d, p in entry["dims"].items()},
            }
        )
    return result
