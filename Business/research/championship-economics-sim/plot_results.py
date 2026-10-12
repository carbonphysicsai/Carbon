"""Optional static research plot; reads this ticket's aggregate output only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    data = json.loads((root / "results.json").read_text(encoding="utf-8"))
    selected = {row["scenario"]: row for row in data["scenarios"]}
    retention = [0.5, 0.8, 0.9, 0.95, 1.0]
    panels = [
        ("paid_fraction_of_challenge_allocation", "Battery allocation paid (%)", 100),
        ("crown_changes_per_30_days", "Owner crown changes / 30 days", 1),
        ("top1_paid_share", "Largest recipient's paid share (%)", 100),
        (
            "newcomer_crowned_within_30_days",
            "Newcomer first-30-day crown chance (%)",
            100,
        ),
        ("research_action_fraction", "Research share of active actor-days (%)", 100),
        ("net_log_accuracy_improvement", "Net latent log accuracy gain", 1),
    ]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 8.3), layout="constrained")
    for ax, (metric, title, scale) in zip(axes.flat, panels):
        for behavior, color, style in [
            ("adaptive", "#176b87", "-"),
            ("fixed", "#737b84", "--"),
        ]:
            stats = [
                selected[f"grid_{behavior}_d{d:g}_N4"]["metrics"][metric]
                for d in retention
            ]
            mid = [v["base"] * scale for v in stats]
            low = [v["low"] * scale for v in stats]
            high = [v["high"] * scale for v in stats]
            ax.plot(retention, mid, style, marker="o", color=color, label=behavior)
            ax.fill_between(retention, low, high, color=color, alpha=0.14)
        ax.set_title(title, loc="left", fontweight="bold")
        ax.set_xlabel("Daily retention d")
        ax.set_xticks(retention, ["0.50", "0.80", "0.90", "0.95", "1.00"])
        ax.grid(axis="y", alpha=0.18)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylim(bottom=0)
    axes[0, 0].legend(title="Effort regime", frameon=False)
    fig.suptitle(
        "Championship economics: conditional synthetic population\n"
        "N=4; 160 episode clusters; shaded 95% Monte Carlo bands",
        fontsize=15,
        fontweight="bold",
    )
    fig.savefig(root / "economics.svg", metadata={"Date": None})
    if args.preview:
        fig.savefig(args.preview, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
