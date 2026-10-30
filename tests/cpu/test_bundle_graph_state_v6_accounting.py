"""A catalog practice's graph check runs under the launch versions' accounting (v6).

Allowlist v8 counts constants as recipe information (`recipe_info_bytes`), a
measurement `graph.measure` does not make; `_checked_graph` once passed only
`graph.measure(doc)` to `check_caps` and every catalog practice failed with a
KeyError (reported as FAILED_INFRA).
"""

import pytest

from carbon.challenge_kit import version_registry
from carbon.development_session import bundle_graph_state
from carbon.development_session.construction_recipe import RecipeRefused
from carbon.level4 import allowlist
from carbon.level4.tooling import lower_jax

LAUNCH_VERSIONS = (
    ("electric-motor-magnetics", "1.5"),
    ("chip-cold-plate", "1.6"),
    ("f08-ribbed-bracket", "1.7"),
    ("f02", "2.5"),
)


def _doc(permitted, constant=0.5):
    import jax.numpy as jnp

    traced = lower_jax.trace(
        lambda p, x: p * x + constant,
        jnp.asarray([2.0, 3.0], dtype=jnp.float32),
        jnp.asarray([4.0, 5.0], dtype=jnp.float32),
    )
    return lower_jax.lower(
        traced,
        role="forward",
        allowlist=permitted,
        input_names=["params/0", "inputs/x"],
    )


@pytest.mark.parametrize("challenge_id,version", LAUNCH_VERSIONS)
def test_checked_graph_runs_under_each_launch_versions_accounting(
    challenge_id, version
):
    served = version_registry.entry(challenge_id, version)
    assert served.allowlist == "v8"
    permitted = allowlist.Allowlist(allowlist.v8_bytes())
    assert allowlist.accounting_for(permitted)[0] == allowlist.CONSTANT_ACCOUNTING_V6
    doc = _doc(permitted)
    assert bundle_graph_state._checked_graph(doc, permitted)


def test_checked_graph_still_refuses_an_over_budget_graph():
    permitted = allowlist.Allowlist(allowlist.v8_bytes())
    doc = _doc(permitted)
    caps = {**allowlist.caps_for(permitted), "constant_bytes": 1}
    original = allowlist.caps_for
    allowlist.caps_for = lambda _a: caps
    try:
        with pytest.raises(RecipeRefused, match="bundle_graph_caps_refused"):
            bundle_graph_state._checked_graph(doc, permitted)
    finally:
        allowlist.caps_for = original
