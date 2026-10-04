// Public, dimensionless numerical illustration ONLY. No production/official data,
// cold-plate geometry, optimizer, timing or model comparison is used here.
// -laplacian(u) = f, zero boundary, unit square, unit conductivity.
// Manufactured analytical control: u = sin(pi*x)*sin(pi*y).
const dot = (a, b) => a.reduce((sum, value, i) => sum + value * b[i], 0);
export function solveIllustration(n = 32) {
  if (!Number.isInteger(n) || n < 8 || n > 64) throw new RangeError("Illustration grid must have 8–64 interior points per axis.");
  const h = 1 / (n + 1);
  const exact = Array.from({ length: n * n }, (_, k) => Math.sin(Math.PI * ((k % n) + 1) * h) * Math.sin(Math.PI * (Math.floor(k / n) + 1) * h));
  const b = exact.map((u) => 2 * Math.PI ** 2 * u);
  const apply = (v) => v.map((value, k) => {
    const x = k % n, y = Math.floor(k / n);
    return (4 * value - (x ? v[k - 1] : 0) - (x < n - 1 ? v[k + 1] : 0) - (y ? v[k - n] : 0) - (y < n - 1 ? v[k + n] : 0)) / h ** 2;
  });
  let values = Array(n * n).fill(0), r = [...b], p = [...r], rr = dot(r, r), iterations = 0;
  const initial = rr;
  while (rr / initial > 1e-20 && iterations < 500) {
    const ap = apply(p), denominator = dot(p, ap);
    if (!(denominator > 0)) throw new Error("Illustration operator is not positive definite.");
    const alpha = rr / denominator;
    values = values.map((u, k) => u + alpha * p[k]);
    r = r.map((value, k) => value - alpha * ap[k]);
    const next = dot(r, r), beta = next / rr;
    p = r.map((value, k) => value + beta * p[k]);
    rr = next; iterations++;
  }
  const residual = Math.sqrt(dot(apply(values).map((v, k) => v - b[k]), apply(values).map((v, k) => v - b[k])) / initial);
  if (!Number.isFinite(residual) || residual > 1e-8) throw new Error("Numerical illustration failed its residual check.");
  const maxError = Math.max(...values.map((u, k) => Math.abs(u - exact[k])));
  return { n, values, maxError, relativeResidual: residual, iterations };
}
const color = (t) => {
  const stops = [[43, 72, 63], [115, 151, 125], [219, 216, 145], [232, 126, 71], [220, 70, 45]];
  const scaled = Math.max(0, Math.min(1, t)) * (stops.length - 1), i = Math.min(stops.length - 2, Math.floor(scaled)), f = scaled - i;
  return `rgb(${stops[i].map((channel, k) => Math.round(channel * (1 - f) + stops[i + 1][k] * f)).join(",")})`;
};
export function renderSolverIllustration() {
  const result = solveIllustration();
  const refinement = solveIllustration(16);
  if (!(result.maxError < refinement.maxError / 3)) throw new Error("Illustration fails its mesh-refinement control.");
  const maximum = Math.max(...result.values), size = 222, step = size / result.n;
  const paths = new Map();
  result.values.forEach((u, k) => {
    const fill = color(u / maximum), cell = (step + 0.02).toFixed(2);
    const path = `M${(189 + k % result.n * step).toFixed(2)} ${(39 + Math.floor(k / result.n) * step).toFixed(2)}h${cell}v${cell}h-${cell}Z`;
    paths.set(fill, (paths.get(fill) ?? "") + path);
  });
  const cells = [...paths].map(([fill, d]) => `<path fill="${fill}" d="${d}"/>`).join("");
  const mesh = Array.from({ length: 9 }, (_, k) => `<path d="M${189 + k * size / 8} 39v222M189 ${39 + k * size / 8}h222" stroke="#e5ece5" stroke-opacity=".13"/>`).join("");
  const legend = Array.from({ length: 80 }, (_, k) => `<rect x="${225 + k * 150 / 80}" y="282" width="1.9" height="7" fill="${color(k / 79)}"/>`).join("");
  return `<svg class="pf-solver-field" viewBox="0 0 600 320" role="img" aria-label="Locally computed normalized field from a manufactured two-dimensional heat-equation test; not a cold-plate benchmark or contest result." xmlns="http://www.w3.org/2000/svg"><title>Numerical illustration: steady 2D heat equation</title><rect width="600" height="320" fill="#e6ece3"/><path d="M20 20H580V300H20Z" fill="none" stroke="#cdd7c9"/>${cells}${mesh}<path d="M189 39H411V261H189Z" fill="none" stroke="#3c5343" stroke-width="2"/><path d="M173 48v204m-4-196 4-8 4 8m-4 196-4-8m4 8 4-8M198 23h204m-196-4-8 4 8 4m196-4-8-4m8 4-8 4" fill="none" stroke="#7c8c7e"/><text x="63" y="151" fill="#52664f" font-size="11">zero edge</text><text x="432" y="151" fill="#52664f" font-size="11">zero edge</text>${legend}<text x="201" y="290" fill="#52664f" font-size="10">0</text><text x="387" y="290" fill="#52664f" font-size="10">1</text><text x="300" y="307" text-anchor="middle" fill="#52664f" font-size="9">NORMALIZED FIELD · SYNTHETIC TEST</text></svg>`;
}
