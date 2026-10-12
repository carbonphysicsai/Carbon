"""A small deterministic SVG of the ledger: one panel per metric, one line per level.

No third-party code and no clock: the same ledger always renders the same bytes. A point is a
measured value with its sample size printed beside it (small samples stay visible); an
UNMEASURED value is a gap, never a zero.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

PANELS = (
    ("Share of Constructor runs BUNDLED", ("constructor", "bundled_share")),
    (
        "USD per BUNDLED run (reservation + model charge)",
        ("constructor", "usd_per_bundled"),
    ),
    ("Share of proposals refused", ("constructor", "refusals", "rate")),
    ("Real findings per Attacker run (triaged)", ("attacker", "real_findings_per_run")),
    (
        "Share of listed attack families attempted",
        ("attacker", "families", "share_attempted"),
    ),
    (
        "Median public-dev decision-loss improvement (n beside; PUBLIC data only)",
        ("constructor", "improvement", "public_dev", "decision_loss"),
    ),
    (
        "Median public-dev accuracy-error improvement (PUBLIC data only)",
        ("constructor", "improvement", "public_dev", "accuracy_error"),
    ),
    ("Readiness items NOT_BUILT", ("gate", "last", "NOT_BUILT")),
)
COLORS = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#8c564b")
WIDTH, HEIGHT, PAD = 420, 190, 36


def _dig(line, path):
    value = line
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None, 0
        value = value[key]
    if isinstance(value, dict) and "value" in value:
        return value["value"], value.get("n", 0)
    return value, 0


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def series_of(lines, path):
    """`{level: [(batch order, value, n)]}` for measured values only."""
    out = {}
    ordered = sorted(lines, key=lambda l: (l["date"], l["batch"], l["level"]))
    for index, line in enumerate(ordered):
        value, n = _dig(line, path)
        number = _number(value)
        if number is not None:
            out.setdefault(line["level"], []).append((index, number, n))
    return out, len(ordered)


def render_svg(lines):
    ordered = sorted(lines, key=lambda l: (l["date"], l["batch"], l["level"]))
    columns, rows = 2, (len(PANELS) + 1) // 2
    total_w, total_h = columns * WIDTH, rows * HEIGHT + 40
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" '
            f'viewBox="0 0 {total_w} {total_h}" font-family="sans-serif" font-size="11">'
        ),
        f'<rect width="{total_w}" height="{total_h}" fill="white"/>',
        (
            '<text x="12" y="20" font-size="14" font-weight="bold">Graphite progress '
            "(DEVELOPMENT evidence; n beside each point; a gap is UNMEASURED)</text>"
        ),
    ]
    for slot, (title, path) in enumerate(PANELS):
        ox, oy = (slot % columns) * WIDTH, 40 + (slot // columns) * HEIGHT
        series, count = series_of(ordered, path)
        values = [v for points in series.values() for _, v, _ in points]
        low, high = (min(values + [0.0]), max(values)) if values else (0.0, 1.0)
        high = high if high > low else low + 1.0
        plot_w, plot_h = WIDTH - 2 * PAD, HEIGHT - 2 * PAD
        parts.append(
            f'<text x="{ox + PAD}" y="{oy + 14}" font-weight="bold">{escape(title)}</text>'
        )
        parts.append(
            f'<rect x="{ox + PAD}" y="{oy + PAD - 8}" width="{plot_w}" height="{plot_h}" '
            'fill="none" stroke="#bbbbbb"/>'
        )
        parts.append(f'<text x="{ox + 4}" y="{oy + PAD}">{high:g}</text>')
        parts.append(f'<text x="{ox + 4}" y="{oy + PAD - 8 + plot_h}">{low:g}</text>')
        if not values:
            parts.append(
                f'<text x="{ox + PAD + 8}" y="{oy + PAD + 24}">UNMEASURED</text>'
            )
            continue
        for color_index, (level, points) in enumerate(sorted(series.items())):
            color = COLORS[color_index % len(COLORS)]
            xy = []
            for index, value, n in points:
                x = ox + PAD + (plot_w * index / max(count - 1, 1))
                y = oy + PAD - 8 + plot_h * (1 - (value - low) / (high - low))
                xy.append((round(x, 1), round(y, 1)))
                parts.append(
                    f'<circle cx="{xy[-1][0]}" cy="{xy[-1][1]}" r="3" fill="{color}"/>'
                )
                parts.append(
                    f'<text x="{xy[-1][0] + 4}" y="{xy[-1][1] - 4}" fill="{color}">n={n}</text>'
                )
            if len(xy) > 1:
                joined = " ".join(f"{x},{y}" for x, y in xy)
                parts.append(
                    f'<polyline points="{joined}" fill="none" stroke="{color}"/>'
                )
            parts.append(
                f'<text x="{ox + PAD + 6 + 44 * color_index}" y="{oy + HEIGHT - 8}" fill="{color}">L{level}</text>'
            )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
