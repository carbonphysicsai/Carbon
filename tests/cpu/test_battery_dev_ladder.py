"""The testnet development-ladder deployment (VALIDATOR-25, slice 1).

OWNER-LADDER-THROUGH-LAUNCHPAD-01: a separate `battery-dev-ladder` deployment
on valV2, reached through the Launchpad with real hotkeys and chain
commitments, that serves only its listed rehearsal hotkeys and only the
development variants of its one level. It shares the main deployment's live
windows (import-only), and it is `development_only`, so it never sets
weights. Its admission refuses, before anything compiles:
- `ladder_hotkey_not_listed`: a hotkey it does not list;
- `ladder_level_not_accepted`: another level's variant;
- `ladder_level_4_not_open`: a Level 4 variant;
- `ladder_variant_not_accepted`: an unlisted variant of its level.

Synthetic fixture variants only (`test_development_variants.install`).
Not a security audit (AGENTS.md §13).
"""

from __future__ import annotations

import copy
import json

import pytest
import test_battery_validator_daemon as tbd
from test_battery_validator_daemon import backend, refs  # noqa: F401 - fixtures
from test_development_variants import FIXTURE_DIGESTS, fixture_document, install

from carbon.battery import deployment
from carbon.reconstruction import capability_registry as registry

MINER_C = "5E49MhzFLBv35AbSPgtwrutCd6yvDm6GK9EC5ocmJ3Czb48N"
OTHER = "5DWznJMnCeoevFSwsck7LXdYBWAbiw1G1qrxnghqSHqQj2qr"
TESTNET = {
    "network": "testnet",
    "endpoint": "wss://test.finney.opentensor.ai:443",
    "provider": "bittensor-official-test",
    "genesis_hash": (
        "0x8f9cf856bf558a14440e75569c9e58594757048d7b3a84b5d25f6bd978263105"
    ),
    "netuid": 567,
}
LEVEL_2 = fixture_document(2)["version"]


@pytest.fixture(autouse=True)
def _registry(tmp_path, monkeypatch):
    install(tmp_path / "registry", monkeypatch)


def config(**changes):
    found = {
        "development_only": True,
        "batch_source": "answer_key",
        "require_commitment": True,
        "commitment_reader": dict(TESTNET),
        "ladder": {"levels": [2], "hotkeys": [MINER_C], "variants": [LEVEL_2]},
    }
    found.update(changes)
    return found


# --- the registry, as data ------------------------------------------------------


def test_a_variants_document_is_read_by_name_or_digest_and_rechecked(
    tmp_path, monkeypatch
):
    by_name = registry.development_variant_document(LEVEL_2)
    assert by_name["level"] == 2
    assert registry.development_variant_document(FIXTURE_DIGESTS[2]) == by_name
    assert registry.development_variant_document("sha256:" + "0" * 64) is None
    changed = copy.deepcopy(by_name)
    changed["level"] = 3
    path = registry.DEVELOPMENT_VARIANT_DIR / f"{LEVEL_2}.json"
    path.write_text(json.dumps(changed))
    with pytest.raises(RuntimeError, match="changed"):
        registry.development_variant_document(LEVEL_2)


# --- the deployment -----------------------------------------------------------


def test_the_ladder_admits_its_hotkeys_and_its_levels_variants():
    ladder = deployment.ladder_for(config())
    assert ladder == {
        "levels": frozenset({2}),
        "hotkeys": frozenset({MINER_C}),
        "variants": {FIXTURE_DIGESTS[2]: {"version": LEVEL_2, "level": 2}},
    }
    assert deployment.ladder_for({}) is None


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"development_only": False}, "evaluation_config_ladder"),
        ({"batch_source": "draw"}, "evaluation_config_ladder"),
        ({"require_commitment": False}, "evaluation_config_ladder"),
        (
            {"commitment_reader": {**TESTNET, "network": "finney"}},
            "evaluation_config_ladder_testnet_only",
        ),
        (
            {"ladder": {"levels": [4], "hotkeys": [MINER_C], "variants": [LEVEL_2]}},
            "evaluation_config_ladder_level_4_not_open",
        ),
        (
            {"ladder": {"levels": [2], "hotkeys": ["minerC"], "variants": [LEVEL_2]}},
            "evaluation_config_ladder",
        ),
        (
            {"ladder": {"levels": [2], "hotkeys": [MINER_C], "variants": []}},
            "evaluation_config_ladder",
        ),
        (
            {
                "ladder": {
                    "levels": [2],
                    "hotkeys": [MINER_C],
                    "variants": [fixture_document(1)["version"]],
                }
            },
            "evaluation_config_ladder_variant",
        ),
        (
            {
                "ladder": {
                    "levels": [2],
                    "hotkeys": [MINER_C],
                    "variants": ["unknown-v1"],
                }
            },
            "evaluation_config_ladder_variant",
        ),
    ],
)
def test_a_malformed_ladder_is_refused(changes, code):
    with pytest.raises(deployment.EvaluationUnavailable) as refused:
        deployment.ladder_for(config(**changes))
    assert refused.value.code == code


def test_only_the_ladder_may_be_a_development_deployment_with_commitments(tmp_path):
    base = {
        "schema": deployment.SCHEMA,
        "state": str(tmp_path / "s.sqlite3"),
        "private_root": str(tmp_path / "root.bin"),
        "journal": str(tmp_path / "j.jsonl"),
        "work": str(tmp_path / "work"),
        "backend": "direct",
    }
    path = tmp_path / "deployment.json"
    for changes, code in (
        (config(), None),
        ({k: v for k, v in config().items() if k != "ladder"}, "development_only"),
    ):
        path.write_text(json.dumps({**base, **changes}))
        path.chmod(0o600)
        if code is None:
            assert deployment.load_config(path)["ladder"]["levels"] == [2]
        else:
            with pytest.raises(deployment.EvaluationUnavailable) as refused:
                deployment.load_config(path)
            assert refused.value.code == "evaluation_config_development_only"


# --- admission ------------------------------------------------------------------


@pytest.fixture
def ladder_validator(tmp_path, refs, backend):  # noqa: F811
    return tbd.make(
        tmp_path,
        refs,
        backend,
        development_only=True,
        ladder=deployment.ladder_for(config()),
    )


def code(validator, hotkey, digest=tbd.DIGEST):
    outcome = validator.admit(tbd.submission(hotkey, digest=digest))
    return (outcome.get("failure") or {}).get("code")


def test_an_unlisted_hotkey_is_refused_before_anything(ladder_validator):
    before = ladder_validator.store.pool()["admitted"]
    assert code(ladder_validator, OTHER) == "ladder_hotkey_not_listed"
    assert code(ladder_validator, "graphite-dev:run:constructor") == (
        "ladder_hotkey_not_listed"
    )
    assert ladder_validator.store.pool()["admitted"] == before


def test_another_levels_variant_is_refused_by_its_own_code(
    ladder_validator, monkeypatch
):
    assert code(ladder_validator, MINER_C, FIXTURE_DIGESTS[1]) == (
        "ladder_level_not_accepted"
    )
    real = registry.development_variant_document

    def as_level_4(value, directory=None):
        document = real(value, directory)
        if value == FIXTURE_DIGESTS[3]:
            return {**document, "level": 4}
        return document

    monkeypatch.setattr(registry, "development_variant_document", as_level_4)
    assert code(ladder_validator, MINER_C, FIXTURE_DIGESTS[3]) == (
        "ladder_level_4_not_open"
    )


def test_a_listed_variant_needs_the_injected_compiler(ladder_validator):
    # Fail closed until the ladder's service entry point supplies it.
    assert code(ladder_validator, MINER_C, FIXTURE_DIGESTS[2]) == (
        "development_variant_not_served"
    )
    seen = []

    def compiler(strategy, digest):
        seen.append(digest)
        raise ValueError("stop after admission")

    ladder_validator.development_compiler = compiler
    code(ladder_validator, MINER_C, FIXTURE_DIGESTS[2])
    assert seen == [FIXTURE_DIGESTS[2]]


def test_the_ladder_never_sets_weights(ladder_validator):
    from carbon.rewards import testnet_winner_publication as publication

    with pytest.raises(Exception, match="DEVELOPMENT_DEPLOYMENT_NEVER_SETS_WEIGHTS"):
        publication.check_weight_source(ladder_validator)


# --- slice 2: the door and the service --------------------------------------------


def door(target, tmp_path):
    from carbon.battery import intake as ib

    target.lock_path = str(tmp_path / "state.sqlite3.lock")
    ledger = ib.attempt_ledger({"inbox": str(tmp_path / "inbox.sqlite3")})
    return ib.neutral_door(target, ledger)


def screened(validator_door, adapter_digest, digest, hotkey=MINER_C):
    from carbon.challenge_validator.interface import Submission

    strategy = {
        "schema_version": "1.0",
        "challenge_id": tbd.BATTERY,
        "backbone": "knn",
        "parameters": {"neighbours": 8},
    }
    return validator_door.screen(
        Submission(
            hotkey=hotkey,
            receipt={"sequence": 1, "digest": "0" * 64},
            challenge_id=tbd.BATTERY,
            challenge_version="1.0",
            strategy_json=json.dumps(strategy),
            contract_digest=digest,
        )
    )


def test_the_ladders_door_passes_only_its_declared_variants(ladder_validator, tmp_path):
    validator_door = door(ladder_validator, tmp_path)
    base = ladder_validator.identities()["contract_digest"]
    passed = screened(validator_door, base, FIXTURE_DIGESTS[2])
    assert passed.adapter.contract_digest == base
    assert passed.admitted.contract_digest == FIXTURE_DIGESTS[2]
    refused = screened(validator_door, base, FIXTURE_DIGESTS[1])
    assert refused["code"] == "development_variant_not_served"
    assert validator_door.served_contracts() == [
        {"level": 0, "digest": base},
        {"level": 2, "variant": LEVEL_2, "digest": FIXTURE_DIGESTS[2]},
    ]


def test_the_main_door_still_refuses_every_variant(
    tmp_path, refs, backend  # noqa: F811
):
    import test_battery_intake as tbi

    intake, target = tbi.build(tmp_path, refs, backend)
    base = target.identities()["contract_digest"]
    refused = screened(intake.door, base, FIXTURE_DIGESTS[2])
    assert refused["code"] == "development_variant_not_served"
    assert tbi.facts(intake)["served_contracts"] == [{"level": 0, "digest": base}]


def test_the_ladders_entry_point_supplies_the_compiler(ladder_validator, monkeypatch):
    from carbon.development_ladder import operate
    from carbon.reconstruction import development_variants as dv

    operate.setup(ladder_validator)
    assert ladder_validator.development_compiler is operate.compile_variant
    calls = []
    monkeypatch.setattr(dv, "registered", lambda digest: ("registered", digest))
    monkeypatch.setattr(
        dv, "compile_development", lambda strategy, v: calls.append(v) or "compiled"
    )
    assert operate.compile_variant({}, FIXTURE_DIGESTS[2]) == "compiled"
    assert calls == [("registered", FIXTURE_DIGESTS[2])]
    with pytest.raises(ValueError):
        operate.setup(type("Main", (), {"ladder": None})())


def test_the_supervisor_runs_the_ladders_daemon_only_for_a_ladder(tmp_path):
    from scripts.dev.battery_validator_service import supervisor

    ladder = tmp_path / "ladder.json"
    ladder.write_text(json.dumps(config()))
    main = tmp_path / "main.json"
    main.write_text(json.dumps({"backend": "carrier"}))
    assert supervisor._daemon_module(ladder) == "carbon.development_ladder.operate"
    assert supervisor._daemon_module(main) == "carbon.battery.operate"
    assert supervisor._daemon_module(tmp_path / "missing.json") == (
        "carbon.battery.operate"
    )


def test_one_door_serves_several_levels(tmp_path, refs, backend):  # noqa: F811
    level_1 = fixture_document(1)["version"]
    ladder = deployment.ladder_for(
        config(
            ladder={
                "levels": [1, 2],
                "hotkeys": [MINER_C],
                "variants": [level_1, LEVEL_2],
            }
        )
    )
    validator = tbd.make(tmp_path, refs, backend, development_only=True, ladder=ladder)
    # Each listed level's variant passes the ladder's own check (and, with no
    # compiler supplied, fails closed after it); an unlisted level is refused.
    for digest in (FIXTURE_DIGESTS[1], FIXTURE_DIGESTS[2]):
        assert code(validator, MINER_C, digest) == "development_variant_not_served"
    assert code(validator, MINER_C, FIXTURE_DIGESTS[3]) == "ladder_level_not_accepted"
    served = door(validator, tmp_path).served_contracts()
    assert {(s["level"], s.get("variant")) for s in served} == {
        (0, None),
        (1, level_1),
        (2, LEVEL_2),
    }


def test_a_development_commitment_binds_the_variant_and_the_whole_strategy(
    tmp_path, refs, backend  # noqa: F811
):
    pytest.importorskip("numpy")
    from test_development_variants import _strategy

    from carbon.battery.daemon import (
        AuthenticatedSubmission,
        CommitmentRequired,
        commitment_digest,
        development_commitment_digest,
    )
    from carbon.development_ladder import operate

    class Chain:
        def __init__(self):
            self.values = {}

        def read(self, hotkey):
            return self.values.get(hotkey)

        def holders(self, digest):
            return sorted(
                (hk, v["block"])
                for hk, v in self.values.items()
                if v["digest"] == digest
            )

    chain = Chain()
    validator = tbd.make(
        tmp_path,
        refs,
        backend,
        development_only=True,
        ladder=deployment.ladder_for(config()),
        require_commitment=True,
        commitments=chain,
    )
    operate.setup(validator)
    strategy = _strategy(fixture_only_cycles=3)
    variant = FIXTURE_DIGESTS[2]
    submission = AuthenticatedSubmission(
        MINER_C,
        {"sequence": 1, "digest": "0" * 64},
        tbd.BATTERY,
        "1.0",
        strategy,
        variant,
    )
    compiled = operate.compile_variant(strategy, variant)
    strategy_hash = compiled.construction.strategy_hash
    for digest in (
        # Level 0's form, over the base digest or the variant's: refused.
        commitment_digest(tbd.BATTERY, compiled.contract_digest, strategy_hash),
        commitment_digest(tbd.BATTERY, variant, strategy_hash),
        # The right form over other widened values: refused.
        development_commitment_digest(
            tbd.BATTERY, variant, strategy_hash, _strategy(fixture_only_cycles=4)
        ),
    ):
        chain.values[MINER_C] = {"digest": digest, "block": 123}
        with pytest.raises(CommitmentRequired):
            validator.admit(submission)
    chain.values[MINER_C] = {
        "digest": development_commitment_digest(
            tbd.BATTERY, variant, strategy_hash, strategy
        ),
        "block": 123,
    }
    admitted = validator.admit(submission)
    binding = validator.store.submission(admitted["submission_id"])["binding"]
    assert binding["development"]["variant_contract_digest"] == variant
    assert binding["commitment"]["block"] == 123
