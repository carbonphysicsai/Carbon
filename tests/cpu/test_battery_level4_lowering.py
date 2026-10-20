"""Battery's Level 4 lowering lives beside the pinned `level4.py`
(Validator ruling, gate failure #3, option A).

The pinned module keeps its bytes (`test_battery_level4_v4`). `level4_lowering`
carries the miner-side lowering that changed after the pin (graph ensembles at
one member's interface, and the published kit inputs). For every Level 0
strategy that lowers, its submission and interface digests are the pinned
module's own, so historical v3 evidence reproduces.
"""

from __future__ import annotations

import pytest

pytest.importorskip("jax")

from carbon.battery import level4 as pinned
from carbon.battery import level4_lowering
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import intake, submission

#: The digests measured when the change moved beside the pin (19 Oct), equal
#: under the pinned and the beside module.
DIGESTS = {
    "scaffold_mlp": "sha256:530026ba",
    "panel_mlp": "sha256:ac2bab95",
    "panel_deeponet": "sha256:fd825567",
}
INTERFACE = "sha256:8b491a4c"


def _lower(module, strategy):
    manifest, _ = module.lower_recipe(
        strategy, allowlist_module.load(), max_bytes=intake.BOUNDS["document_bytes"]
    )
    return submission.digest(manifest), module.interface(strategy).digest()


@pytest.mark.parametrize("label", sorted(DIGESTS))
def test_every_level0_strategy_lowers_as_the_pinned_module_did(label):
    strategy = pinned.level0_strategies()[label]
    beside = _lower(level4_lowering, strategy)
    assert beside == _lower(pinned, strategy)
    assert beside[0].startswith(DIGESTS[label]) and beside[1].startswith(INTERFACE)


def test_the_beside_interface_registers_the_kit_the_pinned_one_does_not():
    strategy = pinned.level0_strategies()["scaffold_mlp"]
    assert pinned.interface(strategy).kit == ()
    assert level4_lowering.interface(strategy).kit
    assert (
        level4_lowering.interface(strategy).digest()
        == pinned.interface(strategy).digest()
    )
