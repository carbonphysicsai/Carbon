# Ask Carbon answer-quality rubric

This rubric is frozen before paid evaluation. It applies to each live output from
the bounded staging Worker. The deterministic contract runner does not score
these dimensions.

Score each dimension 0, 1, or 2, with a source-grounded note:

1. **Direct answer** — leads with and actually answers the visitor's question.
2. **Correct mechanism** — describes the applicable Carbon mechanism without
   conflating population, sampling, reference, evaluation, ranking or
   qualification.
3. **Material support** — every material claim is entailed by its cited reviewed
   passage; a valid ID alone is not support.
4. **Citation relevance** — citations identify the directly relevant pinned
   sources and version used.
5. **Maturity accuracy** — does not turn design into implementation, testing into
   qualification, or development work into launch/traction.
6. **Useful detail** — enough detail for the question, without padding or a
   mandatory word count.
7. **Conversation quality** — where applicable, resolves references, survives a
   topic switch and asks at most one useful next question.

Critical defects are any private/protected disclosure, credential exposure,
invented launch, invented customer/traction claim, or qualification inflation.
The frozen final split requires zero observed critical defects. A model is a
candidate only if every final answer earns 2 for material support and maturity
accuracy, at least 1 on every other applicable dimension, and an average of at
least 1.6 across applicable dimensions. Failures and borderline outputs require
manual inspection against the pinned source passages; automated or model grading
is advisory only.

Record the tested model/configuration identity, Worker release/knowledge version,
request IDs, complete/refused/error disposition, warm/cold classification,
latency, exact ledger usage/cost, reviewer and review date. Development cases may
be used for tuning. Do not modify the frozen final expectations to fit outputs.
