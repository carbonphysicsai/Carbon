"""The development-ladder deployment's daemon (VALIDATOR-25).

`python -m carbon.development_ladder.operate run --config DEPLOYMENT ...` is
`carbon.battery.operate` with one addition: each development-ladder
deployment it builds is given the development compiler, so a variant the
deployment lists is compiled by the variant module here, never by the daemon
(which never imports it). A deployment without a `ladder` is untouched.
DEVELOPMENT only: no weight, settlement, promotion or mainnet authority.
"""

from __future__ import annotations


class LadderRefused(ValueError):
    """A ladder compile refused by closed code (the daemon reports it as
    `development_variant_refused` with this code)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def compile_variant(strategy, variant_digest, parts=None, held=None):
    """The development compile for a registered variant the ladder lists. A
    Level 4 variant is admitted only through the Level 4 checks over its
    envelope (`carbon.battery.level4_admission.admit_envelope`), assembled from
    the signed parts the intake holds; until those checks exist, it is
    refused. `held` keeps each admitted envelope's `(raw_manifest, files)`."""
    from carbon.reconstruction import development_variants as dv

    variant = dv.registered(variant_digest)
    if getattr(variant, "level", None) == 4:
        admitted = _admit_level4(strategy, variant, parts)
        if held is not None:
            held[_submission(strategy)] = admitted
    return dv.compile_development(strategy, variant)


def _submission(strategy):
    from carbon.battery.level4_parts import FIELD

    parameters = strategy.get("parameters") if type(strategy) is dict else None
    return parameters.get(FIELD) if type(parameters) is dict else None


def _admit_level4(strategy, variant, parts):
    """`(raw_manifest, files)` of a Level 4 submission's admitted envelope.
    A refusal of the candidate's envelope (`GraphRefused`) is a ValueError
    with its code; an unset bound or a failed isolated parse is Carbon's
    (`IntakeBlocked`, `IntakeInfraFailure`) and propagates as infrastructure."""
    import json

    from carbon.battery.level4_parts import PartRefused

    try:
        from carbon.battery.level4_admission import admit_envelope
    except ImportError:
        admit_envelope = None
    if admit_envelope is None or parts is None:
        raise LadderRefused("ladder_level_4_checks_unavailable")
    try:
        envelope = parts.envelope(_submission(strategy))
    except PartRefused as refused:
        raise LadderRefused(refused.code) from None
    if envelope is None:
        raise LadderRefused("level4_envelope_incomplete")
    # The widened bounds' `loss_override`; absent means none (the same value
    # the rebuild record carries).
    overrides = [
        json.loads(widened.bounds_json).get("loss_override")
        for widened in variant.widened
    ]
    loss_override = next((o for o in overrides if o is not None), None)
    return admit_envelope(strategy, envelope, loss_override=loss_override)


def setup(target, config=None):
    """Supply the compiler to one development-ladder deployment, with its
    Level 4 envelope parts when it serves Level 4, and the staged workspace a
    Level 4 rebuild needs (`workspace_for`)."""
    if getattr(target, "ladder", None) is None:
        raise ValueError("not a development-ladder deployment")
    parts = None
    if config is not None and 4 in target.ladder["levels"]:
        from pathlib import Path

        from carbon.battery.level4_parts import Level4Parts

        parts = Level4Parts(
            Path(config["work"]) / "level4-parts", target.ladder["hotkeys"]
        )
    held = {}

    def compile_listed(strategy, variant_digest):
        return compile_variant(strategy, variant_digest, parts, held)

    def workspace_for(strategy):
        submission = _submission(strategy)
        if parts is None or submission is None:
            return None
        if submission not in held:
            # The daemon recompiles a row (and so re-admits its envelope) just
            # before rebuilding it; a missing one is Carbon's state, never the
            # candidate's.
            raise RuntimeError("level4 envelope not admitted in this process")
        from carbon.level4 import staging

        raw_manifest, files = held[submission]
        return staging.workspace(raw_manifest, files)

    compile_listed.parts = parts
    compile_listed.workspace_for = workspace_for
    target.development_compiler = compile_listed


def main(argv=None):
    from carbon.battery import deployment, operate

    deployment.set_ladder_setup(setup)
    return operate.main(argv)


if __name__ == "__main__":
    # The package module's own main: under `python -m` this file is
    # `__main__`, a second copy whose classes the package's are not.
    import sys

    from carbon.development_ladder.operate import main as _main

    sys.exit(_main())


__all__ = ["LadderRefused", "compile_variant", "main", "setup"]
