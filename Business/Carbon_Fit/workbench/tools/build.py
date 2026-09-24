"""Build one offline HTML artifact from the canonical source JSON and JS/CSS."""

import base64
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(s):
    return "sha256-" + base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()


def data(p):
    return (
        json.dumps(json.loads(p.read_text()), ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


INTAKE_PUBLIC_KEY_SCHEMA = "carbon.intake-key.v1-public"
INTAKE_PUBLIC_KEY_FIELDS = {"schema", "key_id", "public_spki", "fingerprint"}
# DER prefix of a P-256 SubjectPublicKeyInfo holding an uncompressed point.
P256_SPKI_PREFIX = bytes.fromhex("3059301306072a8648ce3d020106082a8648ce3d030107034200")


def intake_public_key(path):
    """The intake key record the Pilot Designer embeds, or a refusal naming why.

    The page checks the record again before it seals anything. This check is
    here so that a private key file, or a record whose label belongs to another
    key, is never written into a page in the first place.
    """
    record = json.loads(path.read_text())
    if not isinstance(record, dict):
        raise TypeError("The intake key record is not an object")
    if "private_pkcs8" in record:
        raise ValueError(
            "This is an intake private key; only the public key record may be published"
        )
    if (
        record.get("schema") != INTAKE_PUBLIC_KEY_SCHEMA
        or set(record) != INTAKE_PUBLIC_KEY_FIELDS
    ):
        raise ValueError(f"Not a {INTAKE_PUBLIC_KEY_SCHEMA} record")
    spki = base64.b64decode(record["public_spki"], validate=True)
    if len(spki) != len(P256_SPKI_PREFIX) + 65 or not spki.startswith(P256_SPKI_PREFIX):
        raise ValueError("The intake key is not a P-256 public key")
    hexdigest = hashlib.sha256(spki).hexdigest()
    if record["fingerprint"] != " ".join(hexdigest[i : i + 4] for i in range(0, 64, 4)):
        raise ValueError("The intake key record's fingerprint does not match its key")
    if record["key_id"] != "intake-key-" + hexdigest[:32]:
        raise ValueError("The intake key record's key_id does not match its key")
    return data(path)


def build(*, private_science=False, output_directory=None):
    destination = Path(output_directory).resolve() if output_directory else ROOT
    if private_science and destination == ROOT.resolve():
        raise ValueError("Private science builds require a separate output directory")
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["node", str(ROOT / "tools/check_repository_snapshot_admission.cjs")],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    style = (
        (ROOT / "src/styles.css").read_text()
        + "\n"
        + (ROOT / "src/goal_styles.css").read_text()
    )
    engine = (ROOT / "src/engine.js").read_text()
    app = (ROOT / "src/app.js").read_text()
    routing = (ROOT / "src/routing.js").read_text()
    c05_evidence = (ROOT / "src/c05_evidence.js").read_text()
    source_assessment = (ROOT / "src/source_assessment.js").read_text()
    intake = (ROOT / "src/intake.js").read_text()
    team_review = (ROOT / "src/team_review.js").read_text()
    # Shared with the public onboarding edition. The internal side needs it to
    # import a public artifact, and sharing one module is what makes the two
    # sides agree on the draft rather than on a description of it.
    public_workbench = (ROOT / "src/public_workbench.js").read_text()
    workflow = (ROOT / "src/workflow.js").read_text()
    scientific_studies = (ROOT / "src/scientific_studies.js").read_text()
    scientific_studies_ui = (ROOT / "src/scientific_studies_ui.js").read_text()
    goal_app = (ROOT / "src/goal_app.js").read_text()
    atlas = data(ROOT / "data/atlas.json")
    studies = data(ROOT / "data/studies.json")
    cpes = data(ROOT / "data/cpes_study_v1.json")
    c05_index = data(ROOT / "data/c05_fixture_index_v2.json")
    assessment_profile = data(
        ROOT / "source_assessment/repository_snapshot/v1/profile.json"
    )
    assessment_index = data(
        ROOT / "source_assessment/repository_snapshot/v1/approved_assessments.json"
    )
    scripts = " ".join(
        "'" + digest(s) + "'"
        for s in [
            engine,
            app,
            routing,
            c05_evidence,
            source_assessment,
            intake,
            team_review,
            public_workbench,
            workflow,
            scientific_studies,
            scientific_studies_ui,
            goal_app,
            atlas,
            studies,
            cpes,
            c05_index,
            assessment_profile,
            assessment_index,
        ]
    )
    connection_policy = "'self'" if private_science else "'none'"
    csp = f"default-src 'none'; script-src {scripts}; style-src '{digest(style)}'; img-src data:; connect-src {connection_policy}; form-action 'none'; base-uri 'none'; object-src 'none'"
    html = (ROOT / "src/shell.html").read_text()
    for k, v in {
        "CSP": csp,
        "STYLE": style,
        "ATLAS": atlas,
        "STUDIES": studies,
        "CPES": cpes,
        "C05_INDEX": c05_index,
        "SOURCE_ASSESSMENT_PROFILE": assessment_profile,
        "SOURCE_ASSESSMENT_INDEX": assessment_index,
        "ENGINE": engine,
        "APP": app,
        "ROUTING": routing,
        "C05_EVIDENCE": c05_evidence,
        "SOURCE_ASSESSMENT": source_assessment,
        "INTAKE": intake,
        "TEAM_REVIEW": team_review,
        "PUBLIC_WORKBENCH": public_workbench,
        "WORKFLOW": workflow,
        "SCIENTIFIC_STUDIES": scientific_studies,
        "SCIENTIFIC_STUDIES_UI": scientific_studies_ui,
        "SCIENCE_MODE": "private" if private_science else "offline",
        "GOAL_APP": goal_app,
    }.items():
        html = html.replace("{{" + k + "}}", v)
    (destination / "Carbon_Opportunity_Workbench.html").write_text(html)
    intake_style = (ROOT / "src/intake_styles.css").read_text()
    intake_app = (ROOT / "src/intake_app.js").read_text()
    intake_seal = (ROOT / "src/intake_seal.js").read_text()
    intake_key = intake_public_key(ROOT / "data/intake_public_key.json")
    intake_csp = (
        "default-src 'none'; script-src "
        + " ".join(
            "'" + digest(value) + "'" for value in [intake, intake_seal, intake_app]
        )
        + "; style-src '"
        + digest(intake_style)
        + "'; img-src data:; connect-src 'self'; form-action 'none'; base-uri 'none'; object-src 'none'"
    )
    preview = (ROOT / "src/intake_shell.html").read_text()
    for key, value in {
        "CSP": intake_csp,
        "STYLE": intake_style,
        "INTAKE": intake,
        "INTAKE_SEAL": intake_seal,
        "INTAKE_KEY": intake_key,
        "APP": intake_app,
    }.items():
        preview = preview.replace("{{" + key + "}}", value)
    (destination / "Carbon_Client_Intake_Preview.html").write_text(preview)
    (destination / "Carbon_Client_Pilot_Designer_Preview.html").write_text(preview)
    # Not emitted into a private-science build. The connected host verifies that
    # its static directory holds only the artifacts it serves, and the public
    # onboarding edition is not one of them: it has no business on a private
    # origin, and adding it to that allow-list would widen what the host serves
    # to buy nothing. The freshness gate regenerates without --private-science,
    # so the tracked artifact is still covered.
    if not private_science:
        build_public_onboarding(destination)
    return destination / "Carbon_Opportunity_Workbench.html"


# The public onboarding edition's entire contents, named rather than excluded.
#
# An exclusion list is the wrong shape for this: it is correct only while
# somebody remembers to extend it, and the thing being excluded is client
# evidence. This is the whole bundle, and a test asserts the emitted file
# contains nothing else.
PUBLIC_SOURCES = (
    "src/public_shell.html",
    "src/public_styles.css",
    "src/scientific_studies.js",
    "src/public_workbench.js",
    "src/public_app.js",
)


def build_public_onboarding(destination):
    """Emit the client-facing onboarding edition.

    Shares `scientific_studies.js` with the internal bundle unchanged, so the
    structural check a visitor sees is the accepted one rather than a public
    re-implementation of it. `createAdapter` is the only part of that module
    that reaches the network, and nothing here calls it, so the emitted CSP
    grants no connection at all.
    """
    style = (ROOT / "src/public_styles.css").read_text()
    scientific_studies = (ROOT / "src/scientific_studies.js").read_text()
    public_workbench = (ROOT / "src/public_workbench.js").read_text()
    app = (ROOT / "src/public_app.js").read_text()
    scripts = " ".join(
        "'" + digest(source) + "'"
        for source in [scientific_studies, public_workbench, app]
    )
    csp = (
        f"default-src 'none'; script-src {scripts}; style-src '{digest(style)}'; "
        "img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'; "
        "object-src 'none'"
    )
    html = (ROOT / "src/public_shell.html").read_text()
    for key, value in {
        "CSP": csp,
        "STYLE": style,
        "SCIENTIFIC_STUDIES": scientific_studies,
        "PUBLIC_WORKBENCH": public_workbench,
        "APP": app,
    }.items():
        html = html.replace("{{" + key + "}}", value)
    output = destination / "Carbon_Public_Workbench_Onboarding.html"
    output.write_text(html)
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--private-science", action="store_true")
    parser.add_argument("--output-directory", type=Path)
    options = parser.parse_args()
    print(
        build(
            private_science=options.private_science,
            output_directory=options.output_directory,
        )
    )
