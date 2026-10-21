"""Carbon's backbone catalog: tested operator backbones a miner selects by id.

OWNER-BACKBONE-CATALOG-01 (2026-10-20): "I don't want to limit the backbone
selection if it's been run and tested by us". A miner names a catalog id and
bounded settings; Carbon's own pinned code builds, trains and predicts with
it, in practice and in the validator's rebuild. Nothing here lowers a graph,
runs miner source or downloads weights: every entry is an architecture
trained from scratch on the Challenge's public TRAIN.

- `entries`: the table (ids, pinned libraries, bounded settings). Pure data;
  imports neither torch nor any library.
- `torch_backbones`: each entry's module, behind a Challenge-shaped adapter.
- `torch_loop`: Carbon's deterministic training loop and float64 predictions.

The modules import nothing else from Carbon, so the worker can stage them as
they are. An entry is listed for a Challenge version only once its rebuild,
pair-identity and tuning batches have passed; listing describes, it does
not qualify.
"""
