"""No-call model evidence from metadata-only, grant-bound session openings.

The provider freezes its actual selection. No controller, worker, transport
request, miner tool or pod is run. This is configuration evidence only.
"""

from __future__ import annotations

from carbon.agent_campaign.provider import TaskSpec
from carbon.development_session.model_provider import selection_from_record

from . import grant_binding, model_providers
from .ladder import Ladder
from .model import ScriptedModel
from .provider import GraphiteProvider, SessionBrief
from .roles import ROLES, RoleName


def produce(root, *, challenge, level, grants, commit):
    """One frozen *_model block for every explicitly declared run role."""
    from carbon.challenge_pipeline.readiness.model import digest

    report = {"challenge": challenge, "level": level, "worker_ran": False}
    for name, grant in grants.items():
        role = RoleName(name)
        chosen = model_providers.resolve(grant_binding.model_provider_of(grant))
        provider = GraphiteProvider(
            root=(root / name).resolve(),
            grant=grant,
            model=ScriptedModel([], model_provider=chosen.name),
            model_provider=chosen.name,
            adapter_id=("engy-chat" if chosen.is_default else chosen.default_adapter),
        )
        provider.ladder = Ladder(
            provider.root / chosen.ladder_directory,
            models=chosen.ladder,
            start_rungs=grant_binding.start_rungs(grant),
        )
        brief = SessionBrief(
            role=role,
            initial_observation={"purpose": "readiness-model-metadata-only"},
            checkout_commit=commit,
            checkout_manifest_digest=digest({"challenge": challenge, "level": level}),
            level4_stage=(level == 4 and role == RoleName.CONSTRUCTOR),
        )
        task = TaskSpec(
            campaign_id="readiness-model-metadata",
            role=ROLES[role].boundary.value,
            workspace_id="readiness-model-metadata",
            credential_ref="no-credential",
            profile_digest=brief.checkout_manifest_digest,
            instructions_digest=provider.register_brief(brief),
            max_runtime_s=grant.max_runtime_s,
        )
        run_id = provider.start(task, "metadata-only").provider_run_id
        frozen = provider._opened(run_id)["model"]
        selection = selection_from_record(
            frozen,
            credential_file=provider.model.credential_reference,
            adapters=chosen.registry,
        )
        maximum = selection.adapter.output_maxima.get(selection.model_id)
        maximum = maximum or selection.adapter.output_maximum
        report[name + "_model"] = {
            "provider_id": selection.provider_id,
            "provider": chosen.name,
            "model": selection.model_id,
            "selection_digest": digest(frozen),
            "max_input_tokens": selection.settings.max_input_tokens,
            "max_output_tokens": selection.settings.max_output_tokens,
            "recorded_context_tokens": chosen.context_tokens.get(selection.model_id),
            "recorded_output_maximum": None if maximum is None else maximum.record(),
            "charge_reporting": bool(selection.adapter.reported_charge),
        }
    return report
