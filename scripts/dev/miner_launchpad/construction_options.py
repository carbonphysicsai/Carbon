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
    registrations = {row["type"]: row for row in contract.document["types"]}
    serving = any(
        type(facts) is dict
        and facts.get("unified_digest") == public["unified_digest"]
        and facts.get("types") == public["types"]
        and facts.get("ceiling") == public["ceiling"]
        for facts in served
    )
    rows = [
        {
            "type": "parameters",
            "label": "Adjust existing model settings",
            "derived_label": 0,
            "availability": "available",
            "status": "Available",
            "reason": "Uses the Challenge's existing registered submission path.",
        }
    ]
    for change in public["types"]:
        within = (
            public["ceiling"] is not None
            and change["within_ceiling"]
            and change["label"] <= public["ceiling"]
        )
        checks_ready = all(check.get("status") == "PASS" for check in change["checks"])
        arm_open = any(
            arm["external_allowed"] for arm in registrations[change["type"]]["arms"]
        )
        available = (
            within
            and change["open"] == "EXTERNAL"
            and arm_open
            and checks_ready
            and serving
        )
        if not within:
            reason = (
                "The owner has not approved a construction ceiling yet."
                if public["ceiling"] is None
                else "This change is above the owner's approved ceiling."
            )
        elif change["open"] != "EXTERNAL" or not arm_open:
            reason = "This change is not open to external miners yet."
        elif not checks_ready:
            reason = "Its registered checks are not ready."
        elif not serving:
            reason = "No configured validator reports this unified submission path."
        else:
            reason = "The registered contract permits this change and a validator reports serving it."
        rows.append(
            {
                "type": change["type"],
                "label": LABELS.get(change["type"], change["type"].replace("_", " ")),
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
        "launch_mode": "level_bound_until_composed_compile",
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
