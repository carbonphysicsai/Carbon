"""Read-only PUBLIC DEVELOPMENT prerequisites, never dispatch authorization.

Only explicit main-tree metadata is inspected. No host/store enumeration,
solver, imports of producer code, hidden inventory, network or mutation.
"""

import ast
import hashlib
import json
import math
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from carbon.challenge_pipeline.onboarding import packet

BINDINGS = "docs/development/challenge_pipeline/evidence-readiness/bindings.json"
LABELS = (
    "Registered, deduplicated, reuse-checked panel on main",
    "Pinned package and current operator-store image observation",
    "Convergence, conservation AND code verification for current image/family",
    "Kit covers every panel action, condition and observable",
    "Registered TRAIN physically disjoint from panel",
    "Strong cheap-baseline implementation ready",
    "Challenge-supported equal-budget implementation ready",
)
OWNERS = (
    "Data Collection / owner registration",
    "Data Collection / operator",
    "Data Collection / science acceptance",
    "Model Kits / Data Collection",
    "Data Collection",
    "Packets Codex / Data Collection materials",
    "Optimizer Codex",
)


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def identity(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def public_path(value):
    if (
        type(value) is not str
        or not re.fullmatch(r"[A-Za-z0-9_./-]{1,240}", value)
        or any(p in ("", ".", "..") for p in value.split("/"))
        or not value.startswith(
            ("docs/development/", ".agent/decisions/", "carbon/", "tests/cpu/")
        )
        or re.search(
            r"hidden|protected|private|secret|(?:^|/)(?:eval|stress|banks)(?:/|\.)",
            value.lower(),
        )
        or value.startswith("carbon/")
        and not value.endswith(".py")
    ):
        raise packet.DraftError("explicit public metadata path required")
    return value


class MainTree:
    def __init__(self, root, ref):
        if not re.fullmatch(r"[A-Za-z0-9_./-]{1,160}", ref) or ref.startswith("-"):
            raise packet.DraftError("local main ref required")
        self.root = Path(root)
        self.commit = (
            self._git("rev-parse", "--verify", ref + "^{commit}")
            if ref
            in {"main", "origin/main", "refs/heads/main", "refs/remotes/origin/main"}
            else None
        )
        self.commit = self.commit.decode().strip() if self.commit else None
        self.examined = {}

    def _git(self, *args):
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.root,
                capture_output=True,
                timeout=10,
                check=False,
            )
            return result.stdout if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    def read(self, path):
        public_path(path)
        raw = self._git("show", f"{self.commit}:{path}") if self.commit else None
        if raw is None or len(raw) > packet.LIMIT:
            return None
        self.examined[path] = sha(raw)
        return raw

    def json(self, path):
        raw = self.read(path)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise packet.DraftError("invalid public metadata") from None

    def source(self, binding):
        if type(binding) is not dict or set(binding) != {"path", "sha256"}:
            raise packet.DraftError("source identity required")
        raw = self.read(binding["path"])
        return raw is not None and sha(raw) == binding["sha256"]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def case_keys(cases):
    if type(cases) is not list or not cases or len(cases) > 10000:
        raise packet.DraftError("nonempty bounded physical inventory required")
    for case in cases:
        if type(case) is not dict or set(case) != {"action", "condition", "rung"}:
            raise packet.DraftError("exact physical tuples required")
        for values in case.values():
            if type(values) is not dict or not values:
                raise packet.DraftError("explicit physical coordinates required")
            for key, value in values.items():
                if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]{0,79}", key) or not (
                    finite(value) or type(value) is str and 0 < len(value) <= 100
                ):
                    raise packet.DraftError("finite public coordinates required")
    return [identity(case) for case in cases]


def check_panel(tree, data, image=None):
    keys = case_keys(data["cases"])
    reuse = data["reuse"]
    pins = data["pins"]
    if image is not None and pins.get("solver") != image:
        return False, "Panel solver pin differs from selected current image"
    if set(pins) != {
        "solver",
        "environment",
        "materials",
        "observer",
        "geometry_grammar",
    } or not all(re.fullmatch(r"sha256:[0-9a-f]{64}", v) for v in pins.values()):
        return None, "Complete immutable physical/observer pins required"
    registered = tree.json(data["registration"]["path"])
    if (
        not tree.source(data["registration"])
        or registered.get("scope") != "PUBLIC_DEVELOPMENT"
        or registered.get("panel_digest")
        != identity({"cases": data["cases"], "pins": pins})
        or len(keys) != len(set(keys))
        or set(reuse["inventory_coverage"]) != {"COMPLETED", "SCHEDULED"}
        or not tree.source(reuse["source"])
    ):
        return False, "Registration, deduplication or complete reuse coverage failed"
    # Recompute reuse, rather than trusting producer 'deduplicated' booleans.
    known = tree.json(reuse["source"]["path"])
    if type(known) is not list:
        raise packet.DraftError("public completed/scheduled identity index required")
    index = {}
    for row in known:
        if (
            set(row) != {"identity", "state", "receipt"}
            or row["state"] not in {"COMPLETED", "SCHEDULED"}
            or row["identity"] in index
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", row["identity"])
            or not tree.source(row["receipt"])
        ):
            raise packet.DraftError("retained reuse evidence required")
        index[row["identity"]] = row["state"]
    matches = sum(
        identity({"case": case, "pins": pins}) in index for case in data["cases"]
    )
    return (
        True,
        f"{len(keys)} unique tuples; {len(index)} reuse identities; {matches} matches",
    )


def check_image(tree, data, now):
    package = data["package"]
    image = data["image_digest"]
    inventory = data["inventory"]
    if not tree.source(package) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        return False, "Package identity or immutable image pin does not match"
    manifest = tree.json(package["path"])
    current_image = manifest.get("repin_2026_10_10", {}).get(
        "image_id", manifest.get("image_id")
    )
    if current_image != image:
        return False, "Selected image is not the package's current pin"
    if not tree.source(inventory):
        return None, "No matching public operator inventory observation on main"
    observation = tree.json(inventory["path"])
    if (
        observation["scope"] != "PUBLIC_DEVELOPMENT"
        or observation["package_sha256"] != package["sha256"]
        or observation["image_digest"] != image
        or not observation["store_id"]
    ):
        return False, "Operator observation does not bind current package and image"
    checked = datetime.fromisoformat(observation["checked_at"])
    if checked.tzinfo is None or not 0 <= (now - checked).total_seconds() <= 86400:
        return (
            None,
            "Store observation is future/undated/older than 24 h; recheck before dispatch",
        )
    present = observation["present"]
    if type(present) is not bool:
        raise packet.DraftError("explicit image-presence observation required")
    return present, "Current-image observation at " + checked.isoformat()


def check_reference(tree, data, image, family):
    kinds = {"convergence", "conservation", "code_verification"}
    rows = data["checks"]
    if type(rows) is not list or len(rows) != 3 or {r["kind"] for r in rows} != kinds:
        return (
            None,
            "Need separate convergence, conservation and code-verification evidence",
        )
    n = 0
    for row in rows:
        if row["image_digest"] != image or row["family"] != family:
            return False, "Reference finding: stale image or inapplicable case family"
        if not tree.source(row["result"]) or not tree.source(row["acceptance"]):
            return (
                None,
                "Missing identity-bound result or science's acceptance criteria",
            )
        criteria = tree.json(row["acceptance"]["path"])
        measurements = tree.json(row["result"]["path"])
        if (
            criteria.get("status") != "ACCEPTED_DEVELOPMENT"
            or criteria.get("kind") != row["kind"]
            or criteria.get("family") != family
            or measurements.get("image_digest") != image
            or measurements.get("family") != family
            or measurements.get("kind") != row["kind"]
        ):
            return None, "Acceptance pending or result applicability unverified"
        limits = criteria["metrics"]
        values = measurements["metrics"]
        if not limits or set(limits) != set(values):
            return None, "Empty/incomplete measurement basis"
        for key, bounds in limits.items():
            if (
                len(bounds) != 2
                or not all(finite(x) for x in (*bounds, values[key]))
                or bounds[0] > bounds[1]
            ):
                raise packet.DraftError("finite adopted acceptance bands required")
            n += 1
            if not bounds[0] <= values[key] <= bounds[1]:
                return (
                    False,
                    "Reference finding: measured verification outside adopted band",
                )
    return (
        True,
        f"3 applicable checks; {n} measured criteria compared; not Tier-2 qualification",
    )


def check_kit(tree, data, cases):
    if not tree.source(data["source"]) or not tree.source(data["domain_source"]):
        return None, "Kit/domain source not available at main identity"
    domain = tree.json(data["domain_source"]["path"])
    # This is the kit's exported domain contract, not observed panel extrema.
    if domain["kit_sha256"] != data["source"]["sha256"]:
        return False, "Domain contract belongs to another kit revision"
    if not data["required_observables"] or not set(data["required_observables"]) <= set(
        domain["observables"]
    ):
        return False, "Required panel observables are not covered by kit"
    for case in cases:
        if case["condition"] not in domain["conditions"]:
            return False, "Panel condition outside registered kit contexts"
        if set(case["action"]) != set(domain["action_bounds"]):
            return False, "Panel action grammar differs from kit"
        for key, value in case["action"].items():
            bounds = domain["action_bounds"][key]
            if len(bounds) != 2 or not all(finite(x) for x in (*bounds, value)):
                raise packet.DraftError("numeric kit action domain required")
            if not bounds[0] <= value <= bounds[1]:
                return False, "Panel action outside kit domain"
            allowed = domain.get("action_values", {}).get(key)
            if allowed is not None and value not in allowed:
                return False, "Panel action violates kit's discrete action grammar"
    return (
        True,
        f"{len(cases)} actions/conditions checked; all required observables covered",
    )


def check_train(tree, data, cases):
    if not tree.source(data["registration"]) or not tree.source(data["inventory"]):
        return None, "Registered public TRAIN inventory not available on main"
    train = tree.json(data["inventory"]["path"])
    registration = tree.json(data["registration"]["path"])
    if train.get("scope") != "PUBLIC_DEVELOPMENT" or registration.get(
        "train_digest"
    ) != identity(train):
        return None, "TRAIN registration does not bind the actual inventory"
    keys = case_keys(train["cases"])
    # Different seeds, names or rungs do not prove action/condition separation.
    physical = lambda c: identity({"action": c["action"], "condition": c["condition"]})
    overlap = {physical(c) for c in cases} & {physical(c) for c in train["cases"]}
    return not overlap and len(keys) == len(set(keys)), (
        f"{len(keys)} TRAIN tuples compared; {len(overlap)} action/condition overlaps"
    )


def code_route(tree, family, optimizer=False):
    if tree.commit is None:
        return "UNKNOWN", "Main unavailable; no implementation inspected", []
    if optimizer:
        path = "carbon/development_comparison/evidence_pipeline.py"
        functions = {"run", "_baseline"}
        accepted = {"battery-v3", "motor", "f02"}
    elif family in {"battery-v3", "motor"}:
        path = "carbon/development_comparison/cheap_baselines.py"
        functions = {
            "measure",
            "decision_report",
            family.replace("-v3", "") + "_predictions",
        }
        accepted = {"battery-v3", "motor"}
    elif family in {"cooling-cell", "f02"}:
        path = "carbon/development_comparison/portfolio_baselines.py"
        functions = {"measure", "validate_materials", "screening_export"}
        accepted = {"cooling-cell", "f02"}
    elif family in {"f08", "f13"}:
        path = "carbon/development_comparison/reduced_baselines.py"
        functions = {
            "measure",
            "validate_operators",
            "structural_curve",
            "acoustic_curve",
        }
        accepted = {"f08", "f13"}
    else:
        return (
            "NO",
            "No implemented family adapter in this tool's closed route inventory",
            [],
        )
    raw = tree.read(path)
    if raw is None:
        return "UNKNOWN", "Cannot inspect route implementation at main", [path]
    parsed = ast.parse(raw)
    declared = {n.name for n in parsed.body if isinstance(n, ast.FunctionDef)}
    literals = {
        n.value
        for n in ast.walk(parsed)
        if isinstance(n, ast.Constant) and type(n.value) is str
    }
    if family not in accepted or not functions <= declared or family not in literals:
        return (
            "NO",
            "Required family/functions not present in route implementation",
            [path],
        )
    return (
        "YES",
        "Implemented offline route; producer materials/coverage and empirical value not implied",
        [path],
    )


def generate(root, challenge, *, main_ref="origin/main", now=None):
    if type(challenge) is not str or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{0,79}", challenge
    ):
        raise packet.DraftError("bounded challenge key required")
    tree = MainTree(root, main_ref)
    # Bindings are pointers/plans in this ticket, not evidence or status overrides.
    registry = packet.read_json(packet.source_path(root, BINDINGS))
    binding = next(
        (
            b
            for b in registry["challenges"]
            if challenge in (b["challenge"], *b["aliases"])
        ),
        None,
    )
    if binding is None:
        return {
            "schema": "carbon.onboarding.evidence-readiness.v1",
            "challenge": challenge,
            "main": tree.commit,
            "observed_at": (now or datetime.now(UTC)).isoformat(),
            "items": [
                {
                    "item": i + 1,
                    "label": label,
                    "state": "UNKNOWN",
                    "basis": "No configured public evidence adapter; cannot infer absent work",
                    "owner": OWNERS[i],
                    "pointers": [BINDINGS],
                }
                for i, label in enumerate(LABELS)
            ],
            "yes_count": 0,
            "all_prerequisites_yes": False,
            "spend_authorized": False,
            "qualified": False,
            "paid_run_output_exception": "Exact owner/operator authorization required",
            "examined_sources": {},
        }
    family = binding["challenge"]
    now = now or datetime.now(UTC)
    data = tree.json(binding["inputs"])
    if data is not None and (
        data.get("schema") != "carbon.onboarding.evidence-inputs.v1"
        or data.get("scope") != "PUBLIC_DEVELOPMENT"
        or data.get("challenge") != family
    ):
        raise packet.DraftError("matching public DEVELOPMENT inputs required")
    proposal = tree.read(binding["proposal"])
    rows = []
    checks = (
        lambda: check_panel(tree, data["panel"], data["solver"]["image_digest"]),
        lambda: check_image(tree, data["solver"], now),
        lambda: check_reference(
            tree, data["reference"], data["solver"]["image_digest"], family
        ),
        lambda: check_kit(tree, data["kit"], data["panel"]["cases"]),
        lambda: check_train(tree, data["train"], data["panel"]["cases"]),
    )
    for i, check in enumerate(checks):
        state = "PLANNED" if proposal is not None or binding["pending"] else "UNKNOWN"
        reason = "Proposal/pending work exists; required structured main evidence not yet inspectable"
        if tree.commit is None:
            state, reason = (
                "UNKNOWN",
                "Main unavailable; cannot conclude evidence is absent",
            )
        elif data is not None:
            try:
                result, reason = check()
                state = "UNKNOWN" if result is None else "YES" if result else "NO"
            except (KeyError, TypeError, ValueError, packet.DraftError):
                state, reason = (
                    "UNKNOWN",
                    "Missing, malformed or unbound public evidence; no success inferred",
                )
        rows.append(
            {
                "item": i + 1,
                "label": LABELS[i],
                "state": state,
                "basis": reason,
                "owner": OWNERS[i],
                "pointers": [binding["inputs"], binding["proposal"]]
                + ([binding["pending"]] if binding["pending"] else []),
            }
        )
    for i in (5, 6):
        state, reason, pointers = code_route(tree, family, optimizer=i == 6)
        rows.append(
            {
                "item": i + 1,
                "label": LABELS[i],
                "state": state,
                "basis": reason,
                "owner": OWNERS[i],
                "pointers": pointers,
            }
        )
    return {
        "schema": "carbon.onboarding.evidence-readiness.v1",
        "challenge": family,
        "main": tree.commit,
        "observed_at": now.isoformat(),
        "items": rows,
        "yes_count": sum(r["state"] == "YES" for r in rows),
        "all_prerequisites_yes": all(r["state"] == "YES" for r in rows),
        "spend_authorized": False,
        "qualified": False,
        "paid_run_output_exception": "Only exact owner/operator authorization may identify data produced by that run; no automatic waiver",
        "examined_sources": tree.examined,
    }


def portfolio(root, **kwargs):
    registry = packet.read_json(packet.source_path(root, BINDINGS))
    reports = [generate(root, b["challenge"], **kwargs) for b in registry["challenges"]]
    reports.sort(key=lambda r: (-r["yes_count"], r["challenge"]))
    for report in reports:
        report["rank"] = 1 + sum(r["yes_count"] > report["yes_count"] for r in reports)
    return reports


def render(report):
    lines = [
        f"Evidence readiness: {report['challenge']} — {report['yes_count']}/7 YES",
        f"Main: {report['main'] or 'UNKNOWN'}; observation: {report['observed_at']}",
    ]
    for row in report["items"]:
        lines.extend(
            [
                f"{row['item']}. {row['state']}: {row['label']}",
                f"   {row['basis']} | Owner: {row['owner']}",
                "   " + "; ".join(row["pointers"]),
            ]
        )
    lines.append(
        "HOLD: this observation is not a spend grant, scientific qualification or launch permission."
    )
    return "\n".join(lines)
