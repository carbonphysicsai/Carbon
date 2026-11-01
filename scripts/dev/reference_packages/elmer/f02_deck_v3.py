"""f02 burst-thermal decks, VERSION 3 (Burst Thermal 3.0), for the pinned Elmer image (REFERENCE-PACKAGES-01).

A NEW file beside the pinned 2.5 deck (`f02_deck.py`, which is never edited). It is deck v2 (the drop-knot fix of
POOL_PAYLOAD_RULINGS rule 12, SUMS 194d7371...) plus, per F02_V3_BUILD_SPEC_20261101:

- temperature-dependent conductivity and heat capacity as Elmer `Variable Temperature` tables, with Elmer nonlinear
  iterations (numerical settings recorded in the deck header; a run that reaches the iteration limit is
  REFERENCE_INVALID, never OK). A table equal to "HUMAN_INPUT" refuses a production deck; `test_mode` permits clearly
  labelled synthetic tables and marks every output "tables": "TEST_ONLY". No material value is invented here;
- `schedule_v3`: one continuous waveform family (ramp fraction, one or two pulses, gap), reproducing v2 exactly at
  r = 0, n = 1 (and v2's ramp at r = 1, v2's two-pulse at r = 0, n = 2, gap 10 s);
- `tim_thickness_mm` as an input (0.2 mm reproduces v2's mesh exactly);
- `observe_v3`: time above a threshold, recovery, the second-pulse peak (the threshold is a parameter with no default),
  and the 0.5 s sample selector by step index;
- an import that works at any install depth (v2 failed at less than five levels);
- an optional temperature-dependent LEAKAGE heat source in the die (OWNER choice A, F02 3.0): a volumetric ``Heat Source``
  (Elmer, W/kg) that is a function of the local temperature, read from a digest-pinned coefficient file, present whenever the
  die is powered, inside the same nonlinear iteration as k(T). With leakage OFF (the default) the deck is byte-identical to
  the receipted one. A run that fails to converge with leakage on is REFERENCE_INVALID ``thermal_runaway``; a solution past
  the coefficient range is REFERENCE_INVALID ``out_of_property_range``; neither ever yields a number.

Provenance: built on the deck v2 payload (codex-queue/reports/F02_DECK_GATE_20261026/f02_deck_v2.py, sha256 bb48111408d9...,
SUMS 194d7371bcad...; POOL_PAYLOAD_RULINGS rule 12, the two-deck gate NO_IMPACT) with the sample-selector and parents[4] fixes added.
The pinned 2.5 deck (f02_deck.py, sha256 70d51aba5554...) is not edited.

    python -m scripts.dev.reference_packages.elmer.f02_deck_v3 case LABEL --out DIR [--mesh 2] [--dt-scale 0.5]

The packet's stack (round1/f02-burst-thermal.md, requirements.json): silicon
20 x 20 x 0.5 mm on TIM 20 x 20 x 0.2 mm on copper 30 x 30 x 2 mm, centred,
perfect contact, Robin cooling on the whole underside, every other exposed
face insulated. Two 8 x 8 mm patches on the die top at x = -5 and +5 mm carry
the power split (left takes the larger share). Base 20 W throughout; the burst
starts at 20 s; rectangular, ramp and two-pulse waveforms; horizon 120 s.

The mesh is a structured hexahedral grid written directly as an Elmer mesh
database (no external mesher): x and y breakpoints at every layer and patch
edge, graded z layers. Time steps are aligned with every source event and
finer through the burst; the die-top maximum is recorded at every solver
step, so the peak search is over every step, not 0.5 s samples. The 1D slab
control (`slab=True`) is the copper layer alone with uniform flux over its
whole top, compared with the exact series (`slab_top_rise`).
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import sys
from pathlib import Path


def _root():
    """The repository root when this file sits in it, else the working directory (a payload install is any depth)."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "development").is_dir():
            return parent
    return Path.cwd()


ROOT = _root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MM = 1e-3
LAYERS = {  # name: (half side mm, thickness mm, k, rho, cp)
    "copper": (15.0, 2.0, 390.0, 8960.0, 385.0),
    "tim": (10.0, 0.2, 5.0, 2500.0, 1000.0),
    "die": (10.0, 0.5, 130.0, 2330.0, 700.0),
}
NAMES = ("copper", "tim", "die")
TIM_MM_DEFAULT = LAYERS["tim"][1]  # 0.2 mm: v2's mesh


class DeckRefused(ValueError):
    """A deck this module will not write (a typed reason, never a silent default)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def check_tim_mm(tim_mm):
    if (
        type(tim_mm) not in (int, float)
        or isinstance(tim_mm, bool)
        or not 0 < tim_mm <= 5
    ):
        raise DeckRefused("tim_thickness_invalid")
    return float(tim_mm)


PATCH_HALF, PATCH_X = 4.0, 5.0
HORIZON_S, BURST_START_S, BASE_W = 120.0, 20.0, 20.0
LIMIT_C = 95.0
PANELS = Path(
    ROOT, "docs/development/challenge_pipeline/round1/reference-route-panels.json"
)


def panel_case(label):
    d = json.loads(PANELS.read_text())["families"]["f02"]
    row = next(c for c in d["public_cases"] if c["label"] == label)
    return dict(zip(d["panel_fields"], row["parameters"]))


# --- mesh ----------------------------------------------------------------------------


def _axis(breaks, size):
    pts = [breaks[0]]
    for a, b in itertools.pairwise(breaks):
        n = max(1, math.ceil((b - a) / size - 1e-9))
        pts += [a + (b - a) * i / n for i in range(1, n + 1)]
    return pts


def _graded(t, n, ratio):
    """n cells over thickness t, geometric, finest at both ends."""
    w = [ratio ** min(i, n - 1 - i) for i in range(n)]
    s = sum(w)
    out, acc = [0.0], 0.0
    for x in w:
        acc += x
        out.append(t * acc / s)
    return out


def mesh(level=1, slab=False, tim_mm=TIM_MM_DEFAULT):
    """Nodes (mm), hexes (body, 8 node ids) and boundary quads (bc, parent,
    4 node ids). level 2 halves every cell size. ``tim_mm`` is the TIM layer thickness (the die sits above it); the
    TIM keeps its cell count, and 0.2 mm is v2's mesh exactly."""
    h = 1.0 / level
    thickness = {name: LAYERS[name][1] for name in NAMES}
    thickness["tim"] = check_tim_mm(tim_mm)
    if slab:
        xb, yb = [-15.0, 15.0], [-15.0, 15.0]
        xs, ys = _axis(xb, 7.5), _axis(yb, 7.5)
        layers = (("copper", 12 * level),)
    else:
        xb = [-15.0, -10.0, -9.0, -1.0, 1.0, 9.0, 10.0, 15.0]
        yb = [-15.0, -10.0, -4.0, 4.0, 10.0, 15.0]
        xs, ys = _axis(xb, h), _axis(yb, h)
        layers = (("copper", 6 * level), ("tim", 2 * level), ("die", 4 * level))
    zs, z0 = [], 0.0
    for name, n in layers:
        t = thickness[name]
        part = [z0 + z for z in _graded(t, n, 1.3)]
        zs += part if not zs else part[1:]
        z0 += t
    nx, ny, nz = len(xs), len(ys), len(zs)

    def nid(i, j, k):
        return 1 + i + nx * (j + ny * k)

    z_cu = LAYERS["copper"][1]
    z_tim = z_cu + thickness["tim"]
    hexes, owner = [], {}
    for k in range(nz - 1):
        zc = (zs[k] + zs[k + 1]) / 2
        for j in range(ny - 1):
            yc = (ys[j] + ys[j + 1]) / 2
            for i in range(nx - 1):
                xc = (xs[i] + xs[i + 1]) / 2
                if zc < z_cu:
                    body = 1
                elif abs(xc) < 10 and abs(yc) < 10:
                    body = 2 if zc < z_tim else 3
                else:
                    continue
                ids = [nid(i, j, k), nid(i + 1, j, k), nid(i + 1, j + 1, k), nid(i, j + 1, k),
                       nid(i, j, k + 1), nid(i + 1, j, k + 1), nid(i + 1, j + 1, k + 1), nid(i, j + 1, k + 1)]  # fmt: skip
                hexes.append((body, ids))
                owner[(i, j, k)] = len(hexes)
    quads, top = [], nz - 1
    for j in range(ny - 1):
        yc = (ys[j] + ys[j + 1]) / 2
        for i in range(nx - 1):
            xc = (xs[i] + xs[i + 1]) / 2
            quads.append(
                (
                    1,
                    owner[(i, j, 0)],
                    [
                        nid(i, j, 0),
                        nid(i + 1, j, 0),
                        nid(i + 1, j + 1, 0),
                        nid(i, j + 1, 0),
                    ],
                )
            )
            if (i, j, top - 1) not in owner:
                continue
            if slab or abs(yc) < PATCH_HALF and abs(xc + PATCH_X) < PATCH_HALF:
                bc = 2
            elif abs(yc) < PATCH_HALF and abs(xc - PATCH_X) < PATCH_HALF:
                bc = 3
            else:
                bc = 4
            quads.append((bc, owner[(i, j, top - 1)],
                          [nid(i, j, top), nid(i + 1, j, top), nid(i + 1, j + 1, top), nid(i, j + 1, top)]))  # fmt: skip
    used = {n for _b, ids in hexes for n in ids}
    nodes = {
        nid(i, j, k): (xs[i], ys[j], zs[k])
        for k in range(nz)
        for j in range(ny)
        for i in range(nx)
        if nid(i, j, k) in used
    }
    return nodes, hexes, quads


def tim_cell_aspect(level, tim_mm):
    """The lateral-to-vertical aspect of the thinnest TIM cell (the finest lateral cell over the first graded
    layer): logged for every deck, because a thin TIM makes flat cells."""
    n = 2 * level
    widths = [1.3 ** min(i, n - 1 - i) for i in range(n)]
    thinnest = tim_mm * min(widths) / sum(widths)
    return (1.0 / level) / thinnest


def write_mesh(out, level=1, slab=False, tim_mm=TIM_MM_DEFAULT):
    nodes, hexes, quads = mesh(level, slab, tim_mm)
    renum = {old: new for new, old in enumerate(sorted(nodes), start=1)}
    out = Path(out) / "mesh"
    out.mkdir(parents=True, exist_ok=True)
    (out / "mesh.header").write_text(
        f"{len(nodes)} {len(hexes)} {len(quads)}\n2\n808 {len(hexes)}\n404 {len(quads)}\n"
    )
    with (out / "mesh.nodes").open("w") as f:
        for old, (x, y, z) in sorted(nodes.items()):
            f.write(f"{renum[old]} -1 {x * MM!r} {y * MM!r} {z * MM!r}\n")
    with (out / "mesh.elements").open("w") as f:
        for e, (body, ids) in enumerate(hexes, start=1):
            f.write(f"{e} {body} 808 " + " ".join(str(renum[n]) for n in ids) + "\n")
    with (out / "mesh.boundary").open("w") as f:
        for b, (bc, parent, ids) in enumerate(quads, start=1):
            f.write(
                f"{b} {bc} {parent} 0 404 "
                + " ".join(str(renum[n]) for n in ids)
                + "\n"
            )
    return {
        "nodes": len(nodes),
        "hexes": len(hexes),
        "boundary_quads": len(quads),
        "level": level,
        "tim_thickness_mm": tim_mm,
        "tim_cell_aspect": round(tim_cell_aspect(level, tim_mm), 3),
    }


# --- power schedule and time steps -----------------------------------------------


def schedule_labelled(case):
    """Piecewise-linear total power (t, W) knots; rectangles are steps.
    Deck v2 (POOL_PAYLOAD_RULINGS rule 12): every knot sits on the same 6-decimal
    grid as the events `time_steps` rounds, so a step boundary never lands inside
    a 1e-6 power drop. The sums are rounded before eps is added, as the rule says."""
    peak, d, w = case["peak_w"], case["on_time_s"], case["waveform"]
    t0, eps = BURST_START_S, 1e-6
    if w == "rectangular":
        end = round(t0 + d, 6)
        return [(0, BASE_W), (t0, BASE_W), (t0 + eps, peak), (end, peak),
                (end + eps, BASE_W), (HORIZON_S, BASE_W)]  # fmt: skip
    if w == "ramp":
        end = round(t0 + d, 6)
        return [
            (0, BASE_W),
            (t0, BASE_W),
            (end, peak),
            (end + eps, BASE_W),
            (HORIZON_S, BASE_W),
        ]
    if w == "two-pulse":
        a = round(t0 + d / 2, 6)
        b = round(a + 10.0, 6)
        c = round(b + d / 2, 6)
        return [(0, BASE_W), (t0, BASE_W), (t0 + eps, peak), (a, peak), (a + eps, BASE_W), (b, BASE_W),
                (b + eps, peak), (c, peak), (c + eps, BASE_W), (HORIZON_S, BASE_W)]  # fmt: skip
    if w == "constant":
        return [(0, peak), (HORIZON_S, peak)]
    raise ValueError(w)


def schedule_v3(case):
    """The v3 waveform family: ``peak_w``, ``on_time_s`` and

    - ``ramp_fraction`` r in [0, 1]: each pulse rises linearly from the base to the peak over r of its duration, then holds
      (r = 0 a rectangle, r = 1 v2's ramp: the rise fills the pulse);
    - ``pulses`` n in {1, 2}: with two, the on-time is split in two equal pulses (v2's two-pulse), separated by ``gap_s``
      (end of the first to start of the second; required for n = 2, absent for n = 1).

    The burst starts at 20 s as in 2.5. The knots are rounded to the 6-decimal grid `time_steps` rounds to, before eps is
    added (rule 12). r = 0, n = 1 equals v2's rectangular table, r = 1, n = 1 its ramp, r = 0, n = 2, gap 10 its two-pulse.
    """
    peak, d = case["peak_w"], case["on_time_s"]
    r, n = case["ramp_fraction"], case["pulses"]
    gap = case.get("gap_s")
    if (
        type(r) not in (int, float)
        or isinstance(r, bool)
        or not 0 <= r <= 1
        or n not in (1, 2)
        or type(n) is not int
        or (n == 2) != (gap is not None)
        or (gap is not None and (type(gap) not in (int, float) or not gap > 0))
    ):
        raise DeckRefused("waveform_invalid")
    t0, eps = BURST_START_S, 1e-6
    duration = d / n
    starts = [t0] if n == 1 else [t0, round(round(t0 + duration, 6) + gap, 6)]
    knots = [(0, BASE_W), (t0, BASE_W)]
    for start in starts:
        end = round(start + duration, 6)
        if r == 0:
            if start != t0:
                knots += [(start, BASE_W)]
            knots += [(start + eps, peak), (end, peak), (end + eps, BASE_W)]
        else:
            if start != t0:
                knots += [(start, BASE_W)]
            top = round(start + r * duration, 6)
            knots += [(top, peak)]
            if top < end:
                knots += [(end, peak)]
            knots += [(end + eps, BASE_W)]
    last = max(t for t, _ in knots)
    if last >= HORIZON_S:
        raise DeckRefused("waveform_beyond_horizon")
    return [*knots, (HORIZON_S, BASE_W)]


def energy_j(case):
    """The extra energy above the base, analytic: sum over pulses of (peak - base) x duration x (1 - r / 2), exact for
    every shape (the knots' 1 microsecond slivers aside)."""
    n = case["pulses"]
    return (
        n
        * (case["peak_w"] - BASE_W)
        * (case["on_time_s"] / n)
        * (1 - case["ramp_fraction"] / 2)
    )


def schedule(case):
    """v3 knots when the case carries the v3 waveform fields, else v2's labelled waveforms."""
    return schedule_v3(case) if "ramp_fraction" in case else schedule_labelled(case)


def time_steps(case, scale=1.0):
    """(sizes, intervals): 0.1 s before the burst, 0.02 s from the burst to
    10 s after its last event, 0.1 s after; every event lands on a step
    boundary. `scale` 0.5 halves every step (the time witness)."""
    events = sorted({round(t, 6) for t, _ in schedule(case) if 0 < t < HORIZON_S})
    end = (max(events) + 10.0) if events else BURST_START_S + 10.0
    plan = [(BURST_START_S, 0.1), (end, 0.02), (HORIZON_S, 0.1)]
    sizes, intervals, t = [], [], 0.0
    for stop, dt in plan:
        for s in [e for e in events if t < e < stop] + [stop]:
            span = s - t
            n = max(1, round(span / (dt * scale)))
            sizes.append(span / n)
            intervals.append(n)
            t = s
    return sizes, intervals


# --- material property tables ------------------------------------------------------------

HUMAN_INPUT = "HUMAN_INPUT"
#: The production tables, SIGNED by the owner (OWNER-F02-V3-TABLES-SIGNED-01, 2026-11-01): the vendored file is byte-identical
#: to the signed one (sha256 below, checked on every load; a changed or missing file leaves HUMAN_INPUT in place, so a
#: production deck is REFUSED). Silicon and copper k(T) and cp(T) are the handbook tables of the citation below; the TIM is
#: the 2.5 deck's synthetic constant (k 5.0, rho 2500, cp 1000), explicit and unchanged. The table file is data, not a PDF.
TABLES_DECISION = "OWNER-F02-V3-TABLES-SIGNED-01"
TABLES_FILE = "f02_v3_production_tables.json"
TABLES_SHA256 = (
    "sha256:240a6ea2d400d8159202b79114c01d48191c175ab714f431e7a4976e0697718c"
)
TABLES_CITATION = (
    "k(T): C. Y. Ho, R. W. Powell, P. E. Liley, Thermal Conductivity of the Elements, J. Phys. Chem. Ref. Data 1, 279 "
    "(1972) (abridged scan; printed p. 332 copper, p. 394 silicon; silicon rows below 300 K are 'merely typical'); "
    "cp(T): NIST-JANAF"
)


def _load_signed_tables():
    """``(tables, status)``: the signed file's silicon (die) and copper k and cp tables when its bytes hash to the signed
    sha256, else the HUMAN_INPUT placeholders and the reason (fail closed)."""
    closed = {
        "copper": {"k": HUMAN_INPUT, "cp": HUMAN_INPUT},
        "die": {"k": HUMAN_INPUT, "cp": HUMAN_INPUT},
    }
    path = Path(__file__).with_name(TABLES_FILE)
    try:
        raw = path.read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        return closed, "TABLES_FILE_MISSING"
    if "sha256:" + hashlib.sha256(raw).hexdigest() != TABLES_SHA256:
        return closed, "TABLES_FILE_NOT_THE_SIGNED_ONE"
    document = json.loads(raw)
    return {
        layer: {
            prop: [(float(t), float(v)) for t, v in document["tables"][layer][prop]]
            for prop in ("k", "cp")
        }
        for layer in ("copper", "die")
    }, "SIGNED"


PRODUCTION_TABLES, TABLES_STATUS = _load_signed_tables()
#: NUMERICAL settings of Elmer's nonlinear iteration: proposed, recorded in the deck header, verified by the nonlinear
#: MMS (f02_mms_v3.py) and never tuned to match a result. Reaching the limit without converging is REFERENCE_INVALID.
NONLINEAR_MAX_ITERATIONS = 50
NONLINEAR_TOLERANCE = 1e-8


def _check_table(points, label):
    if (
        type(points) not in (list, tuple)
        or len(points) < 2
        or any(type(p) not in (list, tuple) or len(p) != 2 for p in points)
        or any(
            type(x) not in (int, float) or isinstance(x, bool) or not math.isfinite(x)
            for p in points
            for x in p
        )
        or any(b[0] <= a[0] for a, b in itertools.pairwise(points))
        or any(p[1] <= 0 for p in points)
    ):
        raise DeckRefused(f"property_table_invalid:{label}")
    return [(float(t), float(v)) for t, v in points]


def resolve_materials(tables=None, *, production=False, test_mode=False):
    """``(materials, label)``: for each layer its ``k``, ``cp`` (a constant or a checked ``[(T_K, value), ...]`` table)
    and ``rho``. ``tables=None`` is v2's constants. ``label`` is "CONSTANT" (v2's constants), "TEST_ONLY" or "PRODUCTION".

    A table equal to HUMAN_INPUT makes a production deck raise; ``test_mode`` permits clearly labelled synthetic tables
    (every output then carries "tables": "TEST_ONLY") and cannot be combined with ``production``.
    """
    if production and test_mode:
        raise DeckRefused("production_deck_cannot_use_test_tables")
    if tables is None and production:
        tables = PRODUCTION_TABLES
    materials = {
        name: {"k": LAYERS[name][2], "cp": LAYERS[name][4], "rho": LAYERS[name][3]}
        for name in NAMES
    }
    if tables is None:
        return materials, "CONSTANT"
    if set(tables) - set(NAMES) or "tim" in tables:
        raise DeckRefused("property_table_layer_unknown")
    for name, entry in tables.items():
        if type(entry) is not dict or set(entry) - {"k", "cp"}:
            raise DeckRefused(f"property_table_invalid:{name}")
        for prop, value in entry.items():
            if value == HUMAN_INPUT:
                raise DeckRefused(f"property_table_human_input:{name}.{prop}")
            if (
                type(value) in (int, float)
                and not isinstance(value, bool)
                and value > 0
            ):
                materials[name][prop] = float(value)
            else:
                materials[name][prop] = _check_table(value, f"{name}.{prop}")
    if production:
        return materials, "PRODUCTION"
    if not test_mode:
        raise DeckRefused("property_tables_need_test_mode_or_production")
    return materials, "TEST_ONLY"


def tables_source():
    """What a PRODUCTION deck records about its tables: the owner decision, the signed file's sha256 and name, the citation."""
    return {
        "decision": TABLES_DECISION,
        "sha256": TABLES_SHA256,
        "file": TABLES_FILE,
        "citation": TABLES_CITATION,
    }


def is_table(value):
    return type(value) is list


def interpolate(value, temperature_k):
    """The property at ``temperature_k`` (a constant, or linear interpolation clamped at the table ends, as Elmer)."""
    if not is_table(value):
        return value
    if temperature_k <= value[0][0]:
        return value[0][1]
    for (t0, v0), (t1, v1) in itertools.pairwise(value):
        if temperature_k <= t1:
            return v0 + (v1 - v0) * (temperature_k - t0) / (t1 - t0)
    return value[-1][1]


def integral(value, t_from, t_to):
    """The integral of a property over [t_from, t_to] K (the specific enthalpy for ``cp``): exact for the piecewise-linear
    table with Elmer's end clamping, and ``value * (t_to - t_from)`` for a constant."""
    if not is_table(value):
        return value * (t_to - t_from)
    sign = 1.0
    if t_to < t_from:
        t_from, t_to, sign = t_to, t_from, -1.0
    knots = [t_from] + [t for t, _ in value if t_from < t < t_to] + [t_to]
    total = 0.0
    for a, b in itertools.pairwise(knots):
        total += (b - a) * (interpolate(value, a) + interpolate(value, b)) / 2
    return sign * total


# --- leakage (OWNER choice A) --------------------------------------------------------

LEAKAGE_SCHEMA = "carbon.f02.leakage-coefficients.v1"
LEAKAGE_TEST_ONLY = "TEST_ONLY"
LEAKAGE_FORMS = ("constant", "exponential", "table")
#: The grid (K) a constant or exponential law is sampled on for Elmer's piecewise-linear ``Variable Temperature`` table.
LEAKAGE_GRID_K = 1.0


def _finite(value):
    return (
        type(value) in (int, float)
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def load_leakage(path, *, expect_sha256=None, test_mode=False):
    """The leakage law of a digest-pinned coefficient file (``carbon.f02.leakage-coefficients.v1``), or a refusal.

    The file is ``{"schema", "decision", "source", "form", "range_k": [lo, hi], ...}`` with ``form``

    - ``constant``    ``q_w_per_m3``: a temperature-independent volumetric power density (the lumped control's law);
    - ``exponential`` ``q_ref_w_per_m3``, ``t_ref_k``, ``beta_per_k``: q(T) = q_ref exp(beta (T - t_ref));
    - ``table``       ``points``: ``[[T_K, q_w_per_m3], ...]`` ascending in T (``range_k`` is then the table's own span).

    ``decision`` is ``TEST_ONLY`` (clearly synthetic: only ``test_mode`` may use it, and every output is labelled) or the owner
    decision that signs the coefficients, in which case the caller MUST pass the pinned ``expect_sha256`` (the file's digest):
    a changed file is refused. No coefficient is invented here.
    """
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expect_sha256 is not None and digest != expect_sha256:
        raise DeckRefused("leakage_file_digest_differs")
    try:
        doc = json.loads(raw)
    except ValueError:
        raise DeckRefused("leakage_file_not_json") from None
    if type(doc) is not dict or doc.get("schema") != LEAKAGE_SCHEMA:
        raise DeckRefused("leakage_schema")
    decision, form = doc.get("decision"), doc.get("form")
    if type(decision) is not str or not decision or type(doc.get("source")) is not str:
        raise DeckRefused("leakage_decision_and_source_required")
    test = decision == LEAKAGE_TEST_ONLY
    if test and not test_mode:
        raise DeckRefused("leakage_test_coefficients_refuse_production")
    if not test and expect_sha256 is None:
        raise DeckRefused("leakage_signed_coefficients_need_a_pinned_digest")
    if form not in LEAKAGE_FORMS:
        raise DeckRefused("leakage_form")
    keys = {
        "constant": {"q_w_per_m3"},
        "exponential": {"q_ref_w_per_m3", "t_ref_k", "beta_per_k"},
        "table": {"points"},
    }[form]
    if set(doc) != {"schema", "decision", "source", "form", "range_k"} | keys:
        raise DeckRefused("leakage_fields")
    if form == "table":
        points = doc["points"]
        if (
            type(points) is not list
            or len(points) < 2
            or any(type(p) is not list or len(p) != 2 for p in points)
            or any(not _finite(x) for p in points for x in p)
            or any(b[0] <= a[0] for a, b in itertools.pairwise(points))
            or any(p[1] < 0 for p in points)
        ):
            raise DeckRefused("leakage_table_invalid")
        law = {"points": [(float(t), float(q)) for t, q in points]}
        low, high = law["points"][0][0], law["points"][-1][0]
        if doc["range_k"] != [low, high]:
            raise DeckRefused("leakage_range_is_the_tables_span")
    else:
        if any(not _finite(doc[k]) for k in keys) or (
            form == "constant" and doc["q_w_per_m3"] < 0
        ):
            raise DeckRefused("leakage_coefficients_invalid")
        if form == "exponential" and not (
            doc["q_ref_w_per_m3"] >= 0 and doc["t_ref_k"] > 0
        ):
            raise DeckRefused("leakage_coefficients_invalid")
        law = {k: float(doc[k]) for k in sorted(keys)}
        range_k = doc["range_k"]
        if (
            type(range_k) is not list
            or len(range_k) != 2
            or any(not _finite(x) for x in range_k)
            or not 0 < range_k[0] < range_k[1]
        ):
            raise DeckRefused("leakage_range_invalid")
        low, high = float(range_k[0]), float(range_k[1])
    return {
        "form": form,
        "law": law,
        "range_k": (low, high),
        "decision": decision,
        "label": LEAKAGE_TEST_ONLY if test else "REGISTERED",
        "source": doc["source"],
        "sha256": "sha256:" + digest,
    }


def leakage_density(leak, temperature_k):
    """The volumetric leakage power density q(T) in W/m^3 (exact; refuses a temperature outside the law's range)."""
    low, high = leak["range_k"]
    if not low <= temperature_k <= high:
        raise DeckRefused("out_of_property_range")
    law = leak["law"]
    if leak["form"] == "constant":
        return law["q_w_per_m3"]
    if leak["form"] == "exponential":
        return law["q_ref_w_per_m3"] * math.exp(
            law["beta_per_k"] * (temperature_k - law["t_ref_k"])
        )
    return interpolate(law["points"], temperature_k)


def leakage_table_w_per_kg(leak, rho):
    """Elmer's ``Heat Source`` is per unit mass (it is multiplied by the density): the ``[(T_K, q / rho), ...]`` table, the
    table form's own knots, else the law sampled every `LEAKAGE_GRID_K` over its range (a constant is two knots).
    """
    low, high = leak["range_k"]
    if leak["form"] == "table":
        knots = [t for t, _ in leak["law"]["points"]]
    elif leak["form"] == "constant":
        knots = [low, high]
    else:
        count = math.ceil((high - low) / LEAKAGE_GRID_K)
        knots = [low + i * (high - low) / count for i in range(count + 1)]
    return [(t, leakage_density(leak, t) / rho) for t in knots]


def die_volume_m3(tim_mm=TIM_MM_DEFAULT):
    side = 2 * LAYERS["die"][0] * MM
    return side * side * LAYERS["die"][1] * MM


def lumped_control(case_dir):
    """The closed-form check of a STEADY, constant-coefficient leakage deck: the heat in is the base power plus q V_die, and
    the Robin boundary must carry exactly that out (h x the underside integral of T - T_coolant), so the mean underside
    temperature is T_coolant + (BASE_W + q V_die) / (h A). Reads the last scalars row; returns the figures and the relative
    residual. Applies only to ``steady`` decks with ``form == "constant"``."""
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    leak = meta.get("leakage")
    if not meta.get("steady") or leak is None or leak["form"] != "constant":
        raise DeckRefused("lumped_control_needs_a_steady_constant_leakage_deck")
    cols, rows = read_scalars(case_dir)
    i_bottom = next(
        i
        for i, c in enumerate(cols)
        if c.startswith("boundary int") and c.endswith("bc 1")
    )
    h, tc = meta["case"]["h_w_m2_k"], meta["case"]["coolant_c"] + 273.15
    area = (2 * LAYERS["copper"][0] * MM) ** 2
    expected = BASE_W + leak["law"]["q_w_per_m3"] * die_volume_m3(
        meta.get("tim_thickness_mm", TIM_MM_DEFAULT)
    )
    carried = h * (rows[-1][i_bottom] - tc * area)
    return {
        "heat_in_w": expected,
        "robin_out_w": carried,
        "residual_rel": (expected - carried) / expected,
        "mean_underside_k": rows[-1][i_bottom] / area,
        "expected_mean_underside_k": tc + expected / (h * area),
    }


# --- solver input ----------------------------------------------------------------


def _table(points):
    return "\n".join(f"      {t!r} {v!r}" for t, v in points)


def _bc(index, name, target, flux=None, robin=None):
    lines = [
        f"Boundary Condition {index}",
        f"  Target Boundaries(1) = {target}",
        f'  Name = "{name}"',
    ]
    if robin is not None:
        lines += [
            f"  Heat Transfer Coefficient = {robin[0]!r}",
            f"  External Temperature = {robin[1]!r}",
        ]
    if flux is not None:
        lines += ["  Heat Flux = Variable Time", "    Real", _table(flux), "    End"]
    lines += ["  Save Scalars = Logical True", "End", ""]
    return "\n".join(lines)


def _property_lines(label, value):
    if is_table(value):
        return f"  {label} = Variable Temperature\n    Real\n{_table(value)}\n    End\n"
    return f"  {label} = {value!r}\n"


def sif(
    case,
    sizes,
    intervals,
    *,
    steady=False,
    source=True,
    direct=False,
    slab=False,
    materials=None,
    label="CONSTANT",
    tim_mm=TIM_MM_DEFAULT,
    tables_source=None,
    leakage=None,
):
    if leakage is not None and (slab or not source):
        raise DeckRefused("leakage_needs_the_powered_die")
    sched = schedule(case) if source else [(0, 0.0), (HORIZON_S, 0.0)]
    if steady:
        p = BASE_W if source else 0.0
        sched = [(0, p), (HORIZON_S, p)]
    h, tc = case["h_w_m2_k"], case["coolant_c"] + 273.15
    bcs = _bc(1, "underside", 1, robin=(h, tc))
    if slab:
        area = (2 * LAYERS["copper"][0] * MM) ** 2
        bcs += _bc(2, "slab top", 2, flux=[(t, p / area) for t, p in sched])
        points, npoints, bodies = f"0.0 0.0 {LAYERS['copper'][1] * MM!r}", 1, (1,)
    else:
        left = case["left_source_fraction"]
        area = (2 * PATCH_HALF * MM) ** 2
        bcs += _bc(2, "left patch", 2, flux=[(t, left * p / area) for t, p in sched])
        bcs += _bc(
            3, "right patch", 3, flux=[(t, (1 - left) * p / area) for t, p in sched]
        )
        bcs += _bc(4, "die top", 4)
        z = round(LAYERS["copper"][1] + tim_mm + LAYERS["die"][1], 9) * MM
        points = f"{-PATCH_X * MM!r} 0.0 {z!r} {PATCH_X * MM!r} 0.0 {z!r}"
        npoints, bodies = 2, (1, 2, 3)
    bodies_text = "".join(
        f"Body {b}\n  Equation = 1\n  Material = {b}\n  Initial Condition = 1\n"
        + ("  Body Force = 1\n" if leakage is not None and b == 3 else "")
        + "End\n"
        for b in bodies
    )
    if materials is None:
        materials, label = resolve_materials()
    nonlinear = leakage is not None or any(
        is_table(materials[n][p]) for n in NAMES for p in ("k", "cp")
    )
    force_text = (
        "Body Force 1\n  Heat Source = Variable Temperature\n    Real\n"
        + _table(leakage_table_w_per_kg(leakage, materials["die"]["rho"]))
        + "\n    End\nEnd\n"
        if leakage is not None
        else ""
    )
    mats = "".join(
        f'Material {i}\n  Name = "{n}"\n'
        + _property_lines("Heat Conductivity", materials[n]["k"])
        + f"  Density = {materials[n]['rho']!r}\n"
        + _property_lines("Heat Capacity", materials[n]["cp"])
        + "End\n"
        for i, n in enumerate(NAMES, start=1)
    )
    nonlinear_lines = (
        f"  Nonlinear System Max Iterations = {NONLINEAR_MAX_ITERATIONS}\n"
        f"  Nonlinear System Convergence Tolerance = {NONLINEAR_TOLERANCE!r}\n"
        if nonlinear
        else "  Nonlinear System Max Iterations = 1\n"
    )
    timing = (
        ""
        if steady
        else "  Timestepping Method = BDF\n  BDF Order = 2\n"
        f"  Timestep Sizes({len(sizes)}) = {' '.join(repr(s) for s in sizes)}\n"
        f"  Timestep Intervals({len(intervals)}) = {' '.join(str(n) for n in intervals)}\n"
    )
    # A steady solve has no mass term to condition CG; it uses the direct
    # solver (the iterative one hit its limit on a frozen steady deck).
    linear = "Direct" if direct or steady else "Iterative"
    mode = (
        f"ON, max iterations {NONLINEAR_MAX_ITERATIONS}, tolerance {NONLINEAR_TOLERANCE!r}"
        if nonlinear
        else "OFF"
    )
    header = (
        f"! f02 deck v3: tables {label}; nonlinear {mode}\n"
        if label != "CONSTANT"
        else "! f02 deck: REFERENCE-PACKAGES-01, generated by f02_deck.py\n"
    )
    if tables_source is not None:
        header += f"! tables: {tables_source['decision']} {tables_source['sha256']} ({tables_source['file']})\n"
    if leakage is not None:
        header += (
            f"! leakage: {leakage['label']} {leakage['form']} {leakage['sha256']}"
            f" range {leakage['range_k'][0]!r}..{leakage['range_k'][1]!r} K, inside the nonlinear iteration\n"
        )
    return f"""{header}Header
  Mesh DB "." "mesh"
End
Simulation
  Max Output Level = 3
  Coordinate System = Cartesian 3D
  Simulation Type = {"Steady State" if steady else "Transient"}
{timing}  Steady State Max Iterations = 1
End
{bodies_text}Initial Condition 1
  Temperature = {case["initial_c"] + 273.15!r}
End
{mats}{force_text}Equation 1
  Active Solvers(1) = 1
End
Solver 1
  Equation = Heat Equation
  Variable = Temperature
  Procedure = "HeatSolve" "HeatSolver"
  Linear System Solver = {linear}
  Linear System Direct Method = Umfpack
  Linear System Iterative Method = CG
  Linear System Preconditioning = ILU0
  Linear System Convergence Tolerance = 1e-12
  Linear System Max Iterations = 5000
  Linear System Abort Not Converged = True
  Steady State Convergence Tolerance = 1e-9
{nonlinear_lines}End
Solver 2
  Exec Solver = After Timestep
  Equation = SaveScalars
  Procedure = "SaveData" "SaveScalars"
  Filename = scalars.dat
  Variable 1 = Time
  Variable 2 = Temperature
  Operator 2 = boundary max
  Variable 3 = Temperature
  Operator 3 = boundary int
  Save Coordinates({npoints},3) = {points}
End
Solver 3
  Exec Solver = After Simulation
  Equation = ResultOutput
  Procedure = "ResultOutputSolve" "ResultOutputSolver"
  Output File Name = final
  Vtu Format = Logical True
  Ascii Output = Logical True
  Single Precision = Logical False
End
{bcs}"""


def resolve_case(case):
    """The case with its start temperature resolved. A v3-family case (it has ``ramp_fraction``) takes ``start_offset_c``
    >= 0, the start being the coolant plus the offset (the start is never below the coolant), and its ``initial_c`` is
    derived; a legacy labelled case is returned unchanged."""
    if "ramp_fraction" not in case:
        return case
    offset = case.get("start_offset_c")
    if (
        type(offset) not in (int, float)
        or isinstance(offset, bool)
        or not math.isfinite(offset)
        or offset < 0
    ):
        raise DeckRefused("start_offset_invalid")
    initial = case["coolant_c"] + offset
    if "initial_c" in case and abs(case["initial_c"] - initial) > 1e-9:
        raise DeckRefused("start_inconsistent_with_the_offset")
    return {**case, "initial_c": initial}


def property_range_k(materials):
    """``(low, high)`` K over which every table layer is defined (the largest first knot to the smallest last knot), or
    None when no property is a table. Outside it Elmer clamps; a solution leaving it is REFERENCE_INVALID.
    """
    firsts, lasts = [], []
    for entry in materials.values():
        for prop in ("k", "cp"):
            if is_table(entry[prop]):
                firsts.append(entry[prop][0][0])
                lasts.append(entry[prop][-1][0])
    return (max(firsts), min(lasts)) if firsts else None


def combined_range_k(materials, leakage=None):
    """The window a solution must stay in: the property tables' (`property_range_k`) intersected with the leakage law's."""
    window = property_range_k(materials)
    if leakage is None:
        return window
    low, high = leakage["range_k"]
    return (
        (low, high) if window is None else (max(window[0], low), min(window[1], high))
    )


def extremes(value, low_k, high_k):
    """``(min, max)`` of a property over [low_k, high_k] (a constant, or the piecewise-linear table with end clamping)."""
    if not is_table(value):
        return value, value
    points = [low_k, high_k] + [t for t, _ in value if low_k < t < high_k]
    samples = [interpolate(value, t) for t in points]
    return min(samples), max(samples)


def bounds_tables(materials, low_k, high_k):
    """The two constant-property tables of the bounds law over the observed range [low_k, high_k] K: ``(lower, upper)``
    where ``lower`` has every table layer at its MAX k and MIN c_p and ``upper`` at its MIN k and MAX c_p, as specified
    (F02_V3_BUILD_SPEC). Pass each to `write_case(tables=...)`. INFO ONLY until the law is proven (OWNER-F02-V3-PICKS-01);
    note that a lower c_p speeds the transient heating, so which pairing bounds the peak is what a measured panel decides.
    """
    lower, upper = {}, {}
    for name, entry in materials.items():
        if not any(is_table(entry[p]) for p in ("k", "cp")):
            continue
        k_lo, k_hi = extremes(entry["k"], low_k, high_k)
        c_lo, c_hi = extremes(entry["cp"], low_k, high_k)
        lower[name] = {"k": k_hi, "cp": c_lo}
        upper[name] = {"k": k_lo, "cp": c_hi}
    return lower, upper


def bounds_check(peak_kt, peak_lower, peak_upper, u):
    """The bounds law's verdict, info only: ``peak_lower - U <= peak_kt <= peak_upper + U``, with ``ordered`` false when the
    two constant-property peaks are not themselves ordered (the pairing is then not a bound at all).
    """
    return {
        "info_only": True,
        "ordered": peak_lower <= peak_upper,
        "within": peak_lower - u <= peak_kt <= peak_upper + u,
    }


def write_case(
    case,
    out,
    level=1,
    dt_scale=1.0,
    steady=False,
    source=True,
    direct=False,
    slab=False,
    tables=None,
    production=False,
    test_mode=False,
    leakage=None,
):
    """Write the deck. ``leakage`` (a `load_leakage` result, or None for none) adds the die's temperature-dependent heat
    source whenever the die is powered; with None the deck is byte-identical to the one without the parameter. ``tables`` (per layer ``{"k", "cp"}``: a constant or a ``[(T_K, value), ...]`` table, or
    HUMAN_INPUT) turns the nonlinear solve on; without it the deck is v2's constants. ``production=True`` with a
    HUMAN_INPUT table raises `DeckRefused`; ``test_mode`` marks the deck and every output "tables": "TEST_ONLY".
    """
    out = Path(out)
    case = resolve_case(case)
    materials, label = resolve_materials(
        tables, production=production, test_mode=test_mode
    )
    tim_mm = check_tim_mm(case.get("tim_thickness_mm", TIM_MM_DEFAULT))
    if leakage is not None:
        if slab or not source:
            raise DeckRefused("leakage_needs_the_powered_die")
        if production and leakage["label"] == LEAKAGE_TEST_ONLY:
            raise DeckRefused("production_deck_cannot_use_test_leakage")
    source_of_tables = (
        tables_source() if label == "PRODUCTION" and tables is None else None
    )
    out.mkdir(parents=True, exist_ok=True)
    info = write_mesh(out, level, slab, tim_mm)
    sizes, intervals = time_steps(case, dt_scale)
    (out / "case.sif").write_text(
        sif(
            case,
            sizes,
            intervals,
            steady=steady,
            source=source,
            direct=direct,
            slab=slab,
            materials=materials,
            label=label,
            tim_mm=tim_mm,
            tables_source=source_of_tables,
            leakage=leakage,
        )
    )
    (out / "ELMERSOLVER_STARTINFO").write_text("case.sif\n1\n")
    meta = {"case": case, "mesh": info, "steps": 1 if steady else sum(intervals),
            "dt_scale": dt_scale, "schedule_w": schedule(case), "steady": steady,
            "source": source, "slab": slab,
            "linear_solver": "umfpack" if direct or steady else "cg-ilu0-1e-12",
            "tables": label, "materials": materials,
            "nonlinear": {"max_iterations": NONLINEAR_MAX_ITERATIONS, "tolerance": NONLINEAR_TOLERANCE}
            if leakage is not None or any(is_table(m[p]) for m in materials.values() for p in ("k", "cp")) else None,
            "property_range_k": combined_range_k(materials, leakage),
            "tables_source": source_of_tables,
            "tim_thickness_mm": tim_mm}  # fmt: skip
    if leakage is not None:
        # the leakage law is recorded (never its coefficients' source file path); a TEST_ONLY law labels every output
        meta["leakage"] = {
            "form": leakage["form"],
            "law": leakage["law"],
            "range_k": list(leakage["range_k"]),
            "decision": leakage["decision"],
            "label": leakage["label"],
            "sha256": leakage["sha256"],
        }
        if leakage["label"] == LEAKAGE_TEST_ONLY:
            meta["tables"] = LEAKAGE_TEST_ONLY
    (out / "deck.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


# --- observers ---------------------------------------------------------------------


def read_scalars(case_dir):
    text = Path(case_dir, "scalars.dat").read_text()
    rows = [list(map(float, x.split())) for x in text.splitlines() if x.strip()]
    names = Path(case_dir, "scalars.dat.names").read_text().splitlines()
    cols = [n.split(":", 1)[1].strip() for n in names if re.match(r"^\s*\d+:", n)]
    return cols, rows


def half_second_samples(t):
    """Row indices of the 0.5 s samples, selected by step index: for every multiple of 0.5 s up to the last step the row
    whose time is nearest (the earlier one on a tie), each row once. v2 kept only rows within 1e-6 of a multiple, which
    dropped samples when an on-time sat off the grid."""
    chosen, j = [], 0
    for m in range(math.floor(t[-1] * 2 + 1e-9) + 1):
        target = m / 2
        while j + 1 < len(t) and abs(t[j + 1] - target) < abs(t[j] - target):
            j += 1
        if not chosen or chosen[-1] != j:
            chosen.append(j)
    return chosen


def observe(case_dir, baseline_top_c=None):
    """Peak die-top temperature over every solver step and its time, the
    first 95 C crossing (interpolated) or NOT_REACHED, extra energy above
    20 W, recovery to within 1 C of a 20 W steady baseline (when supplied),
    and the 0.5 s samples of the die-top maximum and patch centres."""
    cols, rows = read_scalars(case_dir)
    i_top = next(i for i, c in enumerate(cols) if c.startswith("boundary max"))
    i_pts = [
        i for i, c in enumerate(cols) if c.startswith("value: temperature at node")
    ]
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    t = [r[0] for r in rows]
    top = [r[i_top] - 273.15 for r in rows]
    i_peak = max(range(len(top)), key=top.__getitem__)
    crossing = "NOT_REACHED"
    prev_t, prev_v = 0.0, meta["case"]["initial_c"]
    for ti, vi in zip(t, top):
        if vi >= LIMIT_C > prev_v:
            crossing = prev_t + (LIMIT_C - prev_v) / (vi - prev_v) * (ti - prev_t)
            break
        prev_t, prev_v = ti, vi
    sched = meta["schedule_w"]
    energy = sum(
        (b - a) * ((pa + pb) / 2 - BASE_W)
        for (a, pa), (b, pb) in itertools.pairwise(sched)
    )
    recovery = None
    if baseline_top_c is not None:
        last_event = max(x for x, _ in sched if x < HORIZON_S)
        recovery = next(
            (
                ti
                for ti, vi in zip(t, top)
                if ti > last_event and abs(vi - baseline_top_c) <= 1.0
            ),
            "NOT_RECOVERED",
        )
    samples = half_second_samples(t)
    return {
        "peak_top_c": top[i_peak],
        "peak_time_s": t[i_peak],
        "first_95c_crossing_s": crossing,
        "extra_energy_j": energy,
        "recovery_s": recovery,
        "steps": len(t),
        "top_max_c_at_0p5s": [[t[i], top[i]] for i in samples],
        "patch_centres_c_at_0p5s": [
            [t[i], *(rows[i][j] - 273.15 for j in i_pts)] for i in samples
        ],
    }


def time_above_s(t, top, threshold_c):
    """The total time the die-top maximum is above ``threshold_c``, interpolating linearly between solver steps."""
    total = 0.0
    for (ta, va), (tb, vb) in itertools.pairwise(zip(t, top, strict=True)):
        if va >= threshold_c and vb >= threshold_c:
            total += tb - ta
        elif (va >= threshold_c) != (vb >= threshold_c):
            cross = ta + (threshold_c - va) / (vb - va) * (tb - ta)
            total += (tb - cross) if vb >= threshold_c else (cross - ta)
    return total


def crossings(t, top, threshold_c):
    """The interpolated times at which the maximum crosses ``threshold_c``: ``(up, down)`` lists."""
    up, down = [], []
    for (ta, va), (tb, vb) in itertools.pairwise(zip(t, top, strict=True)):
        if (va < threshold_c <= vb) or (va >= threshold_c > vb):
            cross = ta + (threshold_c - va) / (vb - va) * (tb - ta)
            (up if vb >= threshold_c else down).append(cross)
    return up, down


def recovery_s(t, top, threshold_c):
    """From the last upward crossing of ``threshold_c`` to the final downward crossing: None when the maximum never
    reaches it, "NOT_RECOVERED" when it is still above at the last step."""
    up, down = crossings(t, top, threshold_c)
    if not up:
        return None
    if not down or down[-1] < up[-1]:
        return "NOT_RECOVERED"
    return down[-1] - up[-1]


def second_pulse_window(case):
    """``(start of pulse 2, horizon end)``, or None for a single pulse (OWNER-F02-V3-PICKS-01: the window runs to the end
    of the horizon, so the soak after the second pulse is part of it)."""
    if case.get("pulses") != 2:
        return None
    return second_pulse_times(case)[0], HORIZON_S


def second_pulse_times(case):
    """``(start, end)`` of the second pulse itself."""
    duration = case["on_time_s"] / 2
    start = round(round(BURST_START_S + duration, 6) + case["gap_s"], 6)
    return start, round(start + duration, 6)


def second_pulse_peak_c(t, top, window):
    """The die-top maximum over ``window`` = [pulse-2 start, horizon end] (None for one pulse)."""
    if window is None:
        return None
    lo, hi = window
    inside = [v for ti, v in zip(t, top, strict=True) if lo <= ti <= hi]
    return max(inside) if inside else None


_ITERATION_LINE = re.compile(r"ITER=(\d+)\)\s*\(NRM,RELC\):\s*\(\s*(\S+)\s+(\S+)\s*\)")
_ITERSOLVE_FAILURE = re.compile(
    r"IterSolve:\s*Numerical Error:\s*Too many iterations", re.IGNORECASE
)


def runaway_in_log(text):
    """``{"norms": [...]}`` when the solve of a LEAKAGE-ON deck ended in the iterative-solver error exit ("IterSolve: Numerical
    Error: Too many iterations were needed") AFTER nonlinear iterations whose norm rose strictly (at least two, over the last
    time step's iterations): the signature of thermal runaway. Otherwise None, and the failure stays an ordinary solver failure.
    """
    if not _ITERSOLVE_FAILURE.search(text):
        return None
    norms = []
    for line in text.splitlines():
        found = _ITERATION_LINE.search(line)
        if found is None:
            continue
        if int(found.group(1)) == 1:
            norms = []
        try:
            norms.append(float(found.group(2)))
        except ValueError:
            return None
    if len(norms) < 2 or any(b <= a for a, b in itertools.pairwise(norms)):
        return None
    return {"norms": norms}


def reference_status(case_dir, log_path=None):
    """``{"status": "OK" | "REFERENCE_INVALID", ...}`` for the nonlinear iteration of a solved deck.

    A linear (constant-table) deck is OK. A nonlinear deck needs the solver log (`ElmerSolver case.sif > solver.log`):
    every time step's last iteration is read from its `ComputeChange: NS (ITER=n) (NRM,RELC): (norm change)` line, and a
    step that reached the registered maximum with a relative change above the tolerance is REFERENCE_INVALID, so is a log
    with no nonlinear lines (it cannot be verified). The log format is the pinned image's: a dry run (D2 item d) confirms
    the pattern before a pool uses it."""
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    settings = meta.get("nonlinear")
    if settings is None:
        return {"status": "OK", "nonlinear": False}
    if log_path is None or not Path(log_path).is_file():
        raise DeckRefused("solver_log_required")
    steps, last = [], None
    text = Path(log_path).read_text(errors="replace")
    if meta.get("leakage") is not None:
        runaway = runaway_in_log(text)
        if runaway is not None:
            return {
                "status": "REFERENCE_INVALID",
                "reason": "thermal_runaway",
                "evidence": "solver error exit with a strictly rising nonlinear norm",
                **runaway,
            }
    for line in text.splitlines():
        found = _ITERATION_LINE.search(line)
        if found is None:
            continue
        iteration = int(found.group(1))
        if iteration == 1 and last is not None:
            steps.append(last)
        last = (iteration, float(found.group(3)))
    if last is not None:
        steps.append(last)
    if not steps:
        return {
            "status": "REFERENCE_INVALID",
            "reason": "no_nonlinear_iterations_in_the_log",
        }
    most = max(n for n, _ in steps)
    bad = [
        (n, change)
        for n, change in steps
        if n >= settings["max_iterations"] and change > settings["tolerance"]
    ]
    if bad:
        return {
            "status": "REFERENCE_INVALID",
            "reason": (
                "thermal_runaway"
                if meta.get("leakage") is not None
                else "nonlinear_iteration_limit_reached"
            ),
            "steps_not_converged": len(bad),
            "max_iterations_seen": most,
        }
    return {
        "status": "OK",
        "nonlinear": True,
        "steps": len(steps),
        "max_iterations_seen": most,
    }


def observe_v3(case_dir, *, threshold_c, baseline_top_c=None, log_path=None):
    """v2's observations plus the three v3 outputs, with the reference's status and the tables' label.

    ``threshold_c`` is a PARAMETER with no default (the 90 C value is the owner's pick). New keys: ``time_above_s`` (total
    time above the threshold), ``threshold_recovery_s`` (last upward to final downward crossing; None if never reached,
    "NOT_RECOVERED" if still above), ``second_pulse_peak_c`` (the maximum from the second pulse's start to the horizon end; None
    for one pulse). A REFERENCE_INVALID run returns only its status and reason (never numbers that look valid). Every result carries
    "tables": the label of the deck's property tables ("TEST_ONLY" for synthetic ones).
    """
    if (
        type(threshold_c) not in (int, float)
        or isinstance(threshold_c, bool)
        or not math.isfinite(threshold_c)
    ):
        raise DeckRefused("threshold_required")
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    status = reference_status(case_dir, log_path)
    labelled = {"tables": meta.get("tables", "CONSTANT"), "reference": status}
    if meta.get("leakage") is not None:
        labelled["leakage"] = {
            "label": meta["leakage"]["label"],
            "sha256": meta["leakage"]["sha256"],
        }
    if status["status"] != "OK":
        return {"status": "REFERENCE_INVALID", **labelled}
    cols, rows = read_scalars(case_dir)
    i_top = next(i for i, c in enumerate(cols) if c.startswith("boundary max"))
    t = [r[0] for r in rows]
    top = [r[i_top] - 273.15 for r in rows]
    window = meta.get("property_range_k")
    if window is not None:
        # Elmer clamps outside the table; a solution that leaves its range is never extrapolated, it is invalid
        case = meta["case"]
        coolest = min(
            min(top) + 273.15, case["coolant_c"] + 273.15, case["initial_c"] + 273.15
        )
        if max(top) + 273.15 > window[1] or coolest < window[0]:
            return {
                "status": "REFERENCE_INVALID",
                "tables": labelled["tables"],
                "reference": {
                    "status": "REFERENCE_INVALID",
                    "reason": "out_of_property_range",
                    "range_k": window,
                    "observed_k": [coolest, max(top) + 273.15],
                },
            }
    result = observe(case_dir, baseline_top_c)
    return {
        **result,
        "status": "OK",
        "threshold_c": float(threshold_c),
        "time_above_s": time_above_s(t, top, threshold_c),
        "threshold_recovery_s": recovery_s(t, top, threshold_c),
        "second_pulse_peak_c": second_pulse_peak_c(
            t, top, second_pulse_window(meta["case"])
        ),
        **labelled,
    }


#: The scalar outputs a TRAIN row may publish: inputs -> these, never a time series (OWNER-F02-V3-PICKS-01).
SCALAR_KEYS = (
    "peak_top_c",
    "first_95c_crossing_s",
    "extra_energy_j",
    "time_above_s",
    "threshold_recovery_s",
    "second_pulse_peak_c",
)


def scalar_outputs(observed):
    """The publishable scalars of a valid `observe_v3` result, and nothing else (no 0.5 s series, no patch values)."""
    if observed.get("status") != "OK":
        raise DeckRefused("reference_not_valid")
    return {key: observed[key] for key in SCALAR_KEYS}


def _vtu_arrays(case_dir, tim_mm=TIM_MM_DEFAULT):
    vtu = next(Path(case_dir).rglob("final*.vtu")).read_text()

    def block(pattern):
        return re.search(pattern, vtu, re.DOTALL).group(1).split()

    pts = block(r"<Points>\s*<DataArray[^>]*>(.*?)</DataArray>")
    xyz = [tuple(map(float, pts[i : i + 3])) for i in range(0, len(pts), 3)]
    temp = [float(x) for x in block(r'Name="[Tt]emperature"[^>]*>(.*?)</DataArray>')]
    flat = [int(x) for x in block(r'Name="connectivity"[^>]*>(.*?)</DataArray>')]
    offsets = [int(x) for x in block(r'Name="offsets"[^>]*>(.*?)</DataArray>')]
    types = [int(x) for x in block(r'Name="types"[^>]*>(.*?)</DataArray>')]
    # Keep the hexahedra (VTK type 12); Elmer also writes boundary quads.
    conn, start = [], 0
    for end, kind in zip(offsets, types):
        if kind == 12:
            conn += flat[start:end]
        start = end
    # The layers are flat slabs, so an element's material follows from its
    # centroid height (the VTU carries no body ids).
    z_cu = LAYERS["copper"][1] * MM
    z_tim = z_cu + tim_mm * MM
    body = []
    for e in range(len(conn) // 8):
        zc = sum(xyz[i][2] for i in conn[8 * e : 8 * e + 8]) / 8
        body.append(1 if zc < z_cu else (2 if zc < z_tim else 3))
    return xyz, temp, conn, body


def stored_energy_j(case_dir):
    """Sum over hexes of rho cp (mean nodal T - T0) x volume, from the final
    ASCII VTU (axis-aligned boxes: exact for trilinear elements)."""
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    xyz, temp, conn, body = _vtu_arrays(
        case_dir, meta.get("tim_thickness_mm", TIM_MM_DEFAULT)
    )
    t0 = meta["case"]["initial_c"] + 273.15
    materials = meta.get("materials")
    total = 0.0
    for e, b in enumerate(body):
        ids = conn[8 * e : 8 * e + 8]
        span = [
            max(xyz[i][a] for i in ids) - min(xyz[i][a] for i in ids) for a in range(3)
        ]
        name = NAMES[b - 1]
        if materials is None:
            _h, _t, _k, rho, cp = LAYERS[name]
        else:
            rho, cp = materials[name]["rho"], materials[name]["cp"]
        # constant cp: rho cp (T - T0); a cp table: rho times the specific enthalpy integral from T0 to the element's T
        mean = sum(temp[i] for i in ids) / 8
        total += rho * integral(cp, t0, mean) * span[0] * span[1] * span[2]
    return total


def energy_balance(case_dir):
    """(heat in - stored - Robin out) / heat in over the whole run; the
    Robin loss uses each step's end value, as the BDF load does."""
    cols, rows = read_scalars(case_dir)
    meta = json.loads(Path(case_dir, "deck.json").read_text())
    h, tc = meta["case"]["h_w_m2_k"], meta["case"]["coolant_c"] + 273.15
    i_bottom = next(
        i
        for i, c in enumerate(cols)
        if c.startswith("boundary int") and c.endswith("bc 1")
    )
    area = (2 * LAYERS["copper"][0] * MM) ** 2
    out, prev = 0.0, 0.0
    for r in rows:
        out += (r[0] - prev) * h * (r[i_bottom] - tc * area)
        prev = r[0]
    sched = meta["schedule_w"] if meta["source"] else [(0, 0.0), (HORIZON_S, 0.0)]
    heat_in = sum(
        (b - a) * (pa + pb) / 2 for (a, pa), (b, pb) in itertools.pairwise(sched)
    )
    stored = stored_energy_j(case_dir)
    return {
        "heat_in_j": heat_in,
        "stored_j": stored,
        "robin_out_j": out,
        "residual_rel": (heat_in - stored - out) / heat_in if heat_in else None,
    }


# --- analytic slab control -----------------------------------------------------------


def slab_top_rise(q, h, t, *, k=390.0, rho=8960.0, cp=385.0, length=2e-3, terms=80):
    """Top-surface rise of a slab, initially at the coolant temperature, with
    uniform flux q stepped on at t = 0 on top and Robin h below: the exact
    eigenfunction series (lam tan(lam L) = h/k, X = cos(lam u), u from the
    top)."""
    if t <= 0:
        return 0.0
    alpha, ratio = k / (rho * cp), h / k

    def root(n):
        lo, hi = n * math.pi / length + 1e-12, (n + 0.5) * math.pi / length - 1e-12
        for _ in range(200):
            mid = (lo + hi) / 2
            if mid * math.tan(mid * length) > ratio:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    total = q / h + q * length / k
    for n in range(terms):
        lam = root(n)
        s, c = math.sin(lam * length), math.cos(lam * length)
        # integral of theta_s(u) cos(lam u) over [0, L], theta_s = q/h + q (L - u)/k
        integral = (q / h + q * length / k) * s / lam - (q / k) * (
            (c - 1) / lam**2 + length * s / lam
        )
        norm = length / 2 + math.sin(2 * lam * length) / (4 * lam)
        total += -(integral / norm) * math.exp(-(lam**2) * alpha * t)
    return total


def main(argv=None):
    parser = argparse.ArgumentParser(prog="f02_deck")
    parser.add_argument("command", choices=("case",))
    parser.add_argument("label")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mesh", type=int, default=1)
    parser.add_argument("--dt-scale", type=float, default=1.0)
    parser.add_argument("--tim-mm", type=float)
    parser.add_argument("--steady", action="store_true")
    parser.add_argument("--direct", action="store_true")
    args = parser.parse_args(argv)
    case = panel_case(args.label)
    if args.tim_mm is not None:
        case = {**case, "tim_thickness_mm": args.tim_mm}
    meta = write_case(
        case, args.out, args.mesh, args.dt_scale, args.steady, direct=args.direct
    )
    print(json.dumps(meta["mesh"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
