"""Launchpad campaign for F02 (Burst Thermal) 2.3, a direct-recipe-only version.

The shared direct campaign (`carbon.direct_campaign.campaign`), bound to
F02 (Burst Thermal)'s spec: catalog or graph recipes, practice through the receiver's own
build, freeze from a practice result, submit through the signed construction
receiver. While F02 (Burst Thermal)'s catalog is empty the campaign refuses to start
(`f02_catalog_empty`). Every hook runs under F02 (Burst Thermal)'s research key, which
the registry's composer sets (`challenge_registry.campaigns`).
"""

from __future__ import annotations

from carbon.direct_campaign import campaign as _shared

from .contracts import SPEC

CATALOG_VERSIONS = SPEC.versions
PRACTICE_PROVENANCE = SPEC.practice_provenance
FEEDBACK_MODES = _shared.FEEDBACK_MODES
BACKENDS = ("torch_cpu", "jax")
CATALOG_EMPTY = _shared.catalog_empty_code(SPEC)


def manifest_document(product, **kwargs):
    return _shared.manifest_document(SPEC, product, **kwargs)


def check_attached(manifest, **kwargs):
    return _shared.check_attached(SPEC, manifest, **kwargs)


def compose(**kwargs):
    return _shared.compose(SPEC, **kwargs)


async def prepare_f02(args, *, ledger=None, campaign):
    return await _shared.prepare(SPEC, args, ledger=ledger, campaign=campaign)


async def evaluate_frozen(prepared, epoch, strategy):
    return await _shared.evaluate_frozen(
        SPEC,
        prepared,
        epoch,
        strategy,
        record=lambda *args: record_verdict(*args),
    )


def record_verdict(ledger, owner, epoch, feedback):
    return _shared.record_verdict(ledger, owner, epoch, feedback)


def agent_observation(prepared, epoch, feedback):
    return _shared.agent_observation(SPEC, prepared, epoch, feedback)
