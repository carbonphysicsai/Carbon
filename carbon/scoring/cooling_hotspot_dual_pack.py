"""Cooling 1.6: the encoded grader without the non-monotone hotspot response.

OWNER-COOLING-HOTSPOT-GATE-DROP-01 adopts this change prospectively. The
hotspot ratio remains an input and accuracy still measures its predictions;
only the rise/ratio sign gate and registered power-law exponent are removed.
All other gates, sensitivities and measurements are the encoded grader's.
Earlier Cooling versions keep their original definition builder.
"""

from __future__ import annotations

import sys

from carbon.scoring import cooling_encoded_dual_pack as encoded

CHALLENGE = encoded.CHALLENGE
VERSION = "1.6"
EVALUATION_VERSION = "cooling-dual-development-grid-v3"
CASE_ID = "cooling-development-grid-8x6"
VERSIONS = {VERSION: (EVALUATION_VERSION, CASE_ID)}
POOL_VERSIONS = {VERSION: ("cooling-pool-sealed-v2", "cooling-sealed-pool-set")}
FILES = (*encoded.FILES, "cooling_hotspot_dual_pack.py")


def definition(*, bank, train_raw, rule="baseline_legs"):
    result = encoded.definition(bank=bank, train_raw=train_raw, rule=rule)
    if "physics" in result:
        # The builder returns a fresh definition. Mutate only this version's
        # response; neither the TRAIN fit nor any older definition is altered.
        response = result["physics"]["response"]
        j = response["outputs"].index("rise_c")
        d = response["inputs"].index("hotspot_ratio")
        response["exponent"][j][d] = None
        response["sign_gates"] = [
            gate
            for gate in response["sign_gates"]
            if (gate["output"], gate["input"]) != ("rise_c", "hotspot_ratio")
        ]
    return result


def sealed_adapter(version):
    if type(version) is not str or version not in POOL_VERSIONS:
        return None
    from carbon.scoring import pool_version

    evaluation, case_id = POOL_VERSIONS[version]
    return pool_version.variant(
        _SELF, version, evaluation, case_id, challenge_id=CHALLENGE
    )


def write_sealed_pack(root, bank, *, version=VERSION, **platform):
    from carbon.challenge_kit import cooling_sealed_pack
    from carbon.scoring import sealed_pack_writer

    return sealed_pack_writer.write(
        sealed_adapter(version),
        cooling_sealed_pack,
        root,
        bank,
        challenge=CHALLENGE,
        version=version,
        is_sealed_bank=encoded.is_pool_bank,
        refusal=encoded.Refused("cooling_bank_population"),
        pack_suffix=encoded.PACK_SUFFIX,
        **platform,
    )


def producer_digest():
    from carbon.scoring import physical_dual_pack as physical

    return physical.producer_digest(_SELF)


def adapter(rule="baseline_legs"):
    if rule != "baseline_legs":
        raise ValueError("Cooling 1.6 serves the baseline_legs rule")
    return _SELF


def pack_documents(**kwargs):
    from carbon.scoring import physical_dual_pack as physical

    return physical.pack_documents(_SELF, **kwargs)


def write_development_pack(root, **platform):
    from carbon.scoring import physical_dual_pack as physical

    return physical.write_development_pack(_SELF, root, **platform)


def produce(**kwargs):
    from carbon.scoring import physical_dual_pack as physical

    return physical.produce(_SELF, **kwargs)


def __getattr__(name):
    return getattr(encoded, name)


_SELF = sys.modules[__name__]
