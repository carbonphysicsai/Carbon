"""Carbon's general attack engine (OWNER-GRAPHITE-ATTACKER-01).

A Challenge-neutral engine with one adapter per Challenge and per construction
level. Graphite's Attacker role drives it in phase 4; battery's Track A
harness (`carbon.battery.track_a`) runs its families through it.

- `engine`: a family's attacks, vulnerable specimen and valid control; its
  findings, in the admission CONDITIONS vocabulary, and its state, never an
  acceptance.
- `adapter`: what one Challenge at one construction level supplies: its
  contract digest, its families covering the eight shared Track A checks,
  controls split trained and held out, its oracle, Carbon's rebuild of an
  attack construction, and the higher-level families it declares NOT_RUN;
  and the registry of adapters by (Challenge, level).

DEVELOPMENT only. Nothing here executes hostile code: executable families are
declared seams and reported NOT_RUN, and isolating them is a reserved security
decision. Nothing here grants scientific, security, economic or launch
authority. The miner edition and Launchpad never import this package.

The package imports nothing on its own, so importing one module stays cheap.
"""
