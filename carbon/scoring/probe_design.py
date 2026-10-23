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
import json

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


def row_key(probe):
    """The order of a probe row among its set, from its own metadata (never its
    position), so a bank whose rows were permuted canonicalizes back to the
    builder order: base point, then the base row, the 1% moves by input and sign,
    then the law rows by name."""
    base, dim, sign = probe["base"], probe["dim"], probe["sign"]
    kind = probe.get("kind", "response")
    if kind != "response":
        return (base, 2, 0, 0, kind)
    if dim is None:
        return (base, 0, 0, 0, "")
    return (base, 1, dim, 0 if sign > 0 else 1, "")


def response_rows(points, bounds, *, delta=DELTA, extra=()):
    """The probe rows for ``points``: ``[(case_id, record, x)]``. ``extra`` is
    ``[(name, transform)]``: each adds one law-probe row per base point,
    ``transform(base point) -> point`` (kind ``law:<name>``)."""
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
        for name, transform in extra:
            rows.append(
                (
                    f"probe-{k:02d}-law-{name}",
                    {
                        "status": PROBE_STATUS,
                        "probe": {
                            "base": k,
                            "dim": None,
                            "sign": 0,
                            "kind": "law:" + name,
                        },
                    },
                    list(transform(base)),
                )
            )
    return rows


def content_bytes(cases) -> bytes:
    """The canonical batch input content (never its ids or order): the seed basis
    that every validator copy of one exam shares. ``cases``: input dicts."""
    return json.dumps(
        sorted(json.dumps(c, sort_keys=True, separators=(",", ":")) for c in cases),
        separators=(",", ":"),
    ).encode()


def with_probes(
    bank,
    cases,
    *,
    challenge,
    bounds,
    valid,
    bases,
    dtype,
    extra=(),
    delta=DELTA,
    margin=DELTA,
):
    """``bank`` (a sealed bank in the development bank format) with the private
    probes appended as unreferenced rows (``reference_present`` False, NaN
    references), seeded by the batch input content ``cases`` (input dicts)."""
    import numpy as np

    points = draw_valid(
        seed(content_bytes(cases), challenge),
        bounds,
        valid,
        bases,
        delta=max(delta, margin),
    )
    rows = sorted(
        response_rows(points, bounds, delta=delta, extra=extra),
        key=lambda row: row_key(row[1]["probe"]),
    )
    width = bank["references"].shape[1]
    inputs = np.concatenate(
        [bank["inputs"], np.asarray([x for _, _, x in rows], dtype=dtype)]
    )
    references = np.concatenate(
        [bank["references"], np.full((len(rows), width), np.nan, dtype=dtype)]
    )
    inputs.setflags(write=False)
    references.setflags(write=False)
    return {
        **bank,
        "case_ids": (*bank["case_ids"], *[c for c, _, _ in rows]),
        "cohorts": (*bank["cohorts"], *[PROBE_COHORT] * len(rows)),
        "inputs": inputs,
        "references": references,
        "reference_records": [*bank["reference_records"], *[r for _, r, _ in rows]],
        "reference_present": (True,) * len(bank["case_ids"]) + (False,) * len(rows),
    }


def groups(rows):
    """Group probe bank rows (each with ``record["probe"]`` and an index) into
    bases: ``[{"base": index, "dims": {i: (plus index, minus index)}}]``. ``rows``
    is ``[(index, probe record)]``."""
    bases = {}
    for index, probe in rows:
        if probe.get("kind", "response") != "response":
            continue
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


def law_pairs(rows, name):
    """``[(base index, law-row index)]`` for law probe ``name``, in base order.
    ``rows`` is ``[(index, probe record)]``."""
    base, law = {}, {}
    for index, probe in rows:
        kind = probe.get("kind", "response")
        if kind == "response" and probe["dim"] is None:
            base[probe["base"]] = index
        elif kind == "law:" + name:
            law[probe["base"]] = index
    if set(base) != set(law) or not base:
        raise ProbeRefused("probe_law_incomplete")
    return [(base[k], law[k]) for k in sorted(base)]


_PER_ROW = (
    "case_ids",
    "cohorts",
    "inputs",
    "references",
    "reference_records",
    "reference_present",
)


def cells_only(bank):
    """``bank`` without its probe rows (the exam cells alone)."""
    keep = [i for i, c in enumerate(bank["cohorts"]) if c != PROBE_COHORT]
    return {
        name: ([value[i] for i in keep] if name in _PER_ROW else value)
        for name, value in bank.items()
    }
