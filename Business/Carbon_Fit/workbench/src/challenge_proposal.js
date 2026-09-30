// A proposed Challenge from a client's brief (GOAL-WORKBENCH-16 slice 2).
//
// Pure and deterministic: the same brief and the same family record always give
// the same proposal. It runs in the client's browser over the public family
// record (data/challenge_families_v1.json), which relays Carbon's launch-
// portfolio readiness records and the exam-design evidence behind each setting.
//
// What it decides and what it does not:
// - It suggests families by matching the client's own words and physics. The
//   suggestion is a starting point for Carbon review, not an assessment of fit.
// - For a family with exam-design evidence it proposes that family's tested
//   settings, each with the measurements that chose it. The settings are the
//   campaign's recommendations with the readiness record's status: proposed,
//   not approved, and not scientifically qualified.
// - A condition the client did not give is proposed from the design Carbon
//   tested and labelled as such. A client range outside the tested range is
//   reported as outside the evidence. Nothing is invented, no unit is
//   converted, and nothing here registers, runs, prices or approves anything.
(function (root) {
  "use strict";

  const PROPOSAL_VERSION = "carbon.pilot-designer.proposal.v1";
  const KIND = Object.freeze({
    EVIDENCE: "EVIDENCE_BACKED_PROPOSAL",
    SCOPED: "SCOPED_FAMILY_NO_EVIDENCE",
    NONE: "NO_FAMILY_MATCH",
  });
  // Spelling variants only. No conversion between units is ever made.
  const UNIT_SPELLINGS = {
    degc: ["degc", "°c", "celsius", "deg c", "degrees c", "degrees celsius"],
    "c-rate": ["c-rate", "c rate", "crate"],
    "1": ["1", "", "fraction", "-"],
    v: ["v", "volt", "volts"],
    "a.h": ["a.h", "ah", "a h", "amp-hour", "amp hours"],
  };

  const lower = (value) => String(value || "").toLowerCase();
  const escaped = (term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // A whole-word match, so "cell" does not match "excellent".
  const contains = (text, term) => new RegExp("(^|[^a-z0-9])" + escaped(lower(term)) + "($|[^a-z0-9])").test(text);

  function unitKey(unit) {
    const u = lower(unit).trim();
    for (const [key, spellings] of Object.entries(UNIT_SPELLINGS)) if (spellings.includes(u)) return key;
    return u;
  }

  // The client's own words, as the brief records them.
  function clientText(draft) {
    const parts = Object.values(draft.answers).map((a) => (a.state === "VALUE" ? a.value : ""));
    const system = draft.system;
    if (system) {
      for (const c of system.components) parts.push(c.name, c.regime);
      for (const r of system.inputs) parts.push(r.name, r.definition);
      for (const r of system.outputs) parts.push(r.name, r.purpose);
      for (const r of system.couplings) parts.push(r.quantity);
      parts.push(system.notes);
    }
    return lower(parts.filter(Boolean).join(" \n "));
  }

  function match(draft, record) {
    const text = clientText(draft);
    const physics = new Set((draft.system?.components || []).map((c) => c.physics));
    return record.families
      .map((family, order) => ({
        family_id: family.id,
        title: family.title,
        keywords: family.matching.keywords.filter((k) => contains(text, k)),
        physics: family.matching.physics.filter((p) => physics.has(p)),
        evidence: family.evidence !== null,
        order,
      }))
      .filter((m) => m.keywords.length || m.physics.length)
      .sort((a, b) => b.keywords.length - a.keywords.length || b.physics.length - a.physics.length || a.order - b.order)
      .map(({ order, ...rest }) => rest);
  }

  function rangeOf(input) {
    return input.min === null && input.max === null ? null : [input.min, input.max];
  }

  // One family variable against the client's inputs.
  function condition(variable, inputs) {
    const matched = inputs.filter((input) => {
      const words = lower([input.name, input.definition].join(" "));
      return variable.aliases.some((alias) => contains(words, alias)) || contains(words, variable.name);
    });
    const tested = variable.bounds;
    const base = { variable: variable.name, unit: variable.unit, description: variable.description, tested_range: tested };
    if (!matched.length)
      return {
        ...base,
        client_inputs: [],
        status: tested ? "PROPOSED_FROM_TESTED_DESIGN" : "NEEDED_NO_TESTED_RANGE",
        proposed_range: tested,
        note: tested
          ? `Not in your brief. Carbon's tested design varies it over ${tested[0]} to ${tested[1]} ${variable.unit}; confirm or change.`
          : "Not in your brief, and Carbon has no tested range for it yet. Carbon needs this condition to design the study.",
      };
    const input = matched[0];
    const range = rangeOf(input);
    const clientInputs = matched.map((m) => m.name || "unnamed input");
    if (!tested)
      return { ...base, client_inputs: clientInputs, status: "SUPPLIED_NO_TESTED_RANGE", proposed_range: range, note: "You supplied this. Carbon has no tested range to compare it with yet." };
    if (!range)
      return { ...base, client_inputs: clientInputs, status: "SUPPLIED_RANGE_MISSING", proposed_range: tested, note: `You named this without a range. Carbon's tested range is ${tested[0]} to ${tested[1]} ${variable.unit}; confirm or change.` };
    if (unitKey(input.unit) !== unitKey(variable.unit))
      return { ...base, client_inputs: clientInputs, status: "UNITS_TO_CONFIRM", proposed_range: null, client_range: range, client_unit: input.unit, note: `Your unit (${input.unit || "none"}) differs from the tested design's (${variable.unit}). Carbon does not convert units here; confirm before the ranges are compared.` };
    const low = range[0] ?? tested[0], high = range[1] ?? tested[1];
    const inside = low >= tested[0] && high <= tested[1];
    return {
      ...base,
      client_inputs: clientInputs,
      status: inside ? "INSIDE_TESTED_RANGE" : "OUTSIDE_TESTED_RANGE",
      proposed_range: [low, high],
      client_range: range,
      client_unit: input.unit,
      note: inside
        ? "Inside the range Carbon tested. The evidence below was measured over the tested range, not yours specifically."
        : `Outside the range Carbon tested (${tested[0]} to ${tested[1]} ${variable.unit}). The evidence below does not cover this; the settings would need their own study.`,
    };
  }

  function outputsCoverage(family, system) {
    const clientOutputs = system ? system.outputs : [];
    return family.outputs.map((output) => {
      const words = output.name.split("_").filter((w) => w.length > 2);
      const matched = clientOutputs.filter((o) => words.some((w) => contains(lower(o.name + " " + o.purpose), w)));
      return { output: output.name, unit: output.unit, description: output.description, client_outputs: matched.map((o) => o.name || "unnamed output") };
    });
  }

  function extraInputs(family, system, conditions) {
    if (!system) return [];
    const used = new Set(conditions.flatMap((c) => c.client_inputs));
    return system.inputs.filter((i) => !used.has(i.name || "unnamed input")).map((i) => i.name || "unnamed input");
  }

  function limitStatus(family, limitName) {
    if (!limitName) return null;
    const limit = family.limits.find((l) => l.name === limitName);
    if (!limit) return null;
    return { name: limit.name, proposed: limit.proposed, approved: limit.approved, unit: limit.unit, basis: limit.basis };
  }

  function propose(draft, record, familyId = null) {
    const matches = match(draft, record);
    const chosenId = familyId || matches[0]?.family_id || null;
    const base = { version: PROPOSAL_VERSION, draft: { draft_id: draft.draft_id, revision_id: draft.revision_id }, matches, authority: "PROPOSAL_ONLY_NOT_REGISTERED_QUALIFIED_OR_APPROVED" };
    if (!chosenId) return { ...base, kind: KIND.NONE, family: null };
    const family = record.families.find((f) => f.id === chosenId);
    if (!family) throw Error("Unknown Challenge family: " + chosenId);
    const conditions = family.design_variables.map((v) => condition(v, draft.system ? draft.system.inputs : []));
    const common = {
      ...base,
      family: {
        id: family.id,
        title: family.title,
        status: family.status,
        engineering_decision: family.decision.engineering_decision,
        intended_use: family.decision.intended_use,
        reference_applicability: family.reference.applicability,
        population: family.population,
        reviews: Object.fromEntries(Object.entries(family.reviews).map(([k, v]) => [k, v.state])),
        training_budget_study: family.training_budget_study.state,
        unresolved: family.unresolved,
        next_experiment: family.next_experiment,
        tracking: family.tracking,
        record: family.record,
      },
      matched: matches.find((m) => m.family_id === chosenId) || null,
      conditions,
      extra_client_inputs: extraInputs(family, draft.system, conditions),
      outputs: outputsCoverage(family, draft.system),
      costs: family.costs,
    };
    if (!family.evidence) return { ...common, kind: KIND.SCOPED, evidence: null, settings: [] };
    const evidence = record.evidence[family.evidence];
    const outside = conditions.some((c) => c.status === "OUTSIDE_TESTED_RANGE");
    return {
      ...common,
      kind: KIND.EVIDENCE,
      evidence: { id: evidence.id, title: evidence.title, summary: evidence.summary, source: evidence.source, limits_of_evidence: evidence.limits_of_evidence },
      settings: evidence.settings.map((s) => ({ ...s, limit: limitStatus(family, s.limit), covered: !outside })),
    };
  }

  // A readable proposal, for the client's own records and for Carbon review.
  function markdown(p) {
    const lines = ["# Proposed Challenge: draft for Carbon review", "", `Brief ${p.draft.draft_id} / ${p.draft.revision_id}. ${p.version}.`, "", "This proposal is computed in your browser from Carbon's public records. It registers, runs, prices and approves nothing, and it is not a scientific assessment.", ""];
    if (p.kind === KIND.NONE) {
      lines.push("No launch-portfolio family matched this brief. Carbon would scope it from the start: a new family needs its own reference, measurements and exam-design study.");
      return lines.join("\n") + "\n";
    }
    lines.push(`## Family: ${p.family.title}`, "", `Status: ${p.family.status}. Training budget study: ${p.family.training_budget_study}.`, "", `Carbon's tested decision: ${p.family.engineering_decision}`, "", `Where the evidence applies: ${p.family.reference_applicability}`, "");
    if (p.matched) lines.push(`Matched on: ${[...p.matched.keywords, ...p.matched.physics.map((x) => x + " physics")].join(", ") || "your choice"}.`, "");
    lines.push("## Conditions", "", "| Condition | Unit | Tested range | Your input | Status |", "|---|---|---|---|---|");
    for (const c of p.conditions) lines.push(`| ${c.variable} | ${c.unit} | ${c.tested_range ? c.tested_range.join(" to ") : "none yet"} | ${c.client_inputs.join(", ") || "not given"} | ${c.status} |`);
    lines.push("");
    for (const c of p.conditions) lines.push(`- ${c.variable}: ${c.note}`);
    if (p.extra_client_inputs.length) lines.push("", `Inputs you gave that this family's design does not vary: ${p.extra_client_inputs.join(", ")}. They would need a new design study.`);
    lines.push("", "## Outputs", "");
    for (const o of p.outputs) lines.push(`- ${o.output} (${o.unit}): ${o.description}${o.client_outputs.length ? " Yours: " + o.client_outputs.join(", ") + "." : ""}`);
    if (p.kind === KIND.EVIDENCE) {
      lines.push("", "## Proposed exam settings and why", "", `Evidence: ${p.evidence.title} (${p.evidence.source.path}). ${p.evidence.summary}`, "");
      for (const s of p.settings) {
        lines.push(`### ${s.label}: ${s.value}`, "", s.why, "", `Source: ${p.evidence.source.path} (section: ${s.section}).${s.limit ? ` Limit ${s.limit.name}: proposed ${s.limit.proposed} ${s.limit.unit}, approved: ${s.limit.approved === null ? "not yet" : s.limit.approved}.` : ""}`, "");
        lines.push("| " + s.table.columns.join(" | ") + " |", "|" + s.table.columns.map(() => "---").join("|") + "|", ...s.table.rows.map((r) => "| " + r.join(" | ") + " |"), "");
      }
      lines.push("## Limits of this evidence", "", ...p.evidence.limits_of_evidence.map((l) => "- " + l.replace(/^\d+\.\s*/, "")), "");
    } else {
      lines.push("", "## No exam-design evidence yet", "", "Carbon has scoped this family but has not run its exam-design campaign, so no setting is proposed. What would come first:", "", `- ${p.family.next_experiment}`, "", "Cost items not yet measured: " + p.costs.filter((c) => c.basis === "unknown").map((c) => c.item).join(", ") + ".", "");
    }
    lines.push("## Open items", "", ...p.family.unresolved.map((u) => "- " + u), "");
    return lines.join("\n") + "\n";
  }

  const api = { PROPOSAL_VERSION, KIND, match, propose, markdown, clientText };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.CarbonChallengeProposal = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
