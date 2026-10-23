"""Launchpad campaign for Battery 2.2, Battery's backbone-catalog version.

The shared direct campaign (`carbon.direct_campaign`), bound to Battery's
catalog spec (`spec.BATTERY_CATALOG`; its served material is
`battery.catalog_version`'s): catalog recipes only, practised through the
receiver's own build and scored with Battery's own practice measurement,
frozen from a practice result and submitted through the signed construction
receiver. While its catalog is empty (no entry has its pair-identity receipt)
the campaign refuses to start (`battery_catalog_catalog_empty`). Every hook
runs under the version's research key, which the registry's composer sets
(`challenge_registry.campaigns`). Battery 1.0's campaign (`battery.campaign`)
is not touched.

One module holds the research key, the campaign hooks, the research view and
the practice class, which the F08 and F02 packages split across five.
"""

from __future__ import annotations

from carbon.direct_campaign import campaign as _shared
from carbon.direct_campaign import contracts as _contracts
from carbon.direct_campaign import research_view as _view
from carbon.direct_campaign import spec as _spec
from carbon.direct_campaign.practice import DirectPractice

SPEC = _spec.BATTERY_CATALOG
CHALLENGE_ID = SPEC.challenge_id
CATALOG_VERSIONS = SPEC.versions
PRACTICE_PROVENANCE = SPEC.practice_provenance
FEEDBACK_MODES = _shared.FEEDBACK_MODES
BACKENDS = ("torch_cpu", "jax")
CATALOG_EMPTY = _shared.catalog_empty_code(SPEC)


# -- the research key ---------------------------------------------------------


def research_key():
    return _spec.research_key(SPEC)


def keyed(key):
    return _spec.keyed(SPEC, key)


def key_for(version):
    return _spec.key_for(SPEC, version)


def battery_catalog_contracts(version):
    return _contracts.direct_contracts(SPEC, version)


# -- the campaign -------------------------------------------------------------


def manifest_document(product, **kwargs):
    return _shared.manifest_document(SPEC, product, **kwargs)


def check_attached(manifest, **kwargs):
    return _shared.check_attached(SPEC, manifest, **kwargs)


def compose(**kwargs):
    return _shared.compose(SPEC, **kwargs)


async def prepare_battery_catalog(args, *, ledger=None, campaign):
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


# -- the research view and practice -------------------------------------------


def research_view():
    return _view.research_view(SPEC)


class BatteryCatalogPractice(DirectPractice):
    def __init__(self, **kwargs):
        super().__init__(SPEC, **kwargs)
