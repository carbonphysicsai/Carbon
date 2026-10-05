"""Cooling's Level 0 attack vectors as a public, pure API for the Carbon
Validator's gate-audit harness (VALIDATOR-09), and the byte pin that keeps the
adapter's own output unchanged by it (GRAPHITE-ATTACKER-COOLING-API-01).

The claims tested:
- the pin: every prediction family's attacks, its oracle evidence and specimen
  digests, both control splits and each selective-fault selection on the
  scaffold are byte-identical to `cooling-l0.v2` as merged before the API
  (recorded before the transforms were refactored).
"""

from __future__ import annotations

from carbon.agent_campaign.attack.adapters import cooling as c

A = c.ADAPTER

# -- the byte pin: the adapter's output at cooling-l0.v2 --------------------------------------------
#: The families whose attacks or controls are built from the PRACTICE
#: references by the transforms the vector API shares.
PREDICTION_FAMILIES = (
    "cooling_optimism",
    "flow_imbalance_masking",
    "pressure_underprediction",
    "group_sacrifice",
    "mandatory_failure",
    "practice_disclosure",
    "resource_accounting",
)
#: Recorded at origin/main b327ac12d (`cooling-l0.v2`) before the refactor.
PINNED_VERSION = "carbon.attack.adapter.cooling-l0.v2"
PINNED = {
    "attacks": {
        "cooling_optimism": "sha256:ea1b5804650b121bbd698bae7f121fb886588f13888a9484259dc6e77f7a3691",
        "flow_imbalance_masking": "sha256:dcf797c9ccba52bae9af0b91f7abf2cd94d68fb59f6fcc2f079c4deee9331718",
        "group_sacrifice": "sha256:18296414ccd60ecad586bb99df2c19e68da64485ca732b090a20f308895ad2a6",
        "mandatory_failure": "sha256:510b8dbe1e8c4a93abc6c1e346828e4c25ed53b8ac1cc1e9b3f477e2bb49aa86",
        "practice_disclosure": "sha256:82984b9504113be1ca448208cd3bc03d6e81ed9c21953809b97f7a05cd85a65b",
        "pressure_underprediction": "sha256:1722291598ce6896a70cc912303bf7d40ef735dae2df952b6d2f840f591be8ec",
        "resource_accounting": "sha256:6ad0e897af132346384fcab95eee83546ed9ef65f0f0cb42eb384742845c8f5e",
        "selective_fault": "sha256:40b8766a8ab26cf5f99a8b2bc656ac1eba598ad52e768fe8a661778b3a576e4d",
    },
    "controls": {
        "held_out": "sha256:807184c3c0ac21acf54df105cc438c11e410821191358fe9b67c5f77f99eca08",
        "trained": "sha256:c174e79172e5f0598f59e0cc7194b76be0d50d5923aa8d4f0d1cc5d5097d3d4c",
    },
    "evidence": {
        "cooling_optimism": "sha256:e3f70850ec95dfbd31bd4dd8a961b3e928db5e0db87e97cb62fb5ff100be3c6f",
        "flow_imbalance_masking": "sha256:55bff355fe7f29b02129f9a0e6c9aace327469aae5e4c81758629c9231f7f60e",
        "group_sacrifice": "sha256:862440b4f8e6dcb671c2e15f8121e4434c81c1fd74cf8a7839eea6b24c4e45b0",
        "mandatory_failure": "sha256:4c6f41339e248984176e9f6dbe25c08aef66d7953b685569326c3dd9feafa508",
        "practice_disclosure": "sha256:7316a0f2fccdebe26559818663ddf8c1befa8ea170fcd2550d7a2c224f6807e6",
        "pressure_underprediction": "sha256:0f577a288461d90da061fff8a1bbc3a28467855f92b5b9658a40cac93e378b15",
        "resource_accounting": "sha256:43a5d79e47e881e855b3c45152b13a90359a4ba5db85f3236869710e68550bfb",
    },
    "faulted": {
        "above_own_mean": "sha256:1f6656623106e7fefe62012c6d22c1b00437b5a78436c4673e39334694c3c30e",
        "all": "sha256:bacd726eb924b8cdb80aa681e4fe28af5c694bb162f35e7df62e4ae74cf9903a",
        "hot_group": "sha256:e2354991414b429ae14c527582283729ac98b71c40405dc9e3a2c0da088f63a5",
        "none": "sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "worse_half": "sha256:4dddb6b28fcff369bf4b5ec0043b99d7f1dc86e29ae7238a70c24b3ed124c767",
        "worst_k": "sha256:8d59e55e3ca620eaaf35e055103225ecf760d918fd718f7ef890f480be478046",
    },
}


def _adapter_output():
    """The adapter's own output the pin binds, computed fresh."""
    out = {"attacks": {}, "evidence": {}, "controls": {}, "faulted": {}}
    for name in PREDICTION_FAMILIES + ("selective_fault",):
        spec = A.family_spec(name)
        out["attacks"][name] = c._digest([[n, v] for n, v in spec.attacks()])
    for name in PREDICTION_FAMILIES:
        spec = A.family_spec(name)
        readings = (A.assess(spec, item) for item in spec.attacks())
        out["evidence"][name] = c._digest(
            [[r.oracle.evidence_digest, r.oracle.specimen_digest] for r in readings]
        )
    for split in c.SPLITS:
        out["controls"][split] = A.controls_digest(split)
    for select in c.FAULT_SELECTIONS:
        out["faulted"][select] = c._digest(c._faulted_cases(c._scaffold(), select))
    return out


def test_the_adapters_output_is_byte_identical_to_the_pin():
    """The adapter's attacks, oracle evidence, controls and fault selections
    are unchanged; a change here is a change to the emitted output and moves
    `ADAPTER_VERSION`."""
    assert c.ADAPTER_VERSION == PINNED_VERSION
    c.clear_caches()
    assert _adapter_output() == PINNED
