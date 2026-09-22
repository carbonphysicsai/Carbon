(function (root) {
  "use strict";
  // Resolved the way every other module here resolves its siblings: from the
  // page when the shell loaded them in order, or by require under a test.
  const S =
    root.CarbonScientificStudies ||
    (typeof require !== "undefined" ? require("./scientific_studies.js") : null);
  const P =
    root.CarbonPublicWorkbench ||
    (typeof require !== "undefined" ? require("./public_workbench.js") : null);
  const $ = (id) => root.document.getElementById(id);

  // Question text for a visitor who has never written a scope field. The field
  // identities are the internal design's; only the prompts are new, so an
  // export needs no translation on the way in.
  const PROMPTS = {
    requested_goal: ["What kind of answer do you need?", "For example: Dynamics — how a field evolves over time."],
    physics_family: ["What kind of physics is this?", "Name it however you would say it out loud. Carbon will tell you whether it has a matching source study."],
    intended_use: ["What decision would this prediction feed?", "What changes at your end once you can predict it."],
    inputs: ["What would you give the model, every time you ask it?", "The quantities you can actually supply."],
    outputs: ["What should it give back?", "Which quantities, at which points or times."],
    units: ["What units are these in?", "Or say dimensionless. Ambiguity here cannot be checked."],
    geometry: ["What is the domain?", "Its shape and extent, and whether it repeats."],
    conditions: ["What are the boundary and initial conditions?", "Without these the problem is not determined, however well the rest is described."],
    regime: ["Over what range does it have to hold?", "Speeds, temperatures, pressures — wherever the behaviour changes."],
    exclusions: ["What is explicitly out of scope?", "What you are not asking for is as useful as what you are."],
    query_workload: ["How often would you ask it?", "Per day, per design iteration, per anything."],
    turnaround: ["How fast does an answer have to come back?", "For the decision it feeds, not in the abstract."],
    failure_consequences: ["What happens if it is wrong?", "The consequence, not the error metric."],
    data_access: ["What data could Carbon use?", "And what you cannot share."],
    rights_scope: ["Who owns the data involved?", "Synthetic, internal, or third-party. Unresolved rights stop a study before any physics does."],
    commercial_context: ["What is the commercial setting?", "Optional, and it changes no technical answer."],
    disclosure_scope: ["What may Carbon say about this work?", "Optional."],
    deployment_environment: ["Where would the finished model run?", "Optional."],
    "reference_plan.equation": ["What equation governs this, as far as you know?", "An approximate or uncertain answer is far better than none."],
    "reference_plan.method": ["What do you compute it with today?", "The solver, tool or measurement you compare against."],
  };

  // A field is either on the draft's scope or on its reference plan. One
  // accessor pair, so the form cannot drift from the exported shape.
  const read = (draft, field) =>
    field.startsWith("reference_plan.")
      ? draft.reference_plan[field.slice("reference_plan.".length)]
      : draft.scope[field];
  const write = (draft, field, value) => {
    if (field.startsWith("reference_plan."))
      draft.reference_plan[field.slice("reference_plan.".length)] = value;
    else draft.scope[field] = value;
  };

  function identity() {
    // Local and disposable. It exists so both sides can name the same draft,
    // not to identify a person, and it is generated in the browser.
    const random = root.crypto.getRandomValues(new Uint8Array(8));
    return (
      "public-draft-" +
      Array.from(random, (n) => n.toString(16).padStart(2, "0")).join("")
    );
  }

  // The export's fingerprint is a WebCrypto digest, and a browser that does
  // not expose `crypto.subtle` to a local file cannot compute one. The
  // questions and the structural check do not need it, so that case loses the
  // download and nothing else — provided it says so rather than reporting the
  // draft as incomplete, which is a different problem with a different fix.
  const DIGEST_UNAVAILABLE =
    "This browser does not give a local file the cryptographic digest this " +
    "draft is fingerprinted with, so it cannot be downloaded from here. The " +
    "questions and the check above still work. Open this file over http(s), " +
    "or copy your answers into an email — they are what matters.";
  const canDigest = () => Boolean(root.crypto && root.crypto.subtle);

  // Created in install(), so requiring this module has no side effect.
  let draft = null;
  let revealed = 1;
  let everything = false;

  const escape = (value) =>
    String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  function stageComplete(stage) {
    return stage.fields.some((field) => read(draft, field).trim().length > 0);
  }

  function renderForm() {
    const html = P.STAGES.map((stage, index) => {
      const open = everything || index < revealed;
      const fields = stage.fields
        .map((field) => {
          const [prompt, note] = PROMPTS[field] || [field, ""];
          return (
            '<label class="field"><span class="prompt">' +
            escape(prompt) +
            "</span>" +
            (note ? '<span class="note">' + escape(note) + "</span>" : "") +
            '<textarea data-field="' +
            escape(field) +
            '" rows="2" maxlength="8000">' +
            escape(read(draft, field)) +
            "</textarea></label>"
          );
        })
        .join("");
      return (
        '<fieldset class="stage" data-stage="' +
        escape(stage.id) +
        '"' +
        (open ? "" : " hidden") +
        "><legend>" +
        escape(stage.title) +
        "</legend>" +
        fields +
        "</fieldset>"
      );
    }).join("");
    $("public-form").innerHTML = html;
    for (const node of $("public-form").querySelectorAll("textarea"))
      node.addEventListener("input", onInput);
    $("stage-progress").textContent = everything
      ? P.STAGES.length + " stages open"
      : "Stage " + Math.min(revealed, P.STAGES.length) + " of " + P.STAGES.length;
  }

  function issueItem(item) {
    // The check's own wording first, then the plain-language note. Showing the
    // original is what keeps this a presentation layer: a visitor and an
    // engineer are looking at the same sentence.
    return (
      '<li><span class="issue">' +
      escape(item.issue) +
      '</span><span class="plain">' +
      escape(item.plain) +
      "</span></li>"
    );
  }

  async function renderStatus() {
    const result = S.check(P.checkable(draft));
    const view = P.explain(result);
    $("check-status").textContent =
      view.status === "STRUCTURALLY_CHECKED"
        ? "structurally checked · still NOT_QUALIFIED"
        : view.open_for_visitor === 0
          ? "everything you can close is closed"
          : view.open_for_visitor + " left for you";
    $("check-limitations").textContent = view.limitations;
    const groups = [
      ["yours", "VISITOR"],
      ["carbon", "CARBON"],
      ["unclassified", "UNCLASSIFIED"],
    ];
    for (const [name, owner] of groups) {
      const items = view.explained.filter((item) => item.owner === owner);
      $(name + "-list").innerHTML = items.length
        ? items.map(issueItem).join("")
        : '<li class="clear">Nothing outstanding here.</li>';
      const count = $(name + "-count");
      if (count) count.textContent = items.length ? String(items.length) : "";
    }
    // Only appears when the check says something this page has no note for,
    // which is the case that must never be silent.
    $("unclassified-section").hidden = view.unclassified === 0;
    if (!canDigest()) {
      $("artifact-preview").textContent = DIGEST_UNAVAILABLE;
      return null;
    }
    try {
      const artifact = await P.exportWorkspace(draft, result, S);
      $("artifact-preview").textContent = JSON.stringify(artifact, null, 2);
      return artifact;
    } catch (error) {
      $("artifact-preview").textContent = "Draft not exportable yet: " + error.message;
      return null;
    }
  }

  function onInput(event) {
    write(draft, event.target.dataset.field, event.target.value);
    const index = P.STAGES.findIndex((stage) =>
      stage.fields.includes(event.target.dataset.field),
    );
    // Progressive disclosure: answering anything in the current stage opens the
    // next one. Nothing is ever closed again, and nothing is withheld from a
    // visitor who asked for everything.
    if (index === revealed - 1 && stageComplete(P.STAGES[index]) && revealed < P.STAGES.length) {
      revealed += 1;
      renderForm();
      const opened = $("public-form").querySelector('[data-stage="' + P.STAGES[revealed - 1].id + '"]');
      if (opened) opened.scrollIntoView({ block: "nearest" });
    }
    renderStatus();
  }

  function download(artifact) {
    const blob = new root.Blob([JSON.stringify(artifact, null, 2) + "\n"], {
      type: "application/json",
    });
    const link = root.document.createElement("a");
    link.href = root.URL.createObjectURL(blob);
    link.download = artifact.design_id + ".carbon-public-workbench.json";
    link.click();
    root.URL.revokeObjectURL(link.href);
  }

  function install() {
    $("open-all").onclick = () => {
      everything = true;
      renderForm();
      renderStatus();
    };
    $("export-draft").onclick = async () => {
      try {
        if (!canDigest()) {
          $("export-status").textContent = DIGEST_UNAVAILABLE;
          return;
        }
        const artifact = await renderStatus();
        if (!artifact) throw Error("the draft is not yet exportable");
        download(artifact);
        $("export-status").textContent =
          "Saved to your computer as " +
          artifact.design_id +
          ".carbon-public-workbench.json. Nothing was sent.";
      } catch (error) {
        $("export-status").textContent = "Export blocked: " + error.message;
      }
    };
    $("reset-draft").onclick = () => {
      draft = P.emptyDraft(identity());
      revealed = 1;
      everything = false;
      renderForm();
      renderStatus();
      $("export-status").textContent = "Draft cleared. Nothing was stored.";
    };
    draft = P.emptyDraft(identity());
    // The controls ship disabled so that a visitor without scripting sees
    // controls that plainly do not work rather than three that silently do
    // nothing. They are enabled here, which is the moment they start working.
    for (const id of ["open-all", "export-draft", "reset-draft"])
      $(id).removeAttribute("disabled");
    renderForm();
    renderStatus();
  }

  if (root.document) {
    if (root.document.readyState === "loading")
      root.document.addEventListener("DOMContentLoaded", install);
    else install();
  }
  root.CarbonPublicWorkbenchApp = Object.freeze({ PROMPTS });
  if (typeof module !== "undefined") module.exports = { PROMPTS };
})(typeof globalThis !== "undefined" ? globalThis : this);
