"""Shared Launchpad campaign code for direct-recipe-only Challenge versions.

F08 (Ribbed Bracket) 1.4 and F02 (Burst Thermal) 2.3 have no Level-0 campaign:
their only construction path is a direct recipe (a Carbon-tested catalog
backbone, or a graph trained by Carbon's registered graph training adapter).
This package holds what both share, parameterised by `spec.Spec`; each
Challenge's own package (`carbon.f08`, `carbon.f02`) binds its spec. Motor's
and Cooling's campaigns are not touched by it.

Every value here is a registered fact (names, units, shapes, dtypes, row counts,
digests, bounds) or the literal `HUMAN_INPUT`, so an unresolved decision fails
closed. Nothing here is an evaluation, a qualification or LIVE authority.
"""
