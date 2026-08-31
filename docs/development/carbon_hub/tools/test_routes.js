#!/usr/bin/env node
/* Dependency-free checks for static anchors and optional interactive routes. */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const primary = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const data = JSON.parse(fs.readFileSync(path.join(root, 'data', 'hub_data_v2.json'), 'utf8'));
const eventBundle = JSON.parse(fs.readFileSync(path.join(root, 'data', 'change_events.json'), 'utf8'));

if (/<script\b/i.test(primary)) {
  throw new Error('Primary index.html must contain zero script elements');
}

const staticRoutes = {
  'index.html': 'Carbon Development Hub',
  '#start': 'Understand the layers before changing the system',
  '#current': 'Captured repository position',
  '#waves': 'Wave A through Wave N',
  '#wave-B': 'Wave B: Science-ready authoring skeletons',
  '#tickets': 'Wave A and Wave B tickets',
  '#ticket-B-03': 'B-03: Generator API and fixed-viscosity Burgers fixture',
  '#changes': 'Place the change before implementing it',
  '#change-new-challenge': 'Add a new Challenge',
  '#change-reference-truth': 'Change a reference or truth path',
  '#change-measurement-scoring': 'Change measurement or scoring',
  '#maturity': 'Eight maturity dimensions',
  '#sources': 'Where authority lives'
};

let failures = 0;
for (const [route, expected] of Object.entries(staticRoutes)) {
  const id = route.startsWith('#') ? route.slice(1) : null;
  if ((id && !primary.includes(`id="${id}"`)) || !primary.includes(expected)) {
    console.error(`FAIL static ${route}: missing anchor or ${expected}`);
    failures += 1;
  } else {
    console.log(`PASS static ${route}`);
  }
}

for (const wave of data.waves) {
  if (!primary.includes(`id="wave-${wave.id}"`)) {
    console.error(`FAIL static missing Wave ${wave.id} anchor`);
    failures += 1;
  }
}
for (const ticket of data.tickets) {
  if (!primary.includes(`id="ticket-${ticket.id}"`)) {
    console.error(`FAIL static missing ${ticket.id} anchor`);
    failures += 1;
  }
}
for (const route of data.change_paths) {
  if (!primary.includes(`id="change-${route.id}"`)) {
    console.error(`FAIL static missing ${route.id} anchor`);
    failures += 1;
  }
}
for (const event of eventBundle.events) {
  if (!primary.includes(`id="event-${event.event_id}"`)) {
    console.error(`FAIL static missing ${event.event_id} anchor`);
    failures += 1;
  }
}

function classList() {
  return { add() {}, remove() {}, toggle() {} };
}
function element() {
  const attributes = {};
  return {
    innerHTML: '', innerText: '', value: '', classList: classList(),
    listeners: {},
    addEventListener(type, handler) { this.listeners[type] = handler; },
    closest() { return null; }, contains() { return false; }, querySelector() { return null; }, focus() {},
    setAttribute(name, value) { attributes[name] = String(value); },
    getAttribute(name) { return attributes[name] ?? null; },
    removeAttribute(name) { delete attributes[name]; },
    set onclick(value) { this._onclick = value; },
    get onclick() { return this._onclick; }
  };
}

const interactive = fs.readFileSync(path.join(root, 'interactive.html'), 'utf8');
const scriptMatch = interactive.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) throw new Error('interactive.html has no inline application script');
const elements = {
  '#view': element(), '#globalSearch': element(), '#searchResults': element(),
  '#menuBtn': element(), '#sidebar': element()
};
const document = {
  querySelector(selector) { return elements[selector] || element(); },
  querySelectorAll() { return []; },
  addEventListener() {}
};
const location = { hash: '#/home' };
const context = {
  console, document, location,
  window: { addEventListener() {}, scrollTo() {}, matchMedia() { return { matches: false, addEventListener() {} }; } },
  URLSearchParams, decodeURIComponent, encodeURIComponent
};
vm.createContext(context);
vm.runInContext(scriptMatch[1], context, { filename: 'interactive.html:inline-script' });

const maliciousUrl = 'https://example.test/\" onclick=\"globalThis.__hubXssProbe=1';
const encodedMaliciousUrl = JSON.stringify(maliciousUrl);
const attributeSinkCases = {
  button: vm.runInContext(`btn('probe', ${encodedMaliciousUrl}, 'outline', true)`, context),
  repositoryLinks: vm.runInContext(
    `repoLinks([{label:'probe',url:${encodedMaliciousUrl}}])`, context
  ),
  ticketCard: vm.runInContext(
    `ticketCard({id:'PROBE',status:'todo',title:'probe',one_line:'probe',wave:'B',phase:'probe',repo_links:[{url:${encodedMaliciousUrl}}]})`,
    context
  ),
  footer: vm.runInContext(
    `(() => { const original=DATA.meta.repository; DATA.meta.repository=${encodedMaliciousUrl}; const html=footer(); DATA.meta.repository=original; return html; })()`,
    context
  ),
  sources: vm.runInContext(
    `(() => { DATA.sources.__probe={label:'probe',url:${encodedMaliciousUrl}}; const html=sourcesPage(); delete DATA.sources.__probe; return html; })()`,
    context
  )
};
for (const [name, html] of Object.entries(attributeSinkCases)) {
  if (/"\s+on[a-z]+\s*=/i.test(html) || !html.includes('&quot;')) {
    console.error(`FAIL interactive ${name} URL attribute escaping`);
    failures += 1;
  }
}
if (!interactive.includes('href="${esc(x.href)}"')) {
  console.error('FAIL interactive search-result URL attribute escaping');
  failures += 1;
}

for (const event of eventBundle.events) {
  if (!interactive.includes(`"event_id":"${event.event_id}"`)) {
    console.error(`FAIL interactive data missing event ${event.event_id}`);
    failures += 1;
  }
}
const searchEvent = eventBundle.events[0];
elements['#globalSearch'].value = searchEvent.event_id;
elements['#globalSearch'].listeners.input();
if (!elements['#searchResults'].innerHTML.includes(searchEvent.event_id)) {
  console.error(`FAIL interactive search missing event ${searchEvent.event_id}`);
  failures += 1;
}

const interactiveRoutes = {
  '#/home': 'Understand what is changing and why.',
  '#/start': 'New to Carbon',
  '#/waves': 'The full development plan',
  '#/wave/B': 'Wave B: Science-ready authoring skeletons',
  '#/tickets': 'Ticket index',
  '#/ticket/B-03': 'B-03: Generator API and fixed-viscosity Burgers fixture',
  '#/changes': 'Place a change before you implement it',
  '#/change/new-challenge': 'Add a new Challenge',
  '#/change/reference-truth': 'Change a reference or truth path',
  '#/change/measurement-scoring': 'Change measurement or scoring',
  '#/maturity': 'Eight independent maturity states',
  '#/glossary': 'Carbon terms in plain language',
  '#/sources': 'Where authority lives'
};
for (const [route, expected] of Object.entries(interactiveRoutes)) {
  location.hash = route;
  vm.runInContext('render()', context);
  if (!elements['#view'].innerHTML.includes(expected)) {
    console.error(`FAIL interactive ${route}: missing ${expected}`);
    failures += 1;
  }
}

if (failures) process.exit(1);
console.log(`Static routes passed: ${Object.keys(staticRoutes).length}`);
console.log(`Interactive routes passed: ${Object.keys(interactiveRoutes).length}`);
