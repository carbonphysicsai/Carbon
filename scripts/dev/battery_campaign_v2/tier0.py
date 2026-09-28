"""Battery agent campaign v2, tier 0: can the public material alone produce
an admissible design? (docs/development/BATTERY_AGENT_CAMPAIGN_PREREGISTRATION_V2.md §4)

A model is given exactly the battery public material an agent receives: the
five `public_material` replies, produced by `BatteryPublicMaterial` itself, and
the challenge discovery document. It gets no tool description, no Carbon-insider
text and no hint. It is asked for one design, which the real `check_design`
scores. The rubric is fixed in §4 and applied mechanically here:

    PASS     parses, and check_design's rebuild is accepted
    PARTIAL  parses, at least one choice is "supported", rebuild not accepted
    FAIL     does not parse, check_design rejects it as malformed, or no
             choice is supported

Parsing rule, fixed before any run: the first JSON object in the reply is
taken. If it is a bare strategy ({schema_version, challenge_id, backbone,
parameters}), it is wrapped as {"strategy": ...}. That changes representation
only; nothing is added to the model's input.

The discovery document contains two complete, admission-valid example designs.
A PASS can therefore come from copying one, so each record also notes whether
its strategy exactly matches a provided example. That is a measurement beside
the rubric, not a change to it.

Every call is metered from the provider's own `x_engy.charged_micro`, with its
reasoning and cached tokens and the provenance fields. A hard cap on the
cumulative charge stops the run. Results go to an owner-only directory outside
the repository, because charges are account figures.

    python scripts/dev/battery_campaign_v2/tier0.py --credential KEY_FILE \
        --out DIR [--models m1,m2,m3] [--samples 3] [--max-charged-micro 100000]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import urllib.request
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))

FRAMINGS = {
    "F1": (
        "Here is a challenge's public material. Propose one design for it, as "
        "JSON in the design schema the material describes."
    ),
    "F2": (
        "You are a miner entering this challenge. Using only this material, give "
        "the design you would submit first, as JSON in the material's design "
        "schema."
    ),
    "F3": "Design a construction for this challenge. Output only the JSON design.",
}
#: Engy's Chat Completions endpoint. Measured 2026-09-27: its Anthropic-compatible
#: Messages endpoint returns no x_engy block (no charged_micro, no provenance),
#: and the order requires settling from the provider's own charge.
PROVIDER = "engy-chat"
DEFAULT_MODELS = ("deepseek-v4-flash-0731", "qwen3.8-27b", "glm-5.3-flash")
MODELS_URL = "https://api.engy.ai/v1/models"


class _NoWorkspace:
    """Accepts the files a public_material call would store; keeps nothing."""

    def put(self, name, body):
        return None


def public_material():
    """Exactly what the agent receives: the five public_material replies and
    the discovery document from its initial observation."""
    from carbon.battery.challenge import CHALLENGE
    from carbon.battery.research import BatteryPublicMaterial
    from carbon.challenge_registry import describe

    material = BatteryPublicMaterial(REPOSITORY)
    replies = {name: material(name, _NoWorkspace()) for name in material.NAMES}
    discovery = describe(CHALLENGE.challenge_id, CHALLENGE.version)
    return {"public_material": replies, "challenge_discovery": discovery}


def live_models():
    """The provider's public model list (no key)."""
    with urllib.request.urlopen(MODELS_URL, timeout=30) as response:
        body = json.loads(response.read())
    return {m.get("id") for m in body.get("data", []) if isinstance(m, dict)}


def first_json_object(text):
    """The first balanced JSON object in text, or None."""
    for fenced in re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL):
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    while start != -1:
        depth, in_string, escape = 0, False, False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : index + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


def as_design(value):
    """The fixed representational rule: wrap a bare strategy object."""
    if type(value) is not dict:
        return None
    if "strategy" in value:
        return value
    if {"backbone", "parameters"} <= set(value):
        return {"strategy": value}
    return None


def score(design):
    """The §4 rubric, applied to the real check_design."""
    from carbon.development_session.design_check import check_design

    if design is None:
        return "FAIL", {"reason": "no design parsed"}
    try:
        verdict = check_design(design)
    except (ValueError, TypeError) as refused:
        return "FAIL", {"reason": "malformed", "detail": str(refused)}
    choices = [verdict.get("backbone", {}).get("verdict")]
    choices += [f.get("verdict") for f in verdict.get("fields", [])]
    choices += [r.get("verdict") for r in verdict.get("requested", [])]
    if verdict.get("rebuild", {}).get("accepted"):
        return "PASS", verdict
    if "supported" in choices:
        return "PARTIAL", verdict
    return "FAIL", verdict


def matches_example(design, material):
    """Whether the design's strategy equals one of the discovery examples."""
    if not isinstance(design, dict):
        return False
    examples = material["challenge_discovery"].get("examples", [])
    return any(design.get("strategy") == e.get("strategy") for e in examples)


def material_gaps(verdict, material_text):
    """For each choice not supported: check_design's reason, and whether the
    public material mentions the choice's name at all."""
    gaps = []
    for field in verdict.get("fields", []):
        if field.get("verdict") != "supported":
            name = field.get("field")
            gaps.append(
                {
                    "position": field.get("position"),
                    "verdict": field.get("verdict"),
                    "reason": field.get("reason"),
                    "named_in_material": bool(name) and name in material_text,
                }
            )
    return gaps


def ask(model, framing, material_json, credential, max_output_tokens=4096):
    from carbon.development_session.model_provider import SelectionTransport, select

    selection = select(
        provider_id=PROVIDER,
        model_id=model,
        credential={"kind": "file", "reference": str(credential)},
    )
    return SelectionTransport(selection)(
        request_for(model, framing, material_json, max_output_tokens)
    )


def request_for(model, framing, material_json, max_output_tokens=4096):
    """The framing is the only instruction; the material is the user turn.
    No tools, so the model sees nothing but framing and material."""
    return {
        "model": model,
        "instructions": FRAMINGS[framing],
        "input": [{"role": "user", "content": material_json}],
        "tools": [],
        "parallel_tool_calls": False,
        "max_output_tokens": max_output_tokens,
    }


def reply_text(response):
    parts = []
    for item in response.get("output", []):
        for block in item.get("content", []) or []:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
    return "\n".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--credential", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--max-charged-micro", type=int, default=100000)
    # Run A used 4096. Reasoning models spent it all on reasoning and never
    # answered, so run B allows more. The rubric is unchanged.
    parser.add_argument("--max-output-tokens", type=int, default=4096)
    args = parser.parse_args(argv)
    os.umask(0o077)  # records carry account charges: owner-only files
    if args.out.exists():
        raise SystemExit(f"{args.out} exists; refusing to overwrite a run")
    os.makedirs(args.out, mode=0o700)

    material = public_material()
    material_json = json.dumps(material, sort_keys=True, default=str)
    (args.out / "material.json").write_text(material_json)
    available = live_models()
    models = [m for m in args.models.split(",") if m]
    skipped = [m for m in models if m not in available]
    conditions = [
        (m, f, s)
        for m in models
        if m in available
        for f in FRAMINGS
        for s in range(args.samples)
    ]
    random.SystemRandom().shuffle(conditions)
    spent = 0
    log = (args.out / "records.jsonl").open("x")
    for model, framing, sample in conditions:
        if spent >= args.max_charged_micro:
            print(json.dumps({"stopped": "charge cap reached", "spent_micro": spent}))
            break
        record = {"model": model, "framing": framing, "sample": sample}
        try:
            response = ask(
                model, framing, material_json, args.credential, args.max_output_tokens
            )
        except Exception as failed:  # noqa: BLE001 - recorded, typed by name
            record.update(
                outcome="PROVIDER_FAILURE",
                error=type(failed).__name__,
                message=str(failed)[:300],
            )
            log.write(json.dumps(record) + "\n")
            log.flush()
            continue
        x_engy = response.get("x_engy") or {}
        usage = response.get("usage") or {}
        charged = x_engy.get("charged_micro")
        if charged is None:
            # Fail closed: never estimate a charge or treat a missing one as 0.
            record.update(outcome="NO_CHARGE_REPORT")
            log.write(json.dumps(record) + "\n")
            log.flush()
            print(json.dumps({"stopped": "provider returned no charged_micro"}))
            break
        spent += charged
        text = reply_text(response)
        design = as_design(first_json_object(text))
        outcome, verdict = score(design)
        record.update(
            outcome=outcome,
            matches_example=matches_example(design, material),
            design=design,
            verdict=verdict,
            material_gaps=(
                material_gaps(verdict, material_json)
                if isinstance(verdict, dict) and "fields" in verdict
                else []
            ),
            reply_sha256=hashlib.sha256(text.encode()).hexdigest(),
            reply_text=text,
            charged_micro=charged,
            usage={
                k: usage.get(k)
                for k in (
                    "input_tokens",
                    "output_tokens",
                    "output_tokens_details",
                    "input_tokens_details",
                )
            },
            provenance={k: x_engy.get(k) for k in ("request_id", "miner", "worker")},
        )
        log.write(json.dumps(record, default=str) + "\n")
        log.flush()
    log.close()
    summary = {"models_skipped_not_listed": skipped, "spent_micro": spent}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
