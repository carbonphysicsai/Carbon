"""Cooling 1.8's sealed adapter, reached only through its version-overlay dispatch (`version_overlay`).

Cooling 1.8 grades the SAME quantities as 1.7 (Cooling's own measurement on decoded law-safe rows: die peak, profile,
pressure drop) under a NEW sealed evaluation (a new exam key: no king carries over). What changes is the TRAIN: 1.8 is
trained on its own extended TRAIN (the native 400 rows byte-equal plus the added in-box rows,
`physical_public_train.EXTENDED`), so every TRAIN-relative part of the measurement (the learned-krr-v1 baseline legs, the
physics block's TRAIN response) reads 1.8's native extended TRAIN, never TRAIN 400. Everything else delegates UNCHANGED
to `cooling_encoded_dual_pack`, whose bytes (so every earlier Cooling producer digest) do not move.

The pool grade (A by the pool exam, its headroom `physics` block and the menu D) comes from `pool_version` and the
version's `pool_constants.json` entry: until every owner value there is set, it refuses (HUMAN_INPUT), never a default.
"""

from __future__ import annotations

import sys

import importlib

#: The sealed module this version extends. It is imported LAZILY (`_enc`), never at this module's import: the overlay
#: arms its dispatch on that module's import, so importing it here would call `dispatch` on a half-built module.
_ENCODED = "carbon.scoring.cooling_encoded_dual_pack"
CHALLENGE = "chip-cold-plate"
VERSION = "1.8"
#: The native extended TRAIN whose rows this version's measurement reads (its encoded twin is what miners train on).
NATIVE_TRAIN = "cooling-dev-train-1p8-v1"
#: The served (encoded) TRAIN the version's registry entry must name.
SERVED_TRAIN = "cooling-dev-train-1p8-v1-encoded"
#: Cooling 1.8's sealed evaluation (a new exam key) and its pool set case. The name is the Validator's to confirm.
POOL_VERSIONS = {VERSION: ("cooling-pool-sealed-v4", "cooling-sealed-pool-set")}
_OWN_FILE = "cooling18_dual_pack.py"


def _enc():
    return importlib.import_module(_ENCODED)


def _native_train():
    from carbon.challenge_kit import physical_public_train

    return physical_public_train.load_extended_train(NATIVE_TRAIN, CHALLENGE)["train"]


def definition(*, bank, train_raw, rule="baseline_legs"):
    del train_raw
    return _enc()._cooling.definition(bank=bank, train_raw=_native_train(), rule=rule)


def measure(
    *, bank_rows, outputs, repeats, definition, limits, objective, train_raw, names
):
    """Cooling's measurement of decoded rows against 1.8's native extended TRAIN."""
    del train_raw
    return _enc()._cooling.measure(
        bank_rows=bank_rows,
        outputs=_enc()._decoded(outputs),
        repeats=[_enc()._decoded(repeat) for repeat in repeats],
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=_native_train(),
        names=names,
    )


def applied_pack(*, bank_rows, definition, limits, objective, train_raw, names):
    """Cooling's applied pack (its learned-krr-v1 baseline) on 1.8's native extended TRAIN."""
    del train_raw
    return _enc()._cooling.applied_pack(
        bank_rows=bank_rows,
        definition=definition,
        limits=limits,
        objective=objective,
        train_raw=_native_train(),
        names=names,
    )


def sealed_adapter(version):
    """The pool-graded adapter of Cooling 1.8; None for any other version."""
    if version != VERSION:
        return None
    from carbon.scoring import pool_version

    evaluation, case_id = POOL_VERSIONS[VERSION]
    return pool_version.variant(
        _SELF, VERSION, evaluation, case_id, challenge_id=CHALLENGE
    )


def _adapter_for_bank(bank, version):
    if not _enc().is_pool_bank(bank):
        raise _enc()._cooling.Refused("cooling_bank_population")
    return sealed_adapter(version)


def _writer(root, bank, *, version=VERSION, **platform):
    """Cooling 1.8's receiver pack: the sealed grid, its private probes and the pool rows, under this adapter."""
    from carbon.challenge_kit import cooling_sealed_pack
    from carbon.scoring import sealed_pack_writer

    if version != VERSION:
        raise ValueError("cooling18_dual_pack writes Cooling 1.8 packs only")
    return sealed_pack_writer.write(
        sealed_adapter(VERSION),
        cooling_sealed_pack,
        root,
        bank,
        challenge=CHALLENGE,
        version=VERSION,
        is_sealed_bank=_enc().is_pool_bank,
        refusal=_enc()._cooling.Refused("cooling_bank_population"),
        pack_suffix=_enc().PACK_SUFFIX,
        **platform,
    )


def dispatch(config):
    """The overlay dispatch: registers Cooling 1.8 in `cooling_encoded_dual_pack`'s tables without editing that file.
    ``config`` must be empty (1.8 carries no public region box here; hidden bounds never enter the overlay).
    """
    if config:
        raise ValueError("Cooling 1.8's dispatch takes no config")
    return {
        "challenge": CHALLENGE,
        "version": VERSION,
        "pool_versions": POOL_VERSIONS[VERSION],
        "adapter": sealed_adapter,
        "adapter_for_bank": _adapter_for_bank,
        "writer": _writer,
    }


def producer_digest():
    from carbon.scoring import physical_dual_pack as physical

    return physical.producer_digest(_SELF)


def __getattr__(name):
    if name == "FILES":
        # 1.8's own producer identity: the sealed module's files, then this one
        return (*_enc().FILES, _OWN_FILE)
    return getattr(_enc(), name)


_SELF = sys.modules[__name__]
