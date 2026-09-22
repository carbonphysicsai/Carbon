(function (root) {
  "use strict";
  // The public onboarding edition's own workspace identity.
  //
  // Deliberately not the internal goal workspace. That schema pins
  // `source_sha256` constants to the internal build, so a public edition
  // carrying it would either be lying about which build produced it or would
  // have to be regenerated every time the internal bundle moved. A separate
  // identity also keeps the two import paths honest: the internal Workbench can
  // tell a visitor's draft from its own workspace without inspecting content.
  const WORKSPACE = "carbon.public-workbench.workspace.v1";

  // Every scope field the internal design carries. The structural check reads
  // eleven of them; the design requires all eighteen, so a draft that supplies
  // all eighteen can be imported without the internal side inventing values.
  const SCOPE_FIELDS = [
    "physics_family",
    "requested_goal",
    "intended_use",
    "inputs",
    "outputs",
    "units",
    "geometry",
    "conditions",
    "regime",
    "exclusions",
    "query_workload",
    "turnaround",
    "failure_consequences",
    "data_access",
    "rights_scope",
    "commercial_context",
    "disclosure_scope",
    "deployment_environment",
  ];
  // The two reference-plan fields the check reads. The internal plan has ten;
  // the rest are Carbon's to fill and a visitor is not asked to guess them.
  const REFERENCE_FIELDS = ["equation", "method"];

  // What a visitor is asked first, and what only appears once the shape of the
  // problem is known. Progressive disclosure is an ordering over the same
  // fields, not a reduced set: an expert can open every stage at once and fill
  // them directly, and nothing is withheld from someone who asks for it.
  const STAGES = [
    {
      id: "problem",
      title: "What are you trying to predict?",
      fields: ["requested_goal", "physics_family", "intended_use"],
    },
    {
      id: "physical",
      title: "What goes in, and what comes out?",
      fields: ["inputs", "outputs", "units", "geometry", "conditions"],
    },
    {
      id: "operating",
      title: "Where does it have to hold?",
      fields: ["regime", "exclusions", "query_workload", "turnaround"],
    },
    {
      id: "reference",
      title: "What do you compare against today?",
      fields: ["reference_plan.equation", "reference_plan.method"],
    },
    {
      id: "constraints",
      title: "What are we allowed to use?",
      fields: [
        "rights_scope",
        "data_access",
        "failure_consequences",
        "commercial_context",
        "disclosure_scope",
        "deployment_environment",
      ],
    },
  ];

  // Plain-language help for the issues the accepted check returns.
  //
  // This is presentation only. Each entry is matched against the check's own
  // text and adds a sentence about what to do; the check's wording is always
  // shown as well, and an issue this table does not recognise is surfaced
  // unchanged rather than dropped. No issue class is invented here, none is
  // reworded into something weaker, and none is suppressed.
  const GUIDANCE = [
    {
      match: /^Missing (inputs|outputs|units|geometry|conditions)\.$/,
      owner: "VISITOR",
      plain: (m) =>
        ({
          inputs: "Say what the model would be given: the quantities you can supply for each prediction.",
          outputs: "Say what the model would return, and at what points or times.",
          units: "State the units, or say the problem is dimensionless. Ambiguous units cannot be checked.",
          geometry: "Describe the domain: its shape, extent and whether it repeats.",
          conditions: "Describe the boundary and initial conditions. Without them the problem is not determined.",
        })[m[1]],
    },
    {
      match: /^Missing governing equation\.$/,
      owner: "VISITOR",
      plain: () =>
        "Name the equation you believe governs this, even approximately. A named equation Carbon disagrees with is more useful than none.",
    },
    {
      match: /dimensional units/,
      owner: "VISITOR",
      plain: () =>
        "The available source study is dimensionless. Either restate the scope in dimensionless terms or expect a conversion step that Carbon has not yet built.",
    },
    {
      match: /boundary or forcing condition outside/,
      owner: "VISITOR",
      plain: () =>
        "The available source study is unforced and periodic. A different condition is a real problem to discuss, not one this template can check.",
    },
    {
      match: /^Only the public periodic Burgers source template is available\.$/,
      owner: "CARBON",
      plain: () =>
        "Carbon has one source study available today, so this draft cannot be checked against your physics yet. Send it anyway: the scope is what the conversation needs.",
    },
    {
      match: /^The source template requires the Dynamics goal\.$/,
      owner: "CARBON",
      plain: () =>
        "The one available source study answers a dynamics question. A different goal is recorded and discussed rather than checked.",
    },
    {
      match: /rights are unavailable for this public-source study/,
      owner: "VISITOR",
      plain: () =>
        "State whether the data involved is synthetic, internal, or third-party. Unresolved rights stop a study before any physics does.",
    },
    {
      match: /^Adopt the private service's exact public-source physical definition\.$/,
      owner: "CARBON",
      plain: () =>
        "The exact numerical definition of the source study is held by Carbon and is attached when the team imports this draft. Nothing you can type closes this one.",
    },
  ];

  const clone = (value) => JSON.parse(JSON.stringify(value));

  function identity(value, label) {
    if (typeof value !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(value))
      throw Error("Invalid " + label);
    return value;
  }

  function boundedText(value, label) {
    // The internal design's own bound. A public draft that exceeded it would be
    // rejected on import, which is a worse place to learn about it.
    if (typeof value !== "string" || value.length > 8000)
      throw Error("Invalid " + label);
    return value;
  }

  function emptyDraft(designId, revision = 1) {
    return {
      schema_version: WORKSPACE,
      design_id: identity(designId, "design ID"),
      revision: revision,
      scope: Object.fromEntries(SCOPE_FIELDS.map((field) => [field, ""])),
      reference_plan: Object.fromEntries(REFERENCE_FIELDS.map((field) => [field, ""])),
    };
  }

  /** The design-shaped value the accepted structural check reads.
   *
   * The check is given exactly what it asks for and nothing else, so the public
   * edition cannot influence its result by supplying extra state.
   */
  function checkable(draft) {
    return {
      scope: clone(draft.scope),
      reference_plan: clone(draft.reference_plan),
    };
  }

  /** Run the accepted check and attach plain language to what it returned.
   *
   * The returned `status`, `issues`, `qualification` and `limitations` are the
   * check's own values, passed through untouched. `explained` is a parallel view
   * for a non-expert: same length, same order, every issue present.
   */
  function explain(result) {
    const explained = result.issues.map((issue) => {
      for (const entry of GUIDANCE) {
        const matched = entry.match.exec(issue);
        if (matched) return { issue, owner: entry.owner, plain: entry.plain(matched) };
      }
      // An issue this table has never seen. It is shown with its own wording and
      // marked as nobody's to close, because guessing an owner for it would be
      // the moment a real blocker started looking like a formality.
      return { issue, owner: "UNCLASSIFIED", plain: issue };
    });
    return {
      status: result.status,
      qualification: result.qualification,
      limitations: result.limitations,
      issues: [...result.issues],
      explained,
      // What the visitor can still do something about, and what they cannot.
      // A count, not a verdict: the status above is the check's.
      open_for_visitor: explained.filter((item) => item.owner === "VISITOR").length,
      held_by_carbon: explained.filter((item) => item.owner === "CARBON").length,
      unclassified: explained.filter((item) => item.owner === "UNCLASSIFIED").length,
    };
  }

  function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === "object")
      return Object.fromEntries(
        Object.keys(value)
          .sort()
          .map((key) => [key, canonical(value[key])]),
      );
    return value;
  }

  /** Export the draft as a canonical artifact carrying its own digest.
   *
   * Deterministic: the same draft content, identity and revision produce the
   * same bytes, so two exports can be compared without interpreting them. The
   * digest is computed with the accepted study module's own digest function
   * rather than a second implementation.
   */
  async function exportWorkspace(draft, result, studies) {
    validateDraft(draft);
    const body = {
      schema_version: WORKSPACE,
      design_id: draft.design_id,
      revision: draft.revision,
      scope: clone(draft.scope),
      reference_plan: clone(draft.reference_plan),
      // The check result as the check returned it, so the internal side can
      // compare rather than take the artifact's word for it.
      structural_check: {
        status: result.status,
        issues: [...result.issues],
        qualification: result.qualification,
      },
      // Said in the artifact itself, because an artifact travels away from the
      // page that produced it and arrives without its context.
      authority: {
        effect: "NONE",
        qualification: "NOT_QUALIFIED",
        statement:
          "A client-authored scoping draft. It qualifies no physics, measures " +
          "nothing, and commits Carbon to no capability, cost or timeline.",
      },
    };
    const digest = await studies.digest(canonical(body));
    return { ...canonical(body), digest: "sha256:" + digest };
  }

  function validateDraft(draft) {
    if (!draft || typeof draft !== "object") throw Error("Invalid public draft");
    if (draft.schema_version !== WORKSPACE) throw Error("Unsupported public workspace version");
    identity(draft.design_id, "design ID");
    if (!Number.isSafeInteger(draft.revision) || draft.revision < 1)
      throw Error("Invalid design revision");
    const scopeKeys = Object.keys(draft.scope || {}).sort();
    if (scopeKeys.join("|") !== [...SCOPE_FIELDS].sort().join("|"))
      throw Error("Public draft scope fields are closed");
    for (const field of SCOPE_FIELDS) boundedText(draft.scope[field], "scope " + field);
    const referenceKeys = Object.keys(draft.reference_plan || {}).sort();
    if (referenceKeys.join("|") !== [...REFERENCE_FIELDS].sort().join("|"))
      throw Error("Public draft reference fields are closed");
    for (const field of REFERENCE_FIELDS)
      boundedText(draft.reference_plan[field], "reference " + field);
    return draft;
  }

  /** Validate an exported artifact, including its own digest. */
  async function validateArtifact(value, studies) {
    if (!value || typeof value !== "object") throw Error("Invalid public workspace artifact");
    const keys = Object.keys(value).sort().join("|");
    const expected = [
      "authority",
      "design_id",
      "digest",
      "reference_plan",
      "revision",
      "schema_version",
      "scope",
      "structural_check",
    ].join("|");
    if (keys !== expected) throw Error("Public workspace artifact fields are closed");
    validateDraft({
      schema_version: value.schema_version,
      design_id: value.design_id,
      revision: value.revision,
      scope: value.scope,
      reference_plan: value.reference_plan,
    });
    if (value.authority.effect !== "NONE" || value.authority.qualification !== "NOT_QUALIFIED")
      throw Error("A public artifact carries no authority and cannot claim any");
    if (!/^sha256:[a-f0-9]{64}$/.test(value.digest)) throw Error("Invalid artifact digest");
    const { digest, ...body } = value;
    const recomputed = "sha256:" + (await studies.digest(canonical(body)));
    if (recomputed !== value.digest) throw Error("Artifact digest does not match its content");
    return clone(value);
  }

  const api = Object.freeze({
    WORKSPACE,
    SCOPE_FIELDS,
    REFERENCE_FIELDS,
    STAGES,
    GUIDANCE,
    emptyDraft,
    checkable,
    explain,
    exportWorkspace,
    validateDraft,
    validateArtifact,
    canonical,
  });
  root.CarbonPublicWorkbench = api;
  if (typeof module !== "undefined") module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
