"""Standalone scientific charts from versioned public measurements."""

import argparse
import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

matplotlib.rcParams.update({"svg.hashsalt": "RES09-rev2", "font.size": 9})


def draw(ax, parameter, rows):
    x = list(range(len(rows)))
    labels = [str(r[parameter]) for r in rows]
    if parameter == "population":
        labels = ["Nominal", "Shifted", "Union", "Edge", "Robust SOC", "Robust T"]
    for key, label, color in (
        ("real_point_beats_cheap", "Point win", "#2869a6"),
        ("paired_CI95_lower_positive", "Paired 95% lower > 0", "#ce8100"),
        ("paired_test_pass", "Test pass at delta/alpha", "#397747"),
    ):
        ax.plot(
            x,
            [r.get(key, float("nan")) for r in rows],
            marker="o",
            label=label,
            color=color,
        )
    ax.set_ylim(-5, 105)
    ax.set_ylabel("Raw real members (of 100)")
    ax.set_xticks(x, labels)
    ax.grid(axis="y", alpha=0.2)
    title = {
        "population": "P_V2: strict settled + fallback-feasible",
        "kappa": "kappa: benefit units per condition-solve",
        "k": "k: validator-derived cap",
        "delta": "Delta_min: absolute benefit units",
        "alpha": "alpha: one-sided test error option",
    }[parameter]
    ax.set_title(title, weight="bold", fontsize=10)
    cells = []
    for r in rows:
        if r.get("status") == "EMPTY_BANK_NOT_ZERO_VALUE":
            cells.append(["0 / gap", "gap", "gap", "gap", "gap"])
        else:
            rank = r["always_abstain_rank"]
            tau = r["tau_lex_to_anchor"]
            cells.append(
                [
                    str(r["n"]),
                    f'{rank["best"]}-{rank["worst"]}',
                    str(r["exact_U_tie_pairs"]),
                    str(r["unsafe_separated_exact_tie_pairs"]),
                    f"{tau:.2f}",
                ]
            )
    table = ax.table(
        cellText=list(map(list, zip(*cells, strict=True))),
        rowLabels=[
            "Questions",
            "No-op rank /101",
            "Exact U tie pairs",
            "Unsafe ties split",
            "tau to union anchor",
        ],
        cellLoc="center",
        bbox=[0, -0.63, 1, 0.46],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7)
    for i, r in enumerate(rows):
        if r.get("no_member_beats_cheap_point"):
            ax.annotate(
                "NO POINT WIN",
                (i, 0),
                xytext=(0, 13),
                textcoords="offset points",
                ha="center",
                fontsize=6,
                color="#a42828",
            )
        if r.get("paired_CI_available") is False:
            ax.annotate(
                "CI gap",
                (i, 0),
                xytext=(0, 25),
                textcoords="offset points",
                ha="center",
                fontsize=6,
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--preview", type=pathlib.Path)
    args = parser.parse_args()
    data = json.loads(args.results.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    for parameter in ("population", "kappa", "k", "delta", "alpha"):
        rows = [r for r in data["profiles"] if r["curve"] == parameter]
        fig, ax = plt.subplots(figsize=(8.5, 5.6))
        draw(ax, parameter, rows)
        ax.legend(loc="upper right", fontsize=8)
        fig.subplots_adjust(left=0.22, right=0.97, top=0.89, bottom=0.43)
        fig.text(
            0.03,
            0.015,
            "DEVELOPMENT. Grid/anchor are assumptions, not choices. CI = exploratory block bootstrap; test = exact block sign-flip.\nSingleton CI is a gap; empty bank is not zero. Safety eligibility unknown. All no-op U = 0. Ties: exact U before safety.",
            fontsize=8,
        )
        fig.savefig(args.output / f"{parameter}.svg", metadata={"Date": None})
        plt.close(fig)
    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    for ax, parameter in zip(
        axes.flat, ("population", "kappa", "k", "delta", "alpha"), strict=False
    ):
        draw(ax, parameter, [r for r in data["profiles"] if r["curve"] == parameter])
    axes[2, 1].axis("off")
    axes[2, 1].text(
        0,
        0.95,
        "Read before choosing\n\nOnly 3 strict questions survive.\nNo fresh-fold or gate-pass claim.\nNo test passes the shown alpha grid.\nSingle-question CI is unavailable.\nEmpty edge/robust banks are gaps.\nDelta/alpha do not change U ranks.\nAll values stay HUMAN_INPUT.",
        va="top",
        fontsize=12,
    )
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 0.945))
    fig.suptitle(
        "RES-09 owner-choice curves | DEVELOPMENT | five values, none selected",
        fontsize=16,
    )
    fig.subplots_adjust(
        left=0.15, right=0.97, top=0.89, bottom=0.21, wspace=0.6, hspace=1.4
    )
    fig.text(
        0.02,
        0.02,
        "ASSUMPTION display anchor: union / k=3 / kappa=0.1 / Delta=0.05 / alpha=0.01. Point wins do not establish useful gain.\nPaired CIs are pointwise, exploratory temperature-block bootstrap (2,000 resamples); no simultaneous coverage claim.\nTest counts require U>0, margin>Delta and block sign-flip p<=alpha; not a registered/calibrated takeover rule.",
        fontsize=10,
    )
    fig.savefig(args.output / "owner-five-curves.svg", metadata={"Date": None})
    if args.preview:
        fig.savefig(args.preview, dpi=120)
    plt.close(fig)
    # Matplotlib path serialization contains trailing blanks; retain geometry
    # while producing repository-clean, deterministically replayable SVG text.
    for path in args.output.glob("*.svg"):
        text = path.read_text(encoding="utf-8")
        path.write_bytes(
            ("\n".join(line.rstrip() for line in text.splitlines()) + "\n").encode()
        )


if __name__ == "__main__":
    main()
