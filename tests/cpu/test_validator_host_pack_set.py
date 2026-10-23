"""G2: a pack set reaches a validator over the per-hotkey route.

The set commitment (canonical batch digests only) comes over the first route; each batch
comes as this hotkey's own copy. Setup selects the set once every batch is delivered, and
never chooses one batch of several."""

from __future__ import annotations

import json
import random

import pytest
import test_copy_delivery as cdt
from test_validator_host import (
    SOURCE,
    Receivers,
    state,  # noqa: F401  (a fixture)
)

from carbon.challenge_validator import answer_key as ak
from carbon.challenge_validator import copy_delivery as delivery
from carbon.challenge_validator import copy_route, receiver_setup, validator_host
from carbon.challenge_validator import sealed_pack_import as spi
from carbon.challenge_validator import motor_sealed_grid as hidden_grid  # noqa: F401
from carbon.motor_grid_exam import population
from carbon.scoring import sealed_batch_source as source

MOTOR, VERSION = source.MOTOR, "1.1"
HOTKEY = cdt.HOTKEYS[0]


def _batch(seed):
    """A Motor grid batch of its own draw, as (canonical manifest, files, carried)."""
    import test_copy_package as cpt

    cases, _ = population.draw(random.Random(seed), population.CELLS)
    document = {
        "schema": hidden_grid.DOCUMENT_SCHEMA,
        "challenge": {"id": MOTOR, "version": VERSION},
        "role": "grid",
        "kind": "screening",
        "population": population.POPULATION_VERSION,
        "cases": [{"case_id": f"g{i:02d}", "inputs": c} for i, c in enumerate(cases)],
    }
    return document, cpt.motor_family.records_for(document)


def _issued(producer, document, records, hotkey):
    import test_copy_package as cpt

    challenge, version, manifest, files, carried = cdt._canonical_pack("motor-grid")
    # The canonical pack of THIS draw, not the module's fixed one.
    from carbon.scoring import copy_package as cp

    raw, _src, _fp = cp.canonical_batch(challenge, version, document, records)
    carried = json.loads(raw)
    bank = source._build(
        challenge,
        source._kit(challenge),
        carried["document"],
        carried["records"],
        version,
    )
    roles = source._kit(challenge).private_roles(bank)
    pack_manifest = json.loads(manifest)
    for role in delivery.COPY_ROLES:
        pack_manifest["private"][role]["sha256"] = cdt._sha(roles[role])
        files[pack_manifest["private"][role]["path"]] = roles[role]
    manifest = (
        json.dumps(pack_manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    package = delivery.issue_copy(
        producer,
        cdt.MASTER,
        challenge=challenge,
        version=version,
        canonical_manifest=manifest,
        canonical_files=files,
        document=carried["document"],
        records=carried["records"],
        hotkey=hotkey,
        window=cdt.WINDOW,
    )
    _ = cpt
    return package, cdt._sha(manifest), spi.manifest_content(manifest)


class Routes:
    """Both routes of the distribution host, as in-process fetchers."""

    def __init__(self, producer, packages, set_package):
        self.copies = packages
        self.set_package = set_package
        self.copy_fetcher = self._copy()
        self.set_fetcher = self._first()

    def _copy(self):
        packages = self.copies

        class Fetcher:
            def ask(self, challenge_id, fingerprint=None):
                if fingerprint is None:
                    return {"packages": [copy_route.listing_entry(p) for p in packages]}
                (found,) = [
                    p
                    for p in packages
                    if p["manifest"]["commitment"]["fingerprint"] == fingerprint
                ]
                return {"package": found}

        return Fetcher()

    def _first(self):
        package = self.set_package

        class Fetcher:
            def ask(self, challenge_id, fingerprint=None):
                if package is None:
                    return {"packages": [], "withdrawals": []}
                if fingerprint is None:
                    return {
                        "packages": [ak.listing_entry(package)],
                        "withdrawals": [],
                    }
                return {"package": package}

        return Fetcher()


@pytest.fixture(scope="module")
def producer(tmp_path_factory):
    return ak.ProducerKey.create(str(tmp_path_factory.mktemp("k") / "producer.key"))


@pytest.fixture(scope="module")
def world(producer):
    drawn = [_batch(3), _batch(4)]
    issued = [_issued(producer, d, r, HOTKEY) for d, r in drawn]
    digests = [digest for _package, digest, _content in issued]
    assert digests[0] != digests[1]
    commitment = spi.set_commitment_for(
        MOTOR,
        VERSION,
        digests,
        cdt.WINDOW,
        contents={d: c for d, (_p, _d, c) in zip(digests, issued, strict=True)},
    )
    set_package = ak.package(producer, commitment, spi.set_payload_for(commitment))
    return {
        "packages": [p for p, _d, _c in issued],
        "digests": digests,
        "set_key": commitment["set_key"],
        "set_package": set_package,
    }


def _run(state, producer, routes):
    receivers = Receivers()
    validator_host.setup(
        installed_state=state,
        hotkey=HOTKEY,
        challenges=[{"id": MOTOR, "version": VERSION}],
        exam_source=SOURCE,
        prepare=receivers.prepare,
        service=receivers.service,
        fetch=lambda *args: validator_host.fetch_exams(
            *args,
            fetcher=routes.copy_fetcher,
            set_fetcher=routes.set_fetcher,
            producer_public_key=producer.public_key,
        ),
    )
    return receivers


def test_setup_selects_the_signed_pack_set_once_every_batch_is_this_hotkeys_copy(
    state, producer, world
):
    routes = Routes(producer, world["packages"], world["set_package"])
    receivers = _run(state, producer, routes)
    (prepared,) = receivers.prepared
    assert prepared["pack_set_key"] == world["set_key"]
    assert "pack_digest" not in prepared
    store = spi.SealedPackStore(prepared["pack_store"])
    batches = store.pack_set(world["set_key"], MOTOR, VERSION)
    assert [d for d, _ in batches] == sorted(world["digests"])  # canonical ids


def test_a_set_with_a_batch_this_hotkey_has_no_copy_of_is_refused(
    state, producer, world
):
    routes = Routes(producer, world["packages"][:1], world["set_package"])
    with pytest.raises(
        receiver_setup.SetupRefused, match="evaluation_pack_set_incomplete"
    ):
        _run(state, producer, routes)


def test_several_packs_and_no_set_is_still_ambiguous(state, producer, world):
    routes = Routes(producer, world["packages"], None)
    with pytest.raises(receiver_setup.SetupRefused, match="evaluation_pack_ambiguous"):
        _run(state, producer, routes)


def test_one_pack_and_no_set_is_selected_as_before(state, producer, world):
    routes = Routes(producer, world["packages"][:1], None)
    receivers = _run(state, producer, routes)
    (prepared,) = receivers.prepared
    assert prepared["pack_digest"] == world["digests"][0]
    assert "pack_set_key" not in prepared


def test_a_set_signed_by_another_key_is_refused_and_imports_nothing(
    state, producer, world, tmp_path
):
    stranger = ak.ProducerKey.create(str(tmp_path / "stranger.key"))
    commitment = spi.set_commitment_for(MOTOR, VERSION, world["digests"], cdt.WINDOW)
    forged = ak.package(stranger, commitment, spi.set_payload_for(commitment))
    routes = Routes(producer, world["packages"], forged)
    with pytest.raises(receiver_setup.SetupRefused):
        _run(state, producer, routes)
    sets = state / "validator" / validator_host.EXAMS_DIRECTORY / spi.SETS_DIRECTORY
    assert not sets.exists() or not list(sets.glob("*.json"))
