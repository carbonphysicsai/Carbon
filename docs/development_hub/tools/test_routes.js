#!/usr/bin/env node
/* Browser-free smoke test for the static-first Carbon Development Hub. */
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const checks = {
  'home': 'Understand what is changing and why.',
  'start': 'New to Carbon',
  'waves': 'Waves A through N',
  'wave-b': 'Wave B: Science-ready authoring skeletons',
  'tickets': 'Ticket index',
  'ticket-b-03': 'B-03',
  'routes': 'Place a change before implementing it',
  'change-new-challenge': 'Add a new Challenge',
  'change-model-architecture': 'Add or change a model architecture',
  'change-miner-prior': 'Add or change a miner prior',
  'maturity': 'Eight independent maturity states',
  'glossary': 'Glossary',
  'sources': 'Authority and sources'
};
let failures = 0;
for (const [id, expected] of Object.entries(checks)) {
  const idPattern = new RegExp(`id=["']${id}["']`);
  if (!idPattern.test(html) || !html.includes(expected)) {
    console.error(`FAIL #${id}: missing anchor or text ${expected}`);
    failures += 1;
  } else {
    console.log(`PASS #${id}`);
  }
}
if (/<script\b/i.test(html)) {
  console.error('FAIL index.html: primary hub must not require scripts');
  failures += 1;
}
if (failures) process.exit(1);
console.log(`Static hub route smoke test passed: ${Object.keys(checks).length} anchors.`);
