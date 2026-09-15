#!/usr/bin/env node
'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '..');
const source = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/c05_fixture_index_v1.json'), 'utf8'));
const filenames = [
  'c05_public_development_evidence_v1.json',
  'c05_public_development_noncomplete_v1.json',
];
const digest = (raw) => 'sha256:' + crypto.createHash('sha256').update(raw).digest('hex');

const fixtures = source.fixtures.map((item, index) => {
  const raw = fs.readFileSync(path.join(ROOT, 'data', filenames[index]), 'utf8');
  const bundle = JSON.parse(raw);
  const result = JSON.parse(bundle.measurement_result_json);
  if (bundle.source.fixture_id !== item.fixture_id || bundle.source.result_digest !== item.result_digest)
    throw Error('Retained fixture ordering or source identity mismatch');
  return {
    ...item,
    saved_projection: {
      evidence_state:
        result.disposition === 'COMPLETE_DEVELOPMENT_ONLY'
          ? 'SOURCE_MEASUREMENT_EVIDENCE_BOUND'
          : 'SOURCE_MEASUREMENT_EVIDENCE_NOT_EXECUTED',
      source_disposition: result.disposition,
      measurements: result.measurements,
      physics: result.physics,
      diagnostics: result.diagnostics,
      behavior_classification: bundle.behavior_classification,
      limitations: bundle.limitations,
      trace_state:
        result.disposition === 'COMPLETE_DEVELOPMENT_ONLY'
          ? 'SOURCE_MEASUREMENT_EXECUTED_SCIENTIFIC_DECISION_UNRESOLVED'
          : 'SOURCE_MEASUREMENT_NOT_EXECUTED',
      imported_artifact_digest: digest(raw),
    },
  };
});
const output = {
  ...source,
  schema_version: 'carbon.goal-workbench.c05-fixture-index.v2',
  fixtures,
};
fs.writeFileSync(
  path.join(ROOT, 'data/c05_fixture_index_v2.json'),
  JSON.stringify(output, null, 2) + '\n',
);
console.log('v2 saved-fixture index generated');
