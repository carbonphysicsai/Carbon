"""Per-Challenge sources for sealed confirmation sets (VALIDATOR-03).

A source says, for one Challenge, how a confirmation case is drawn under each
sampling law it serves, how two cases are compared for the overlap check
(`key`), which cases the Challenge has already published, and where its sets
are held (`custody`). It calls each Challenge's own code unchanged:

- battery: `carbon.battery.seeds.make_batch` in the validator deployment's
  seed journal, exactly as EV5's set was made (`daemon.seal_batch`);
- the cold plate and the motor: their DEVELOPMENT populations
  (`population.draw`: uniform over the box, kept if admitted).

A law a source serves is only available: a registered set uses it only when
a recorded owner decision names it in the set's document.
"""

from __future__ import annotations

import json
from pathlib import Path

from .confirmation import (
    ConfirmationRefused,
    _same_role_refusal,
    overlap_check,
)
from .interface import canonical_role


def _numeric_cases(value, names):
    """Every object inside `value` carrying all `names` as numbers."""
    stack = [value]
    while stack:
        item = stack.pop()
        if type(item) is dict:
            if all(type(item.get(n)) in (int, float) for n in names):
                yield item
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)


def _published_cases(repository, patterns, names):
    """Every case in the Challenge's published evidence (JSON and JSONL)."""
    root = Path(repository) / "docs/development/evidence"
    for pattern in patterns:
        for directory in sorted(root.glob(pattern)):
            for path in sorted(directory.rglob("*")):
                if path.suffix not in (".json", ".jsonl") or not path.is_file():
                    continue
                text = path.read_text()
                try:
                    documents = (
                        [json.loads(line) for line in text.splitlines() if line]
                        if path.suffix == ".jsonl"
                        else [json.loads(text)]
                    )
                except ValueError:
                    continue
                for document in documents:
                    yield from _numeric_cases(document, names)


class PopulationSource:
    """A Challenge whose sets are drawn from its DEVELOPMENT population and
    held in an owner-only custody (`confirmation.ConfirmationCustody`)."""

    custody = "confirmation_journal"
    #: Overlap keys round each input to this many decimal places.
    places = 6

    def __init__(self, challenge_id, module, evidence):
        self.challenge_id = challenge_id
        self.module = module
        self.evidence = evidence

    def _population(self):
        import importlib

        return importlib.import_module(f"carbon.{self.module}.population")

    def inputs(self):
        import importlib

        return importlib.import_module(f"carbon.{self.module}.domain").INPUTS

    @property
    def laws(self):
        """Law ids served: the population's own version, nothing else."""
        return frozenset({self._population().POPULATION_VERSION})

    def draw(self, rng, count, law):
        if law not in self.laws:
            raise ConfirmationRefused("confirmation_law_not_served")
        cases, _attempts = self._population().draw(rng, count)
        return cases

    def key(self, inputs):
        return tuple(round(float(inputs[name]), self.places) for name in self.inputs())

    def published(self, repository):
        names = self.inputs()
        return {
            self.key(case)
            for case in _published_cases(repository, self.evidence, names)
        }

    def implementation(self):
        import importlib

        return {
            name: Path(importlib.import_module(f"carbon.{self.module}.{name}").__file__)
            for name in ("population", "domain")
        }


class BatterySource:
    """Battery: sets are made by `seeds.make_batch` and committed to the
    validator deployment's seed journal under its writer lock, as EV5's was."""

    challenge_id = "battery-fastcharge-ageing-development-v1"
    custody = "battery_deployment"
    #: `seeds.draw_inputs`: uniform over the published box, 4 decimal places.
    laws = frozenset({"battery-published-box-uniform-v1"})
    places = 4

    def inputs(self):
        from carbon.battery.challenge import INPUTS

        return INPUTS

    def key(self, inputs):
        return tuple(round(float(inputs[name]), self.places) for name in self.inputs())

    def published(self, repository):
        from carbon.battery.daemon import published_inputs

        return set(published_inputs(repository))

    def public_decision(self, repository):
        """Every committed engineering-value study's decision cases (each
        scenario condition times each candidate), as case keys. They are
        public, so a sealed set must not repeat one (VALIDATOR-17)."""
        from carbon.battery.value import contract as ev

        found = set()
        folder = Path(repository) / "carbon/battery/value/contracts"
        for path in sorted(folder.glob("*.json")):
            document, _digest = ev.load(path)
            found.update(self.key(case) for case in ev.decision_cases(document))
        return found

    def implementation(self):
        from carbon.battery import daemon, seeds

        return {"seeds": Path(seeds.__file__), "daemon": Path(daemon.__file__)}

    def export(self, item, config, repository):
        """A set sealed in the deployment `config`'s journal: its distinct
        case inputs, regenerated in memory from the deployment's root and
        checked against the committed fingerprint. Read only."""
        from carbon.battery import deployment, seeds

        if item.human_input:
            raise ConfirmationRefused("confirmation_human_input_missing")
        target = deployment.validator(config, repository=repository, readonly=True)
        committed = [
            e
            for e in target.journal.public()
            if e["kind"] == "batch" and canonical_role(e["role"]) == item.role
        ]
        if not committed:
            raise ConfirmationRefused("confirmation_prior_not_sealed:" + item.role)
        if len({e["fingerprint"] for e in committed}) != 1:
            raise ConfirmationRefused("confirmation_role_reused")
        batch = seeds.make_batch(
            target.root,
            target.pin,
            committed[0]["role"],
            item.batch_size,
            item.hidden_duplicates,
        )
        if batch.fingerprint != committed[0]["fingerprint"]:
            raise ConfirmationRefused(
                "confirmation_prior_regeneration_mismatch:" + item.role
            )
        duplicates = dict(batch.duplicates)
        return [dict(x) for case_id, x in batch.cases if case_id not in duplicates]

    def seal(self, item, sets, config, private, repository):
        """Seal `item` in the deployment `config`'s seed journal."""
        from carbon.battery import deployment, seeds

        if item.strata:
            # seeds.make_batch draws one law with no strata, as EV5's set did.
            raise ConfirmationRefused("confirmation_strata_not_served")
        target = deployment.validator(config, repository=repository, readonly=True)
        with deployment.writer(target):
            count, duplicates = item.batch_size, item.hidden_duplicates
            batch = seeds.make_batch(
                target.root, target.pin, item.role, count, duplicates
            )
            committed = [e for e in target.journal.public() if e["kind"] == "batch"]
            again = _same_role_refusal(item.role, committed, batch.fingerprint)
            pooled = {b["fingerprint"]: b for b in target.store.batches()}
            priors = {
                "published": self.published(repository),
                "public_decision": self.public_decision(repository),
                **private,
            }
            present = set()
            for entry in committed:
                role = canonical_role(entry["role"])
                if role == item.role:
                    continue
                if entry["fingerprint"] in pooled:
                    cases = pooled[entry["fingerprint"]]["document"]["cases"]
                    priors.setdefault("pooled", set()).update(
                        self.key(case["inputs"]) for case in cases
                    )
                    continue
                present.add(role)
                if role not in sets:
                    raise ConfirmationRefused(
                        "confirmation_prior_not_regenerable:" + role
                    )
                prior = sets[role]
                # Regenerated in memory only, and checked against the
                # fingerprint the journal committed: never stored or printed.
                regenerated = seeds.make_batch(
                    target.root,
                    target.pin,
                    entry["role"],
                    prior.batch_size,
                    prior.hidden_duplicates,
                )
                if regenerated.fingerprint != entry["fingerprint"]:
                    raise ConfirmationRefused(
                        "confirmation_prior_regeneration_mismatch:" + role
                    )
                priors["sealed:" + role] = {
                    self.key(dict(x)) for _c, x in regenerated.cases
                }
            for role in item.required_prior_roles:
                if role not in present:
                    raise ConfirmationRefused(
                        "confirmation_required_prior_absent:" + role
                    )
            inputs = {case_id: dict(x) for case_id, x in batch.cases}
            checked = overlap_check(self, inputs, priors, dict(batch.duplicates))
            sealed_batch = target.seal_batch(
                item.role, count=count, duplicates=duplicates
            )
            if sealed_batch.fingerprint != batch.fingerprint:
                raise ConfirmationRefused("confirmation_seal_fingerprint_mismatch")
        return {
            "newly_committed": not again,
            "commitment": {
                "fingerprint": sealed_batch.fingerprint,
                "journal_sequence": sealed_batch.sequence,
            },
            "overlap_checked": checked,
        }


def _sources():
    from carbon.reconstruction.capability_registry import (
        COLD_PLATE_CHALLENGE,
        MOTOR_CHALLENGE,
    )

    battery = BatterySource()
    return {
        battery.challenge_id: battery,
        COLD_PLATE_CHALLENGE: PopulationSource(
            COLD_PLATE_CHALLENGE, "cold_plate", ("cold-plate-*",)
        ),
        MOTOR_CHALLENGE: PopulationSource(MOTOR_CHALLENGE, "motor", ("motor-*",)),
    }


def source_for(challenge_id):
    sources = _sources()
    if challenge_id not in sources:
        raise ConfirmationRefused("confirmation_challenge_not_served")
    return sources[challenge_id]
