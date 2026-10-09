"""The challenge-neutral validator contract (VALIDATOR-01), with a fake adapter.

The fake adapter serves the Burgers construction contract's registered digest,
so dispatch, refusals, the outcome contract, pinned identities, reserved seed
roles and the attempt ledger are exercised without any Challenge's science.
Battery's own adapter is tested in `test_challenge_validator_battery.py`.

These tests are not a security audit (AGENTS.md §13).
"""

import json

import pytest

from carbon.challenge_validator import (
    RESERVED_SEED_ROLES,
    Adapters,
    AttemptLedger,
    ChallengeAdapter,
    Operator,
    ReservedRole,
    Submission,
    Unavailable,
    Validator,
)
from carbon.challenge_validator.dispatch import RESULT_SCHEMA
from carbon.challenge_validator.ledger import LedgerUnavailable
from carbon.challenge_validator.strict_json import (
    MAX_DEPTH,
    MalformedStrategy,
    parse_strategy,
)
from carbon.reconstruction import capability_registry as registry

TOKEN = registry.BURGERS_CHALLENGE
VERSION = registry.contract(TOKEN).version
DIGEST = registry.contract_digest(TOKEN)
MARKER = "PROTECTED-CASE-7f3a"
RESULT_KEYS = {
    "schema",
    "kind",
    "code",
    "pinned",
    "outcome",
    "evidence",
    "qualification",
    "reward",
}


class Fake(ChallengeAdapter):
    challenge_id = TOKEN
    challenge_version = VERSION
    contract_digest = DIGEST
    max_strategy_bytes = 4096
    disclosure_fields = frozenset({"score"})

    def __init__(self, rule_digest="sha256:" + "a" * 64, sealed=()):
        self.rule_digest = rule_digest
        self.sealed = set(sealed)
        self.seen = []
        self.prepared = []
        self.returns = None
        self.raises = None

    def identities(self):
        return {
            "contract_digest": DIGEST,
            "rule_digest": self.rule_digest,
            "implementation_digest": "sha256:" + "b" * 64,
            "material": {"train": "sha256:" + "c" * 64},
        }

    def evaluate(self, submission):
        self.seen.append(submission)
        if self.raises is not None:
            raise self.raises
        if self.returns is not None:
            return self.returns
        return self.outcome("sub-1")

    def outcome(self, submission_id):
        return {
            "schema": "fake.outcome.v1",
            "submission_id": submission_id,
            "challenge": {"id": TOKEN, "version": VERSION},
            "state": "SCORED",
            "evidence": "DEVELOPMENT_SHADOW",
            "qualification": False,
            "reward": False,
            "score": 0.5,
        }

    def owner(self, submission_id):
        return "hk-owner" if submission_id == "sub-1" else None

    def advance(self):
        return 0

    def score_record(self, submission_id):
        return {"cases": [{"case_id": MARKER, "error": 0.1}]}

    def sealed_roles(self):
        return self.sealed

    def _prepare_batch(self, role, *, kind, **options):
        self.prepared.append(role)
        return "sha256:" + "d" * 64

    def reference_jobs(self, fingerprint):
        return []

    def ingest_references(self, fingerprint, records):
        return True

    def open_pool(self):
        return None

    def status(self):
        return {"pending": 0}


def strategy(**extra):
    return json.dumps({"challenge_id": TOKEN, "backbone": "fno", **extra})


def sub(strategy_json=None, **fields):
    base = {
        "hotkey": "hk-owner",
        "receipt": {"sequence": 1, "digest": "0" * 64, "block": 10},
        "challenge_id": TOKEN,
        "challenge_version": VERSION,
        "strategy_json": strategy() if strategy_json is None else strategy_json,
        "contract_digest": DIGEST,
    }
    base.update(fields)
    return Submission(**base)


@pytest.fixture
def ledger(tmp_path):
    tmp_path.chmod(0o700)
    return AttemptLedger(tmp_path / "ledger.sqlite3")


@pytest.fixture
def fake():
    return Fake()


@pytest.fixture
def validator(fake, ledger):
    return Validator(Adapters([fake]), ledger)


def no_echo(result):
    assert MARKER not in json.dumps(result)


# --- strict parsing ---------------------------------------------------------------


HOSTILE = [
    ('{"a": NaN}', "non_finite_value"),
    ('{"a": Infinity}', "non_finite_value"),
    ('{"a": -Infinity}', "non_finite_value"),
    ('{"a": 1e999}', "non_finite_value"),
    ('{"a": 1, "a": 2}', "duplicate_key"),
    ('{"a": {"b": 1, "b": 1}}', "duplicate_key"),
    ('{"a": ' + "9" * 5000 + "}", "integer_out_of_range"),
    ('{"a": 9223372036854775808}', "integer_out_of_range"),
    ("[" * (MAX_DEPTH + 1) + "]" * (MAX_DEPTH + 1), "strategy_nesting_too_deep"),
    ('{"a":' * 5000 + "1" + "}" * 5000, "strategy_nesting_too_deep"),
    (b"\xff\xfe{}", "strategy_not_utf8"),
    (b'{"a": "\xc3\x28"}', "strategy_not_utf8"),
    ('{"a": "\ud800"}', "strategy_not_utf8"),
    ('{"a": "\\ud800"}', "strategy_not_utf8"),
    (b"\xef\xbb\xbf{}", "strategy_bom"),
    ("﻿{}", "strategy_bom"),
    ("[1, 2]", "strategy_not_object"),
    ('"text"', "strategy_not_object"),
    ("null", "strategy_not_object"),
    ("{", "strategy_not_json"),
    ("", "strategy_not_json"),
    (None, "strategy_not_json"),
    (12, "strategy_not_json"),
    ("{} trailing", "strategy_not_json"),
]


@pytest.mark.parametrize(
    ("raw", "code"), HOSTILE, ids=[f"{i}-{c}" for i, (_, c) in enumerate(HOSTILE)]
)
def test_strict_parser_refuses_hostile_strategies(raw, code):
    with pytest.raises(MalformedStrategy) as refused:
        parse_strategy(raw, max_bytes=1 << 20)
    assert refused.value.code == code


def test_strict_parser_keeps_brackets_inside_strings_and_valid_values():
    text = json.dumps({"note": "[[[[{{{{" * 20, "n": -3, "x": 1.5, "ok": True})
    assert parse_strategy(text, max_bytes=4096)["n"] == -3
    assert parse_strategy(text.encode(), max_bytes=4096) == json.loads(text)


def test_strict_parser_refuses_oversized_by_bytes_not_characters():
    text = json.dumps({"a": "é" * 60})  # 60 characters, 120 bytes
    with pytest.raises(MalformedStrategy) as refused:
        parse_strategy(text, max_bytes=100)
    assert refused.value.code == "oversized_submission"
    with pytest.raises(MalformedStrategy):
        parse_strategy(text.encode(), max_bytes=100)


# --- dispatch and refusals ----------------------------------------------------------


def test_a_valid_submission_reaches_its_adapter_with_pinned_identities(
    validator, fake, ledger
):
    result = validator.evaluate(sub())
    assert set(result) == RESULT_KEYS
    assert result["schema"] == RESULT_SCHEMA
    assert (result["kind"], result["code"]) == ("OUTCOME", None)
    assert result["pinned"] == fake.pinned()
    assert result["pinned"]["contract_digest"] == DIGEST
    assert (result["qualification"], result["reward"]) == (False, False)
    assert fake.seen[0].strategy == json.loads(strategy())
    (attempt,) = ledger.attempts()
    assert (attempt["kind"], attempt["state"]) == ("OUTCOME", "SCORED")


@pytest.mark.parametrize(
    "digest",
    [
        DIGEST.upper(),
        DIGEST.replace("sha256:", "SHA256:"),
        " " + DIGEST,
        DIGEST + "\n",
        DIGEST + " ",
        DIGEST[7:],
        "sha256:" + "g" * 64,
        "sha256:" + "a" * 63,
        "",
        None,
        12,
        b"sha256:" + b"a" * 64,
    ],
)
def test_a_malformed_contract_digest_is_refused_by_name(
    validator, fake, ledger, digest
):
    result = validator.evaluate(sub(contract_digest=digest))
    assert (result["kind"], result["code"]) == ("REFUSED", "contract_digest_malformed")
    assert result["pinned"] is None and result["outcome"] is None
    assert fake.seen == []
    assert ledger.attempts()[0]["code"] == "contract_digest_malformed"


def test_an_unserved_digest_is_refused_and_recorded_never_scored(
    validator, fake, ledger
):
    other = registry.contract_digest(registry.BATTERY_CHALLENGE)
    for digest in (other, "sha256:" + "e" * 64):
        result = validator.evaluate(sub(contract_digest=digest))
        assert (result["kind"], result["code"]) == ("REFUSED", "contract_not_served")
        assert result["outcome"] is None
    assert fake.seen == []
    assert [a["contract_digest"] for a in ledger.attempts()] == [
        other,
        "sha256:" + "e" * 64,
    ]


@pytest.mark.parametrize(
    "fields",
    [
        {"challenge_id": registry.BATTERY_CHALLENGE},
        {"challenge_version": "2.0"},
        {"strategy_json": json.dumps({"challenge_id": registry.BATTERY_CHALLENGE})},
        {"strategy_json": json.dumps({"backbone": "fno"})},
    ],
)
def test_a_challenge_the_digest_does_not_serve_is_refused(validator, fake, fields):
    result = validator.evaluate(sub(**fields))
    assert (result["kind"], result["code"]) == ("REFUSED", "challenge_mismatch")
    assert fake.seen == []


@pytest.mark.parametrize(
    "fields",
    [
        {"hotkey": ""},
        {"hotkey": "h" * 129},
        {"hotkey": "hk\n" + MARKER},
        {"hotkey": None},
        {"hotkey": 7},
        {"receipt": None},
        {"receipt": [1]},
        {"receipt": {"sequence": True}},
        {"receipt": {"sequence": 1.5}},
        {"receipt": {"nested": {"a": MARKER}}},
        {"receipt": {str(i): i for i in range(17)}},
        {"receipt": {"digest": "x" * 129}},
        {"challenge_id": None},
        {"challenge_version": "v" * 200},
    ],
)
def test_malformed_transport_fields_are_refused_without_echo(
    validator, fake, ledger, fields
):
    result = validator.evaluate(sub(**fields))
    assert (result["kind"], result["code"]) == ("REFUSED", "malformed_submission")
    assert fake.seen == []
    no_echo(result)
    no_echo(ledger.attempts())


def test_a_non_submission_object_is_refused(validator, fake, ledger):
    for thing in (None, {"hotkey": "hk"}, object()):
        result = validator.evaluate(thing)
        assert (result["kind"], result["code"]) == ("REFUSED", "malformed_submission")
    assert fake.seen == [] and len(ledger.attempts()) == 3


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (
            f'{{"challenge_id": "{TOKEN}", "x": NaN, "m": "{MARKER}"}}',
            "non_finite_value",
        ),
        (
            f'{{"challenge_id": "{TOKEN}", "m": "{MARKER}", "m": 1}}',
            "duplicate_key",
        ),
        ("[" + json.dumps(MARKER) + "]", "strategy_not_object"),
        ("x" * 5000 + MARKER, "oversized_submission"),
        (b"\xef\xbb\xbf" + strategy().encode(), "strategy_bom"),
        (MARKER.encode() + b"\xff", "strategy_not_utf8"),
    ],
    ids=["nan", "duplicate", "array", "oversized", "bom", "not-utf8"],
)
def test_hostile_strategies_are_refused_before_the_adapter_without_echo(
    validator, fake, ledger, raw, code
):
    result = validator.evaluate(sub(strategy_json=raw))
    assert (result["kind"], result["code"]) == ("REFUSED", code)
    assert result["pinned"] == fake.pinned()
    assert fake.seen == []
    no_echo(result)
    (attempt,) = ledger.attempts()
    no_echo(attempt)
    assert attempt["submission_sha256"].startswith("sha256:")


def test_the_ledger_hash_distinguishes_submissions(validator, ledger):
    validator.evaluate(sub(strategy_json="[1]"))
    validator.evaluate(sub(strategy_json="[2]"))
    validator.evaluate(sub(strategy_json=b"[1]"))
    hashes = [a["submission_sha256"] for a in ledger.attempts()]
    assert len(set(hashes)) == 3


# --- the outcome contract and infrastructure ---------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        {"qualification": True},
        {"reward": True},
        {"evidence": "LIVE"},
        {"state": "WINNER"},
        {"challenge": {"id": registry.BATTERY_CHALLENGE, "version": "1.0"}},
        {"seed": 1234},
        {"hidden_cases": [MARKER]},
        {"failure": {"code": "x", "detail": MARKER}},
        {"score": float("nan")},
    ],
)
def test_an_outcome_outside_the_contract_is_infrastructure_never_returned(
    validator, fake, ledger, change
):
    fake.returns = {**fake.outcome("sub-1"), **change}
    result = validator.evaluate(sub())
    assert (result["kind"], result["code"]) == (
        "FAILED_INFRA",
        "outcome_contract_violation",
    )
    assert result["outcome"] is None
    no_echo(result)
    assert ledger.attempts()[0]["kind"] == "FAILED_INFRA"


def test_a_missing_required_outcome_key_is_a_violation(validator, fake):
    outcome = fake.outcome("sub-1")
    del outcome["reward"]
    fake.returns = outcome
    assert validator.evaluate(sub())["code"] == "outcome_contract_violation"


def test_an_adapter_fault_is_failed_infra_and_never_echoes_its_text(
    validator, fake, ledger
):
    fake.raises = RuntimeError("could not open " + MARKER)
    result = validator.evaluate(sub())
    assert (result["kind"], result["code"]) == ("FAILED_INFRA", "adapter_failure")
    assert result["outcome"] is None
    no_echo(result)
    no_echo(ledger.attempts())


def test_unavailable_is_typed_unrecorded_against_the_miner_and_carries_retry(
    validator, fake, ledger
):
    fake.raises = Unavailable("hotkey_window_used", retry={"next_block": 360})
    result = validator.evaluate(sub())
    assert (result["kind"], result["code"]) == ("UNAVAILABLE", "hotkey_window_used")
    assert result["retry"] == {"next_block": 360}
    assert result["outcome"] is None
    assert ledger.attempts()[0]["kind"] == "UNAVAILABLE"


# --- miner-facing outcome reads ------------------------------------------------------------


def test_outcome_answers_only_the_submitting_hotkey(validator):
    assert validator.outcome(DIGEST, "sub-1", "hk-owner")["kind"] == "OUTCOME"
    other = validator.outcome(DIGEST, "sub-1", "hk-other")
    missing = validator.outcome(DIGEST, "sub-404", "hk-owner")
    assert other == missing  # no oracle for which submissions exist
    assert (other["kind"], other["code"]) == ("REFUSED", "unknown_submission")
    assert validator.outcome("sha256:" + "e" * 64, "sub-1", "hk-owner")["code"] == (
        "contract_not_served"
    )
    assert validator.outcome(DIGEST.upper(), "sub-1", "hk-owner")["code"] == (
        "contract_digest_malformed"
    )


def test_the_miner_surface_has_no_route_to_operator_records(validator, fake):
    public = {n for n in dir(Validator) if not n.startswith("_")}
    # `screen` and `note` serve a queueing transport (battery's intake): they
    # check and record; neither reads the ledger or any operator record.
    # `served_contracts` is the public list of what is admitted (VALIDATOR-25).
    assert public == {
        "evaluate",
        "outcome",
        "served",
        "served_contracts",
        "screen",
        "note",
    }
    results = [
        validator.evaluate(sub()),
        validator.outcome(DIGEST, "sub-1", "hk-owner"),
        validator.served(),
        validator.served_contracts(),
        validator.screen(sub(strategy_json="[1]")),
    ]
    no_echo(results)  # the fake's score record names MARKER as a case id


# --- identities ------------------------------------------------------------------------------


def test_pinned_identities_follow_the_rule(ledger):
    first, second = Fake(), Fake(rule_digest="sha256:" + "f" * 64)
    a = Validator(Adapters([first]), ledger).evaluate(sub())["pinned"]
    b = Validator(Adapters([second]), ledger).evaluate(sub())["pinned"]
    assert a["contract_digest"] == b["contract_digest"] == DIGEST
    assert a["rule_digest"] != b["rule_digest"]
    assert a["identities_digest"] != b["identities_digest"]


def test_registration_binds_the_registered_contract():
    with pytest.raises(ValueError, match="two adapters"):
        Adapters([Fake(), Fake()])

    class Invented(Fake):
        contract_digest = "sha256:" + "1" * 64

        def identities(self):
            return {**super().identities(), "contract_digest": self.contract_digest}

    with pytest.raises(ValueError, match="registered contract"):
        Adapters([Invented()])

    class Mislabelled(Fake):
        def identities(self):
            return {**super().identities(), "contract_digest": "sha256:" + "1" * 64}

    with pytest.raises(ValueError, match="another contract digest"):
        Adapters([Mislabelled()])

    class Unpinned(Fake):
        def identities(self):
            return {**super().identities(), "rule_digest": "v1"}

    with pytest.raises(ValueError, match="pinned digests"):
        Adapters([Unpinned()])

    class Unregistered(Fake):
        challenge_id = "cold-plate-unregistered"

    with pytest.raises(ValueError, match="no registered contract"):
        Adapters([Unregistered()])
    with pytest.raises(TypeError):
        Adapters([object()])


# --- reserved seed roles ------------------------------------------------------------------------


@pytest.mark.parametrize("role", sorted(RESERVED_SEED_ROLES))
def test_reserved_seed_roles_are_refused_and_recorded(ledger, role):
    fake = Fake()
    operator = Operator(Adapters([fake]), ledger)
    with pytest.raises(ReservedRole) as refused:
        operator.prepare_batch(DIGEST, role, kind="screening")
    assert refused.value.code == "seed_role_reserved"
    assert fake.prepared == []
    assert ledger.operator_refusals() == [
        {
            "action": "prepare_batch",
            "code": "seed_role_reserved",
            "contract_digest": DIGEST,
        }
    ]


def test_a_role_already_sealed_outside_the_pool_is_refused(ledger):
    fake = Fake(sealed={"cooling-confirmation-v1"})
    operator = Operator(Adapters([fake]), ledger)
    with pytest.raises(ReservedRole) as refused:
        operator.prepare_batch(DIGEST, "cooling-confirmation-v1", kind="screening")
    assert refused.value.code == "seed_role_sealed"
    for bad in ("", None, 3):
        with pytest.raises(ReservedRole):
            fake.prepare_batch(bad, kind="screening")
    assert operator.prepare_batch(DIGEST, "pscreen-new", kind="screening")
    assert fake.prepared == ["pscreen-new"]


def test_the_reserved_list_names_both_sealed_studies():
    assert {"ev5-confirmation", "graphite-confirmation-v1"} <= RESERVED_SEED_ROLES


# --- the attempt ledger ------------------------------------------------------------------------


def test_attempts_are_counted_per_hotkey_by_kind_and_contract(validator, fake, ledger):
    validator.evaluate(sub())
    validator.evaluate(sub(strategy_json="[]"))
    validator.evaluate(sub(contract_digest="sha256:" + "e" * 64))
    fake.raises = Unavailable("commitment_required")
    validator.evaluate(sub())
    fake.raises = None
    validator.evaluate(sub(hotkey="hk-other"))
    counts = Operator(Adapters([Fake()]), ledger).attempt_counts("hk-owner")
    assert counts["total"] == 4
    assert counts["by_kind"] == {
        "OUTCOME": 1,
        "RECEIVED": 0,
        "REFUSED": 2,
        "UNAVAILABLE": 1,
        "FAILED_INFRA": 0,
    }
    assert counts["by_contract"] == {DIGEST: 3, "sha256:" + "e" * 64: 1}
    assert ledger.attempt_counts("hk-other")["total"] == 1


def test_the_operator_reports_the_declared_budget_only(ledger):
    status = Operator(Adapters([Fake()]), ledger).status()
    assert status[DIGEST]["disclosure_budget"] is None


def test_the_ledger_must_be_owner_only(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    with pytest.raises(LedgerUnavailable) as refused:
        AttemptLedger(shared / "ledger.sqlite3")
    assert refused.value.code == "ledger_directory_not_owner_only"
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    path = private / "ledger.sqlite3"
    path.write_bytes(b"")
    path.chmod(0o644)
    with pytest.raises(LedgerUnavailable):
        AttemptLedger(path)


def test_the_validator_requires_its_parts(ledger):
    with pytest.raises(TypeError):
        Validator([Fake()], ledger)
    with pytest.raises(TypeError):
        Validator(Adapters([Fake()]), None)


def test_screen_passes_the_same_checks_as_evaluate_without_evaluating(
    validator, fake, ledger
):
    from carbon.challenge_validator.dispatch import SCREEN_REFUSALS, Screened

    screened = validator.screen(sub())
    assert type(screened) is Screened
    assert screened.adapter is fake
    assert screened.admitted.strategy == json.loads(strategy())
    assert fake.seen == [] and ledger.attempts() == []  # nothing evaluated or recorded
    refused = validator.screen(sub(contract_digest="sha256:" + "e" * 64))
    assert (refused["kind"], refused["code"]) == ("REFUSED", "contract_not_served")
    assert refused["code"] in SCREEN_REFUSALS
    assert [a["kind"] for a in ledger.attempts()] == ["REFUSED"]
    validator.note(sub(), kind="RECEIVED", submission_id="sub-9", state="RECEIVED")
    assert ledger.attempts()[-1]["submission_id"] == "sub-9"
    assert ledger.totals()["RECEIVED"] == 1 and ledger.totals()["REFUSED"] == 1
    with pytest.raises(ValueError):
        validator.note(sub(), kind="SCORED")
