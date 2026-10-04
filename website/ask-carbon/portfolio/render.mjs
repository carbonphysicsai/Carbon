import { sources, reviewedDate } from "./content.mjs";
import { highlights } from "./highlights.mjs";
import { impactCases, outcomes, scaleIllustration } from "./impact.mjs";
import { visual } from "./visuals.mjs";
import { renderSolverIllustration } from "./solver-preview.mjs";
const esc = (value) => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const card = (p, index) => {
  const scale = scaleIllustration(p.id);
  return `<article class="pf-card" id="${p.id}" aria-labelledby="${p.id}-title">
    <div class="pf-visual"><span class="pf-number">${String(index + 1).padStart(2, "0")}</span>${visual(p.id, esc(`Concept illustration: ${p.title}`))}<span class="pf-state">${p.state}</span></div>
    <div class="pf-card-copy"><h2 id="${p.id}-title">${p.title}</h2><p class="pf-highlight">${p.highlight}</p>
      <div class="pf-use"><h3>Industrial use</h3><p>${p.industry}</p></div>
      <div class="pf-impact"><h3>Impact to prove</h3><p class="pf-outcome">${outcomes[p.id]}</p><div class="pf-scale pf-scale--${impactCases[p.id].kind}"><h3>If achieved at scale <span>· illustration</span></h3><div class="pf-impact-values"><div><strong>${esc(scale.first)}</strong><small>${scale.firstLabel}</small></div><span class="pf-impact-arrow" aria-hidden="true">→</span><div><strong>${esc(scale.second)}</strong><small>${scale.secondLabel}</small></div></div><p class="pf-scale-note">${scale.note}</p></div><a class="pf-basis" href="${sources[p.source].url}" target="_blank" rel="noreferrer">Research basis ↗</a></div>
      <div class="pf-customers"><h3>Customer targets</h3><p>${p.customers}</p></div>
    </div>
  </article>`;
};
export function renderPortfolio() {
  return `<!doctype html>
<html lang="en" data-page="portfolio"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Research Portfolio · Carbon</title><meta name="description" content="Eight physical problems. Faster engineering decisions, physical outcomes to prove and conditional value at customer scale. Future fixed-resource model-versus-solver design contests.">
<link rel="canonical" href="https://carbonphysics.ai/portfolio/"><meta name="theme-color" content="#f5f5f0">
<meta property="og:title" content="Eight problems. Real-world value. · Carbon"><meta property="og:type" content="website"><meta property="og:url" content="https://carbonphysics.ai/portfolio/"><meta property="og:image" content="https://carbonphysics.ai/assets/og-carbon.png">
<link rel="icon" href="../favicon.svg" type="image/svg+xml"><link rel="preload" href="../assets/neue-0.otf" as="font" type="font/otf" crossorigin>
<link rel="stylesheet" href="./portfolio.css"><script type="module" src="./portfolio.js"></script>
</head><body><a class="pf-skip" href="#portfolio">Skip to portfolio</a>
<header class="pf-header"><div class="pf-wrap pf-header-inner"><a class="pf-brand" href="https://carbonphysics.ai/" aria-label="Carbon home"><img src="../assets/brand-2.svg" width="172" height="40" alt="Carbon"></a><nav aria-label="Main"><a href="https://carbonphysics.ai/investors/">Investors</a><a href="#portfolio" aria-current="page">Portfolio</a><a class="pf-contact" href="mailto:hello@carbonphysics.ai?subject=Carbon%20research%20portfolio">Discuss a program ↗</a></nav></div></header>
<main class="pf-wrap"><section class="pf-hero" aria-labelledby="portfolio-title"><p class="pf-eyebrow">Carbon / Research portfolio</p><h1 id="portfolio-title">Eight problems.<br class="pf-mobile-break"> Real-world value<span>.</span></h1><p class="pf-lede">Queryable physics for faster engineering decisions—and better outcomes across real products. The value is the decision, not just the compute saved.</p><p class="pf-scenario-note">Proposed programs. Scale figures are conditional illustrations—not Carbon results, performance targets, forecasts or total ROI.</p></section>
<section class="pf-grid" id="portfolio" aria-label="Eight research problems">${highlights.map(card).join("\n")}</section>
<aside class="pf-method" aria-labelledby="scenario-title"><div><h2 id="scenario-title">From a physical improvement to customer value</h2><p>Scale illustrations show what a specified gain would mean—not what a Carbon model has achieved. Prototype costs and lead times need customer quotes. Operational gains require separate validation.</p></div><p>Net value must include data, training, verification, integration, serving and upkeep. Faster queries alone do not establish better decisions. Customer types are targets, not clients; card visuals are concepts.</p></aside>
<section class="pf-contest" id="design-contest" aria-labelledby="contest-title"><div class="pf-contest-intro"><div><p class="pf-eyebrow">Future demonstration / fixed-resource design contest</p><h2 id="contest-title">Better designs.<br> Same constraints.</h2></div><p>Once eligible models ship, this becomes a side-by-side automated design contest: the leading model versus a strong solver-led optimization workflow, including competitive reduced methods.</p></div>
<div class="pf-contest-panels"><figure class="pf-solver-panel"><div class="pf-panel-heading"><h3>Solver view</h3><span>Numerical illustration only</span></div>${renderSolverIllustration()}<figcaption>Locally computed 2D heat-equation test. Not a cold-plate benchmark, optimization run or contest result.</figcaption></figure><div class="pf-model-panel"><div class="pf-panel-heading"><h3>Leading model</h3><span>Comparison slot</span></div><div class="pf-model-slot"><span class="pf-slot-mark" aria-hidden="true">↔</span><h4>Side by side when models ship.</h4><p>No model output or winner is shown yet.</p></div></div></div>
<div class="pf-contest-rules"><p><strong>Fixed:</strong> design bounds, physical constraints, compute and wall-clock budgets.</p><p><strong>Compare:</strong> independently checked design quality, elapsed search time and total cost—including preparation and model build.</p></div></section>
</main><footer class="pf-wrap pf-footer"><span>© 2026 Carbon Physics, Inc.</span><p>${reviewedDate} · Portfolio planning includes 25% Bittensor investor fit; this is not an emissions allocation or launch approval.</p><a href="${sources.roadmap.url}" target="_blank" rel="noreferrer">Research basis ↗</a></footer>
</body></html>\n`;
}
