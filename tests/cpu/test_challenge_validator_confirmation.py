"""Challenge-neutral sealed confirmation sets (VALIDATOR-03).

Pins:
- the registry: every confirmation role is registered, pinned by digest and
  reserved; size, law and strata are the recorded decisions'
  (OWNER-GRAPHITE-TEST-WAVE-01 §7, -05 §4), and an unset value refuses every
  seal;
- sealing in an owner-only custody (motor): strata quotas, hidden
  duplicates, idempotent reruns, case-insensitive role reuse, the overlap
  check against published, private and earlier sealed cases, and earlier
  sets regenerated against their committed fingerprints;
- sealing in battery's deployment journal, with EV5's set as a required
  prior, as EV5 itself was sealed;
- that nothing printed carries a case id, an input or the root.

Synthetic roots and temporary custodies only: no deployment, root or journal
of a real validator is read. Not a security audit (AGENTS.md §13).
"""

import json
import pickle
import shutil
from pathlib import Path

import pytest

from carbon.challenge_validator import confirmation as cf
from carbon.challenge_validator import interface
from carbon.challenge_validator.confirmation_sources import source_for

REPOSITORY = Path(__file__).resolve().parents[2]
MOTOR = "electric-motor-magnetics"
MOTOR_ROLE = "motor-graphite-confirmation-v1"
COOLING_ROLE = "cooling-graphite-confirmation-v1"
BATTERY_ROLE = "graphite-confirmation-v1"
PRIVATE = "motor-pools-v1-private"


def refused(call, code):
    with pytest.raises(cf.ConfirmationRefused) as caught:
        call()
    assert caught.value.code == code, caught.value.code
    return caught.value


# --- the registry ---------------------------------------------------------------------


def test_the_registry_holds_the_recorded_decisions_and_every_role_is_reserved():
    sets = cf.load_sets()
    # Every reserved role is a registered confirmation set, except the
    # training-budget study's own roles, which are never registered here.
    assert set(sets) | interface.STUDY_ROLES == set(interface.RESERVED_SEED_ROLES)
    assert not set(sets) & interface.STUDY_ROLES
    for role, item in sets.items():
        assert interface.role_reserved(role.upper())
        assert item.skeleton()["set_digest"] == item.digest
    battery = sets[BATTERY_ROLE]
    assert (battery.cases, battery.hidden_duplicates, battery.strata) == (120, 4, ())
    # "No strata" is stated explicitly, never an empty list (the readiness
    # gate, D7).
    assert battery.skeleton()["strata"] == cf.STRATA_NONE
    assert sets["ev5-confirmation"].skeleton()["strata"] == cf.STRATA_NONE
    assert battery.required_prior_roles == ("ev5-confirmation",)
    assert sets["ev5-confirmation"].sealable is False
    motor = sets[MOTOR_ROLE]
    assert (motor.cases, motor.hidden_duplicates) == (60, 2)
    (stratum,) = motor.strata
    assert stratum["lower_bounds"] == {"current_density_a_mm2": 10.0}
    assert stratum["min_fraction"] == {"numerator": 1, "denominator": 3}
    from carbon.motor.exam import J_IMPORTANT

    assert stratum["lower_bounds"]["current_density_a_mm2"] == J_IMPORTANT
    cooling = sets[COOLING_ROLE]
    assert (cooling.cases, cooling.hidden_duplicates) == (60, 2)
    (stratum,) = cooling.strata
    assert stratum["lower_bounds"] == {"heat_load_w": 1200.0, "inlet_c": 40.0}
    assert cooling.human_input == [] and cooling.skeleton()["batch_size"] == 62


def test_the_skeleton_is_public_only():
    def keys(value):
        if type(value) is dict:
            for key, item in value.items():
                yield key
                yield from keys(item)
        elif type(value) is list:
            for item in value:
                yield from keys(item)

    for item in cf.load_sets().values():
        found = set(keys(item.skeleton()))
        assert not found & {"case_id", "inputs", "root", "seed", "fingerprint"}


def _registry_copy(tmp_path, edit=None, *, extra=()):
    """A registry copy with `edit(documents)` applied and pins recomputed."""
    directory = tmp_path / "sets"
    shutil.copytree(cf.SET_DIR, directory)
    documents = {
        role: json.loads((directory / f"{role}.json").read_text())
        for role in json.loads((directory / "registry.json").read_text())["sets"]
    }
    for document in extra:
        documents[document["role"]] = document
    if edit is not None:
        edit(documents)
    for role, document in documents.items():
        (directory / f"{role}.json").write_text(json.dumps(document))
    registry = json.loads((directory / "registry.json").read_text())
    registry["sets"] = {role: cf.digest(d) for role, d in documents.items()}
    (directory / "registry.json").write_text(json.dumps(registry))
    return directory


def test_an_altered_or_malformed_document_is_refused(tmp_path):
    directory = _registry_copy(tmp_path)
    path = directory / f"{MOTOR_ROLE}.json"
    document = json.loads(path.read_text())
    path.write_text(json.dumps({**document, "cases": 59}))
    refused(lambda: cf.load_sets(directory), "confirmation_set_altered:" + MOTOR_ROLE)

    def unset_but_unlisted(documents):
        documents[MOTOR_ROLE]["cases"] = None

    directory = _registry_copy(tmp_path / "b", unset_but_unlisted)
    refused(
        lambda: cf.load_sets(directory),
        "confirmation_set_malformed:human_input_does_not_match_unset_values",
    )

    def too_many_strata(documents):
        stratum = dict(documents[MOTOR_ROLE]["strata"][0])
        documents[MOTOR_ROLE]["strata"] = [
            {
                **stratum,
                "id": f"s{i}",
                "min_fraction": {"numerator": 1, "denominator": 2},
            }
            for i in range(3)
        ]

    directory = _registry_copy(tmp_path / "c", too_many_strata)
    refused(
        lambda: cf.load_sets(directory),
        "confirmation_set_malformed:strata_exceed_cases",
    )


def test_an_empty_strata_list_is_refused(tmp_path):
    def empty(documents):
        documents[BATTERY_ROLE]["strata"] = []

    directory = _registry_copy(tmp_path, empty)
    refused(
        lambda: cf.load_sets(directory),
        "confirmation_set_malformed:strata_empty_state_NONE_UNIFORM_LAW",
    )


def test_an_unreserved_role_cannot_be_registered(tmp_path):
    document = json.loads((cf.SET_DIR / f"{MOTOR_ROLE}.json").read_text())
    directory = _registry_copy(
        tmp_path, extra=[{**document, "role": "motor-unreserved-v1"}]
    )
    refused(
        lambda: cf.load_sets(directory),
        "confirmation_role_not_reserved:motor-unreserved-v1",
    )


def test_an_unset_value_refuses_every_seal(tmp_path, capsys):
    def unset(documents):
        documents[COOLING_ROLE]["strata"] = None
        documents[COOLING_ROLE]["authority"]["human_input"] = ["strata"]

    registry = _registry_copy(tmp_path, unset)
    refused(
        lambda: cf.seal(COOLING_ROLE, custody=tmp_path, directory=registry),
        "confirmation_human_input_missing:strata",
    )
    assert cf.manifest(COOLING_ROLE, directory=registry)["blockers"] == [
        "human_input:strata",
        "not_sealed",
    ]
    assert cf.main(["seal", "--role", "no-such-role", "--custody", "/tmp/x"]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "refused": "confirmation_role_not_registered"
    }
    refused(
        lambda: cf.seal("ev5-confirmation", config="/tmp/x"),
        "confirmation_set_not_sealable:ev5-confirmation",
    )
    refused(
        lambda: cf.seal("no-such-role", custody="/tmp/x"),
        "confirmation_role_not_registered",
    )


# --- sealing in an owner-only custody (motor) -----------------------------------------


@pytest.fixture
def custody(tmp_path):
    tmp_path.chmod(0o700)
    directory = tmp_path / "custody"
    _custody, entry = cf.ConfirmationCustody.init(directory, MOTOR)
    assert entry["sequence"] == 0 and entry["root_commitment"].startswith("sha256:")
    return directory


def _private_prior(tmp_path, cases):
    path = tmp_path / "private.plan.json"
    path.write_text(json.dumps({"cases": [{"inputs": c} for c in cases]}))
    path.chmod(0o600)
    return {PRIVATE: str(path)}


def _motor_cases(count, seed):
    from carbon.motor import population

    return population.draw(population.public_rng(f"test-prior-{seed}"), count)[0]


def _batch(directory, role=MOTOR_ROLE, registry=None):
    custody = cf.ConfirmationCustody(directory, MOTOR)
    item = cf.confirmation_set(role, registry)
    return cf.make_batch(custody.root(), source_for(MOTOR), item)


def test_a_motor_set_is_sealed_with_its_stratum_and_hidden_duplicates(
    tmp_path, custody
):
    priors = _private_prior(tmp_path, _motor_cases(5, "a"))
    result = cf.seal(MOTOR_ROLE, custody=custody, private_priors=priors)
    assert result["newly_committed"] is True
    assert (result["cases"], result["hidden_duplicates"]) == (60, 2)
    assert cf.sealed(result["commitment"]) == result["commitment"]
    assert result["commitment"]["journal_sequence"] == 1
    assert set(result["overlap_checked"]) == {"published", "private:" + PRIVATE}
    assert result["overlap_checked"]["published"] > 200
    batch = _batch(custody)
    assert batch.fingerprint == result["commitment"]["fingerprint"]
    duplicates = dict(batch.duplicates)
    assert len(batch.cases) == 62 and len(duplicates) == 2
    fresh = [x for c, x in batch.inputs().items() if c not in duplicates]
    from carbon.motor import population
    from carbon.motor.domain import INPUT_BOUNDS

    assert all(population.admitted(x) for x in fresh)
    for inputs in fresh:
        for name, value in inputs.items():
            low, high = INPUT_BOUNDS[name]
            assert low <= value <= high
    # At least a third of the fresh cases lie in the stratum.
    inside = [x for x in fresh if x["current_density_a_mm2"] >= 10.0]
    assert len(inside) >= 20
    # Every hidden duplicate repeats a fresh case's inputs under another id.
    for duplicate, original in duplicates.items():
        assert batch.inputs()[duplicate] == batch.inputs()[original]
        assert duplicate != original


def test_sealing_again_recalls_the_same_commitment_in_any_spelling(tmp_path, custody):
    priors = _private_prior(tmp_path, _motor_cases(5, "a"))
    first = cf.seal(MOTOR_ROLE, custody=custody, private_priors=priors)
    again = cf.seal(MOTOR_ROLE.upper(), custody=custody, private_priors=priors)
    assert again["commitment"] == first["commitment"]
    assert again["newly_committed"] is False
    batches = cf.ConfirmationCustody(custody, MOTOR).batches()
    assert len(batches) == 1


def test_a_second_batch_under_the_role_in_any_spelling_is_refused(tmp_path, custody):
    target = cf.ConfirmationCustody(custody, MOTOR)
    target._append(
        {
            "kind": "batch",
            "challenge": MOTOR,
            "role": "Motor-Graphite-Confirmation-V1",
            "fingerprint": "sha256:" + "0" * 64,
            "cases": 3,
            "set_digest": "sha256:" + "0" * 64,
        }
    )
    priors = _private_prior(tmp_path, _motor_cases(5, "a"))
    refused(
        lambda: cf.seal(MOTOR_ROLE, custody=custody, private_priors=priors),
        "confirmation_role_reused",
    )


def test_a_case_repeating_a_published_or_private_case_is_refused(
    tmp_path, custody, monkeypatch
):
    batch = _batch(custody)
    duplicates = dict(batch.duplicates)
    fresh = [x for c, x in batch.inputs().items() if c not in duplicates]
    source = source_for(MOTOR)
    priors = _private_prior(tmp_path, [*_motor_cases(5, "a"), fresh[7]])
    refused(
        lambda: cf.seal(MOTOR_ROLE, custody=custody, private_priors=priors),
        "confirmation_overlaps_prior:private:" + PRIVATE,
    )
    clean = _private_prior(tmp_path, _motor_cases(5, "a"))
    from carbon.challenge_validator import confirmation_sources

    published = source.published(REPOSITORY) | {source.key(fresh[3])}
    monkeypatch.setattr(
        confirmation_sources.PopulationSource, "published", lambda self, r: published
    )
    refused(
        lambda: cf.seal(MOTOR_ROLE, custody=custody, private_priors=clean),
        "confirmation_overlaps_prior:published",
    )
    assert cf.ConfirmationCustody(custody, MOTOR).batches() == []


def test_the_registered_private_pool_is_required_and_checked(tmp_path, custody):
    refused(
        lambda: cf.seal(MOTOR_ROLE, custody=custody),
        "confirmation_private_prior_missing:" + PRIVATE,
    )
    priors = _private_prior(tmp_path, _motor_cases(5, "a"))
    refused(
        lambda: cf.seal(
            MOTOR_ROLE,
            custody=custody,
            private_priors={**priors, "other": priors[PRIVATE]},
        ),
        "confirmation_private_prior_not_registered:other",
    )
    Path(priors[PRIVATE]).chmod(0o640)
    refused(
        lambda: cf.seal(MOTOR_ROLE, custody=custody, private_priors=priors),
        "confirmation_custody_not_owner_only",
    )
    Path(priors[PRIVATE]).chmod(0o600)
    Path(priors[PRIVATE]).write_text("{}")
    refused(
        lambda: cf.seal(MOTOR_ROLE, custody=custody, private_priors=priors),
        "confirmation_private_prior_malformed:" + PRIVATE,
    )


def _prior_document():
    document = json.loads((cf.SET_DIR / f"{MOTOR_ROLE}.json").read_text())
    return {
        **document,
        "role": "motor-test-prior-v1",
        "cases": 6,
        "hidden_duplicates": 1,
        "strata": "NONE_UNIFORM_LAW",
        "required_private_priors": [],
    }


def test_earlier_sets_are_regenerated_and_checked_against_their_commitment(
    tmp_path, custody, monkeypatch
):
    monkeypatch.setattr(
        interface,
        "RESERVED_SEED_ROLES",
        interface.RESERVED_SEED_ROLES | {"motor-test-prior-v1"},
    )

    def requires_prior(documents):
        documents[MOTOR_ROLE]["required_prior_roles"] = ["motor-test-prior-v1"]

    registry = _registry_copy(tmp_path, requires_prior, extra=[_prior_document()])
    priors = _private_prior(tmp_path, _motor_cases(5, "a"))

    def run():
        return cf.seal(
            MOTOR_ROLE, custody=custody, private_priors=priors, directory=registry
        )

    refused(run, "confirmation_required_prior_absent:motor-test-prior-v1")
    prior = cf.seal("motor-test-prior-v1", custody=custody, directory=registry)
    assert prior["newly_committed"] is True
    result = run()
    assert result["overlap_checked"]["sealed:motor-test-prior-v1"] == 6
    # A journal entry the registry cannot regenerate, or one that does not
    # match what its role regenerates, stops every later seal.
    target = cf.ConfirmationCustody(custody, MOTOR)
    target._append(
        {
            "kind": "batch",
            "challenge": MOTOR,
            "role": "motor-unknown-v1",
            "fingerprint": "sha256:" + "1" * 64,
            "cases": 3,
            "set_digest": "sha256:" + "1" * 64,
        }
    )
    refused(run, "confirmation_prior_not_regenerable:motor-unknown-v1")


def test_a_prior_that_regenerates_differently_is_refused(
    tmp_path, custody, monkeypatch
):
    monkeypatch.setattr(
        interface,
        "RESERVED_SEED_ROLES",
        interface.RESERVED_SEED_ROLES | {"motor-test-prior-v1"},
    )
    registry = _registry_copy(tmp_path, extra=[_prior_document()])
    target = cf.ConfirmationCustody(custody, MOTOR)
    target._append(
        {
            "kind": "batch",
            "challenge": MOTOR,
            "role": "motor-test-prior-v1",
            "fingerprint": "sha256:" + "2" * 64,
            "cases": 7,
            "set_digest": "sha256:" + "2" * 64,
        }
    )
    priors = _private_prior(tmp_path, _motor_cases(5, "a"))
    refused(
        lambda: cf.seal(
            MOTOR_ROLE, custody=custody, private_priors=priors, directory=registry
        ),
        "confirmation_prior_regeneration_mismatch:motor-test-prior-v1",
    )


def test_the_custody_is_owner_only_outside_the_repository(tmp_path, custody):
    refused(
        lambda: cf.ConfirmationCustody.init(REPOSITORY / "custody", MOTOR),
        "confirmation_custody_inside_repository",
    )
    refused(
        lambda: cf.ConfirmationCustody.init(custody, MOTOR),
        "confirmation_custody_exists",
    )
    refused(
        lambda: cf.ConfirmationCustody(custody, "chip-cold-plate"),
        "confirmation_custody_root_not_committed",
    )
    (custody / "root").chmod(0o644)
    refused(
        lambda: cf.ConfirmationCustody(custody, MOTOR),
        "confirmation_custody_not_owner_only",
    )
    (custody / "root").chmod(0o600)
    custody.chmod(0o750)
    refused(
        lambda: cf.ConfirmationCustody(custody, MOTOR),
        "confirmation_custody_not_owner_only",
    )
    custody.chmod(0o700)
    root = cf.ConfirmationCustody(custody, MOTOR).root()
    assert repr(root) == "ConfirmationRoot(<redacted>)"
    with pytest.raises(TypeError):
        pickle.dumps(root)
    assert "<redacted>" in repr(_batch(custody))


def test_the_seal_command_prints_only_the_public_commitment(tmp_path, custody, capsys):
    priors = _private_prior(tmp_path, _motor_cases(5, "a"))
    argv = ["seal", "--role", MOTOR_ROLE, "--custody", str(custody)]
    argv += ["--prior", f"{PRIVATE}={priors[PRIVATE]}"]
    assert cf.main(argv) == 0
    printed = capsys.readouterr().out
    result = json.loads(printed)
    assert set(result) == {
        "challenge_id",
        "role",
        "cases",
        "hidden_duplicates",
        "set_digest",
        "newly_committed",
        "commitment",
        "overlap_checked",
        "private_priors",
    }
    batch = _batch(custody)
    for case_id, inputs in batch.inputs().items():
        assert case_id not in printed
        assert not any(repr(v) in printed for v in inputs.values())
    assert (custody / "root").read_bytes().hex() not in printed
    assert "." not in printed.replace(".json", "")
    # The journal holds commitments only.
    journal = (custody / "journal.jsonl").read_text()
    assert all(case_id not in journal for case_id in batch.inputs())


def test_draws_follow_the_root_and_the_role(tmp_path, custody):
    first, again = _batch(custody), _batch(custody)
    assert first.fingerprint == again.fingerprint
    other = tmp_path / "other"
    cf.ConfirmationCustody.init(other, MOTOR)
    assert _batch(other).fingerprint != first.fingerprint
    assert cf._quota(60, {"min_fraction": {"numerator": 1, "denominator": 3}}) == 20
    assert cf._quota(61, {"min_fraction": {"numerator": 1, "denominator": 3}}) == 21


def test_a_cooling_set_meets_its_stratum_quota(tmp_path):
    tmp_path.chmod(0o700)
    directory = tmp_path / "custody"
    cf.ConfirmationCustody.init(directory, "chip-cold-plate")
    plan = tmp_path / "private.plan.json"
    from carbon.cold_plate import population

    cases = population.draw(population.public_rng("test-cooling-prior"), 5)[0]
    plan.write_text(json.dumps({"cases": [{"inputs": c} for c in cases]}))
    plan.chmod(0o600)
    result = cf.seal(
        COOLING_ROLE,
        custody=directory,
        private_priors={"cold-plate-pools-v1-private": str(plan)},
    )
    assert result["overlap_checked"]["published"] > 500
    custody = cf.ConfirmationCustody(directory, "chip-cold-plate")
    item = cf.confirmation_set(COOLING_ROLE)
    batch = cf.make_batch(custody.root(), source_for("chip-cold-plate"), item)
    assert batch.fingerprint == result["commitment"]["fingerprint"]
    duplicates = dict(batch.duplicates)
    fresh = [x for c, x in batch.inputs().items() if c not in duplicates]
    assert len(fresh) == 60 and all(population.admitted(x) for x in fresh)
    (stratum,) = item.strata
    assert sum(cf.in_stratum(x, stratum) for x in fresh) >= 20


# --- battery: the deployment's seed journal -------------------------------------------


def _deployment(tmp_path, monkeypatch):
    """A validator deployment whose root `operate init` has committed."""
    from carbon.battery import deployment, seeds
    from carbon.battery.daemon import rule_digest

    monkeypatch.setattr(deployment, "_VALIDATORS", {})
    tmp_path.chmod(0o700)
    root = seeds.PrivateRoot.create(tmp_path / "root.bin")
    journal = seeds.SeedJournal(tmp_path / "journal.jsonl")
    journal.commit_root(root, seeds.seed_pin("sha256:" + "1" * 64, rule_digest()))
    path = tmp_path / "deployment.json"
    path.write_text(
        json.dumps(
            {
                "schema": deployment.SCHEMA,
                "state": str(tmp_path / "state.sqlite3"),
                "private_root": str(tmp_path / "root.bin"),
                "journal": str(tmp_path / "journal.jsonl"),
                "work": str(tmp_path / "work"),
                "backend": "direct",
                "require_commitment": False,
            }
        )
    )
    path.chmod(0o600)
    return path


def test_battery_seals_after_ev5_in_its_deployment_journal(tmp_path, monkeypatch):
    from carbon.battery import deployment, seeds
    from carbon.battery.daemon import BatteryValidator
    from carbon.battery.value import ev5

    path = _deployment(tmp_path, monkeypatch)

    def forbidden(self):
        raise AssertionError("sealing started or recovered the validator")

    monkeypatch.setattr(BatteryValidator, "start", forbidden)
    monkeypatch.setattr(BatteryValidator, "recover", forbidden)
    refused(
        lambda: cf.seal(BATTERY_ROLE, config=path),
        "confirmation_required_prior_absent:ev5-confirmation",
    )
    refused(
        lambda: cf.seal(BATTERY_ROLE, custody=tmp_path),
        "confirmation_needs_the_deployment_config",
    )
    ev5.seal_confirmation(path)
    result = cf.seal(BATTERY_ROLE, config=path)
    assert result["newly_committed"] is True
    assert (result["cases"], result["hidden_duplicates"]) == (120, 4)
    assert result["overlap_checked"]["sealed:ev5-confirmation"] == 120
    assert result["overlap_checked"]["published"] > 0
    again = cf.seal(BATTERY_ROLE.upper(), config=path)
    assert again["commitment"] == result["commitment"]
    assert again["newly_committed"] is False
    root = seeds.PrivateRoot.load(tmp_path / "root.bin")
    pin = seeds.SeedJournal(tmp_path / "journal.jsonl").root_pin(root)
    batch = seeds.make_batch(root, pin, BATTERY_ROLE, 124, 4)
    assert batch.fingerprint == result["commitment"]["fingerprint"]
    target = deployment.validator(path, repository=REPOSITORY, readonly=True)
    assert target.store.batches() == []


def test_battery_refuses_reuse_and_an_ev5_that_does_not_regenerate(
    tmp_path, monkeypatch
):
    from carbon.battery import deployment

    path = _deployment(tmp_path, monkeypatch)
    target = deployment.validator(path, repository=REPOSITORY, readonly=True)
    # EV5's role committed with another size: its regeneration cannot match.
    target.seal_batch("ev5-confirmation", count=10, duplicates=2)
    refused(
        lambda: cf.seal(BATTERY_ROLE, config=path),
        "confirmation_prior_regeneration_mismatch:ev5-confirmation",
    )
    (tmp_path / "b").mkdir()
    other = _deployment(tmp_path / "b", monkeypatch)
    target = deployment.validator(other, repository=REPOSITORY, readonly=True)
    target.seal_batch("Graphite-Confirmation-V1", count=10, duplicates=2)
    refused(lambda: cf.seal(BATTERY_ROLE, config=other), "confirmation_role_reused")


# --- the pinning manifest -------------------------------------------------------------


def test_the_manifest_binds_the_document_code_and_commitment():
    pinned = cf.manifest(MOTOR_ROLE)
    assert pinned["blockers"] == ["not_sealed"]
    assert pinned["set_digest"] == cf.confirmation_set(MOTOR_ROLE).digest
    assert pinned["registry_digest"] == cf.registry_digest()
    assert {"confirmation", "confirmation_sources", "population", "domain"} <= set(
        pinned["implementation"]
    )
    commitment = {"fingerprint": "sha256:" + "a" * 64, "journal_sequence": 3}
    assert cf.manifest(MOTOR_ROLE, commitment=commitment)["blockers"] == []
    assert cf.manifest(COOLING_ROLE)["blockers"] == ["not_sealed"]
    refused(
        lambda: cf.manifest(MOTOR_ROLE, commitment={"fingerprint": "x"}),
        "confirmation_commitment_malformed",
    )
