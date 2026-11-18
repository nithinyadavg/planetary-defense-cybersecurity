// NEO-EYE — modelled (undiscovered) near-Earth asteroid population.
//
// These are NOT real objects. They are a statistical stand-in for what the surveys have
// not found yet, so the visual shows the gap between the catalogue and the sky.
//
// Size-frequency model (cumulative N(<H), log-linear between published anchors):
//   N(H<17.75) =    964  — Deienno et al. 2025, debiased ATLAS population (arXiv:2409.10453)
//   N(H<22.00) = 22,800  — mean of Nesvorný+24 (NEOMOD), Harris & Chodas 2021, Grav+23,
//                          as used by arXiv:2508.02418
//   Extrapolated with the same slope to H = 24 (~55 m at albedo 0.14). This is a deliberate
//   simplification: real size distributions are "wavy", so treat H > 22 as order-of-magnitude.
// Orbit model: orbits are resampled from the known H < 20 catalogue (the most complete,
// least discovery-biased part), jittered in a, e, i, with uniformly random node, perihelion
// and mean anomaly. Undiscovered objects are actually biased towards poor observing
// geometry, so this is an illustrative, not predictive, distribution.

export const POP_MODEL = {
  anchors: [[17.75, 964], [22.0, 22800]],
  hMin: 12, hMax: 24, bin: 0.25, seed: 20261118,
  refs: [
    ["Deienno et al. 2025 — Debiased NEO population from ATLAS", "https://arxiv.org/abs/2409.10453"],
    ["Placing the NEO impact probability in context (2025)", "https://arxiv.org/abs/2508.02418"],
    ["Nesvorný et al. 2024 — NEOMOD 3", "https://arxiv.org/abs/2404.18805"],
    ["Grav et al. 2023 — NEO Surveyor Known Object Model", "https://arxiv.org/abs/2310.20149"],
  ],
};

export function cumN(H) {
  const [[h1, n1], [h2, n2]] = POP_MODEL.anchors;
  const slope = Math.log10(n2 / n1) / (h2 - h1);
  return n1 * Math.pow(10, slope * (H - h1));
}

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// known: { H:[], a:[], e:[], i:[], kind:[] } — returns { a,e,i,om,w,ma,H } typed arrays + per-bin table
export function generatePopulation(known) {
  const { hMin, hMax, bin, seed } = POP_MODEL;
  const rnd = mulberry32(seed);
  const nb = Math.round((hMax - hMin) / bin);
  const knownCount = new Array(nb).fill(0);
  const templates = [];
  for (let k = 0; k < known.H.length; k++) {
    const H = known.H[k];
    if (H == null || known.kind[k] !== "a") continue;
    const b = Math.floor((H - hMin) / bin);
    if (b >= 0 && b < nb) knownCount[b]++;
    if (H < 20) templates.push(k);
  }
  const table = [];
  let total = 0;
  for (let b = 0; b < nb; b++) {
    const h0 = hMin + b * bin, h1 = h0 + bin;
    const est = cumN(h1) - (b === 0 ? 0 : cumN(h0));
    const miss = Math.max(0, Math.round(est - knownCount[b]));
    table.push({ h0, h1, est, known: knownCount[b], miss });
    total += miss;
  }
  const out = {
    a: new Float32Array(total), e: new Float32Array(total), i: new Float32Array(total),
    om: new Float32Array(total), w: new Float32Array(total), ma: new Float32Array(total), H: new Float32Array(total),
  };
  let n = 0;
  for (const row of table) {
    for (let j = 0; j < row.miss; j++) {
      const t = templates[Math.floor(rnd() * templates.length)];
      let a = known.a[t] * (1 + (rnd() - 0.5) * 0.1);
      let e = Math.min(0.97, Math.max(0, known.e[t] + (rnd() - 0.5) * 0.06));
      // keep it near-Earth: perihelion q = a(1-e) < 1.3 au
      if (a * (1 - e) > 1.3) e = Math.min(0.97, 1 - 1.29 / a);
      out.a[n] = a; out.e[n] = e;
      out.i[n] = Math.abs(known.i[t] + (rnd() - 0.5) * 4);
      out.om[n] = rnd() * 360; out.w[n] = rnd() * 360; out.ma[n] = rnd() * 360;
      out.H[n] = row.h0 + rnd() * bin;
      n++;
    }
  }
  return { ...out, count: total, table };
}

// Diameter (km) from absolute magnitude, assumed geometric albedo pv (Pravec & Harris 2007)
export const diamKm = (H, pv = 0.14) => (1329 / Math.sqrt(pv)) * Math.pow(10, -H / 5);
