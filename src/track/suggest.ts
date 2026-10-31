import type { Graph } from '../sim/graph';
import type { RouteHypothesis } from '../sim/types';

/** One ambiguous segment: candidate routes with base weights and their interior junctions. */
export type SegModel = { paths: { nodes: number[]; w: number }[] };

export function modelFromHyps(g: Graph, hyps: RouteHypothesis[]): SegModel {
  return {
    paths: hyps.map(h => ({
      nodes: h.nodeIds.slice(1, -1).map(id => g.nodeIdx.get(id)!),
      w: h.prob,
    })),
  };
}

const H = (ws: number[]) => {
  const z = ws.reduce((a, b) => a + b, 0);
  if (z <= 0) return 0;
  let h = 0;
  for (const w of ws) if (w > 0) h -= (w / z) * Math.log(w / z);
  return h;
};

/** Posterior weights of the routes given cameras `S` (nodeIdx -> detectProb) that did NOT see the car. */
function weights(m: SegModel, S: Map<number, number>): number[] {
  return m.paths.map(p => {
    let w = p.w;
    for (const n of p.nodes) { const d = S.get(n); if (d !== undefined) w *= 1 - d; }
    return w;
  });
}

export const segEntropy = (m: SegModel, S: Map<number, number>) => H(weights(m, S));

/**
 * Expected entropy of the route distribution after adding a camera at junction j (detect prob p):
 * split routes into "passes j" / "doesn't", weighted by probability mass.
 *  - seen at j  (prob p·P_pass): only routes through j remain
 *  - not seen   (else): routes through j are down-weighted by (1-p)
 */
export function expectedEntropyAfter(m: SegModel, S: Map<number, number>, j: number, p: number, w = weights(m, S)): number {
  const pass: number[] = [], notPass: number[] = [];
  m.paths.forEach((path, i) => (path.nodes.includes(j) ? pass : notPass).push(w[i]));
  const wp = pass.reduce((a, b) => a + b, 0), wn = notPass.reduce((a, b) => a + b, 0);
  const z = wp + wn;
  if (z <= 0 || wp === 0 || wn === 0) return H(w); // camera cannot split anything
  const pSeen = p * (wp / z);
  const hSeen = H(pass);
  const hSilent = H([...pass.map(x => x * (1 - p)), ...notPass]);
  return pSeen * hSeen + (1 - pSeen) * hSilent;
}

export type Suggestion = { node: string; nodeIdx: number; gain: number; gainPct: number; baseEntropy: number };

/** Junction (without a camera) with the largest total expected entropy reduction over the given segments. */
export function bestCamera(g: Graph, models: SegModel[], S: Map<number, number>, p: number): Suggestion | null {
  const gain = new Map<number, number>();
  let base = 0;
  for (const m of models) {
    const w = weights(m, S);
    const h0 = H(w);
    base += h0;
    const cand = new Set<number>();
    for (const path of m.paths) for (const n of path.nodes) if (!S.has(n)) cand.add(n);
    for (const j of cand) {
      const d = h0 - expectedEntropyAfter(m, S, j, p, w);
      if (d > 1e-12) gain.set(j, (gain.get(j) ?? 0) + d);
    }
  }
  let bestJ = -1, bestG = 0;
  for (const [j, d] of gain) if (d > bestG) { bestG = d; bestJ = j; }
  if (bestJ < 0 || base <= 0) return null;
  return { node: g.nodes[bestJ].id, nodeIdx: bestJ, gain: bestG, gainPct: (100 * bestG) / base, baseEntropy: base };
}

/** Greedy smart placement: k cameras (after `existing`), in pick order. */
export function greedyPlacement(g: Graph, models: SegModel[], k: number, p: number, existing: number[] = []): number[] {
  const S = new Map<number, number>(existing.map(n => [n, p]));
  const picked: number[] = [];
  for (let i = 0; i < k; i++) {
    const s = bestCamera(g, models, S, p);
    if (!s) break;
    picked.push(s.nodeIdx);
    S.set(s.nodeIdx, p);
  }
  return picked;
}
