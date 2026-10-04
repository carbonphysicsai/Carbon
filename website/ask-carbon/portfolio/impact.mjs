// Conditional scale illustrations, not Carbon performance, targets, prices or ROI.
// Prototype illustrations deliberately have no invented price or lead time.
export const impactCases = Object.freeze({
  cooling: Object.freeze({ kind: "energy", powerKw: 100, hours: 8760, usdPerKwh: 0.10 }),
  thermal: Object.freeze({ kind: "capacity", gainPct: 1, units: 10000 }),
  photonics: Object.freeze({ kind: "yield", gainPoints: 1, devices: 1000000 }),
  battery: Object.freeze({ kind: "dwell", minutes: 5, events: 1000 }),
  motors: Object.freeze({ kind: "prototype", rounds: 1 }),
  vibration: Object.freeze({ kind: "prototype", rounds: 1 }),
  acoustics: Object.freeze({ kind: "unitCost", usdPerUnit: 1, annualUnits: 100000 }),
  mixing: Object.freeze({ kind: "throughput", gainPct: 10, runHours: 8 }),
});
export const outcomes = Object.freeze({
  cooling: "Lower pumping demand at the same thermal requirement.",
  thermal: "More useful compute within independently checked temperature limits.",
  photonics: "More devices meeting the optical specification across actual manufacturing variation.",
  battery: "Less charging dwell at independently checked cell-specific constraints.",
  motors: "Lower torque ripple without sacrificing required mean torque.",
  vibration: "Less vibration while meeting mass and stiffness requirements.",
  acoustics: "Required band attenuation in a compact, manufacturable package.",
  mixing: "Greater flow at the same verified outlet-mixing requirement.",
});
const count = (n) => Math.round(n).toLocaleString("en-US");
const positive = (n) => {
  if (!Number.isFinite(n) || n <= 0 || n > 1e12) throw new RangeError("Illustration inputs must be finite positive numbers.");
};
const integer = (n) => { positive(n); if (!Number.isSafeInteger(n)) throw new RangeError("Counts must be whole numbers."); };
export function calculateScale(c) {
  if (!c || typeof c !== "object" || Array.isArray(c)) throw new RangeError("An explicit illustration is required.");
  switch (c.kind) {
    case "energy":
      [c.powerKw, c.hours, c.usdPerKwh].forEach(positive);
      if (c.hours > 8760) throw new RangeError("Annual hours exceed a non-leap year.");
      return { kwh: c.powerKw * c.hours, annualUsd: c.powerKw * c.hours * c.usdPerKwh };
    case "capacity":
      positive(c.gainPct); integer(c.units);
      if (c.gainPct > 100) throw new RangeError("Capacity sensitivity exceeds 100%.");
      return { equivalents: c.gainPct / 100 * c.units };
    case "yield":
      positive(c.gainPoints); integer(c.devices);
      if (c.gainPoints > 100) throw new RangeError("Pass-rate change exceeds 100 percentage points.");
      return { passingDevices: c.gainPoints / 100 * c.devices };
    case "dwell":
      positive(c.minutes); integer(c.events);
      return { hoursPerDay: c.minutes * c.events / 60 };
    case "prototype":
      integer(c.rounds);
      return { rounds: c.rounds };
    case "unitCost":
      positive(c.usdPerUnit); integer(c.annualUnits);
      return { annualUsd: c.usdPerUnit * c.annualUnits };
    case "throughput":
      positive(c.gainPct); positive(c.runHours);
      if (c.gainPct > 100) throw new RangeError("Throughput sensitivity exceeds 100%.");
      return { minutesAvoided: c.runHours * 60 * (1 - 1 / (1 + c.gainPct / 100)) };
    default: throw new RangeError("Unknown scale illustration.");
  }
}
export function scaleIllustration(id) {
  const c = impactCases[id];
  const result = calculateScale(c);
  switch (c.kind) {
    case "energy": return { first: `${count(c.powerKw)} kW`, firstLabel: "less electrical demand", second: `~$${count(result.annualUsd / 1000)}k/yr`, secondLabel: "electricity value", note: "At 8,760 hours/year and an illustrative $0.10/kWh; not a current tariff." };
    case "capacity": return { first: `+${c.gainPct}%`, firstLabel: "useful throughput", second: count(result.equivalents), secondLabel: "accelerator-equivalents", note: "Across 10,000 comparable accelerators; not automatically avoided hardware spend." };
    case "yield": return { first: `+${c.gainPoints} pp`, firstLabel: "measured pass rate", second: count(result.passingDevices), secondLabel: "more passing devices", note: "Per 1 million fabricated devices; actual yield needs manufacturing evidence." };
    case "dwell": return { first: `−${c.minutes} min`, firstLabel: "per qualified charge", second: `~${count(result.hoursPerDay)} h/day`, secondLabel: "potential dwell released", note: "At 1,000 charge events/day; not labor savings or a real-cell safety claim." };
    case "prototype": return { first: `${c.rounds} fewer`, firstLabel: "prototype round", second: "Build + test", secondLabel: "spend and lead time avoided", note: "Value at the customer's actual quote; no prototype price or duration assumed." };
    case "unitCost": return { first: `$${c.usdPerUnit}/unit`, firstLabel: "verified component saving", second: `$${count(result.annualUsd / 1000)}k/yr`, secondLabel: "manufacturing value", note: "At 100,000 units/year; pressure-loss and integration checks remain separate." };
    case "throughput": return { first: `+${c.gainPct}%`, firstLabel: "compliant flow rate", second: `~${count(result.minutesAvoided)} min`, secondLabel: "potential flow time avoided", note: "On an 8-hour flow-limited run of fixed volume; other steps unchanged." };
  }
}
