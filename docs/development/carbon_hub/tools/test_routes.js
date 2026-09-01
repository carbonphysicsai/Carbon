#!/usr/bin/env node
/* Dependency-free checks for static anchors and optional interactive routes. */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const primary = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const data = JSON.parse(fs.readFileSync(path.join(root, 'data', 'hub_data_v2.json'), 'utf8'));
const eventBundle = JSON.parse(fs.readFileSync(path.join(root, 'data', 'change_events.json'), 'utf8'));
const currentWave = data.waves.find(wave => wave.id === data.current.wave);
const currentTicket = data.tickets.find(ticket => ticket.id === data.current.ticket);
const ticketWaveIds = [...new Set(data.tickets.map(ticket => ticket.wave))];
function humanJoin(values) {
  if (values.length === 1) return values[0];
  if (values.length === 2) return `${values[0]} and ${values[1]}`;
  return `${values.slice(0, -1).join(', ')}, and ${values.at(-1)}`;
}
const ticketWaveLabel = humanJoin(ticketWaveIds.map(wave => `Wave ${wave}`));

if (/<script\b/i.test(primary)) {
  throw new Error('Primary index.html must contain zero script elements');
}

const staticRoutes = {
  'index.html': 'Carbon Development Hub',
  '#start': 'Understand the layers before changing the system',
  '#current': 'Captured repository position',
  '#waves': `Wave ${data.waves[0].id} through Wave ${data.waves.at(-1).id}`,
  [`#wave-${currentWave.id}`]: `Wave ${currentWave.id}: ${currentWave.title}`,
  '#tickets': `Captured tickets across ${ticketWaveLabel}`,
  [`#ticket-${currentTicket.id}`]: `${currentTicket.id}: ${currentTicket.title}`,
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
if (!interactive.includes(`<strong>Wave ${data.current.wave} / ${data.current.ticket}</strong>`) ||
    !interactive.includes(data.current.stage) ||
    interactive.includes('__CURRENT_POSITION__') || interactive.includes('__CURRENT_STAGE__')) {
  console.error('FAIL interactive sidebar current-position binding');
  failures += 1;
}
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
  [`#/wave/${currentWave.id}`]: `Wave ${currentWave.id}: ${currentWave.title}`,
  '#/tickets': 'Ticket index',
  [`#/ticket/${currentTicket.id}`]: `${currentTicket.id}: ${currentTicket.title}`,
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

const livingStateFixture = vm.runInContext(`(() => {
  const originalCurrent = DATA.current;
  const originalWaves = DATA.waves;
  const originalTickets = DATA.tickets;
  try {
    const fixtureTitle = 'Wave C living-state fixture';
    DATA.current = {
      ...originalCurrent,
      wave: 'C',
      wave_title: 'Portfolio learning',
      wave_status: 'active in bounded fixture scope',
      ticket: 'C-01',
      ticket_title: fixtureTitle,
      ticket_status: 'in_progress',
      stage: 'C-01 is the selected current fixture ticket.',
      recent_dependencies: [],
      other_completed_wave_context: [],
      downstream_handoffs: [],
      parallel_context: [],
      next_selected_ticket: null,
      maturity_summary: 'C-01 is specified in this fixture; later maturity states remain unearned.',
      decision_series: ['C-01-D1'],
      decision_series_status: 'C-01-D1 is the captured fixture decision.',
      technical_decision_route: 'https://example.test/decisions/C-01'
    };
    DATA.waves = originalWaves.map(wave => ({
      ...wave,
      status: wave.id === 'C' ? 'active' : wave.status === 'active' ? 'planned' : wave.status,
      ticket_ids: wave.id === 'C' ? ['C-01'] : wave.ticket_ids
    }));
    DATA.tickets = [...originalTickets, {
      id: 'C-01', wave: 'C', title: fixtureTitle, status: 'in_progress', phase: 'Wave C',
      one_line: 'Exercise renderer living-state bindings without changing repository authority.',
      what: 'Fixture-only route coverage.', why: 'Prevent stale current-wave presentation.',
      adds: 'A test-only current ticket.', does_not: 'It grants no implementation authority.',
      depends_on: [], unlocks: [], owner: 'Fixture driver', reviewer: 'Fixture reviewer',
      master_questions: [], repo_links: [{label:'Fixture ticket',url:'https://example.test/tickets/C-01'}],
      orientation_note: 'Fixture-only presentation test.'
    }];
    location.hash = '#/home';
    const homeHtml = home();
    location.hash = '#/tickets';
    const ticketsHtml = ticketsPage();
    return {
      homeHtml,
      ticketsHtml,
      waveHtml: wavePage('C'),
      maturityHtml: maturityPage(),
      emptyAnchorHtml: changePage('protocol-defect')
    };
  } finally {
    DATA.current = originalCurrent;
    DATA.waves = originalWaves;
    DATA.tickets = originalTickets;
  }
})()`, context);

const fixtureExpectations = {
  home: [livingStateFixture.homeHtml, ['Wave C', 'C-01', 'C-01-D1']],
  tickets: [livingStateFixture.ticketsHtml, ['Wave C', 'value="C"', 'ticket C-01']],
  wave: [livingStateFixture.waveHtml, ['Wave C:', 'C-01']],
  maturity: [livingStateFixture.maturityHtml, ['Example: current C-01', 'C-01 is specified in this fixture']],
  emptyAnchor: [livingStateFixture.emptyAnchorHtml, ['No current Wave C ticket anchor', 'WAVE-C/C-01']]
};
for (const [surface, [html, expectedText]] of Object.entries(fixtureExpectations)) {
  for (const expected of expectedText) {
    if (!html.includes(expected)) {
      console.error(`FAIL living-state fixture ${surface}: missing ${expected}`);
      failures += 1;
    }
  }
}
for (const stale of ['Wave B is active', 'current B-03', 'B-03 supplies', 'B-03-D1 through B-03-D8']) {
  if (livingStateFixture.homeHtml.includes(stale) || livingStateFixture.maturityHtml.includes(stale) || livingStateFixture.emptyAnchorHtml.includes(stale)) {
    console.error(`FAIL living-state fixture retained stale current claim: ${stale}`);
    failures += 1;
  }
}

if (failures) process.exit(1);
console.log(`Static routes passed: ${Object.keys(staticRoutes).length}`);
console.log(`Interactive routes passed: ${Object.keys(interactiveRoutes).length}`);
console.log(`Living-state fixture surfaces passed: ${Object.keys(fixtureExpectations).length}`);
