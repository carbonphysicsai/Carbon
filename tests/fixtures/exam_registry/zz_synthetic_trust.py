"""The synthetic exam's trust derive (X1): its one trust output is its one physics column. Synthetic, public, no science."""

from __future__ import annotations


def derive(rows, inputs):
    return rows[:, :1]
