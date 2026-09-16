(function (root) {
  "use strict";

  const DRAFT_VERSION = "carbon.client-intake.draft.v1";
  const MAPPING_VERSION = "carbon.client-intake.mapping.v1";
  const REVIEW_VERSION = "carbon.client-intake.reviewed.v1";
  const GUIDANCE_VERSION = "carbon.client-intake.guidance.v1";
  const LOCAL_SCOPE = "LOCAL_SYNTHETIC_DEVELOPMENT_NOT_TRANSMITTED";
  const REVIEW_SCOPE = "LOCAL_REVIEW_PACKAGE_NOT_SUBMITTED";
  const TEXT_FIELDS = [
    "intended_decision",
    "requested_result",
    "current_baseline",
    "baseline_limitation",
    "changing_conditions",
    "exclusions",
    "consequential_error",
    "comparison_evidence",
    "access_limitations",
  ];
  const QUANTITY_FIELDS = [
    "preparation_time",
    "prediction_latency",
    "reference_query_time",
    "workload_frequency",
    "desired_accuracy",
  ];
  const PILOT_FIELDS = [
    "candidate_inputs",
    "candidate_outputs",
    "operating_envelope",
    "evaluation_questions",
    "requested_targets",
    "missing_evidence",
    "implementation_work",
    "bounded_first_pilot",
    "next_discussion",
  ];
  const clone = (value) => JSON.parse(JSON.stringify(value));

  function exact(value, keys, label) {
    const proto = value && Object.getPrototypeOf(value);
    if (!value || (proto !== Object.prototype && proto !== null))
      throw Error(label + " must be an object");
    const actual = Object.keys(value).sort();
    const expected = [...keys].sort();
    if (
      actual.length !== expected.length ||
      actual.some((key, index) => key !== expected[index])
    )
      throw Error(label + " has unsupported or missing fields");
    return value;
  }

  function text(value, label, limit = 8000, required = false) {
    if (
      typeof value !== "string" ||
      value.length > limit ||
      (required && !value.trim())
    )
      throw Error("Invalid " + label);
    return value;
  }

  function ident(value, label) {
    if (
      typeof value !== "string" ||
      !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(value)
    )
      throw Error("Invalid " + label);
    return value;
  }

  function textAnswer(value, label) {
    exact(value, ["state", "value", "origin"], label);
    if (!['UNKNOWN', 'VALUE'].includes(value.state))
      throw Error("Invalid " + label + " state");
    text(value.value, label + " value");
    if (value.origin !== "USER_ENTERED_LOCAL")
      throw Error("Invalid " + label + " origin");
    if (value.state === "UNKNOWN" && value.value !== "")
      throw Error(label + " unknown value must be empty");
    if (value.state === "VALUE" && !value.value.trim())
      throw Error(label + " value is required");
    return clone(value);
  }

  function finiteOrNull(value, label) {
    if (value === null) return null;
    if (typeof value !== "number" || !Number.isFinite(value))
      throw Error("Invalid " + label);
    return value;
  }

  function quantityAnswer(value, label) {
    exact(value, ["state", "value", "minimum", "maximum", "unit", "note", "origin"], label);
    if (!['UNKNOWN', 'POINT', 'RANGE'].includes(value.state))
      throw Error("Invalid " + label + " state");
    const point = finiteOrNull(value.value, label + " value");
    const minimum = finiteOrNull(value.minimum, label + " minimum");
    const maximum = finiteOrNull(value.maximum, label + " maximum");
    text(value.unit, label + " unit", 120);
    text(value.note, label + " note", 1000);
    if (value.origin !== "USER_ENTERED_LOCAL")
      throw Error("Invalid " + label + " origin");
    if (value.state === "UNKNOWN" && [point, minimum, maximum].some((x) => x !== null))
      throw Error(label + " unknown quantity cannot contain values");
    if (value.state === "POINT" && (point === null || minimum !== null || maximum !== null))
      throw Error(label + " point quantity is malformed");
    if (
      value.state === "RANGE" &&
      (point !== null || minimum === null || maximum === null || minimum > maximum)
    )
      throw Error(label + " range is malformed");
    if (value.state !== "UNKNOWN" && !value.unit.trim())
      throw Error(label + " unit is required");
    return clone(value);
  }

  function emptyTextAnswer() {
    return { state: "UNKNOWN", value: "", origin: "USER_ENTERED_LOCAL" };
  }

  function emptyQuantityAnswer() {
    return {
      state: "UNKNOWN",
      value: null,
      minimum: null,
      maximum: null,
      unit: "",
      note: "",
      origin: "USER_ENTERED_LOCAL",
    };
  }

  function newDraft(draftId = "local-inquiry-001", revisionId = "rev-001") {
    const answers = {};
    for (const field of TEXT_FIELDS) answers[field] = emptyTextAnswer();
    const quantities = {};
    for (const field of QUANTITY_FIELDS)
      quantities[field] = emptyQuantityAnswer();
    return {
      schema_version: DRAFT_VERSION,
      draft_id: ident(draftId, "draft ID"),
      revision_id: ident(revisionId, "revision ID"),
      predecessor: null,
      answers,
      quantities,
      summary: {
        mapping_version: MAPPING_VERSION,
        text: "",
        unknown_fields: [],
        next_clarification: "",
      },
      source: {
        application: "Carbon Client Intake Preview",
        mapping_version: MAPPING_VERSION,
        local_scope: LOCAL_SCOPE,
      },
    };
  }

  function quantityText(value) {
    if (value.state === "UNKNOWN") return "unknown";
    if (value.state === "POINT") return `${value.value} ${value.unit}`;
    return `${value.minimum}–${value.maximum} ${value.unit}`;
  }

  function summaryFor(draft) {
    const unknown = [
      ...TEXT_FIELDS.filter((field) => draft.answers[field].state === "UNKNOWN"),
      ...QUANTITY_FIELDS.filter(
        (field) => draft.quantities[field].state === "UNKNOWN",
      ),
    ];
    const answer = (field) =>
      draft.answers[field].state === "VALUE"
        ? draft.answers[field].value
        : "Unknown";
    const lines = [
      `Decision: ${answer("intended_decision")}`,
      `Requested result: ${answer("requested_result")}`,
      `Current baseline: ${answer("current_baseline")}`,
      `Reported limitation: ${answer("baseline_limitation")}`,
      `Changing conditions: ${answer("changing_conditions")}`,
      `Exclusions: ${answer("exclusions")}`,
      `Consequential error: ${answer("consequential_error")}`,
      `Comparison evidence (claimed): ${answer("comparison_evidence")}`,
      `Access/use limitations: ${answer("access_limitations")}`,
      `Preparation time: ${quantityText(draft.quantities.preparation_time)}`,
      `Recurring prediction latency: ${quantityText(draft.quantities.prediction_latency)}`,
      `Reference-query time: ${quantityText(draft.quantities.reference_query_time)}`,
      `Workload frequency: ${quantityText(draft.quantities.workload_frequency)}`,
      `Requested accuracy: ${quantityText(draft.quantities.desired_accuracy)} (unreviewed client intent)`,
    ];
    return {
      mapping_version: MAPPING_VERSION,
      text: lines.join("\n"),
      unknown_fields: unknown,
      next_clarification: unknown.length
        ? `Clarify ${unknown[0].replaceAll("_", " ")} without supplying sensitive data.`
        : "Operator review is required before route or scientific interpretation.",
    };
  }

  function validateDraft(value) {
    exact(
      value,
      ["schema_version", "draft_id", "revision_id", "predecessor", "answers", "quantities", "summary", "source"],
      "intake draft",
    );
    if (value.schema_version !== DRAFT_VERSION)
      throw Error("Unsupported intake draft version");
    ident(value.draft_id, "draft ID");
    ident(value.revision_id, "revision ID");
    if (value.predecessor !== null) {
      exact(value.predecessor, ["draft_id", "revision_id", "canonical_digest"], "predecessor");
      ident(value.predecessor.draft_id, "predecessor draft ID");
      ident(value.predecessor.revision_id, "predecessor revision ID");
      if (!/^sha256:[0-9a-f]{64}$/.test(value.predecessor.canonical_digest))
        throw Error("Invalid predecessor digest");
      if (value.predecessor.draft_id !== value.draft_id)
        throw Error("A successor must retain its draft identity");
    }
    exact(value.answers, TEXT_FIELDS, "intake answers");
    for (const field of TEXT_FIELDS)
      textAnswer(value.answers[field], field);
    exact(value.quantities, QUANTITY_FIELDS, "intake quantities");
    for (const field of QUANTITY_FIELDS)
      quantityAnswer(value.quantities[field], field);
    exact(value.summary, ["mapping_version", "text", "unknown_fields", "next_clarification"], "intake summary");
    if (value.summary.mapping_version !== MAPPING_VERSION)
      throw Error("Unsupported intake mapping version");
    text(value.summary.text, "summary text", 24000);
    if (!Array.isArray(value.summary.unknown_fields) || value.summary.unknown_fields.some((x) => ![...TEXT_FIELDS, ...QUANTITY_FIELDS].includes(x)))
      throw Error("Invalid intake unknown fields");
    text(value.summary.next_clarification, "next clarification", 1000);
    exact(value.source, ["application", "mapping_version", "local_scope"], "intake source");
    if (
      value.source.application !== "Carbon Client Intake Preview" ||
      value.source.mapping_version !== MAPPING_VERSION ||
      value.source.local_scope !== LOCAL_SCOPE
    )
      throw Error("Invalid intake source boundary");
    const expected = summaryFor(value);
    if (JSON.stringify(value.summary) !== JSON.stringify(expected))
      throw Error("Intake summary does not match the deterministic mapping");
    return clone(value);
  }

  function nullableText(value, label, limit = 8000) {
    if (value === null) return null;
    return text(value, label, limit);
  }

  function validateReviewedPackage(value) {
    exact(value, ["schema_version", "brief", "pilot", "field_provenance", "accepted_suggestions", "unresolved_assumptions", "ai_guidance", "sharing", "contact", "local_scope"], "reviewed intake package");
    if (value.schema_version !== REVIEW_VERSION || value.local_scope !== REVIEW_SCOPE)
      throw Error("Unsupported reviewed intake package");
    const brief = validateDraft(value.brief);
    exact(value.pilot, ["label", ...PILOT_FIELDS], "draft pilot");
    if (value.pilot.label !== "Draft pilot for Carbon review")
      throw Error("Invalid draft pilot label");
    for (const field of PILOT_FIELDS) text(value.pilot[field], "pilot " + field);
    if (!Array.isArray(value.field_provenance) || value.field_provenance.length > 64)
      throw Error("Invalid field provenance");
    const allowedFields = new Set([...TEXT_FIELDS, ...QUANTITY_FIELDS, ...PILOT_FIELDS.map((field) => "pilot." + field)]);
    const suggestibleFields = new Set([...TEXT_FIELDS, ...PILOT_FIELDS.map((field) => "pilot." + field)]);
    const seenFields = new Set();
    for (const item of value.field_provenance) {
      exact(item, ["field", "origin", "suggestion_id"], "field provenance");
      if (!allowedFields.has(item.field) || seenFields.has(item.field)) throw Error("Invalid field provenance field");
      seenFields.add(item.field);
      if (!["CLIENT_TYPED", "AI_SUGGESTED_CLIENT_ACCEPTED", "UNKNOWN"].includes(item.origin)) throw Error("Invalid field provenance origin");
      nullableText(item.suggestion_id, "suggestion ID", 128);
      if (item.origin === "AI_SUGGESTED_CLIENT_ACCEPTED" && !item.suggestion_id) throw Error("Accepted AI provenance requires a suggestion ID");
    }
    if (seenFields.size !== allowedFields.size) throw Error("Field provenance must cover every reviewable field");
    if (!Array.isArray(value.accepted_suggestions) || value.accepted_suggestions.length > 64)
      throw Error("Invalid accepted suggestions");
    const suggestionIds = new Set();
    for (const item of value.accepted_suggestions) {
      exact(item, ["suggestion_id", "field", "proposed_value", "rationale", "accepted_at"], "accepted suggestion");
      ident(item.suggestion_id, "suggestion ID");
      if (suggestionIds.has(item.suggestion_id)) throw Error("Duplicate accepted suggestion ID");
      suggestionIds.add(item.suggestion_id);
      if (!suggestibleFields.has(item.field)) throw Error("Invalid suggestion field");
      text(item.proposed_value, "suggested value");
      text(item.rationale, "suggestion rationale", 1200);
      text(item.accepted_at, "suggestion acceptance time", 64, true);
      const provenance = value.field_provenance.find((entry) => entry.field === item.field);
      if (provenance?.origin !== "AI_SUGGESTED_CLIENT_ACCEPTED" || provenance.suggestion_id !== item.suggestion_id)
        throw Error("Accepted suggestion does not match field provenance");
      const current = item.field.startsWith("pilot.")
        ? value.pilot[item.field.slice("pilot.".length)]
        : brief.answers[item.field]?.value;
      if (current !== item.proposed_value) throw Error("Accepted suggestion does not match the current field value");
    }
    if (!Array.isArray(value.unresolved_assumptions) || value.unresolved_assumptions.length > 32 || value.unresolved_assumptions.some((item) => typeof item !== "string" || !item.trim() || item.length > 1200))
      throw Error("Invalid unresolved assumptions");
    exact(value.ai_guidance, ["enabled", "provider", "guidance_version", "notice_version", "consented_at", "cleared_locally"], "AI guidance record");
    if (typeof value.ai_guidance.enabled !== "boolean" || typeof value.ai_guidance.cleared_locally !== "boolean") throw Error("Invalid AI guidance flags");
    if (value.ai_guidance.guidance_version !== GUIDANCE_VERSION) throw Error("Unsupported guidance version");
    nullableText(value.ai_guidance.provider, "AI provider", 120);
    nullableText(value.ai_guidance.notice_version, "notice version", 128);
    nullableText(value.ai_guidance.consented_at, "consent time", 64);
    if (value.ai_guidance.enabled && (value.ai_guidance.provider !== "OPENAI_API" || !value.ai_guidance.notice_version || !value.ai_guidance.consented_at))
      throw Error("Enabled AI guidance requires provider and consent details");
    if (!value.ai_guidance.enabled && (value.ai_guidance.provider !== null || value.ai_guidance.notice_version !== null || value.ai_guidance.consented_at !== null))
      throw Error("Disabled AI guidance cannot claim consent");
    exact(value.sharing, ["include_conversation", "conversation"], "sharing choice");
    if (typeof value.sharing.include_conversation !== "boolean" || !Array.isArray(value.sharing.conversation) || value.sharing.conversation.length > 32)
      throw Error("Invalid conversation sharing choice");
    if (!value.sharing.include_conversation && value.sharing.conversation.length) throw Error("Conversation history requires explicit inclusion");
    for (const turn of value.sharing.conversation) {
      exact(turn, ["turn_id", "role", "text"], "conversation turn");
      ident(turn.turn_id, "conversation turn ID");
      if (!["CLIENT", "ASSISTANT"].includes(turn.role)) throw Error("Invalid conversation role");
      text(turn.text, "conversation text", 4000, true);
    }
    exact(value.contact, ["name", "email", "organization"], "contact details");
    text(value.contact.name, "contact name", 300);
    text(value.contact.email, "contact email", 320);
    text(value.contact.organization, "contact organization", 300);
    return { ...clone(value), brief };
  }

  function draftFromTransport(value) {
    if (value?.schema_version === REVIEW_VERSION) return validateReviewedPackage(value).brief;
    return validateDraft(value);
  }

  function canonical(value) {
    const validated = validateDraft(value);
    function stable(item) {
      if (Array.isArray(item)) return item.map(stable);
      if (item && typeof item === "object")
        return Object.fromEntries(
          Object.keys(item)
            .sort()
            .map((key) => [key, stable(item[key])]),
        );
      return item;
    }
    return JSON.stringify(stable(validated));
  }

  async function sha256(textValue) {
    if (!root.crypto || !root.crypto.subtle)
      throw Error("Web Crypto is required for intake identity");
    const bytes = new TextEncoder().encode(textValue);
    const digest = await root.crypto.subtle.digest("SHA-256", bytes);
    return (
      "sha256:" +
      [...new Uint8Array(digest)]
        .map((value) => value.toString(16).padStart(2, "0"))
        .join("")
    );
  }

  async function inspect(raw, strictParser) {
    if (typeof raw !== "string" || new TextEncoder().encode(raw).length > 120000)
      throw Error("Intake draft exceeds 120 KB");
    const parsed = strictParser(raw, { maxBytes: 120000, maxDepth: 10 });
    const reviewed = parsed?.schema_version === REVIEW_VERSION ? validateReviewedPackage(parsed) : null;
    const draft = reviewed ? reviewed.brief : validateDraft(parsed);
    return {
      draft,
      review_package: reviewed,
      transport_kind: reviewed ? "REVIEWED_PACKAGE" : "LOCAL_DRAFT",
      raw_json: raw,
      raw_sha256: await sha256(raw),
      canonical_digest: await sha256(canonical(draft)),
    };
  }

  function mapDraft(draft, canonicalDigest, reviewed = null) {
    validateDraft(draft);
    if (reviewed) validateReviewedPackage(reviewed);
    const value = (field) =>
      draft.answers[field].state === "VALUE" ? draft.answers[field].value : "";
    const quantities = draft.quantities;
    const timing = [
      `preparation ${quantityText(quantities.preparation_time)}`,
      `prediction ${quantityText(quantities.prediction_latency)}`,
      `reference query ${quantityText(quantities.reference_query_time)}`,
      `workload ${quantityText(quantities.workload_frequency)}`,
    ].join("; ");
    const requirements = [];
    if (value("consequential_error"))
      requirements.push({
        original_words: value("consequential_error"),
        source_reference: `intake:${canonicalDigest}#answers.consequential_error`,
        consequence: "Client-reported consequential error; Carbon review required.",
        kind: "MATERIAL",
      });
    if (quantities.desired_accuracy.state !== "UNKNOWN")
      requirements.push({
        original_words: `Requested accuracy: ${quantityText(quantities.desired_accuracy)}`,
        source_reference: `intake:${canonicalDigest}#quantities.desired_accuracy`,
        consequence: "Requested target only; not an accepted scientific tolerance.",
        kind: "PREFERENCE",
      });
    return {
      title: (value("requested_result") || value("intended_decision") || "Unreviewed local inquiry").slice(0, 300),
      assignment: {
        client_words: draft.summary.text + (reviewed?.pilot?.bounded_first_pilot ? `\n\nDraft pilot for Carbon review: ${reviewed.pilot.bounded_first_pilot}` : ""),
        client_source: `LOCAL_INTAKE ${draft.draft_id}/${draft.revision_id} ${canonicalDigest}`,
        intended_decision: value("intended_decision"),
        credible_baseline: [value("current_baseline"), value("baseline_limitation")].filter(Boolean).join(" — "),
        context: value("changing_conditions"),
        allowances: "No execution allowance supplied by local intake.",
        rights_summary: value("access_limitations") || "UNRESOLVED",
        next_owner_decision: reviewed?.pilot?.next_discussion || draft.summary.next_clarification,
      },
      scope: {
        intended_use: value("intended_decision"),
        outputs: reviewed?.pilot?.candidate_outputs || value("requested_result"),
        conditions: reviewed?.pilot?.operating_envelope || value("changing_conditions"),
        exclusions: value("exclusions"),
        query_workload: timing,
        turnaround: `Recurring prediction latency: ${quantityText(quantities.prediction_latency)}; reference-query time: ${quantityText(quantities.reference_query_time)}`,
        failure_consequences: value("consequential_error"),
        data_access: value("comparison_evidence") || "UNRESOLVED",
        rights_scope: "UNRESOLVED",
      },
      requirements,
      unknown_fields: clone(draft.summary.unknown_fields),
    };
  }

  const api = {
    DRAFT_VERSION,
    MAPPING_VERSION,
    LOCAL_SCOPE,
    REVIEW_VERSION,
    GUIDANCE_VERSION,
    REVIEW_SCOPE,
    TEXT_FIELDS,
    QUANTITY_FIELDS,
    PILOT_FIELDS,
    newDraft,
    summaryFor,
    validateDraft,
    validateReviewedPackage,
    draftFromTransport,
    canonical,
    inspect,
    mapDraft,
    sha256,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CarbonClientIntake = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
