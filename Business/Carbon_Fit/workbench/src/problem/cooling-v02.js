/* Carbon workbench: deterministic planning rules. No evaluation or approval API. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CarbonCoolingV02 = api;
})(typeof window === 'object' ? window : this, function () {
  'use strict';
  const VERSION = 'carbon.workbench.planning.v0.2';
  const RULES = 'cooling.rules.2026-09-11.1';
  const ENUMS = {
    goal: ['ranking', 'hotspots', 'speed'], geometry: ['fixed', 'family', 'unseen'],
    model: ['existing', 'search', 'unsure'], evidence: ['simulation', 'physical', 'both', 'none'],
    independence: ['yes', 'no', 'unknown'], rights: ['yes', 'review', 'no'],
    dynamics: ['steady', 'transient'], regime: ['single', 'two', 'unknown']
  };
  const TEXT = ['title', 'notes', 'hardware'];
  const NUMBERS = ['loadMin', 'loadMax', 'flowMin', 'flowMax', 'temperatureTolerance',
    'queries', 'baselineSeconds', 'targetSeconds', 'baselineCost', 'targetCost', 'setupCost', 'monthlyCost'];
  const INPUT_KEYS = [...Object.keys(ENUMS), ...TEXT, ...NUMBERS, 'matchedTiming'];
  const DEFAULTS = {
    title: 'A faster way to screen cooling designs', goal: 'ranking', geometry: 'family', model: 'existing',
    evidence: 'simulation', independence: 'unknown', rights: 'review', dynamics: 'steady', regime: 'single',
    notes: '', hardware: '', matchedTiming: false,
    ...Object.fromEntries(NUMBERS.map(k => [k, null]))
  };
  function newJob(id) {
    return {schema: VERSION, ruleVersion: RULES, id, revision: 1, inputs: {...DEFAULTS},
      origins: Object.fromEntries(INPUT_KEYS.map(k => [k, 'example'])), checkpoints: []};
  }
  function object(o) { return o !== null && typeof o === 'object' && !Array.isArray(o); }
  function exact(o, keys, name) {
    if (!object(o) || Object.keys(o).length !== keys.length || keys.some(k => !Object.hasOwn(o, k)))
      throw Error(name + ': missing or unsupported fields.');
  }
  function validateInputs(x) {
    exact(x, INPUT_KEYS, 'Inputs');
    for (const [k, allowed] of Object.entries(ENUMS)) if (!allowed.includes(x[k])) throw Error('Invalid ' + k + '.');
    for (const k of TEXT) if (typeof x[k] !== 'string' || x[k].length > (k === 'notes' ? 2000 : 200)) throw Error('Invalid ' + k + '.');
    for (const k of NUMBERS) if (x[k] !== null && (typeof x[k] !== 'number' || !Number.isFinite(x[k]) || x[k] < 0 || x[k] > 1e9)) throw Error('Invalid ' + k + '.');
    if (x.queries !== null && !Number.isSafeInteger(x.queries)) throw Error('Queries must be a whole number.');
    if (typeof x.matchedTiming !== 'boolean') throw Error('Invalid timing comparability.');
    return x;
  }
  function checkRanges(x) {
    const errors = [];
    if (x.goal === 'ranking' && x.geometry === 'fixed') errors.push('Design ranking needs multiple designs. Choose a family or another objective.');
    for (const [a, b, label] of [['loadMin','loadMax','Heat load'],['flowMin','flowMax','Flow']]) {
      if ((x[a] === null) !== (x[b] === null)) errors.push(label + ': enter both limits or leave both unknown.');
      if (x[a] !== null && x[b] !== null && x[a] > x[b]) errors.push(label + ': the lower limit exceeds the upper limit.');
    }
    return errors;
  }
  function validateJob(j) {
    exact(j, ['schema','ruleVersion','id','revision','inputs','origins','checkpoints'], 'Draft');
    if (j.schema !== VERSION || j.ruleVersion !== RULES) throw Error('This draft uses another schema or rule version. Keep the original and request a reviewed migration.');
    if (typeof j.id !== 'string' || !/^[a-zA-Z0-9_-]{8,80}$/.test(j.id)) throw Error('Invalid job identity.');
    if (!Number.isSafeInteger(j.revision) || j.revision < 1) throw Error('Invalid revision.');
    validateInputs(j.inputs); exact(j.origins, INPUT_KEYS, 'Input origins');
    if (Object.values(j.origins).some(v => !['example','user'].includes(v))) throw Error('Invalid input origin.');
    if (!Array.isArray(j.checkpoints) || j.checkpoints.length > 12) throw Error('At most 12 local checkpoints.');
    let previous = 0;
    for (const c of j.checkpoints) {
      exact(c, ['revision','inputs','origins'], 'Checkpoint'); validateInputs(c.inputs); exact(c.origins, INPUT_KEYS, 'Checkpoint origins');
      if (Object.values(c.origins).some(v => !['example','user'].includes(v))) throw Error('Invalid checkpoint origin.');
      if (!Number.isSafeInteger(c.revision) || c.revision <= previous || c.revision >= j.revision) throw Error('Invalid checkpoint order.');
      previous = c.revision;
    }
    return j;
  }
  function importJob(text) {
    if (typeof text !== 'string' || new TextEncoder().encode(text).length > 200000) throw Error('Draft exceeds the 200 KB limit.');
    let j; try { j = JSON.parse(text); } catch (_) { throw Error('Choose a valid Carbon draft JSON file.'); }
    return validateJob(j);
  }
  function checkpoint(j) {
    validateJob(j);
    if (j.checkpoints.length >= 12) throw Error('Twelve checkpoints retained. Export this record and fork a new draft.');
    return {...j, revision: j.revision + 1, checkpoints: [...j.checkpoints,
      {revision: j.revision, inputs: {...j.inputs}, origins: {...j.origins}}]};
  }
  function changes(j) {
    const c = j.checkpoints[j.checkpoints.length - 1];
    return c ? INPUT_KEYS.filter(k => c.inputs[k] !== j.inputs[k]) : [];
  }
  function economics(x) {
    const keys = ['queries','baselineCost','targetCost','setupCost','monthlyCost'];
    const missing = keys.filter(k => x[k] === null);
    const timingKnown = x.queries !== null && x.matchedTiming && x.hardware.trim() && x.baselineSeconds !== null && x.targetSeconds !== null;
    const secondsSaved = timingKnown ? x.queries * (x.baselineSeconds - x.targetSeconds) : null;
    if (missing.length) return {kind: 'unknown', missing, timingKnown: Boolean(timingKnown), secondsSaved};
    // Monetary comparisons use microdollars to avoid equality surprises from binary floats.
    const micro = n => BigInt(Math.round(n * 1e6));
    const q = BigInt(x.queries), margin = micro(x.baselineCost) - micro(x.targetCost);
    const net = q * margin - micro(x.monthlyCost), setup = micro(x.setupCost);
    const months = setup === 0n ? (net >= 0n ? 0 : null) : net > 0n ? Number((setup + net - 1n) / net) : null;
    return {kind: 'scenario', monthlyNet: Number(net) / 1e6, months,
      annualNet: Number(net * 12n - setup) / 1e6,
      secondsSaved,
      timingKnown: Boolean(timingKnown),
      maxTargetCost12: x.queries > 0 ? x.baselineCost - (x.monthlyCost + x.setupCost / 12) / x.queries : null,
      curve: [0,.25,.5,.75,1,1.25,1.5,2].map(f => {
        const n = Math.round(x.queries * f);
        return {queries:n, value:Number((BigInt(n)*margin - micro(x.monthlyCost))*12n-setup)/1e6};
      })};
  }
  return {VERSION,RULES,DEFAULTS,ENUMS,TEXT,NUMBERS,INPUT_KEYS,newJob,validateInputs,validateJob,importJob,checkpoint,changes,economics};
});
