import { sources, reviewedDate } from "./content.mjs";
import { highlights, screeningImpact, screeningScenario } from "./highlights.mjs";
import { visual } from "./visuals.mjs";
const esc = (value) => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const round = (value) => Math.round(value).toLocaleString("en-US");
const dollars = (value) => value >= 1000 ? `$${(value / 1000).toFixed(1)}k` : `$${round(value)}`;
const card = (p, index) => {
  const impact = screeningImpact(p.solverSeconds);
  return `<article class="pf-card" id="${p.id}" aria-labelledby="${p.id}-title">
    <div class="pf-visual"><span class="pf-number">${String(index + 1).padStart(2, "0")}</span>${visual(p.id, esc(`Concept illustration: ${p.title}`))}<span class="pf-state">${p.state}</span></div>
    <div class="pf-card-copy"><h2 id="${p.id}-title">${p.title}</h2><p class="pf-highlight">${p.highlight}</p>
      <div class="pf-use"><h3>Industrial use</h3><p>${p.industry}</p></div>
      <div class="pf-impact"><h3>Illustrative screening savings <span>• trained model</span></h3><div class="pf-impact-values"><div><strong>~${round(impact.runHoursSaved)}<span>run-hours</span></strong><small>simulation time avoided</small></div><div><strong>~${dollars(impact.dollarsSaved)}</strong><small>compute cost avoided</small></div></div><a class="pf-basis" href="${sources[p.source].url}" target="_blank" rel="noreferrer" title="${esc(p.basis)}">Solve assumption: ${p.baseline} ↗</a></div>
      <div class="pf-customers"><h3>Customer targets</h3><p>${p.customers}</p></div>
    </div>
  </article>`;
};
export function renderPortfolio() {
  return `<!doctype html>
<html lang="en" data-page="portfolio"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Research Portfolio · Carbon</title><meta name="description" content="Eight physical problems. The industrial use, customer targets and illustrative time-and-cost impact of fast surrogate models.">
<link rel="canonical" href="https://carbonphysics.ai/portfolio/"><meta name="theme-color" content="#f5f5f0">
<meta property="og:title" content="Eight problems. Real-world value. · Carbon"><meta property="og:type" content="website"><meta property="og:url" content="https://carbonphysics.ai/portfolio/"><meta property="og:image" content="https://carbonphysics.ai/assets/og-carbon.png">
<link rel="icon" href="../favicon.svg" type="image/svg+xml"><link rel="preload" href="../assets/neue-0.otf" as="font" type="font/otf" crossorigin>
<link rel="stylesheet" href="./portfolio.css"><script type="module" src="./portfolio.js"></script>
</head><body><a class="pf-skip" href="#portfolio">Skip to portfolio</a>
<header class="pf-header"><div class="pf-wrap pf-header-inner"><a class="pf-brand" href="https://carbonphysics.ai/" aria-label="Carbon home"><img src="../assets/brand-2.svg" width="172" height="40" alt="Carbon"></a><nav aria-label="Main"><a href="https://carbonphysics.ai/investors/">Investors</a><a href="#portfolio" aria-current="page">Portfolio</a><a class="pf-contact" href="mailto:hello@carbonphysics.ai?subject=Carbon%20research%20portfolio">Discuss a program ↗</a></nav></div></header>
<main class="pf-wrap"><section class="pf-hero" aria-labelledby="portfolio-title"><p class="pf-eyebrow">Carbon / Research portfolio</p><h1 id="portfolio-title">Eight problems.<br class="pf-mobile-break"> Real-world value<span>.</span></h1><p class="pf-lede">Fast physical models for decisions that matter. The problems, industrial uses and potential customers behind our research portfolio.</p><p class="pf-scenario-note">Proposed programs. Illustrative savings per 1,000 candidate cases with a trained surrogate—not measured Carbon results or total ROI.</p></section>
<section class="pf-grid" id="portfolio" aria-label="Eight research problems">${highlights.map(card).join("\n")}</section>
<aside class="pf-method" aria-labelledby="scenario-title"><div><h2 id="scenario-title">What the impact figures mean</h2><p>${screeningScenario.designs.toLocaleString("en-US")} candidate cases · ${screeningScenario.solverChecks} final solver checks · ${screeningScenario.predictionSeconds * 1000} ms per surrogate prediction · assumed $${screeningScenario.dollarsPerRunHour}/run-hour. Figures are rounded serial run-hours and compute spend avoided with an already-trained model, not elapsed project time.</p></div><p>Solver times are roadmap estimates, except battery's historical study median. Build, data, training, calibration and upkeep costs are excluded. Compare against optimized solvers and cheap reduced models before claiming savings. Customer types are targets, not clients; visuals are concepts, not results.</p></aside>
</main><footer class="pf-wrap pf-footer"><span>© 2026 Carbon Physics, Inc.</span><p>${reviewedDate} · Portfolio planning includes 25% Bittensor investor fit; this is not an emissions allocation or launch approval.</p><a href="${sources.roadmap.url}" target="_blank" rel="noreferrer">Research basis ↗</a></footer>
</body></html>\n`;
}
