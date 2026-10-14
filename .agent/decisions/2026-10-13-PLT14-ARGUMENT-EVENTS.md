# PLT-14: positive projections and exact canary preservation

Classification: IMPLEMENTATION_LAG. Successful tool events omit arguments;
refusals log raw arguments to support the controller's canary scan. The queue
explicitly authorizes complete events with an allow-list and protected-value
exclusion. It grants no deployment or security-acceptance authority.

Use a versioned, fixed projection; do not copy arbitrary fields or trust a
field name to make its free-text value public. Redact free text and private
identifiers instead of hashing them. Preserve selected action/numeric settings
for operational comparisons and report redaction explicitly.

Observe at the loop's response boundary so engine/rejected/not-run calls count.
The optional observer does not affect prompts, tools, budgets, domain results
or the historical epoch-plan bytes. New session records freeze its policy.

Preserve exact configured-canary matching through a Boolean provider lookup
against the call intent already retained by the loop. The controller receives
no raw token, token digest or new private archive. Missing/corrupt intent is
unavailable evidence and fails closed; it never means no exposure. Other
providers retain their existing event scan. Dedicated disclosure review belongs
to Carbon Validator on this PR; no security qualification is declared.
