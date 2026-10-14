"""One plain public options projection for the page and its agent tools."""

from __future__ import annotations

LABELS = {
    "loss_expressions": "Change the loss function",
    "optimizer_and_data": "Change the optimizer or training data",
    "numerics": "Change the optimization method",
    "graph": "Change the model structure",
}


def build(contract, served=()):
    """Read registered policy and receiver-checked serving facts; grant no admission."""
    from carbon.development_session.unified_construction import UnifiedContract

    if type(contract) is not UnifiedContract:
        raise ValueError("a validated public construction contract is required")
    public = contract.facts()
    from carbon.reconstruction.capability_registry import (
        development_composition_document,
        development_composition_registry,
    )

    registry = development_composition_registry()
    name = registry["current"].get(contract.document["challenge"])
    composition = development_composition_document(name) if name is not None else None
    composed_digest = registry["versions"][name] if composition is not None else None
    if composition is not None:
        serving = any(
            type(facts) is dict
            and type(facts.get("served_contracts")) is list
            and any(
                type(entry) is dict
                and entry.get("digest") == composed_digest
                and entry.get("variant") == name
                for entry in facts["served_contracts"]
            )
            for facts in served
        )
    else:
        serving = any(
            type(facts) is dict
            and facts.get("unified_digest") == public["unified_digest"]
            and facts.get("types") == public["types"]
            for facts in served
        )
    pins = (
        {part["digest"] for part in composition["composes"]}
        if composition is not None
        else set()
    )
    registrations = {row["type"]: row for row in contract.document["types"]}
    rows = [
        {
            "type": "parameters",
            "label": "Adjust existing model settings",
            "derived_label": 0,
            "availability": (
                "available" if composition is None or serving else "coming_soon"
            ),
            "status": "Available" if composition is None or serving else "Coming soon",
            "reason": (
                "Uses the registered construction contract; its receiving validator must explicitly serve that identity."
                if composition is not None
                else "Uses the Challenge's existing registered submission path."
            ),
        }
    ]
    for change in public["types"]:
        pending = [
            check["id"] for check in change["checks"] if check["status"] != "PASS"
        ]
        registered = composition is not None and any(
            arm["digest"] in pins for arm in registrations[change["type"]]["arms"]
        )
        available = (
            serving
            and not pending
            and (registered if composition is not None else True)
        )
        label = LABELS.get(change["type"], change["type"].replace("_", " "))
        if composition is not None and not registered:
            reason = (
                f"{label}: this change is not part of the registered combined contract."
            )
        elif pending:
            reason = f"{label}: required checks are not ready: {', '.join(pending)}."
        elif not serving:
            reason = f"{label}: no configured validator reports this registered submission path."
        else:
            reason = "The registered construction path is served. Each recipe still has to pass its reconstruction, bounds and cost checks."
        rows.append(
            {
                "type": change["type"],
                "label": label,
                "derived_label": change["label"],
                "within_ceiling": change["within_ceiling"],
                "open": change["open"],
                "checks": change["checks"],
                "registration_digest": change["registration_digest"],
                "availability": "available" if available else "coming_soon",
                "status": "Available" if available else "Coming soon",
                "reason": reason,
            }
        )
    return {
        "schema": "carbon.launchpad.construction-options.v1",
        "challenge": contract.document["challenge"],
        "unified_digest": contract.digest,
        "scope": public["scope"],
        "ceiling": public["ceiling"],
        "types": rows,
        "launch_mode": (
            "composition_bound"
            if composition is not None
            else "level_bound_until_composed_compile"
        ),
        "construction_digest": composed_digest,
        "submission_path_available": serving,
        "qualification": False,
        "basis": "REGISTERED_PUBLIC_CONTRACT_AND_RECEIVER_CHECKED_SERVING_FACTS",
    }


def for_profile(cfg, read=None):
    """Registry-owned public providers; no door names a Challenge implementation."""
    from carbon.challenge_registry.campaigns import implemented_campaigns
    from carbon.development_session.intake_targets import for_challenge
    from scripts.dev.miner_launchpad.runner import intakes, receivers

    found = {}
    for entry, composition in implemented_campaigns():
        if composition.construction_contract is None:
            continue
        try:
            registered = composition.construction_contract()
            if registered.document["challenge"] != entry.challenge_id:
                raise ValueError("registered construction provider differs")
        except (OSError, ValueError, KeyError, TypeError):
            found[entry.challenge_id] = {
                "schema": "carbon.launchpad.construction-options.v1",
                "status": "PUBLIC_CONTRACT_UNAVAILABLE",
                "ceiling": None,
                "types": [],
                "submission_path_available": False,
                "qualification": False,
            }
            continue
        served = []
        callback = read or composition.intake_check
        paired = for_challenge(cfg, entry.challenge_id)
        if paired is None:
            url, pin = intakes(cfg).get(entry.challenge_id), receivers(cfg).get(
                entry.challenge_id
            )
            paired = (
                [{"intake_url": url, "receiver_hotkey": pin}] if url and pin else []
            )
        for target in paired:
            try:
                facts = callback(target["intake_url"]) if callback is not None else None
                if (
                    type(facts) is not dict
                    or facts.get("receiver") != target["receiver_hotkey"]
                ):
                    raise ValueError("unbound serving facts")
                served.append(facts)
            except Exception:  # noqa: BLE001
                # Unread/unbound facts grant no serving permission.
                served.append(None)
        found[entry.challenge_id] = build(registered, served)
    return found
