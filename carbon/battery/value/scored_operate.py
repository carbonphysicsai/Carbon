"""The daemon entry point for a deployment scored by a registered candidate
(VALIDATOR-26).

`python -m carbon.battery.value.scored_operate run --config DEPLOYMENT ...`
is `carbon.battery.operate` with the registered score installed on each
deployment it builds (`registered_score.install`), and, for a
development-ladder deployment, the ladder's compiler too. The intake and the
daemon never import the score's value-analysis code; only this operator entry
point does.

DEVELOPMENT only: no qualification, LIVE, reward or mainnet claim.
"""

from __future__ import annotations


def main(argv=None):
    from carbon.battery import deployment, operate

    from .registered_score import install

    deployment.set_score_setup(install)
    from carbon.development_ladder.operate import setup as ladder_setup

    deployment.set_ladder_setup(ladder_setup)
    return operate.main(argv)


if __name__ == "__main__":
    # The package module's own main: under `python -m` this file is
    # `__main__`, a second copy whose classes the package's are not.
    import sys

    from carbon.battery.value.scored_operate import main as _main

    sys.exit(_main())
