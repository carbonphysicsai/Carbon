"""Bounded private task input, never policy or execution authority."""

import json

from .profile import canonical, digest

MAX_BYTES = 4096
SCHEMA = "carbon.autoresearch.guidance.v1"


def bind(text):
    if (
        type(text) is not str
        or not text.strip()
        or any(ord(c) < 32 and c not in "\t\r\n" for c in text)
    ):
        raise ValueError("bounded research guidance text required")
    try:
        raw = text.encode("utf-8")
    except UnicodeError:
        raise ValueError("UTF-8 research guidance required") from None
    if len(raw) > MAX_BYTES:
        raise ValueError("research guidance exceeds byte limit")
    return {"schema": SCHEMA, "text": text, "digest": digest(raw)}


def verify(value):
    if value is None:
        return None
    if type(value) is not dict or value != bind(value.get("text")):
        raise ValueError("research guidance binding differs")
    return value


def configured(profile):
    return (
        bind(profile["research_guidance"]) if "research_guidance" in profile else None
    )


def effective_digest(policy, observation):
    """The policy template stays pinned separately from user-role task input."""
    verify(observation["research_guidance"])
    return digest(canonical({"policy": policy, "initial_observation": observation}))


def context(manifest):
    return {
        "campaign_id": manifest["campaign_id"],
        "implementation": manifest["implementation"],
    }


def verify_history(root, task, policy, expected_context):
    """Verify existing private epoch plans without replaying any operation."""
    identities = []
    for epoch in (1, 2):
        path = root / f"epoch-{epoch}" / "plan.json"
        if not path.exists():
            continue
        if path.is_symlink() or path.stat().st_size > 4 * 1024**2:
            raise ValueError("bounded research input required")
        plan = json.loads(path.read_bytes())
        observation = plan["initial_observation"]
        if (
            verify(observation.get("research_guidance")) != task
            or observation.get("research_context") != expected_context
            or plan.get("agent_policy", policy) != policy
            or digest(plan["prompt"].encode("utf-8")) != policy["prompt_digest"]
            or plan.get("effective_input_digest")
            != effective_digest(policy, observation)
        ):
            raise ValueError("frozen effective research input differs")
        identities.append({"epoch": epoch, "digest": plan["effective_input_digest"]})
    return identities
