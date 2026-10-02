# Copyright (c) 2026 Carbon Physics AI, Inc.
# SPDX-License-Identifier: MIT
# Full license text: see LICENSE at the repository root.

"""Which published strategy capture limit a refused strategy exceeded.

The compiler refuses a strategy that breaks a capture limit with its closed
code `strategy.identity_invalid` (Design_Specs/Candidate_Assembly_and_Strategy_
Compiler_Contract.md section 10.4 fixes the code list and forbids dynamic
diagnostics in the compiler). That code has three causes, so an agent told only
the code cannot tell which rule it broke (OWNER-BATTERY-V2-DISCLOSURE-01,
item 4). The research surface names the limit beside the unchanged code.

The answer comes from the real capture, not a second copy of its rules: for
each published limit, every other limit is relaxed and the capture rerun. If
it still fails, that limit alone is exceeded. Each capture check compares one
measure with its own limit, so a strategy breaks the capture exactly when at
least one of them is named. A copy of the rules could drift from the capture;
this cannot.
"""

from __future__ import annotations

from dataclasses import replace

from carbon.fees.model import SubmissionResourceError, SubmissionResourceLimits
from carbon.fees.strategy_identity import identify_strategy

#: The limits a strategy's capture is measured against, in the order the
#: published limits list them. The retained-store and concurrency fields are
#: not about one strategy and are never reported.
CAPTURE_LIMITS = (
    "max_total_value_nodes",
    "max_object_members",
    "max_list_items",
    "max_string_utf8_bytes",
    "max_object_key_utf8_bytes",
    "max_strategy_identity_bytes",
)
#: A relaxed limit: large enough that a bounded tool argument never meets it.
_RELAXED = 1 << 32


def _breaks(strategy, limits):
    try:
        identify_strategy(strategy, limits)
    except SubmissionResourceError:
        return True
    except Exception:  # noqa: BLE001 - any other failure is not a limit breach
        return False
    return False


def limits_exceeded(strategy, limits):
    """The published capture limits this strategy exceeds, each with its
    value, in published order; empty when no capture limit is exceeded."""
    if type(limits) is not SubmissionResourceLimits:
        raise TypeError("exact SubmissionResourceLimits required")
    if not _breaks(strategy, limits):
        return ()
    relaxed = {name: _RELAXED for name in CAPTURE_LIMITS}
    exceeded = []
    for name in CAPTURE_LIMITS:
        only = replace(limits, **{k: v for k, v in relaxed.items() if k != name})
        if _breaks(strategy, only):
            exceeded.append({"limit": name, "value": getattr(limits, name)})
    return tuple(exceeded)
