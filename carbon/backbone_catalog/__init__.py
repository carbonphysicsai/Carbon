"""Carbon's backbone catalog: tested operator backbones a miner selects by id.

OWNER-BACKBONE-CATALOG-01 (2026-10-20): "I don't want to limit the backbone
selection if it's been run and tested by us". A miner names a catalog id and
bounded settings; Carbon's own pinned code builds, trains and predicts with
it, in practice and in the validator's rebuild. Nothing here lowers a graph,
runs miner source or downloads weights: every entry is an architecture
trained from scratch on the Challenge's public TRAIN.

- `listing`: the manifest of tested entries, read-only (miner surfaces).
- `served`: what a Challenge version serves, and a catalog recipe's expansion
  to the Carbon bundle it names.
- `settings`: each entry's settings, checked by its pinned build's own
  vocabulary; no size cap of Carbon's own.
- `entries`: the catalog's refusal codes.
- `pipeline`: the owner's add, verify and install commands.

An entry is listed for a Challenge version only once its rebuild,
pair-identity and tuning batches have passed; listing describes, it does
not qualify.
"""
