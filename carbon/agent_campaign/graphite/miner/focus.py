"""Focused hunts and per-Challenge ranking (OWNER-GRAPHITE-MINER-01 §5).

Rule `carbon.graphite.miner-focus.v1`. Everything here is deterministic and
reads only public material and the miner's own practice results:

- **Queries from public discovery** (`queries_for`). Carbon composes the
  hunt's queries from the Challenge's public discovery document
  (`challenge_registry.describe`) through a closed grammar: a domain phrase
  from `DOMAIN_LEXICON`, matched in the document's title, task, interface
  units and reference text, followed by `surrogate` or by the arXiv terms
  `METHOD_LEXICON` gives each rebuildable model family the document lists.
  Only `DISCOVERY_FIELDS` are read; nothing else in the document is.
- **Miner queries** (`parse_miner_queries`). At most `MAX_MINER_QUERIES`
  queries of at most `MAX_TERMS` terms of `[A-Za-z0-9-]`. Raw arXiv query
  syntax is never accepted: Carbon writes every query itself, each term
  quoted in the abstract field, restricted to `CATEGORIES`.
- **Triage** (`triage`). A free first pass on a record's title and abstract
  before any paid extraction: its categories, then `TRIAGE_RULE`: the
  Challenge's primary domain, a secondary domain with a surrogate cue, two
  method cues one of which is a surrogate cue, or every term of one of the
  miner's focus terms. A broad machine-learning cue never keeps a record
  alone.
- **Ranking** (`assess`, `rank`). A grade 0-3 with reasons: relevance to the
  Challenge's public focus, buildability under the Challenge's public
  construction contract (`capability_registry.public_registry`), the miner's
  own focus terms, and the miner's own practice outcomes on this Challenge. A
  card whose recognised capabilities are all outside the contract is a
  `capability_request` candidate, never a plan input, and its grade is at
  most 1. Pins are flagged; bans are applied by the caller before ranking.
- **Learning.** `learned_queries` seeds the next hunt from the techniques of
  cards the miner's practice on the same Challenge improved with. Only the
  `improved` and `not_improved` counts of the miner's own outcomes reach the
  ranking.
- **Freezing.** `frozen_context` cuts the discovery document and contract to
  what this rule reads, so a campaign can freeze exactly the public inputs
  its ranking used and replay them.

A card is read only through `RANKED_FIELDS`. No other field, and nothing an
outcome's evidence holds beyond its two counts, can change a grade or an
order. Nothing here is a scientific claim: the lexicons say what to read, not
what is true.
"""

from __future__ import annotations

import functools
import re

from carbon.development_session.profile import canonical, digest

FOCUS_RULE = "carbon.graphite.miner-focus.v1"
#: The arXiv categories a hunt searches and keeps.
CATEGORIES = (
    "cs.LG",
    "physics.comp-ph",
    "math.NA",
    "eess.SY",
    "physics.chem-ph",
    "cond-mat.mtrl-sci",
    "stat.ML",
)
MAX_MINER_QUERIES = 8
MAX_TERMS = 6
MAX_TERM_CHARS = 40
MAX_QUERY_CHARS = 200
DISCOVERY_QUERY_CAP = 6
LEARNED_QUERY_CAP = 2
#: Boolean words a term may not be, whatever its case.
OPERATORS = frozenset({"and", "or", "not", "andnot"})
HUNT_QUERY_INVALID = "hunt_query_invalid"

#: The discovery document's fields this rule reads; nothing else is read.
DISCOVERY_FIELDS = (
    "challenge_id",
    "title",
    "task",
    "interface.inputs.*.unit",
    "interface.outputs.*.unit",
    "interface.outputs.*.meaning",
    "reference.reference",
    "reference.protocol",
    "models.rebuildable.*.selector",
    "public_material.train.cases",
)
#: The card fields a grade reads; nothing else on a card is read. A card's
#: `applicability` is the extraction prompt's own speculation about Carbon's
#: Challenges, not the paper's content, so it does not steer the ranking.
RANKED_FIELDS = (
    "title",
    "technique",
    "claimed_effect",
    "data_regime",
    "abstract",
)
#: Grade thresholds on the raw score (see `assess`).
GRADE_THRESHOLDS = ((5, 3), (3, 2), (1, 1))

#: (name, cues, arXiv terms). A cue is matched as a whole phrase,
#: case-insensitively; the terms are what a query searches for.
DOMAIN_LEXICON = (
    (
        "battery",
        ("battery", "batteries", "lithium-ion", "li-ion", "lithium ion"),
        ("battery",),
    ),
    (
        "fast-charging",
        ("fast charge", "fast charging", "fast-charge", "fast-charging", "c-rate"),
        ("fast", "charging"),
    ),
    (
        "degradation",
        ("ageing", "aging", "degradation", "capacity fade", "cycle life"),
        ("degradation",),
    ),
    ("lithium-plating", ("lithium plating", "plating"), ("lithium", "plating")),
    (
        "electrochemical",
        (
            "electrochemical",
            "doyle-fuller-newman",
            "pseudo-two-dimensional",
            "dfn",
            "p2d",
            "pybamm",
            "single particle model",
        ),
        ("electrochemical",),
    ),
    ("thermal", ("thermal", "temperature", "heat transfer"), ("thermal",)),
    ("burgers", ("burgers",), ("Burgers",)),
    (
        "navier-stokes",
        ("navier-stokes", "navier stokes", "incompressible flow"),
        ("Navier-Stokes",),
    ),
    ("turbulence", ("turbulence", "turbulent"), ("turbulence",)),
    (
        "fluid-dynamics",
        ("fluid dynamics", "computational fluid dynamics", "cfd"),
        ("fluid", "dynamics"),
    ),
    (
        "reaction-diffusion",
        ("reaction-diffusion", "reaction diffusion"),
        ("reaction-diffusion",),
    ),
    ("darcy", ("darcy", "porous media"), ("Darcy", "flow")),
    ("wave", ("wave equation", "acoustic", "seismic"), ("wave", "propagation")),
    ("elasticity", ("elasticity", "solid mechanics"), ("elasticity",)),
    (
        "molecular",
        ("molecular dynamics", "interatomic potential"),
        ("molecular", "dynamics"),
    ),
    ("materials", ("microstructure", "materials science"), ("materials",)),
    ("pde", ("partial differential equation", "pde", "pdes"), ("PDE",)),
)
#: Rebuildable family selector -> (cues, arXiv terms), in query order.
METHOD_LEXICON = (
    ("fno", ("fourier neural operator", "fno"), ("Fourier", "neural", "operator")),
    ("deeponet", ("deeponet", "deep operator network"), ("DeepONet",)),
    ("transolver", ("transolver",), ("Transolver",)),
    ("gno", ("graph neural operator",), ("graph", "neural", "operator")),
    (
        "gino",
        ("geometry-informed neural operator",),
        ("geometry-informed", "neural", "operator"),
    ),
    (
        "haar_operator",
        ("wavelet neural operator", "multiwavelet"),
        ("wavelet", "neural", "operator"),
    ),
    (
        "mlp",
        ("multilayer perceptron", "multi-layer perceptron", "mlp"),
        ("neural", "network", "surrogate"),
    ),
    (
        "knn",
        ("nearest neighbor", "nearest neighbour", "nearest-neighbor", "knn"),
        ("nearest", "neighbor"),
    ),
)
#: Method cues that name learned fast models of physics specifically.
SURROGATE_CUES = (
    "surrogate",
    "surrogates",
    "neural operator",
    "operator learning",
    "reduced-order",
    "reduced order",
    "emulator",
    "physics-informed",
)
#: Broad machine-learning cues: they count toward a grade, but never keep a
#: record in triage on their own.
BROAD_ML_CUES = ("neural network", "deep learning", "machine learning")
#: Method cues every Challenge shares.
GENERIC_METHOD_CUES = SURROGATE_CUES + BROAD_ML_CUES
#: Rebuildable families whose cues are broad machine learning, not surrogate
#: cues, in triage.
BROAD_FAMILIES = ("mlp", "knn")
#: The cues triage treats as surrogate cues: `SURROGATE_CUES` and the operator
#: families of `METHOD_LEXICON`.
TRIAGE_SURROGATE_CUES = tuple(
    sorted(
        set(SURROGATE_CUES)
        | {
            cue
            for selector, cues, _ in METHOD_LEXICON
            if selector not in BROAD_FAMILIES
            for cue in cues
        }
    )
)
#: When triage keeps an allowed-category record, in order; anything else is
#: triaged out before any paid call.
TRIAGE_RULE = (
    "primary_domain",
    "secondary_domain_and_surrogate",
    "two_methods_one_surrogate",
    "miner_focus_terms",
)
#: The raw-score weights of a grade (see `assess`).
SCORES = {
    "primary_domain": 3,
    "secondary_domain": 1,
    "method": 1,
    "buildable": 1,
    "miner_focus_terms": 1,
    "practice": 1,
}
#: The highest grade of a card that is not a plan input.
NOT_PLAN_INPUT_MAX_GRADE = 1
#: A small public training set (cases) makes small-data methods relevant.
SMALL_DATA_CASES = 2000
SMALL_DATA_CUES = (
    "small data",
    "limited data",
    "scarce data",
    "data-efficient",
    "data efficient",
    "few samples",
    "low-data",
)
#: (capability id, cues). A cue recognises a capability on a card; the
#: Challenge's public contract says whether Carbon rebuilds it. An id the
#: contract does not register is outside it.
CAPABILITY_CUES = (
    ("model_family.fno", ("fourier neural operator", "fno")),
    ("model_family.deeponet", ("deeponet", "deep operator network")),
    (
        "model_family.mlp",
        (
            "multilayer perceptron",
            "multi-layer perceptron",
            "mlp",
            "feedforward neural network",
            "feed-forward neural network",
            "fully connected network",
        ),
    ),
    (
        "model_family.knn",
        ("nearest neighbor", "nearest neighbour", "nearest-neighbor", "knn", "k-nn"),
    ),
    ("model_family.transolver", ("transolver",)),
    ("model_family.gno", ("graph neural operator",)),
    ("model_family.gino", ("geometry-informed neural operator", "gino")),
    ("model_family.haar_operator", ("wavelet neural operator", "multiwavelet")),
    ("model_family.unet1d", ("u-net", "unet")),
    ("model_family.pointnet", ("pointnet",)),
    ("model_family.gnot", ("gnot",)),
    ("model_family.geofno", ("geo-fno", "geofno")),
    ("model_family.gaussian_process", ("gaussian process", "kriging")),
    ("model_family.recurrent", ("recurrent neural network", "lstm", "gru")),
    ("model_family.julia_backend", ("julia", "neuralpde")),
    (
        "model_family.pretrained_weights",
        ("pretrained", "pre-trained", "foundation model", "transfer learning"),
    ),
    ("objective.pde_weight", ("physics-informed", "pinn", "pinns", "pde residual")),
    ("objective.h1_weight", ("sobolev", "derivative loss", "gradient-enhanced")),
    ("objective.spectral_weight", ("spectral loss", "frequency loss")),
    ("objective.relative_loss", ("relative loss", "relative l2")),
    ("stages.polish_steps", ("l-bfgs", "lbfgs")),
    (
        "optimizer.optimizer_family",
        ("adam", "adamw", "muon", "sgd", "stochastic gradient descent", "radam"),
    ),
    (
        "schedule.learning_rate_curve",
        ("learning rate schedule", "learning-rate schedule", "cosine annealing"),
    ),
    ("inference.ensemble_members", ("ensemble", "ensembles", "deep ensemble")),
    (
        "inference.ema_decay",
        ("exponential moving average", "polyak averaging", "weight averaging"),
    ),
    ("training_data.curriculum", ("curriculum",)),
    (
        "training_data.hard_example_weight",
        ("hard example", "hard-example", "importance sampling"),
    ),
    ("training_data.support_leaving_augmentation", ("data augmentation",)),
    ("prediction.rollout", ("autoregressive", "rollout", "time-stepping")),
    (
        "hybrid.candidate_solver_template",
        ("single particle model", "hybrid physics", "grey-box", "gray-box"),
    ),
    ("hybrid.symbolic_template", ("symbolic regression", "sindy")),
    ("architecture.normalization", ("layer normalization", "batch normalization")),
    ("inference.backend", ("pytorch", "jax")),
    (
        "physical_structure.structure_layers",
        ("monotone", "monotonic", "hard constraint", "physics-constrained"),
    ),
)
REBUILDABLE = "rebuildable_development"
#: Words a learned query never takes from a card's technique text.
STOPWORDS = frozenset(
    (
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "based",
        "be",
        "by",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "the",
        "to",
        "via",
        "with",
        "without",
        "using",
        "use",
        "method",
        "methods",
        "model",
        "models",
        "approach",
        "framework",
        "learning",
        "network",
        "networks",
        "neural",
        "new",
        "novel",
        "stated",
        "not",
    )
)

_CAPABILITY_SETS = tuple((cid, frozenset(cues)) for cid, cues in CAPABILITY_CUES)
#: Every cue of this rule, matched once per card text.
ALL_CUES = tuple(
    sorted(
        {cue for _, cues, _ in DOMAIN_LEXICON for cue in cues}
        | {cue for _, cues, _ in METHOD_LEXICON for cue in cues}
        | set(GENERIC_METHOD_CUES)
        | set(SMALL_DATA_CUES)
        | {cue for _, cues in CAPABILITY_CUES for cue in cues}
    )
)

_TERM = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")
_QUERY = re.compile(r"[A-Za-z0-9 -]+")
_WORD = re.compile(r"[a-z0-9]+")


class QueryRefused(ValueError):
    """A hunt's queries cannot be used; nothing was fetched."""

    code = HUNT_QUERY_INVALID

    def __init__(self, detail):
        super().__init__(HUNT_QUERY_INVALID + ": " + detail)
        self.detail = detail


def rule_document():
    """Everything this rule's behaviour depends on, as data."""
    return {
        "schema": FOCUS_RULE,
        "categories": list(CATEGORIES),
        "limits": {
            "miner_queries": MAX_MINER_QUERIES,
            "terms": MAX_TERMS,
            "term_chars": MAX_TERM_CHARS,
            "discovery_queries": DISCOVERY_QUERY_CAP,
            "learned_queries": LEARNED_QUERY_CAP,
            "small_data_cases": SMALL_DATA_CASES,
        },
        "discovery_fields": list(DISCOVERY_FIELDS),
        "ranked_fields": list(RANKED_FIELDS),
        "grade_thresholds": [list(pair) for pair in GRADE_THRESHOLDS],
        "scores": dict(SCORES),
        "not_plan_input_max_grade": NOT_PLAN_INPUT_MAX_GRADE,
        "triage": {
            "keep_when": list(TRIAGE_RULE),
            "primary_domains": 2,
            "surrogate_cues": list(TRIAGE_SURROGATE_CUES),
            "broad_families": list(BROAD_FAMILIES),
        },
        "domain_lexicon": [[n, list(c), list(t)] for n, c, t in DOMAIN_LEXICON],
        "method_lexicon": [[s, list(c), list(t)] for s, c, t in METHOD_LEXICON],
        "surrogate_cues": list(SURROGATE_CUES),
        "broad_ml_cues": list(BROAD_ML_CUES),
        "small_data_cues": list(SMALL_DATA_CUES),
        "capability_cues": [[i, list(c)] for i, c in CAPABILITY_CUES],
        "stopwords": sorted(STOPWORDS),
    }


def rule_digest():
    return digest(canonical(rule_document()))


@functools.lru_cache(maxsize=1024)
def _cue(cue):
    return re.compile(r"(?<![a-z0-9])" + re.escape(cue) + r"(?![a-z0-9])")


def _has(text, cues):
    return any(cue in text and _cue(cue).search(text) for cue in cues)


@functools.lru_cache(maxsize=16384)
def text_cues(text):
    """Every cue of this rule a lower-case text names, as whole phrases."""
    return frozenset(cue for cue in ALL_CUES if cue in text and _cue(cue).search(text))


@functools.lru_cache(maxsize=16384)
def _words(text):
    return frozenset(_WORD.findall(text))


def _lower(value):
    return " ".join(value.split()).lower() if type(value) is str else ""


# -- the public discovery document -------------------------------------------------


def _get(document, *path):
    value = document
    for key in path:
        if type(value) is not dict:
            return None
        value = value.get(key)
    return value


def _discovery_text(discovery):
    """The discovery fields this rule reads, as one lower-case text."""
    parts = [_lower(_get(discovery, "title")), _lower(_get(discovery, "task"))]
    interface = _get(discovery, "interface")
    for side in ("inputs", "outputs"):
        items = _get(interface, side) if type(interface) is dict else None
        if type(items) is dict:
            for name in sorted(items, key=str):
                item = items[name]
                if type(item) is dict:
                    parts.append(_lower(item.get("unit")))
                    if side == "outputs":
                        parts.append(_lower(item.get("meaning")))
    parts.append(_lower(_get(discovery, "reference", "reference")))
    parts.append(_lower(_get(discovery, "reference", "protocol")))
    return " | ".join(part for part in parts if part)


def _selectors(discovery):
    rebuildable = _get(discovery, "models", "rebuildable")
    if type(rebuildable) is not list:
        return ()
    found = []
    for item in rebuildable:
        selector = item.get("selector") if type(item) is dict else None
        if type(selector) is str and selector not in found:
            found.append(selector)
    return tuple(found)


def discovery_focus(discovery):
    """The Challenge's public focus, read from `DISCOVERY_FIELDS` only."""
    if type(discovery) is not dict:
        discovery = {}
    text = _discovery_text(discovery)
    domains = [entry for entry in DOMAIN_LEXICON if _has(text, entry[1])]
    selectors = _selectors(discovery)
    methods = [entry for entry in METHOD_LEXICON if entry[0] in selectors]
    cases = _get(discovery, "public_material", "train", "cases")
    small = type(cases) is int and 0 < cases <= SMALL_DATA_CASES
    challenge = _get(discovery, "challenge_id")
    return {
        "challenge_id": challenge if type(challenge) is str else None,
        "domains": [name for name, _, _ in domains],
        "domain_cues": sorted({cue for _, cues, _ in domains for cue in cues}),
        # The first two domains the document names are its primary focus.
        "primary_cues": sorted({cue for _, cues, _ in domains[:2] for cue in cues}),
        "secondary_cues": sorted(
            {cue for _, cues, _ in domains[2:] for cue in cues}
            - {cue for _, cues, _ in domains[:2] for cue in cues}
        ),
        "domain_terms": [list(terms) for _, _, terms in domains],
        "methods": [selector for selector, _, _ in methods],
        "method_cues": sorted(
            {cue for _, cues, _ in methods for cue in cues} | set(GENERIC_METHOD_CUES)
        ),
        "method_terms": [list(terms) for _, _, terms in methods],
        "small_data": small,
        "train_cases": cases if type(cases) is int else None,
    }


def discovery_projection(discovery):
    """The discovery document cut to `DISCOVERY_FIELDS`, in its own shape.

    `discovery_focus` and `queries_for` give the same answer for the
    projection as for the whole document, so a campaign freezes this.
    """
    if type(discovery) is not dict:
        return {}
    projected = {
        key: discovery[key]
        for key in ("challenge_id", "title", "task")
        if type(discovery.get(key)) is str
    }
    interface = discovery.get("interface")
    sides = {}
    for side, fields in (("inputs", ("unit",)), ("outputs", ("unit", "meaning"))):
        items = interface.get(side) if type(interface) is dict else None
        if type(items) is dict:
            sides[side] = {
                str(name): {
                    field: item[field]
                    for field in fields
                    if type(item.get(field)) is str
                }
                for name, item in items.items()
                if type(item) is dict
            }
    if sides:
        projected["interface"] = sides
    reference = discovery.get("reference")
    if type(reference) is dict:
        kept = {
            key: reference[key]
            for key in ("reference", "protocol")
            if type(reference.get(key)) is str
        }
        if kept:
            projected["reference"] = kept
    selectors = _selectors(discovery)
    if selectors:
        projected["models"] = {
            "rebuildable": [{"selector": selector} for selector in selectors]
        }
    cases = _get(discovery, "public_material", "train", "cases")
    if type(cases) is int:
        projected["public_material"] = {"train": {"cases": cases}}
    return projected


def contract_projection(contract):
    """The public registry cut to what this rule reads: `{capabilities:
    [{id, status}]}` by id, or None when there is no contract."""
    statuses = contract_statuses(contract)
    if statuses is None:
        return None
    return {
        "capabilities": [
            {"id": cid, "status": statuses[cid]} for cid in sorted(statuses)
        ]
    }


def frozen_context(discovery, contract):
    """`{discovery, contract}`: the public inputs a ranking reads, cut to
    what it reads. Passing them back reproduces every grade and order."""
    return {
        "discovery": discovery_projection(discovery),
        "contract": contract_projection(contract),
    }


def checked_context(context):
    """A frozen context as `frozen_context` makes it, or ValueError."""
    if type(context) is not dict or set(context) != {"discovery", "contract"}:
        raise ValueError("a frozen context is {discovery, contract}")
    discovery, contract = context["discovery"], context["contract"]
    if type(discovery) is not dict or (
        contract is not None and type(contract) is not dict
    ):
        raise ValueError("a frozen context holds a discovery and a contract")
    if frozen_context(discovery, contract) != context:
        raise ValueError("a frozen context holds only what the focus rule reads")
    return context


def _query(query_id, terms, source, purpose):
    return {
        "query_id": query_id,
        "source": source,
        "terms": list(terms),
        "search_query": search_query(terms),
        "purpose": purpose,
    }


def _fallback_terms(discovery):
    """Up to two title words when no domain phrase matches."""
    title = _get(discovery, "title") if type(discovery) is dict else None
    words = []
    for word in _TERM.findall(title if type(title) is str else ""):
        lowered = word.lower()
        if (
            len(word) >= 4
            and not lowered.isdigit()
            and lowered not in STOPWORDS
            and lowered not in OPERATORS
            and lowered not in ("development", "challenge")
            and len(word) <= MAX_TERM_CHARS
        ):
            words.append(lowered)
        if len(words) == 2:
            break
    return words


def queries_for(discovery):
    """The hunt queries Carbon composes from a public discovery document.

    The grammar is closed: `<domain> surrogate`, `<domain> <second domain>
    surrogate`, then `<domain> <method>` for each rebuildable family the
    document lists, in `METHOD_LEXICON` order, at most `DISCOVERY_QUERY_CAP`
    queries of at most `MAX_TERMS` terms.
    """
    focus = discovery_focus(discovery)
    domains = focus["domain_terms"]
    if domains:
        primary = [term for terms in domains[:2] for term in terms][:3]
        first = list(domains[0])
    else:
        primary = _fallback_terms(discovery)
        first = primary[:1]
    if not primary:
        return []
    candidates = [(primary + ["surrogate"], "the Challenge's domain")]
    if len(domains) >= 3:
        candidates.append(
            (first + list(domains[2]) + ["surrogate"], "the Challenge's domain")
        )
    for selector, terms in zip(focus["methods"], focus["method_terms"]):
        candidates.append(
            (first + terms, f"the rebuildable {selector} family in this domain")
        )
    queries, seen = [], set()
    for terms, purpose in candidates:
        terms = terms[:MAX_TERMS]
        key = tuple(term.lower() for term in terms)
        if key in seen:
            continue
        seen.add(key)
        queries.append(
            _query(f"discovery-{len(queries) + 1}", terms, "discovery", purpose)
        )
        if len(queries) == DISCOVERY_QUERY_CAP:
            break
    return queries


# -- queries --------------------------------------------------------------------------


def search_query(terms):
    """The arXiv search Carbon writes for validated terms: each term quoted in
    the abstract field, all required, restricted to `CATEGORIES`."""
    terms = _checked_terms(list(terms), "query")
    return (
        "("
        + " AND ".join(f'abs:"{term}"' for term in terms)
        + ") AND ("
        + " OR ".join(f"cat:{category}" for category in CATEGORIES)
        + ")"
    )


def registered_search_query(search):
    """A registered query (Carbon's own syntax), restricted to `CATEGORIES`."""
    return (
        "("
        + search
        + ") AND ("
        + " OR ".join(f"cat:{category}" for category in CATEGORIES)
        + ")"
    )


def _checked_terms(terms, label):
    if not terms or len(terms) > MAX_TERMS:
        raise QueryRefused(f"{label}: 1-{MAX_TERMS} terms")
    for term in terms:
        if type(term) is not str or not _TERM.fullmatch(term):
            raise QueryRefused(f"{label}: a term is letters, digits and hyphens")
        if len(term) > MAX_TERM_CHARS:
            raise QueryRefused(f"{label}: a term is at most {MAX_TERM_CHARS} chars")
        if term.lower() in OPERATORS:
            raise QueryRefused(f"{label}: query operators are not accepted")
    return terms


def parse_miner_queries(values):
    """The miner's own queries, validated, as hunt queries.

    Each is plain text of letters, digits, spaces and hyphens: at most
    `MAX_TERMS` terms, no operator words, no field prefixes, no quotes. Case
    and repeated spaces are kept as typed; a repeated query is used once.
    """
    if values is None:
        return []
    if type(values) is not list:
        raise QueryRefused("queries are a list of text")
    if len(values) > MAX_MINER_QUERIES:
        raise QueryRefused(f"at most {MAX_MINER_QUERIES} queries")
    queries, seen = [], set()
    for position, value in enumerate(values, 1):
        label = f"query {position}"
        if type(value) is not str:
            raise QueryRefused(f"{label}: a query is text")
        if not 1 <= len(value) <= MAX_QUERY_CHARS or not _QUERY.fullmatch(value):
            raise QueryRefused(
                f"{label}: only letters, digits, spaces and hyphens, "
                f"1-{MAX_QUERY_CHARS} characters"
            )
        terms = _checked_terms(value.split(), label)
        key = tuple(term.lower() for term in terms)
        if key in seen:
            continue
        seen.add(key)
        queries.append(
            _query(f"miner-{len(queries) + 1}", terms, "miner", "the miner's query")
        )
    return queries


def learned_queries(cards, evidence, discovery):
    """Queries seeded by the miner's own practice: the techniques of cards
    cited by plans whose practice improved, most improved first.

    `cards` maps card id to a served card; only its `technique` is read.
    """
    focus = discovery_focus(discovery)
    prefix = list(focus["domain_terms"][0]) if focus["domain_terms"] else []
    ranked = sorted(
        (
            (counts["improved"] - counts["not_improved"], card_id)
            for card_id, counts in _counts(evidence).items()
            if counts["improved"] > counts["not_improved"] and card_id in cards
        ),
        key=lambda item: (-item[0], item[1]),
    )
    queries, seen = [], set()
    for _, card_id in ranked:
        words = []
        for word in _TERM.findall(_text_of(cards[card_id], "technique")):
            lowered = word.lower()
            if (
                len(word) >= 3
                and not lowered.isdigit()
                and lowered not in STOPWORDS
                and lowered not in OPERATORS
                and len(word) <= MAX_TERM_CHARS
                and lowered not in (w.lower() for w in words)
            ):
                words.append(word)
            if len(words) == 3:
                break
        if not words:
            continue
        terms = (prefix + words)[:MAX_TERMS]
        key = tuple(term.lower() for term in terms)
        if key in seen:
            continue
        seen.add(key)
        queries.append(
            _query(
                f"learned-{len(queries) + 1}",
                terms,
                "learned",
                f"seeded by card {card_id}, which the miner's practice improved with",
            )
        )
        if len(queries) == LEARNED_QUERY_CAP:
            break
    return queries


# -- triage -------------------------------------------------------------------------


def focus_phrases(values):
    """The miner's focus terms (text, as hunt queries take them), validated,
    as lower-case term tuples. A card or record matches one when it names
    every term of it."""
    return tuple(
        tuple(term.lower() for term in query["terms"])
        for query in parse_miner_queries(values)
    )


def _phrase_hit(text, phrases):
    """The first phrase every term of which the lower-case text names."""
    for phrase in phrases:
        if phrase and all(_has(text, (term,)) for term in phrase):
            return phrase
    return None


def triage(record, focus, *, phrases=()):
    """`(keep, score, reasons)` for an arXiv record, before any paid call.

    Reads the record's title, abstract and categories only. A record in an
    allowed category is kept by `TRIAGE_RULE`: it names the Challenge's
    primary domain; or a secondary domain and a surrogate cue; or two method
    cues, one of them a surrogate cue; or every term of one of the miner's
    focus `phrases` (`focus_phrases`). The score is the number of distinct
    cues it names, for the record only.
    """
    categories = record.get("categories") if type(record) is dict else None
    if type(categories) is not list or not set(categories) & set(CATEGORIES):
        return False, 0, ["category outside the hunt's arXiv categories"]
    text = _lower(record.get("title")) + " | " + _lower(record.get("abstract"))
    cues = text_cues(text)
    primary = cues & set(focus["primary_cues"])
    secondary = cues & set(focus["secondary_cues"])
    surrogate = cues & set(TRIAGE_SURROGATE_CUES)
    method = cues & (set(focus["method_cues"]) | surrogate)
    phrase = _phrase_hit(text, phrases)
    kept = {
        "primary_domain": bool(primary),
        "secondary_domain_and_surrogate": bool(secondary and surrogate),
        "two_methods_one_surrogate": bool(surrogate) and len(method) >= 2,
        "miner_focus_terms": phrase is not None,
    }
    reasons = [
        (
            f"names the Challenge's primary domain ({len(primary)} cue(s))"
            if primary
            else (
                f"names a secondary domain ({len(secondary)} cue(s))"
                if secondary
                else "no domain cue"
            )
        ),
        (
            f"names {len(method)} method cue(s), {len(surrogate)} of them "
            "surrogate cues"
            if method
            else "no method cue"
        ),
    ]
    if phrase is not None:
        reasons.append("names every term of the miner's focus terms")
    keep = next((rule for rule in TRIAGE_RULE if kept[rule]), None)
    reasons.append(f"kept: {keep}" if keep else "triaged out")
    score = len(primary | secondary | method) + (1 if phrase else 0)
    return keep is not None, score, reasons


# -- ranking ------------------------------------------------------------------------


def _text_of(card, name):
    value = card.get(name) if type(card) is dict else None
    return value if type(value) is str else ""


def _card_text(card):
    return " | ".join(_lower(_text_of(card, name)) for name in RANKED_FIELDS)


def _counts(evidence):
    """`{card_id: {improved, not_improved}}`: only the two counts are read."""
    counts = {}
    if type(evidence) is not dict:
        return counts
    for card_id, value in evidence.items():
        if type(card_id) is not str or type(value) is not dict:
            continue
        improved, missed = value.get("improved"), value.get("not_improved")
        counts[card_id] = {
            "improved": improved if type(improved) is int and improved > 0 else 0,
            "not_improved": missed if type(missed) is int and missed > 0 else 0,
        }
    return counts


def contract_statuses(contract):
    """`{capability id: status}` from a public registry document, or None."""
    capabilities = contract.get("capabilities") if type(contract) is dict else None
    if type(capabilities) is not list:
        return None
    statuses = {}
    for item in capabilities:
        if type(item) is dict and type(item.get("id")) is str:
            statuses[item["id"]] = item.get("status")
    return statuses


def buildability(card, statuses, cues=None):
    """The capabilities a card names and their status under the contract."""
    cues = text_cues(_card_text(card)) if cues is None else cues
    named = [cid for cid, found in _CAPABILITY_SETS if cues & found]
    if statuses is None:
        return {
            "known": False,
            "capabilities": [{"id": cid, "status": None} for cid in named],
            "buildable": False,
            "capability_request_candidate": False,
        }
    rows = [{"id": cid, "status": statuses.get(cid, "not_registered")} for cid in named]
    buildable = any(row["status"] == REBUILDABLE for row in rows)
    outside = [row for row in rows if row["status"] != REBUILDABLE]
    return {
        "known": True,
        "capabilities": rows,
        "buildable": buildable,
        "capability_request_candidate": bool(outside),
    }


def assess(card, *, focus, statuses, counts, pinned=False, phrases=()):
    """The grade 0-3 and reasons for one card under one Challenge.

    Raw score (`SCORES`): 3 when the card names the Challenge's primary
    domain, 1 for a secondary domain, 1 for one of its methods, 1 when a
    capability it names is rebuildable for the Challenge, 1 when it names
    every term of one of the miner's focus `phrases`, and +1 or -1 from the
    miner's own practice outcomes on this Challenge (`counts`). Grade 3 from
    5, 2 from 3, 1 from 1. A card whose named capabilities are all outside
    the contract is not a plan input and grades at most 1.
    """
    text = _card_text(card)
    cues = text_cues(text)
    primary = sorted(cues & set(focus["primary_cues"]))
    secondary = sorted(cues & set(focus["secondary_cues"]))
    method = sorted(cues & set(focus["method_cues"]))
    relevance = (
        SCORES["primary_domain"]
        if primary
        else SCORES["secondary_domain"] if secondary else 0
    ) + (SCORES["method"] if method else 0)
    reasons = []
    if relevance:
        named = ", ".join((primary + secondary + method)[:4])
        reasons.append(f"focus: names {named}")
    else:
        reasons.append("focus: names none of the Challenge's public focus cues")
    if focus["small_data"] and cues & set(SMALL_DATA_CUES):
        reasons.append(
            "regime: a small-data method, and the Challenge's public training "
            f"set has {focus['train_cases']} cases"
        )
    build = buildability(card, statuses, cues)
    if not build["known"]:
        reasons.append("buildability: no public construction contract to check")
    elif not build["capabilities"]:
        reasons.append("buildability: names no registered capability")
    for row in build["capabilities"]:
        if row["status"] == REBUILDABLE:
            reasons.append(f"buildable: {row['id']} is rebuildable for this Challenge")
        elif build["known"]:
            reasons.append(
                f"capability_request candidate: {row['id']} is {row['status']} "
                "for this Challenge"
            )
    phrase = _phrase_hit(text, phrases)
    if phrase is not None:
        reasons.append("miner focus: names " + " ".join(phrase))
    count = counts.get(card.get("card_id"), {"improved": 0, "not_improved": 0})
    learning = 0
    if count["improved"] > count["not_improved"]:
        learning = SCORES["practice"]
    elif count["not_improved"] > count["improved"]:
        learning = -SCORES["practice"]
    if count["improved"] or count["not_improved"]:
        reasons.append(
            f"miner practice: {count['improved']} plan(s) citing it improved, "
            f"{count['not_improved']} did not"
        )
    raw = (
        relevance
        + (SCORES["buildable"] if build["buildable"] else 0)
        + (SCORES["miner_focus_terms"] if phrase is not None else 0)
        + learning
    )
    grade = next((g for low, g in GRADE_THRESHOLDS if raw >= low), 0)
    plan_input = build["buildable"] or not build["capability_request_candidate"]
    if not plan_input:
        grade = min(grade, NOT_PLAN_INPUT_MAX_GRADE)
        reasons.append("not a plan input: request the capability instead")
    if pinned:
        reasons.append("pinned by the miner: the Planner must consider it")
    return {
        "score": grade,
        "reasons": reasons,
        "pinned": bool(pinned),
        "buildable": build["buildable"],
        "capability_request_candidate": build["capability_request_candidate"],
        "plan_input": plan_input,
        "capabilities": build["capabilities"],
        "_order": (
            0 if pinned else 1,
            -grade,
            0 if plan_input else 1,
            -raw,
            -(len(primary) + len(secondary) + len(method)),
        ),
    }


@functools.lru_cache(maxsize=64)
def _registered_version(challenge_id):
    try:
        from carbon.challenge_registry import entries

        return next(
            (e.version for e in entries() if e.challenge_id == challenge_id), None
        )
    except (LookupError, ValueError, TypeError, OSError):  # none registered
        return None


@functools.lru_cache(maxsize=16)
def _public_context(challenge_id, version):
    discovery = contract = None
    try:
        from carbon.reconstruction.capability_registry import public_registry

        contract = public_registry(challenge_id)
    except (LookupError, ValueError, TypeError):  # no registered contract
        contract = None
    try:
        from carbon.challenge_registry import describe

        if version is not None:
            discovery = describe(challenge_id, version)
    except (LookupError, ValueError, TypeError, OSError):  # none registered
        discovery = None
    return discovery, contract


def challenge_id(challenge):
    if type(challenge) is dict:
        challenge = challenge.get("id")
    if type(challenge) is not str or not challenge:
        raise ValueError("a challenge is an id or an {id, version} mapping")
    return challenge


def challenge_ref(challenge):
    """`{id, version}`: the version given, else the registered one, else None.

    Practice outcomes and frozen literature are bound to this reference: a
    result on one Challenge (or version) never steers another's ranking.
    """
    cid = challenge_id(challenge)
    version = challenge.get("version") if type(challenge) is dict else None
    if version is not None and (type(version) is not str or not version):
        raise ValueError("a challenge version is text")
    return {"id": cid, "version": version or _registered_version(cid)}


def public_context(challenge):
    """`(discovery, contract)`: the Challenge's public discovery document and
    its public capability registry, or None for either Carbon does not have."""
    ref = challenge_ref(challenge)
    return _public_context(ref["id"], ref["version"])


def rank(
    cards,
    *,
    challenge,
    contract=None,
    evidence=None,
    discovery=None,
    pins=(),
    focus_terms=None,
):
    """`[(card, score, reasons)]`, best first, for one Challenge.

    `contract` is the Challenge's public registry document and `discovery`
    its public discovery document; either defaults to Carbon's own for the
    Challenge. `evidence` is the miner's own outcome counts on this
    Challenge. `focus_terms` are the miner's focus terms (as hunt queries).
    """
    if discovery is None or contract is None:
        found_discovery, found_contract = public_context(challenge)
        discovery = found_discovery if discovery is None else discovery
        contract = found_contract if contract is None else contract
    focus = discovery_focus(discovery)
    statuses = contract_statuses(contract)
    counts = _counts(evidence)
    phrases = focus_phrases(focus_terms)
    pinned = set(pins)
    rows = []
    for card in cards:
        result = assess(
            card,
            focus=focus,
            statuses=statuses,
            counts=counts,
            pinned=card.get("card_id") in pinned,
            phrases=phrases,
        )
        rows.append((result["_order"], _text_of(card, "card_id"), card, result))
    rows.sort(key=lambda row: (row[0], row[1]))
    return [(card, result["score"], result["reasons"]) for _, _, card, result in rows]


def query_hits(query, card):
    """How many distinct words of a search query a card's text holds."""
    words = _words(_card_text(card) + " | " + _lower(_text_of(card, "card_id")))
    return sum(1 for term in set(_WORD.findall(_lower(query))) if term in words)
