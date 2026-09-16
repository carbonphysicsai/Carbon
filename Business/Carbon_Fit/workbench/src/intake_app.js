(function () {
  "use strict";
  const I = CarbonClientIntake;
  const quantityLabels = {
    preparation_time: "One-time preparation / training / reference generation",
    prediction_latency: "Recurring prediction latency",
    reference_query_time: "Reference-query time",
    workload_frequency: "Workload frequency",
    desired_accuracy: "Requested accuracy (unreviewed intent)",
  };
  const quantityRoot = document.getElementById("quantity-fields");
  quantityRoot.innerHTML = I.QUANTITY_FIELDS.map(
    (field) => `<div class="quantity-row" data-quantity-row="${field}"><label>${quantityLabels[field]}<select data-quantity-state="${field}"><option value="UNKNOWN">Unknown</option><option value="POINT">Point estimate</option><option value="RANGE">Supplied range</option></select></label><label data-quantity-unit-wrap="${field}" hidden>Unit<input data-quantity-unit="${field}" disabled></label><div class="quantity-values"><label class="point" data-quantity-point-wrap="${field}" hidden>Value<input type="number" step="any" data-quantity-value="${field}" disabled></label><label data-quantity-range-wrap="${field}" hidden>Minimum<input type="number" step="any" data-quantity-min="${field}" disabled></label><label data-quantity-range-wrap="${field}" hidden>Maximum<input type="number" step="any" data-quantity-max="${field}" disabled></label></div></div>`,
  ).join("");

  function answer(value) {
    return value.trim()
      ? { state: "VALUE", value, origin: "USER_ENTERED_LOCAL" }
      : { state: "UNKNOWN", value: "", origin: "USER_ENTERED_LOCAL" };
  }
  function numberOrNull(input) {
    return input.value === "" ? null : Number(input.value);
  }
  function buildDraft() {
    const draft = I.newDraft(
      document.getElementById("draft-id").value,
      document.getElementById("revision-id").value,
    );
    document.querySelectorAll("[data-text]").forEach((node) => {
      draft.answers[node.dataset.text] = answer(node.value);
    });
    I.QUANTITY_FIELDS.forEach((field) => {
      const state = document.querySelector(`[data-quantity-state="${field}"]`).value;
      draft.quantities[field] = {
        state,
        value: state === "POINT" ? numberOrNull(document.querySelector(`[data-quantity-value="${field}"]`)) : null,
        minimum: state === "RANGE" ? numberOrNull(document.querySelector(`[data-quantity-min="${field}"]`)) : null,
        maximum: state === "RANGE" ? numberOrNull(document.querySelector(`[data-quantity-max="${field}"]`)) : null,
        unit: state === "UNKNOWN" ? "" : document.querySelector(`[data-quantity-unit="${field}"]`).value,
        note: "",
        origin: "USER_ENTERED_LOCAL",
      };
    });
    const predecessorRevision = document.getElementById("predecessor-revision").value.trim();
    const predecessorDigest = document.getElementById("predecessor-digest").value.trim();
    if (predecessorRevision || predecessorDigest)
      draft.predecessor = {
        draft_id: draft.draft_id,
        revision_id: predecessorRevision,
        canonical_digest: predecessorDigest,
      };
    draft.summary = I.summaryFor(draft);
    return I.validateDraft(draft);
  }
  function render() {
    try {
      const draft = buildDraft();
      document.getElementById("summary-text").textContent = draft.summary.text;
      document.getElementById("next-clarification").textContent = draft.summary.next_clarification;
      document.getElementById("intake-status").textContent = "Ready for local review. Nothing has been sent.";
    } catch (error) {
      document.getElementById("intake-status").textContent = error.message;
    }
  }
  document.querySelectorAll("textarea,input,select").forEach((node) =>
    node.addEventListener("input", render),
  );
  document.querySelectorAll("[data-quantity-state]").forEach((node) =>
    node.addEventListener("change", () => {
      const field = node.dataset.quantityState;
      const point = node.value === "POINT";
      const range = node.value === "RANGE";
      document.querySelector(`[data-quantity-unit-wrap="${field}"]`).hidden = node.value === "UNKNOWN";
      document.querySelector(`[data-quantity-point-wrap="${field}"]`).hidden = !point;
      document.querySelectorAll(`[data-quantity-range-wrap="${field}"]`).forEach((element) => (element.hidden = !range));
      document.querySelector(`[data-quantity-unit="${field}"]`).disabled = node.value === "UNKNOWN";
      document.querySelector(`[data-quantity-value="${field}"]`).disabled = !point;
      document.querySelector(`[data-quantity-min="${field}"]`).disabled = !range;
      document.querySelector(`[data-quantity-max="${field}"]`).disabled = !range;
      render();
    }),
  );
  document.getElementById("export-intake").onclick = () => {
    try {
      const draft = buildDraft();
      const blob = new Blob([JSON.stringify(draft, null, 2) + "\n"], { type: "application/json" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `${draft.draft_id}_${draft.revision_id}.carbon-intake.json`;
      link.click();
      URL.revokeObjectURL(link.href);
      document.getElementById("intake-status").textContent = "Draft downloaded locally. Nothing was transmitted to Carbon.";
    } catch (error) {
      document.getElementById("intake-status").textContent = "Export blocked: " + error.message;
    }
  };
  render();
})();
