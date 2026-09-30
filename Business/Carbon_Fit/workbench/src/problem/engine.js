/* General problem assembly. Outputs are planning proposals, never scientific authority. */
(function (root, factory) {
  if (typeof module === "object" && module.exports)
    module.exports = factory(require("./cooling-v02.js"));
  else root.CarbonWorkbench = factory(root.CarbonCoolingV02);
})(typeof window === "object" ? window : this, function (Legacy) {
  "use strict";
  const VERSION = "carbon.workbench.problem.v0.3",
    RULES = "problem.rules.2026-09-12.2",
    MAX_BYTES = 2000000;
  const PHYSICS = {
    thermal: "Heat transfer",
    fluid: "Fluid flow",
    solid: "Structures & motion",
    electromagnetic: "Electromagnetics",
    acoustic: "Acoustics & waves",
    chemical: "Reaction & transport",
    other: "Other physics",
    unknown: "Not sure yet",
  };
  const GOALS = {
    unknown: "I need help defining the goal",
    predict: "Predict behavior",
    ranking: "Choose between designs",
    inverse: "Infer unknown properties",
    optimize: "Optimize operating conditions",
    audit: "Assess an existing model",
    custom: "Another engineering goal",
  };
  const OPTIONS = {
    geometry: {
      unknown: "Not defined",
      fixed: "One fixed system",
      family: "A defined design family",
      unseen: "New design families",
    },
    time: {
      unknown: "Not defined",
      steady: "Steady behavior",
      transient: "Transient / time history",
      frequency: "Frequency response",
    },
    model: {
      unknown: "Not chosen",
      existing: "We have a model",
      develop: "Develop or compare approaches",
    },
    deployment: {
      unknown: "Not defined",
      offline: "Offline engineering study",
      batch: "Repeated batch predictions",
      online: "Online decision support",
      control: "Control-system use",
    },
    access: {
      unknown: "Needs review",
      yes: "Reported permission",
      no: "Unavailable for this use",
    },
    independence: {
      unknown: "Needs review",
      independent: "Reported independent cases",
      shared: "Used in development",
    },
    dataType: {
      simulation: "Simulation / solver results",
      experiment: "Physical measurements",
      analytical: "Analytical reference",
      operational: "Operational observations",
      other: "Other reference",
    },
    dataRole: {
      undecided: "Role to agree",
      learning: "Learning only",
      evaluation: "Evaluation candidate",
      both: "Learning and evaluation (split needed)",
    },
    countUnit: {
      unknown: "Unit not defined",
      cases: "Reported independent cases",
      designs: "Designs / devices",
      runs: "Runs / experiments",
      snapshots: "Snapshots / time points",
    },
    variation: {
      unknown: "Not defined",
      design: "Design variable",
      operating: "Operating condition",
      material: "Material property",
      initial: "Initial condition",
      boundary: "Boundary condition",
      history: "Input history",
      other: "Other",
    },
    priority: { primary: "Primary outcome", supporting: "Supporting outcome" },
    criterion: {
      performance: "Performance target",
      physical: "Mandatory physical requirement",
    },
    operator: {
      unknown: "Criterion to agree",
      max: "At most",
      min: "At least",
      match: "Match / preserve",
      custom: "Custom criterion",
    },
    coupling: { oneway: "One-way influence", twoway: "Two-way coupling" },
    safety: {
      unknown: "Needs discussion",
      low: "Offline / low-consequence study",
      high: "Consequential operating decision",
    },
  };
  const copy = (x) => JSON.parse(JSON.stringify(x));
  function object(x) {
    return x !== null && typeof x === "object" && !Array.isArray(x);
  }
  function exact(x, keys, name) {
    if (
      !object(x) ||
      Object.keys(x).length !== keys.length ||
      keys.some((k) => !Object.hasOwn(x, k))
    )
      throw Error(name + ": missing or unsupported fields.");
  }
  function text(x, max, name) {
    if (typeof x !== "string" || x.length > max)
      throw Error(name + ": invalid text.");
  }
  function id(x) {
    if (
      typeof x !== "string" ||
      !/^[A-Za-z0-9_-]{1,80}$/.test(x) ||
      ["__proto__", "constructor", "prototype"].includes(x)
    )
      throw Error("Invalid record identity.");
  }
  function enumValue(x, values, name) {
    if (!Object.hasOwn(values, x)) throw Error("Invalid " + name + ".");
  }
  function num(x, name, signed = false) {
    if (
      x !== null &&
      (typeof x !== "number" ||
        !Number.isFinite(x) ||
        Math.abs(x) > 1e12 ||
        (!signed && x < 0))
    )
      throw Error(name + ": invalid number.");
  }
  function list(x, max, name) {
    if (!Array.isArray(x) || x.length > max)
      throw Error(name + ": too many entries or invalid list.");
  }
  const econKeys = [
    "queries",
    "baselineSeconds",
    "targetSeconds",
    "baselineCost",
    "targetCost",
    "setupCost",
    "monthlyCost",
    "hardware",
    "matchedTiming",
  ];
  const problemKeys = [
    "title",
    "description",
    "goal",
    "decision",
    "components",
    "couplings",
    "inputs",
    "outputs",
    "requirements",
    "sources",
    "geometry",
    "time",
    "model",
    "baseline",
    "deployment",
    "safety",
    "compute",
    "timeline",
    "notes",
    "economics",
    "sourceRefs",
  ];
  function blankProblem() {
    return {
      title: "",
      description: "",
      goal: "unknown",
      decision: "",
      components: [],
      couplings: [],
      inputs: [],
      outputs: [],
      requirements: [],
      sources: [],
      geometry: "unknown",
      time: "unknown",
      model: "unknown",
      baseline: "",
      deployment: "unknown",
      safety: "unknown",
      compute: "",
      timeline: "",
      notes: "",
      economics: {
        queries: null,
        baselineSeconds: null,
        targetSeconds: null,
        baselineCost: null,
        targetCost: null,
        setupCost: null,
        monthlyCost: null,
        hardware: "",
        matchedTiming: false,
      },
      sourceRefs: [],
    };
  }
  function newJob(jobId) {
    id(jobId);
    return {
      schema: VERSION,
      ruleVersion: RULES,
      id: jobId,
      revision: 1,
      origin: "user_draft",
      problem: blankProblem(),
      checkpoints: [],
      migration: null,
    };
  }
  function row(type, rowId) {
    id(rowId);
    const rows = {
      components: { id: rowId, name: "", physics: "unknown", regime: "" },
      couplings: {
        id: rowId,
        from: "",
        to: "",
        quantity: "",
        direction: "oneway",
      },
      inputs: {
        id: rowId,
        name: "",
        unit: "",
        variation: "unknown",
        min: null,
        max: null,
        definition: "",
      },
      outputs: {
        id: rowId,
        name: "",
        unit: "",
        priority: "primary",
        purpose: "",
      },
      requirements: {
        id: rowId,
        output: "",
        kind: "performance",
        measure: "",
        operator: "unknown",
        target: null,
        unit: "",
      },
      sources: {
        id: rowId,
        name: "",
        type: "simulation",
        role: "undecided",
        access: "unknown",
        independence: "unknown",
        count: null,
        countUnit: "unknown",
        coverage: "",
        uncertainty: "",
      },
    };
    if (!rows[type]) throw Error("Unknown collection.");
    return rows[type];
  }
  function validateProblem(p) {
    exact(p, problemKeys, "Problem");
    for (const k of ["title", "baseline", "compute", "timeline"])
      text(p[k], 300, k);
    for (const k of ["description", "decision", "notes"]) text(p[k], 3000, k);
    enumValue(p.goal, GOALS, "goal");
    for (const k of ["geometry", "time", "model", "deployment", "safety"])
      enumValue(p[k], OPTIONS[k], k);
    const limits = {
      components: 12,
      couplings: 24,
      inputs: 24,
      outputs: 24,
      requirements: 24,
      sources: 12,
    };
    const allIds = new Set();
    for (const [key, max] of Object.entries(limits)) {
      list(p[key], max, key);
      for (const r of p[key]) {
        exact(r, Object.keys(row(key, "schema")), key);
        id(r.id);
        if (allIds.has(r.id)) throw Error("Duplicate row identity.");
        allIds.add(r.id);
      }
    }
    for (const r of p.components) {
      text(r.name, 140, "Component name");
      enumValue(r.physics, PHYSICS, "physics");
      text(r.regime, 600, "Regime");
    }
    const comps = new Set(p.components.map((c) => c.id)),
      outputs = new Set(p.outputs.map((o) => o.id));
    for (const r of p.couplings) {
      text(r.from, 80, "Coupling source");
      text(r.to, 80, "Coupling target");
      text(r.quantity, 300, "Coupling quantity");
      enumValue(r.direction, OPTIONS.coupling, "coupling");
      if ((r.from && !comps.has(r.from)) || (r.to && !comps.has(r.to)))
        throw Error("Coupling references a missing component.");
      if (r.from && r.from === r.to)
        throw Error("Connect two distinct components.");
    }
    for (const r of p.inputs) {
      text(r.name, 160, "Input");
      text(r.unit, 80, "Input unit");
      enumValue(r.variation, OPTIONS.variation, "variation");
      num(r.min, "Minimum", true);
      num(r.max, "Maximum", true);
      text(r.definition, 1200, "Input definition");
    }
    for (const r of p.outputs) {
      text(r.name, 160, "Output");
      text(r.unit, 80, "Output unit");
      text(r.purpose, 700, "Output purpose");
      enumValue(r.priority, OPTIONS.priority, "priority");
    }
    for (const r of p.requirements) {
      text(r.output, 80, "Requirement output");
      if (r.output && !outputs.has(r.output))
        throw Error("Requirement references a missing output.");
      enumValue(r.kind, OPTIONS.criterion, "criterion");
      text(r.measure, 600, "Measurement");
      enumValue(r.operator, OPTIONS.operator, "comparison");
      num(r.target, "Target", true);
      text(r.unit, 80, "Target unit");
    }
    for (const r of p.sources) {
      text(r.name, 160, "Source");
      enumValue(r.type, OPTIONS.dataType, "source type");
      enumValue(r.role, OPTIONS.dataRole, "data role");
      enumValue(r.access, OPTIONS.access, "access");
      enumValue(r.independence, OPTIONS.independence, "independence");
      num(r.count, "Count");
      if (r.count !== null && !Number.isSafeInteger(r.count))
        throw Error("Source count must be a whole number.");
      enumValue(r.countUnit, OPTIONS.countUnit, "count unit");
      text(r.coverage, 1200, "Coverage");
      text(r.uncertainty, 1200, "Uncertainty");
    }
    exact(p.economics, econKeys, "Economics");
    for (const k of econKeys.filter(
      (k) => !["hardware", "matchedTiming"].includes(k),
    )) {
      num(p.economics[k], k);
      if (p.economics[k] !== null && p.economics[k] > 1e9)
        throw Error("Economics input exceeds supported bound.");
    }
    if (
      p.economics.queries !== null &&
      !Number.isSafeInteger(p.economics.queries)
    )
      throw Error("Predictions must be a whole number.");
    text(p.economics.hardware, 300, "Timing context");
    if (typeof p.economics.matchedTiming !== "boolean")
      throw Error("Invalid timing assertion.");
    list(p.sourceRefs, 20, "Source references");
    if (new Set(p.sourceRefs).size !== p.sourceRefs.length)
      throw Error("Duplicate source reference.");
    for (const s of p.sourceRefs) {
      const m = typeof s === "string" && /^PHY-([ABCD])([0-9]{2})$/.exec(s);
      if (
        !m ||
        Number(m[2]) < 1 ||
        Number(m[2]) > { A: 13, B: 17, C: 15, D: 19 }[m[1]]
      )
        throw Error("Invalid atlas source ID.");
    }
    return p;
  }
  function validateJob(j) {
    exact(
      j,
      [
        "schema",
        "ruleVersion",
        "id",
        "revision",
        "origin",
        "problem",
        "checkpoints",
        "migration",
      ],
      "Draft",
    );
    if (j.schema !== VERSION || j.ruleVersion !== RULES)
      throw Error(
        "Unsupported draft version; retain the original for migration.",
      );
    id(j.id);
    if (!Number.isSafeInteger(j.revision) || j.revision < 1)
      throw Error("Invalid revision.");
    if (
      !["user_draft", "illustrative_template", "migrated_unreviewed"].includes(
        j.origin,
      )
    )
      throw Error("Invalid draft origin.");
    validateProblem(j.problem);
    list(j.checkpoints, 12, "Checkpoints");
    let prev = 0;
    for (const c of j.checkpoints) {
      exact(c, ["revision", "label", "problem"], "Checkpoint");
      text(c.label, 160, "Checkpoint label");
      if (
        !Number.isSafeInteger(c.revision) ||
        c.revision <= prev ||
        c.revision >= j.revision
      )
        throw Error("Invalid checkpoint sequence.");
      prev = c.revision;
      validateProblem(c.problem);
    }
    if (j.migration !== null) {
      exact(j.migration, ["sourceSchema", "originalText", "note"], "Migration");
      text(j.migration.originalText, MAX_BYTES, "Original draft");
      if (j.migration.sourceSchema === Legacy.VERSION) Legacy.importJob(j.migration.originalText);
      else if(j.migration.sourceSchema === VERSION) {
        const source=JSON.parse(j.migration.originalText);
        if(source.ruleVersion !== "problem.rules.2026-09-12.1" || source.migration?.sourceSchema === VERSION) throw Error("Unsupported prior rules.");
        source.ruleVersion=RULES; validateJob(source);
      } else throw Error("Unsupported migration source.");
      text(j.migration.note, 1000, "Migration note");
    }
    return j;
  }
  function exportJob(j) {
    validateJob(j);
    const s = JSON.stringify(j, null, 2);
    if (new TextEncoder().encode(s).length > MAX_BYTES)
      throw Error(
        "Draft exceeds 2 MB; export fewer checkpoints in a separate fork.",
      );
    return s;
  }
  function importJob(s) {
    if (typeof s !== "string" || new TextEncoder().encode(s).length > MAX_BYTES)
      throw Error("Draft exceeds 2 MB.");
    let j;
    try {
      j = JSON.parse(s);
    } catch (_) {
      throw Error("Choose a valid Carbon draft JSON.");
    }
    if (!object(j)) throw Error("Choose a Carbon draft object.");
    if (j.schema === Legacy.VERSION)
      return { kind: "legacy", originalText: s, preview: Legacy.importJob(s) };
    if (j.schema === VERSION && j.ruleVersion === "problem.rules.2026-09-12.1") {
      const next=copy(j); next.ruleVersion=RULES; validateJob(next);
      next.origin="migrated_unreviewed";
      next.migration={sourceSchema:VERSION,originalText:s,note:"Rules updated from 2026-09-12.1 to .2. Original draft retained; review new planning questions."};
      exportJob(next);
      return {kind:"rules_update",job:next};
    }
    return { kind: "current", job: validateJob(j) };
  }
  function checkpoint(j, label) {
    validateJob(j);
    if (j.checkpoints.length >= 12)
      throw Error(
        "Twelve checkpoints retained. Export this draft and fork to continue.",
      );
    const next = copy(j);
    next.checkpoints.push({
      revision: j.revision,
      label: label || "Working assumptions",
      problem: copy(j.problem),
    });
    next.revision++;
    exportJob(next);
    return next;
  }
  function changes(j) {
    const last = j.checkpoints.at(-1);
    return last
      ? problemKeys.filter(
          (k) =>
            JSON.stringify(last.problem[k]) !== JSON.stringify(j.problem[k]),
        )
      : [];
  }
  function fork(j, newId) {
    validateJob(j);
    const next = newJob(newId);
    next.problem = copy(j.problem);
    next.origin = j.origin;
    next.migration = copy(j.migration);
    return next;
  }
  function removeRow(p, type, rowId) {
    validateProblem(p);
    if (
      ![
        "components",
        "couplings",
        "inputs",
        "outputs",
        "requirements",
        "sources",
      ].includes(type)
    )
      throw Error("Invalid collection.");
    const q = copy(p);
    q[type] = q[type].filter((r) => r.id !== rowId);
    if (type === "components")
      q.couplings = q.couplings.filter(
        (r) => r.from !== rowId && r.to !== rowId,
      );
    if (type === "outputs")
      q.requirements = q.requirements.map((r) =>
        r.output === rowId ? { ...r, output: "" } : r,
      );
    return q;
  }
  const GUIDANCE = {
    thermal: {
      review:
        "Review conduction, convection, radiation and any phase-change assumptions, as applicable.",
      reference:
        "Compare applicable analytical limits, converged thermal models and calibrated temperature/heat-flow measurements.",
      measure:
        "Consider temperature fields and extrema, heat rates, boundary conditions and an energy balance under stated assumptions.",
      specialist: "Thermal engineering",
    },
    fluid: {
      review:
        "Define the flow regime, compressibility, phase, boundaries and any turbulence or constitutive closure.",
      reference:
        "Review appropriate analytical limits, converged flow solvers and pressure, velocity or flow-rate measurements.",
      measure:
        "Consider pressure drop, forces, flow fields and applicable mass/momentum balances with uncertainty.",
      specialist: "Fluid mechanics",
    },
    solid: {
      review:
        "Define loading, material law, deformation regime, contacts, constraints and any dynamic behavior.",
      reference:
        "Review analytical cases, converged structural/dynamics models and relevant load/displacement measurements.",
      measure:
        "Consider stress/strain, displacement, forces, modes and applicable balance or stability requirements.",
      specialist: "Solid mechanics / dynamics",
    },
    electromagnetic: {
      review:
        "Define fields, excitation, geometry, material response and any frequency or nonlinear effects.",
      reference:
        "Review analytical benchmarks, converged field models and calibrated electrical/magnetic measurements.",
      measure:
        "Consider fields, force/torque, impedance or losses; choose equation and interface checks for the declared formulation.",
      specialist: "Electromagnetics",
    },
    acoustic: {
      review:
        "Define wave type, propagation medium, boundaries, frequency range and damping/nonlinearity assumptions.",
      reference:
        "Review analytical wave cases, converged acoustic models and calibrated frequency/time-response measurements.",
      measure:
        "Consider amplitude, phase, spectra, transmission and applicable boundary or energy requirements.",
      specialist: "Acoustics / wave physics",
    },
    chemical: {
      review:
        "Define species, reactions, kinetics, transport, thermodynamic assumptions and relevant scales.",
      reference:
        "Review benchmark kinetics/transport cases, converged models and calibrated composition or reaction-rate measurements.",
      measure:
        "Consider species concentrations, rates, conservation and admissibility under the stated chemical model.",
      specialist: "Reaction / transport modeling",
    },
    other: {
      review:
        "A specialist must define the governing assumptions and applicable evidence for this custom physics.",
      reference: "No applicable reference method has been selected.",
      measure:
        "Define decision-relevant quantities and physical requirements with a domain specialist.",
      specialist: "Domain specialist",
    },
    unknown: {
      review:
        "Identify the physical processes that influence the requested outputs.",
      reference:
        "Select a reference route after identifying the relevant physics.",
      measure: "Define observable outcomes before selecting measurements.",
      specialist: "Engineering scoping",
    },
  };
  const METHODS = {
    unknown: {
      claim:
        "Define the engineering decision and observable outcomes before selecting an evaluation.",
      measure: "Agree the quantities that would distinguish a useful result.",
      deliverable: "A scoped problem and a proposed evaluation plan.",
    },
    predict: {
      claim:
        "Investigate prediction quality for the requested outputs across the declared conditions.",
      measure:
        "Measure decision-relevant errors, subgroups, tails and uncertainty against an applicable reference.",
      deliverable:
        "An output-error and coverage report with limitations and unresolved cases.",
    },
    ranking: {
      claim:
        "Investigate whether model-based comparisons preserve the engineering choices that matter.",
      measure:
        "Measure ranking errors, decision regret and near-tie uncertainty, alongside required physical checks.",
      deliverable:
        "A comparison of decisions, disagreements and unresolved alternatives.",
    },
    inverse: {
      claim:
        "Investigate whether the available observations support useful estimates of the unknown properties.",
      measure:
        "Assess identifiability, ambiguity, observation noise, parameter recovery where observable, and independent predictive checks.",
      deliverable:
        "An inference report with identifiable quantities, alternatives and uncertainty.",
    },
    optimize: {
      claim:
        "Investigate whether the proposed optimization improves the objective while respecting the agreed constraints.",
      measure:
        "Confirm selected solutions on independent evidence; inspect constraint violations, search cost and comparison to a suitable baseline.",
      deliverable:
        "A verified-candidate proposal with objective, constraint and search-cost evidence.",
    },
    audit: {
      claim:
        "Investigate the existing model’s performance and limits for the intended engineering use.",
      measure:
        "Compare the frozen model with the reference over the agreed population, failures and relevant difficult cases.",
      deliverable:
        "A model audit with applicability limits, uncertainty and remediation priorities.",
    },
    custom: {
      claim:
        "Translate the custom engineering decision into a testable claim with your team.",
      measure:
        "Define observable success, required constraints, comparisons and uncertainty before choosing metrics.",
      deliverable: "A custom claim, reference plan and measurement proposal.",
    },
  };
  function derive(p) {
    validateProblem(p);
    const gaps = [],
      contradictions = [],
      addGap = (priority, topic, text) => gaps.push({ ruleId: "WB-" + topic.toUpperCase().replace(/[^A-Z0-9]+/g,"-"), priority, topic, text });
    const families = [...new Set(p.components.map((c) => c.physics))],
      method = METHODS[p.goal];
    if (!p.title.trim() && !p.description.trim())
      addGap(
        "Scope",
        "Purpose",
        "Describe the system and the decision you want to improve.",
      );
    if (p.goal === "unknown" || !p.decision.trim())
      addGap(
        "Scope",
        "Decision",
        "Agree the engineering decision, outcome and consequence of an error.",
      );
    if (!p.components.length)
      addGap(
        "Scope",
        "Physics",
        "Add a physical component or choose “Not sure yet”.",
      );
    for (const c of p.components) {
      if (!c.name.trim())
        addGap(
          "Scope",
          "Component",
          "Name the " + PHYSICS[c.physics] + " component.",
        );
      if (["other", "unknown"].includes(c.physics))
        addGap(
          "Scope",
          "Custom physics",
          "A specialist must scope " +
            (c.name || "the unnamed component") +
            ".",
        );
      if (!c.regime.trim())
        addGap(
          "Scope",
          "Regime",
          "Describe relevant assumptions and operating regime for " +
            (c.name || PHYSICS[c.physics]) +
            ".",
        );
    }
    if (p.components.length > 1 && !p.couplings.length)
      addGap(
        "Scope",
        "Coupling",
        "Confirm whether the components interact; add links or document why they are independent.",
      );
    for (const c of p.couplings)
      if (!c.from || !c.to || !c.quantity.trim())
        addGap(
          "Scope",
          "Coupling",
          "Complete the endpoints and exchanged quantity for each proposed link.",
        );
    if (!p.inputs.length)
      addGap(
        "Scope",
        "Inputs",
        "Define what varies and what the model receives.",
      );
    for (const i of p.inputs) {
      if (!i.name.trim()) addGap("Scope", "Input", "Name an input quantity.");
      if (i.variation === "unknown")
        addGap(
          "Scope",
          "Input variation",
          "Define how " + (i.name || "an unnamed input") + " varies.",
        );
      if (i.min === null && i.max === null && !i.definition.trim())
        addGap(
          "Scope",
          "Input domain",
          "Describe the range, categories, geometry or history for " +
            (i.name || "an unnamed input") +
            ".",
        );
      if (!i.unit.trim())
        addGap(
          "Scope",
          "Units",
          "Define the unit or representation for " +
            (i.name || "the unnamed input") +
            ".",
        );
      if ((i.min === null) !== (i.max === null))
        contradictions.push(
          (i.name || "Input") +
            ": supply both range limits or leave both unknown.",
        );
      if (i.min !== null && i.max !== null && i.min > i.max)
        contradictions.push(
          (i.name || "Input") +
            ": the lower range limit exceeds the upper limit.",
        );
    }
    if (!p.outputs.length)
      addGap(
        "Scope",
        "Outputs",
        "Define the outputs and the decisions they support.",
      );
    if (p.outputs.length && !p.outputs.some((o) => o.priority === "primary"))
      addGap(
        "Scope",
        "Primary outcome",
        "Identify at least one primary outcome.",
      );
    for (const o of p.outputs) {
      if (!o.name.trim() || !o.unit.trim())
        addGap(
          "Scope",
          "Output contract",
          "Complete the name and unit/representation of each output.",
        );
      if (!p.requirements.some((r) => r.output === o.id))
        addGap(
          "Scope",
          "Success criteria",
          "Propose a measurement and criterion for " +
            (o.name || "an unnamed output") +
            ".",
        );
    }
    for (const r of p.requirements) {
      if (!r.output || !r.measure.trim() || r.operator === "unknown")
        addGap(
          "Scope",
          "Criterion",
          "Complete the output, measurement and interpretation of each criterion.",
        );
      if (["max", "min"].includes(r.operator) && r.target === null)
        addGap(
          "Scope",
          "Target value",
          "Agree a numeric target or choose a qualitative criterion for " +
            (r.measure || "an unnamed measurement") +
            ".",
        );
      if (r.target !== null && !r.unit.trim())
        addGap(
          "Scope",
          "Target units",
          "Define units for the proposed target on " +
            (r.measure || "an unnamed measurement") +
            ".",
        );
    }
    if (
      p.components.length &&
      !p.requirements.some((r) => r.kind === "physical")
    )
      addGap(
        "Scope",
        "Physical requirements",
        "Identify applicable mandatory physical requirements, or document why no separate gate is appropriate.",
      );
    if (p.geometry === "unknown")
      addGap(
        "Scope",
        "Population",
        "Define the geometry/system family and intended operating population.",
      );
    if (p.time === "unknown")
      addGap(
        "Scope",
        "Time behavior",
        "Clarify steady, transient or frequency behavior.",
      );
    if (
      p.goal === "ranking" &&
      p.geometry === "fixed" &&
      !p.inputs.some((i) => ["design", "operating"].includes(i.variation))
    )
      contradictions.push(
        "Ranking needs alternatives. Identify operating choices or design variations, or select a prediction/audit goal.",
      );
    const candidates = p.sources.filter(
      (s) => s.access !== "no" && s.role !== "learning" && s.count !== 0,
    );
    if (!p.sources.length)
      addGap(
        "Scope",
        "Reference",
        "Identify a potential solver, analytical reference or measurement source.",
      );
    if (p.sources.length && !candidates.length)
      addGap(
        "Scope",
        "Reference access",
        "Current sources are unavailable for evaluation or learning-only. Identify an evaluation reference.",
      );
    for (const s of p.sources) {
      if (s.access !== "yes")
        addGap(
          "Scope",
          "Access",
          "Review access to " + (s.name || "the unnamed source") + ".",
        );
      if (!s.coverage.trim())
        addGap(
          "Run",
          "Coverage",
          "Map " +
            (s.name || "the unnamed source") +
            " to the requested outputs and conditions.",
        );
      if (!s.uncertainty.trim())
        addGap(
          "Run",
          "Reference uncertainty",
          "Inspect uncertainty and applicability for " +
            (s.name || "the unnamed source") +
            ".",
        );
      if (s.role === "both")
        addGap(
          "Run",
          "Separation",
          "Plan separate learning and evaluation use for " +
            (s.name || "the unnamed source") +
            ".",
        );
      if (s.independence !== "independent" && s.role !== "learning")
        addGap(
          "Run",
          "Independence",
          "Audit development exposure and dependence for " +
            (s.name || "the unnamed source") +
            ".",
        );
      if (s.count !== null && s.countUnit === "snapshots")
        addGap(
          "Run",
          "Experimental unit",
          "Do not count snapshots in " +
            (s.name || "this source") +
            " as independent cases without a justified design.",
        );
    }
    for (const s of p.sources) {
      if (s.count === 0) addGap("Run","Empty source",(s.name || "This source") + " currently reports zero observations. Plan evidence acquisition; do not treat it as usable validation data.");
      if (s.role !== "learning" && s.independence === "independent") addGap("Run","Independence verification","Reported independence in " + (s.name || "this source") + " still needs a split, lineage and exposure audit.");
    }
    if (p.goal === "inverse") addGap("Run","Identifiability","Test whether the available observations distinguish the unknown quantities; retain ambiguity and prior assumptions.");
    if (["optimize","ranking"].includes(p.goal)) addGap("Run","Selection bias","Define alternatives and keep independent confirmation of the selected design or setting outside the search loop.");
    if (p.inputs.length && p.outputs.length) addGap("Run","Causal availability","Verify that every input exists at the intended prediction time and does not contain the answer, future observations or evaluation labels.");
    if (p.economics.baselineCost !== null || p.economics.baselineSeconds !== null) addGap("Claim","Comparable workflow","Separate the truth reference from the deployable comparison baseline. Compare complete costs at adequate output quality and matching workload boundaries.");
    for (const r of p.requirements) {
      const out=p.outputs.find(o=>o.id===r.output);
      if(out && r.unit.trim() && out.unit.trim() && r.unit.trim()!==out.unit.trim()) addGap("Run","Measurement units","Review the relation between criterion units " + r.unit + " and output units " + out.unit + ". A normalized or derived metric needs an explicit definition; no conversion is inferred.");
    }
    const physical = candidates.some((s) =>
      ["experiment", "operational"].includes(s.type),
    );
    const referenceBoundary = !candidates.length
      ? "No candidate evaluation reference is available in this draft. The next work is reference scoping."
      : physical
        ? "You report potential physical observations. A reviewer must verify calibration, uncertainty, independent coverage and relevance before proposing physical validation."
        : "The listed non-physical references may support model/reference agreement in a scoped study. Physical validation needs suitable physical evidence and review.";
    const guidance = families.map((f) => ({
      physics: f,
      name: PHYSICS[f],
      ...GUIDANCE[f],
      status: "Proposed checklist; specialist review required",
    }));
    const split =
      p.geometry === "unseen"
        ? "Reserve entire design or system families for transfer evaluation. Bound the claim to the shifts represented."
        : p.geometry === "family"
          ? "Separate at the design/device level where relevant. Repeated observations of one design are not independent design coverage."
          : "Define independent operating cases or experiments. Separate learning and confirmatory evaluation use.";
    const time =
      p.time === "transient"
        ? "Bind initial state, input histories, requested times and rollout horizon. Inspect peak timing, stability and accumulated error."
        : p.time === "frequency"
          ? "Define frequency range and resolution, amplitude/phase conventions and boundary conditions."
          : "Declare the time assumptions and measurement context; do not infer untested temporal behavior.";
    const coupling = p.couplings.length
      ? "Check interface quantities, units, sign conventions, timing and conservation where applicable. Validate the coupled system; component checks do not establish system accuracy."
      : "Describe physical interactions or document independence before assembling a joint claim.";
    let route =
      p.model === "existing" || p.goal === "audit"
        ? "Scope an audit of the existing model"
        : "Compare a baseline and candidate approaches";
    if (!candidates.length) route = "Establish an evaluation reference first";
    if (!p.components.length || p.goal === "unknown")
      route = "Define the engineering problem";
    if (families.some((f) => ["other", "unknown"].includes(f)))
      route = "Resolve specialist scoping questions";
    addGap(
      "Claim",
      "Decision resolution",
      "Reference uncertainty, dependence and sample size need job-specific evidence before a performance claim.",
    );
    const next = contradictions.length
      ? contradictions[0]
      : gaps.find((g) => g.priority === "Scope")?.text ||
        "Review one representative reference sample and agree the proposed measurement protocol.";
    const alternatives = [
      p.model === "existing"
        ? "Audit and retain the current model if it meets the job."
        : "Start with a suitable conventional baseline.",
      "Compare a learned or hybrid approach when evidence and workflow economics justify it.",
      "Consider a competitive research challenge after the objective, references and resource contract are ready.",
    ];
    return {
      route,
      method,
      referenceBoundary,
      guidance,
      gaps,
      contradictions,
      next,
      split,
      time,
      coupling,
      alternatives,
      evidenceStages: [
        {
          name: "Learning / construction",
          text: "Define permitted training data or development observations and the conditions they cover.",
        },
        {
          name: "Independent performance",
          text:
            split + " Estimate the agreed outcomes on the intended population.",
        },
        {
          name: "Targeted stress",
          text: "Investigate selected difficult conditions and failure modes; keep these results distinct from representative performance.",
        },
      ],
      deliverables: [
        method.deliverable,
        "A coverage, reference uncertainty and failure report with unresolved questions.",
        "A versioned input/model/method record and a scoped recommendation for the next use or investigation.",
      ],
      economics: Legacy.economics({ ...Legacy.DEFAULTS, ...p.economics }),
      support:
        "Planning guidance only. No specialist approval, solver run or measured result.",
    };
  }
  function template(key, jobId) {
    const j = newJob(jobId),
      p = j.problem;
    j.origin = "illustrative_template";
    p.geometry = "family";
    p.time = "steady";
    p.model = "develop";
    p.deployment = "offline";
    p.safety = "low";
    const component = (id, name, physics, regime) => ({
      ...row("components", id),
      name,
      physics,
      regime,
    });
    const input = (id, name, unit, variation) => ({
      ...row("inputs", id),
      name,
      unit,
      variation,
    });
    const output = (id, name, unit, purpose) => ({
      ...row("outputs", id),
      name,
      unit,
      purpose,
    });
    const source = (id, name, type) => ({
      ...row("sources", id),
      name,
      type,
      role: "undecided",
    });
    if (key === "cooling") {
      Object.assign(p, {
        title: "Compare cooling designs",
        description:
          "Screen a family of cold plates under varying loads and flow conditions.",
        goal: "ranking",
        decision:
          "Choose which cooling designs deserve detailed simulation or physical testing.",
        model: "existing",
      });
      p.components = [
        component(
          "c_heat",
          "Cold plate heat transfer",
          "thermal",
          "Single-phase planning example; material and boundaries to define.",
        ),
        component(
          "c_flow",
          "Coolant flow",
          "fluid",
          "Flow regime and fluid properties to confirm.",
        ),
      ];
      p.couplings = [
        {
          id: "link_heat_flow",
          from: "c_flow",
          to: "c_heat",
          quantity:
            "Flow-dependent heat transfer and temperature-dependent properties",
          direction: "twoway",
        },
      ];
      p.inputs = [
        input("i_load", "Heat load", "W", "operating"),
        input("i_flow", "Coolant flow rate", "L/min", "operating"),
        input(
          "i_geometry",
          "Cold plate geometry",
          "CAD or parameter vector",
          "design",
        ),
      ];
      p.outputs = [
        output(
          "o_temperature",
          "Peak temperature",
          "K",
          "Check cooling adequacy.",
        ),
        output("o_pressure", "Pressure drop", "Pa", "Assess pumping burden."),
      ];
      p.sources = [source("s_cfd", "Candidate CFD reference", "simulation")];
    } else if (key === "actuator") {
      Object.assign(p, {
        title: "Predict an electric actuator’s response",
        description:
          "Study the interaction between electromagnetic force, mechanical motion and heating.",
        goal: "predict",
        decision:
          "Compare actuator response under load and duty-cycle changes.",
        time: "transient",
      });
      p.components = [
        component(
          "c_em",
          "Motor / field model",
          "electromagnetic",
          "Excitation and material assumptions to define.",
        ),
        component(
          "c_motion",
          "Mechanical load",
          "solid",
          "Rigid/flexible dynamics, constraints and friction to define.",
        ),
        component(
          "c_heat",
          "Thermal response",
          "thermal",
          "Losses, boundaries and cooling to define.",
        ),
      ];
      p.couplings = [
        {
          id: "l_em_motion",
          from: "c_em",
          to: "c_motion",
          quantity: "Force/torque and motion feedback",
          direction: "twoway",
        },
        {
          id: "l_em_heat",
          from: "c_em",
          to: "c_heat",
          quantity: "Losses and temperature-dependent material response",
          direction: "twoway",
        },
      ];
      p.inputs = [
        input("i_current", "Excitation history", "A versus s", "history"),
        input("i_load", "Mechanical load", "N or N·m", "operating"),
      ];
      p.outputs = [
        output(
          "o_response",
          "Position / response history",
          "m or rad versus s",
          "Compare tracking and response.",
        ),
        output(
          "o_heat",
          "Temperature history",
          "K versus s",
          "Inspect thermal limits.",
        ),
      ];
      p.sources = [
        source("s_bench", "Potential bench measurements", "experiment"),
      ];
    } else if (key === "aero") {
      Object.assign(p, {
        title: "Compare aerodynamic designs",
        description:
          "Evaluate a family of shapes over selected speeds and orientations.",
        goal: "ranking",
        decision:
          "Select designs for higher-fidelity simulation or wind-tunnel testing.",
      });
      p.components = [
        component(
          "c_flow",
          "External airflow",
          "fluid",
          "Reynolds/Mach ranges, turbulence and boundaries to define.",
        ),
      ];
      p.inputs = [
        input("i_shape", "Geometry", "CAD or parameter vector", "design"),
        input("i_speed", "Flow speed", "m/s", "operating"),
        input("i_angle", "Yaw / incidence", "deg", "operating"),
      ];
      p.outputs = [
        output("o_drag", "Drag", "N", "Rank aerodynamic burden."),
        output(
          "o_lift",
          "Lift / side force",
          "N",
          "Check secondary consequences.",
        ),
      ];
      p.sources = [
        source("s_cfd", "Potential flow-solver results", "simulation"),
      ];
    } else if (key === "structure") {
      Object.assign(p, {
        title: "Compare load-bearing components",
        description:
          "Assess a component family under material and load variation.",
        goal: "ranking",
        decision: "Choose components for detailed structural verification.",
      });
      p.components = [
        component(
          "c_solid",
          "Loaded structure",
          "solid",
          "Material law, deformation regime and boundary conditions to define.",
        ),
      ];
      p.inputs = [
        input("i_load", "Applied load", "N", "operating"),
        input(
          "i_material",
          "Material parameters",
          "parameter vector",
          "material",
        ),
        input(
          "i_shape",
          "Component geometry",
          "CAD or parameter vector",
          "design",
        ),
      ];
      p.outputs = [
        output("o_disp", "Displacement", "m", "Compare stiffness."),
        output(
          "o_stress",
          "Stress quantities",
          "Pa",
          "Inspect required structural criteria.",
        ),
      ];
      p.sources = [
        source("s_fe", "Potential structural reference", "simulation"),
      ];
    } else if (key === "acoustic") {
      Object.assign(p, {
        title: "Compare acoustic response",
        description:
          "Assess wave response over a frequency range and geometry family.",
        goal: "predict",
        decision:
          "Identify designs with the desired response before further testing.",
        time: "frequency",
      });
      p.components = [
        component(
          "c_wave",
          "Acoustic domain",
          "acoustic",
          "Medium, damping, boundaries and wave assumptions to define.",
        ),
      ];
      p.inputs = [
        input("i_frequency", "Excitation frequency", "Hz", "operating"),
        input(
          "i_shape",
          "Domain geometry",
          "CAD or parameter vector",
          "design",
        ),
      ];
      p.outputs = [
        output(
          "o_amplitude",
          "Response amplitude",
          "quantity / reference to define",
          "Compare transmission or attenuation.",
        ),
        output(
          "o_phase",
          "Phase response",
          "rad",
          "Inspect response timing in frequency representation.",
        ),
      ];
      p.sources = [
        source("s_test", "Potential acoustic measurements", "experiment"),
      ];
    } else throw Error("Unknown example.");
    p.requirements = p.outputs.map((o, i) => ({
      ...row("requirements", "r_" + i),
      output: o.id,
      measure: "Decision-relevant error in " + o.name,
      operator: "unknown",
      unit: o.unit,
    }));
    validateJob(j);
    return j;
  }
  function migrateLegacy(originalText) {
    const old = Legacy.importJob(originalText),
      j = template("cooling", old.id),
      p = j.problem,
      x = old.inputs;
    j.origin = "migrated_unreviewed";
    j.revision = old.revision;
    Object.assign(p, {
      title: x.title,
      description: x.notes,
      notes:
        "Migrated cooling draft. Original bytes and historical checkpoints remain in the migration record.",
      goal: x.goal === "ranking" ? "ranking" : "predict",
      decision:
        x.goal === "hotspots"
          ? "Locate and quantify hot spots."
          : x.goal === "speed"
            ? "Reduce repeated prediction time while meeting agreed quality."
            : "Choose between cooling designs.",
      geometry: x.geometry,
      time: x.dynamics,
      model:
        x.model === "existing"
          ? "existing"
          : x.model === "search"
            ? "develop"
            : "unknown",
    });
    p.components[0].regime =
      x.regime === "two"
        ? "Two-phase scope: specialist review required."
        : x.regime === "single"
          ? "Single-phase scope; assumptions require review."
          : "Regime unknown.";
    p.inputs.find((i) => i.id === "i_load").min = x.loadMin;
    p.inputs.find((i) => i.id === "i_load").max = x.loadMax;
    p.inputs.find((i) => i.id === "i_flow").min = x.flowMin;
    p.inputs.find((i) => i.id === "i_flow").max = x.flowMax;
    const type = x.evidence === "physical" ? "experiment" : "simulation";
    p.sources =
      x.evidence === "none"
        ? []
        : [
            {
              ...row("sources", "s_migrated"),
              name: "Legacy reported reference (" + x.evidence + ")",
              type,
              role: "undecided",
              access:
                x.rights === "yes"
                  ? "yes"
                  : x.rights === "no"
                    ? "no"
                    : "unknown",
              independence:
                x.independence === "yes"
                  ? "independent"
                  : x.independence === "no"
                    ? "shared"
                    : "unknown",
            },
          ];
    if (x.evidence === "both")
      p.sources.push({
        ...p.sources[0],
        id: "s_physical",
        name: "Legacy reported physical measurements",
        type: "experiment",
      });
    p.requirements[0].target = x.temperatureTolerance;
    p.requirements[0].operator =
      x.temperatureTolerance === null ? "unknown" : "max";
    p.economics = Object.fromEntries(econKeys.map((k) => [k, x[k]]));
    j.migration = {
      sourceSchema: Legacy.VERSION,
      originalText,
      note: "User must review the generalized mapping. A legacy speed objective appears as a prediction goal with its original decision text. Historical snapshots and per-input origins remain in the original record; no approval carries forward.",
    };
    validateJob(j);
    return j;
  }
  function brief(j) {
    validateJob(j);
    const p = derive(j.problem);
    return [
      "CARBON / ENGINEERING PROBLEM BRIEF",
      "Planning proposal. No scientific evaluation or authenticated approval.",
      j.problem.title || "Untitled engineering problem",
      "Job " + j.id + " / revision " + j.revision,
      "Rules: " + RULES,
      "Origin: " + j.origin,
      "",
      "ENGINEERING DECISION",
      j.problem.decision || "Unknown",
      j.problem.description,
      "",
      "PROPOSED ROUTE",
      p.route,
      "",
      "CLAIM TO INVESTIGATE",
      p.method.claim,
      "",
      "PROPOSED DELIVERABLES",
      ...p.deliverables.map((x) => "- " + x),
      "",
      "EVIDENCE LIMIT",
      p.referenceBoundary,
      "",
      "NEXT WORK",
      p.next,
      "",
      "GAPS",
      ...p.gaps.map((g) => g.priority + " / " + g.topic + ": " + g.text),
      "",
      "CONTRADICTIONS",
      ...p.contradictions,
      "",
      "COMPLETE INPUT RECORD",
      JSON.stringify(j.problem, null, 2),
      "",
      "COST SCENARIO",
      JSON.stringify(p.economics, null, 2),
      "",
      "Draft checkpoints: " + j.checkpoints.length,
      "Migration: " + (j.migration ? j.migration.note : "None"),
      "No inquiry was sent through this workbench.",
    ].join("\n");
  }
  return {
    VERSION,
    RULES,
    MAX_BYTES,
    PHYSICS,
    GOALS,
    OPTIONS,
    GUIDANCE,
    problemKeys,
    econKeys,
    copy,
    row,
    newJob,
    blankProblem,
    validateProblem,
    validateJob,
    exportJob,
    importJob,
    checkpoint,
    changes,
    fork,
    removeRow,
    derive,
    template,
    migrateLegacy,
    brief,
  };
});
