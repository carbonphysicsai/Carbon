"""The direct campaign of a version registered by data (owner G-LEAD-61): the shared one, bound to its own pinned module.

A version with a build row (`challenge_registry.exam_build`) and an entry row (`exam_entry`) has a research campaign when its
build module also states its PRACTICE MEASUREMENT, which no code here chooses:

- ``error_scale(challenge_id, version)``: the registered practice error scale, as `practice.error_scale` serves one;
- ``practice_summary(challenge_id, version, rows, material)``: the aggregate practice result on that scale (no per-case
  value), with exactly the ``PRACTICE_COMPONENTS``;
- ``PRACTICE_COMPONENTS``: ``((name, label), ...)``, the aggregate's components in order;
- ``train_facts(challenge_id, version)``: public TRAIN's registered facts, as `contracts.train_facts` serves them;
- optional ``UNIT_LABELS`` (units `contracts.UNIT_LABELS` does not name) and ``FACTS`` / ``LABELS`` (the owner-approved
  facts and clause labels, as `facts` keeps them; each one absent is HUMAN_INPUT and fails closed where it is read).

The module is pinned by sha256 in its row, so these values are the row's. A version without a complete, well-formed set has
no campaign and its reason is in `REFUSED`; a nearby version or family is never used in its place. A version the code serves
is never read from a row. The exam's own practice dual grades a version its family's code registers; here it says it is not
available, so practice feedback is the registered aggregate alone.
"""

from __future__ import annotations

import contextvars
import functools
import logging
import math
from dataclasses import dataclass
from types import SimpleNamespace

from carbon.challenge_registry import exam_build, exam_entry, exam_registry

from .spec import HUMAN_INPUT, Spec

_LOG = logging.getLogger(__name__)
#: ``{(challenge id, version): reason}`` of every registered version that gets no campaign.
REFUSED: dict = {}
#: One prefix for every registered version: its identifiers are already scoped by its Challenge key.
PREFIX = "registered"
PRACTICE_PROVENANCE = "REGISTERED_PUBLIC_PRACTICE"
BACKENDS = ("torch_cpu", "jax")
#: What a campaign's build module must define beside `exam_build.FUNCTIONS`.
FUNCTIONS = ("error_scale", "practice_summary", "train_facts")
_SUMMARY = {
    "cases",
    "outputs",
    "score",
    "aggregate_error",
    "components",
    "error_scale",
    "status",
}
_TRAIN_FACTS = {
    "train_cases",
    "train_dtype",
    "train_provenance_sha256",
    "file",
    "format",
}


class CampaignRefused(ValueError):
    """A registered version's campaign parts are missing or malformed."""


@dataclass(frozen=True)
class RegisteredSpec(Spec):
    """`spec.Spec` for exactly one version registered by data; every value is its module's."""

    #: The digest of the version's registry row: another row is another spec (the shared caches are keyed by it).
    row_digest: str

    @property
    def _key(self):
        return self.challenge_id, self.versions[0]

    def public(self):
        return exam_build.module(*self._key)

    def output_dtype(self):
        from carbon.challenge_kit.interface_dtype import output_dtype

        return output_dtype(self.public().interface_document(*self._key))

    def error_scale(self, version):
        return self.public().error_scale(self.challenge_id, version)

    def components(self):
        return tuple(tuple(item) for item in self.public().PRACTICE_COMPONENTS)

    def unit_labels(self):
        return dict(getattr(self.public(), "UNIT_LABELS", {}))

    def fact(self, name):
        return getattr(self.public(), "FACTS", {}).get(name, HUMAN_INPUT)

    def fact_label(self, name):
        return getattr(self.public(), "LABELS", {}).get(name)

    def practice_summary(self, version, rows, material):
        value = self.public().practice_summary(
            self.challenge_id, version, rows, material
        )
        names = tuple(name for name, _label in self.components())
        if (
            type(value) is not dict
            or not _SUMMARY <= set(value)
            or type(value["components"]) is not dict
            or tuple(value["components"]) != names
            or value["outputs"]
            != list(material["interface_document"]["output"]["names"])
            or not all(
                type(number) is float and math.isfinite(number)
                for number in (
                    value["score"],
                    value["aggregate_error"],
                    *value["components"].values(),
                )
            )
        ):
            # a nonfinite, per-case or unnamed value never reaches a miner's feedback
            raise ValueError("registered_practice_summary_invalid")
        return value

    def dual_feedback(self, version):
        from carbon.scoring import practice_dual

        return practice_dual.unavailable_v2(
            self.challenge_id, version, "practice_version_not_registered"
        )


def _check(key) -> None:
    """The version's module states a complete practice measurement, in the interface the shared campaign serves."""
    import numpy as np

    from carbon.challenge_kit.interface_dtype import output_dtype

    from .contracts import PRECISION, UNIT_LABELS

    module = exam_build.module(*key)
    missing = [name for name in FUNCTIONS if not callable(getattr(module, name, None))]
    components = getattr(module, "PRACTICE_COMPONENTS", None)
    if missing or type(components) is not tuple or not components:
        raise CampaignRefused("campaign_needs_its_practice_measurement")
    if not all(
        type(item) is tuple
        and len(item) == 2
        and all(type(text) is str and text for text in item)
        for item in components
    ) or len({name for name, _label in components}) != len(components):
        raise CampaignRefused("campaign_components_malformed")
    units, facts, labels = (
        getattr(module, name, {}) for name in ("UNIT_LABELS", "FACTS", "LABELS")
    )
    if not all(
        type(table) is dict
        and all(type(text) is str and text for item in table.items() for text in item)
        for table in (units, facts, labels)
    ):
        raise CampaignRefused("campaign_facts_malformed")
    # a label is a stated fact's; the one fact a clause always needs a label for has one
    if any(name.split(".")[0] not in facts for name in labels) or (
        "known_limitation" in facts and "known_limitation" not in labels
    ):
        raise CampaignRefused("campaign_facts_malformed")
    interface = module.interface_document(*key)
    try:
        fields = [
            unit
            for side in ("input", "output")
            for _name, unit in zip(
                interface[side]["names"], interface[side]["units"], strict=True
            )
        ]
        declared = output_dtype(interface)
        train = module.train_facts(*key)
        wanted = exam_build.block(*key)["graph_spec"]["dtype"]
        if not (
            fields
            and all(unit in UNIT_LABELS or unit in units for unit in fields)
            and interface["train_dtype"] in PRECISION
            and np.dtype(declared) == np.dtype(wanted)
            and (wanted != "float32" or declared == "<f4")
            and _TRAIN_FACTS <= set(train)
            and train["train_dtype"] == interface["train_dtype"]
        ):
            raise CampaignRefused("campaign_interface_unserved")
    except (KeyError, TypeError, ValueError) as error:
        raise CampaignRefused("campaign_interface_unserved") from error


def _refuse(key, reason) -> None:
    if REFUSED.get(key) != reason:
        REFUSED[key] = reason
        _LOG.warning("exam registry campaign %r refused: %s", key, reason)


def keys() -> tuple:
    """Every registered version that has a campaign. Read once per set of rows (they are add-only)."""
    return _serving(
        tuple((key, exam_registry.digest(*key)) for key in sorted(exam_entry.rows()))
    )


@functools.lru_cache(maxsize=4)
def _serving(named) -> tuple:
    found = []
    for key, _digest in named:
        try:
            _check(key)
        except (CampaignRefused, exam_build.ExamBuildRefused) as refused:
            _refuse(key, str(refused))
            continue
        except Exception as error:  # noqa: BLE001
            # its module's own failure is this version's alone: it never takes another campaign down with it
            _refuse(key, "campaign_module_failed: " + type(error).__name__)
            continue
        found.append(key)
    return tuple(found)


def spec_for(challenge_id: str, version: str) -> RegisteredSpec:
    """The version's spec, one per row (its research key is one variable), or a refusal: it has no campaign."""
    if (challenge_id, version) not in keys():
        raise ValueError("registered direct campaign version required")
    return _spec(challenge_id, version, exam_registry.digest(challenge_id, version))


@functools.lru_cache(maxsize=64)
def _spec(challenge_id, version, row_digest):
    return RegisteredSpec(
        challenge_id,
        PREFIX,
        exam_registry.field(challenge_id, version, "entry")["title"],
        (version,),
        "",
        PRACTICE_PROVENANCE,
        contextvars.ContextVar("carbon_registered_research_key", default=None),
        row_digest,
    )


def campaign(challenge_id: str, version: str) -> SimpleNamespace:
    """What `challenge_registry.campaigns._direct` composes: the key, hooks and view one family package holds each."""
    from . import campaign as shared
    from . import research_view, spec

    own = spec_for(challenge_id, version)

    async def evaluate_frozen(prepared, epoch, strategy):
        return await shared.evaluate_frozen(
            own, prepared, epoch, strategy, record=shared.record_verdict
        )

    return SimpleNamespace(
        SPEC=own,
        PRACTICE_PROVENANCE=PRACTICE_PROVENANCE,
        FEEDBACK_MODES=shared.FEEDBACK_MODES,
        BACKENDS=BACKENDS,
        key_for=functools.partial(spec.key_for, own),
        keyed=functools.partial(spec.keyed, own),
        research_key=functools.partial(spec.research_key, own),
        manifest_document=functools.partial(shared.manifest_document, own),
        check_attached=functools.partial(shared.check_attached, own),
        compose=functools.partial(shared.compose, own),
        prepare_registered=functools.partial(shared.prepare, own),
        evaluate_frozen=evaluate_frozen,
        record_verdict=shared.record_verdict,
        agent_observation=functools.partial(shared.agent_observation, own),
        research_view=functools.partial(research_view.research_view, own),
    )
