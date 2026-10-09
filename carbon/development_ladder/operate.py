"""The development-ladder deployment's daemon (VALIDATOR-25).

`python -m carbon.development_ladder.operate run --config DEPLOYMENT ...` is
`carbon.battery.operate` with one addition: each development-ladder
deployment it builds is given the development compiler, so a variant the
deployment lists is compiled by the variant module here, never by the daemon
(which never imports it). A deployment without a `ladder` is untouched.
DEVELOPMENT only: no weight, settlement, promotion or mainnet authority.
"""

from __future__ import annotations


def compile_variant(strategy, variant_digest):
    """The development compile for a registered variant the ladder lists."""
    from carbon.reconstruction import development_variants as dv

    return dv.compile_development(strategy, dv.registered(variant_digest))


def setup(target):
    """Supply the compiler to one development-ladder deployment."""
    if getattr(target, "ladder", None) is None:
        raise ValueError("not a development-ladder deployment")
    target.development_compiler = compile_variant


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


__all__ = ["compile_variant", "main", "setup"]
