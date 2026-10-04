export function calculateEconomics({ build, upkeep, baseline, model, campaigns }) {
  const values = { build, upkeep, baseline, model, campaigns };
  const maxima = { build: 1e9, upkeep: 1e9, baseline: 1e6, model: 1e6, campaigns: 1e6 };
  for (const [key, value] of Object.entries(values)) {
    if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > maxima[key]) throw new RangeError(`Invalid ${key} assumption.`);
  }
  if (!Number.isInteger(campaigns) || campaigns < 1) throw new RangeError("Campaigns must be a whole number from 1 to 1,000,000.");
  const cents = (value) => {
    const scaled = value * 100;
    const rounded = Math.round(scaled);
    if (Math.abs(scaled - rounded) > Math.max(1e-7, Math.abs(scaled) * Number.EPSILON * 4)) throw new RangeError("Costs must use whole cents.");
    return rounded;
  };
  // Integer cents prevent a floating-point edge from moving exact cost parity
  // to the next campaign (for example 0.10 / (0.30 - 0.20)). Bounded products
  // remain below Number.MAX_SAFE_INTEGER.
  const fixed = cents(build) + cents(upkeep);
  const margin = cents(baseline) - cents(model);
  const baselineTotal = campaigns * cents(baseline);
  const modelTotal = fixed + campaigns * cents(model);
  const parity = fixed === 0 && margin === 0;
  const breakEven = margin > 0 ? Math.ceil(fixed / margin) : parity ? 0 : null;
  return { baselineTotal: baselineTotal / 100, modelTotal: modelTotal / 100, difference: (baselineTotal - modelTotal) / 100, breakEven, parity };
}
