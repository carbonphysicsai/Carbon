import { calculateEconomics } from "./economics.mjs";

const cards = [...document.querySelectorAll(".pf-card")];
const disclosures = cards.map((card) => card.querySelector("details"));
const filterButtons = [...document.querySelectorAll("[data-filter]")];
const expandButton = document.querySelector(".pf-expand-all");
const results = document.querySelector(".pf-results");
const menu = document.querySelector(".pf-mobile-menu");

const synchronizeExpansion = () => {
  const visible = disclosures.filter((detail) => !detail.closest("article").hidden);
  const expanded = visible.length > 0 && visible.every((detail) => detail.open);
  expandButton.setAttribute("aria-pressed", String(expanded));
  expandButton.textContent = expanded ? "Collapse visible cases" : "Expand visible cases";
};

function filter(group) {
  for (const card of cards) card.hidden = group !== "all" && card.dataset.group !== group;
  for (const button of filterButtons) button.setAttribute("aria-pressed", String(button.dataset.filter === group));
  const count = cards.filter((card) => !card.hidden).length;
  results.textContent = `${count} research program${count === 1 ? "" : "s"} · no live result implied`;
  synchronizeExpansion();
}

for (const button of filterButtons) button.addEventListener("click", () => filter(button.dataset.filter));
expandButton.addEventListener("click", () => {
  const open = expandButton.getAttribute("aria-pressed") !== "true";
  for (const detail of disclosures) if (!detail.closest("article").hidden) detail.open = open;
  synchronizeExpansion();
});
for (const detail of disclosures) detail.addEventListener("toggle", synchronizeExpansion);
document.querySelector(".pf-portfolio-toolbar").hidden = false;

function revealHash() {
  const detail = disclosures.find((item) => `#${item.id}` === location.hash);
  if (!detail) return;
  filter("all");
  detail.open = true;
  requestAnimationFrame(() => {
    detail.closest("article").scrollIntoView({ block: "start", behavior: "instant" });
    detail.querySelector("summary").focus({ preventScroll: true });
  });
}
window.addEventListener("hashchange", revealHash);
// Also reveal a same-hash link after a visitor has collapsed or filtered it.
document.addEventListener("click", (event) => {
  const anchor = event.target.closest("a[href^='#']");
  if (anchor && anchor.hash === location.hash) revealHash();
});
revealHash();

menu.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && menu.open) {
    menu.open = false;
    menu.querySelector("summary").focus();
  }
});
for (const link of menu.querySelectorAll("a")) link.addEventListener("click", () => { menu.open = false; });
document.addEventListener("click", (event) => {
  if (menu.open && !menu.contains(event.target)) menu.open = false;
});

const form = document.querySelector("#pf-economic-form");
const inputs = [...form.querySelectorAll("input")];
const error = document.querySelector("#pf-calc-error");
const dollar = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 2 });
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
function updateEconomics() {
  const values = {};
  for (const input of inputs) {
    const valid = input.value.trim() !== "" && input.validity.valid && Number.isFinite(input.valueAsNumber);
    input.setAttribute("aria-invalid", String(!valid));
    if (!valid) {
      error.hidden = false;
      error.textContent = input.name === "campaigns" ? "Use a whole campaign count from 1 to 1,000,000." : "Use costs from $0 to the stated input maximum; do not leave an assumption blank.";
      document.querySelector(".pf-calculator-results").hidden = true;
      return;
    }
    values[input.name] = input.valueAsNumber;
  }
  const calculation = calculateEconomics(values);
  error.hidden = true;
  document.querySelector(".pf-calculator-results").hidden = false;
  document.querySelector("#pf-baseline-total").textContent = dollar.format(calculation.baselineTotal);
  document.querySelector("#pf-model-total").textContent = dollar.format(calculation.modelTotal);
  const breakEven = document.querySelector("#pf-break-even");
  const note = document.querySelector("#pf-break-even-note");
  if (calculation.parity) {
    breakEven.textContent = "Cost parity at any volume";
    note.textContent = "No fixed cost and equal per-campaign costs; there is no cost saving.";
  } else if (calculation.breakEven === null) {
    breakEven.textContent = "No cost break-even";
    note.textContent = "The model route is not cheaper per campaign under these assumptions.";
  } else {
    breakEven.textContent = `${number.format(calculation.breakEven)} campaign${calculation.breakEven === 1 ? "" : "s"}`;
    note.textContent = "First whole campaign count at or below baseline cost; useful life and equal decision quality still have to hold.";
  }
  const savings = document.querySelector("#pf-savings");
  savings.dataset.state = calculation.difference > 0 ? "saving" : calculation.difference < 0 ? "loss" : "parity";
  savings.textContent = calculation.difference === 0 ? "Equal modeled cost at this campaign count." : `${dollar.format(Math.abs(calculation.difference))} ${calculation.difference > 0 ? "lower" : "higher"} modeled cost across ${number.format(values.campaigns)} campaign${values.campaigns === 1 ? "" : "s"}.`;
}
for (const input of inputs) { input.disabled = false; input.addEventListener("input", updateEconomics); }
form.addEventListener("submit", (event) => event.preventDefault());
updateEconomics();

// Printed evidence should include the limitations, not just collapsed teasers.
let beforePrint;
window.addEventListener("beforeprint", () => {
  beforePrint = { hidden: cards.map((card) => card.hidden), open: disclosures.map((detail) => detail.open) };
  for (const card of cards) card.hidden = false;
  for (const detail of disclosures) detail.open = true;
});
window.addEventListener("afterprint", () => {
  if (!beforePrint) return;
  cards.forEach((card, index) => { card.hidden = beforePrint.hidden[index]; });
  disclosures.forEach((detail, index) => { detail.open = beforePrint.open[index]; });
  beforePrint = undefined;
  synchronizeExpansion();
});
