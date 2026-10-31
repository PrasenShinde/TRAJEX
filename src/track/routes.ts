import type { Graph } from '../sim/graph';
import { angDiff } from '../sim/graph';
import type { RouteHypothesis } from '../sim/types';

export type Path = { edges: number[]; t: number; dev?: number };

/**
 * Yen's k-shortest loop-free paths by typical travel time.
 * Returns up to K paths with minT <= t <= maxT (generation stops once t > maxT).
 */
export function kPaths(
  g: Graph, src: number, dst: number,
  opts: { minT?: number; maxT: number; K?: number; maxGen?: number },
): Path[] {
  const { minT = 0, maxT, K = 40, maxGen = 150 } = opts;
  if (src === dst) return [];
  const w = (e: number) => g.timeS[e];
  const h = g.distTo(dst, w);
  if (!isFinite(h[src]) || h[src] > maxT) return [];
  const first = g.pathEdges(g.dijkstra(src, w, { target: dst, h }).prevE, src, dst);
  if (!first) return [];
  const sum = (es: number[]) => es.reduce((a, e) => a + g.timeS[e], 0);
  const A: Path[] = [{ edges: first, t: sum(first), dev: 0 }];
  if (A[0].t > maxT) return [];
  const B: Path[] = [];
  const seen = new Set<string>([first.join(',')]);
  while (A.length < maxGen) {
    const prev = A[A.length - 1];
    for (let i = prev.dev ?? 0; i < prev.edges.length; i++) { // Lawler: earlier spurs were already explored
      const spurNode = i === 0 ? src : g.ev[prev.edges[i - 1]];
      const root = prev.edges.slice(0, i);
      const blockedEdges = new Set<number>();
      for (const p of A) {
        if (p.edges.length > i) {
          let same = true;
          for (let j = 0; j < i; j++) if (p.edges[j] !== root[j]) { same = false; break; }
          if (same) blockedEdges.add(p.edges[i]);
        }
      }
      const blockedNodes = new Set<number>([src]);
      for (let j = 0; j < i - 1; j++) blockedNodes.add(g.ev[root[j]]);
      blockedNodes.delete(spurNode);
      const { prevE, dist } = g.dijkstra(spurNode, w, { target: dst, blockedEdges, blockedNodes, maxCost: maxT, h });
      if (!isFinite(dist[dst])) continue;
      const spur = g.pathEdges(prevE, spurNode, dst);
      if (!spur) continue;
      const edges = root.concat(spur);
      const key = edges.join(',');
      if (seen.has(key)) continue;
      seen.add(key);
      B.push({ edges, t: sum(edges), dev: i });
    }
    if (!B.length) break;
    let bi = 0;
    for (let i = 1; i < B.length; i++) if (B[i].t < B[bi].t) bi = i;
    const next = B.splice(bi, 1)[0];
    if (next.t > maxT) break;
    A.push(next);
    if (A.filter(p => p.t >= minT).length >= K) break;
  }
  return A.filter(p => p.t >= minT && p.t <= maxT).slice(0, K);
}

/** Unnormalised score of one path hypothesis (spec 6.2). */
export function scorePath(args: {
  travelTimeS: number; dt: number; extraKm: number; silentDetectProbs: number[]; headingPenalty?: number;
}): number {
  const { travelTimeS, dt, extraKm, silentDetectProbs, headingPenalty = 1 } = args;
  const sigma = 0.25 * dt;
  let s = Math.exp(-((travelTimeS - dt) ** 2) / (2 * sigma * sigma));
  for (const p of silentDetectProbs) s *= 1 - p; // negative evidence
  s *= Math.exp(-0.1 * extraKm);
  return s * headingPenalty;
}

export const entropyOf = (probs: number[]) => -probs.reduce((a, p) => (p > 0 ? a + p * Math.log(p) : a), 0);
/** Effective number of routes = exp(entropy). */
export const effectiveRoutes = (probs: number[]) => (probs.length ? Math.exp(entropyOf(probs)) : 0);

export function normalise(scores: number[]): number[] {
  const z = scores.reduce((a, b) => a + b, 0);
  return z > 0 ? scores.map(s => s / z) : scores.map(() => 0);
}

export type Inference = {
  hyps: RouteHypothesis[]; // ranked, prob >= 1%
  rawCount: number; // feasible paths enumerated
  effective: number; // exp(entropy) over kept hypotheses
  bestFitErr: number; // smallest |T - dt| over feasible paths (s); Infinity if none
  minTimeS: number; // fastest route time (s)
};

/** Camera lookup used for negative evidence: nodeIdx -> detectProb. */
export type CamMap = Map<number, number>;

export function inferRoute(
  g: Graph, a: number, b: number, tA: number, tB: number, cams: CamMap,
  opts: { headingA?: number; K?: number } = {},
): Inference {
  const dt = tB - tA;
  const empty: Inference = { hyps: [], rawCount: 0, effective: 0, bestFitErr: Infinity, minTimeS: Infinity };
  if (dt <= 0 || a === b) return empty;
  const paths = kPaths(g, a, b, { minT: 0.7 * dt, maxT: 1.8 * dt, K: opts.K ?? 40 });
  if (!paths.length) {
    const sp = g.shortestPath(a, b, e => g.timeS[e]);
    if (sp) empty.minTimeS = sp.reduce((s, e) => s + g.timeS[e], 0);
    return empty;
  }
  const lenOf = (es: number[]) => es.reduce((s, e) => s + g.lengthM[e], 0);
  const lens = paths.map(p => lenOf(p.edges));
  const minLen = Math.min(...lens);
  const scores = paths.map((p, i) => {
    const silent: number[] = [];
    for (let j = 0; j < p.edges.length - 1; j++) {
      const n = g.ev[p.edges[j]];
      const dp = cams.get(n);
      if (dp !== undefined && n !== a && n !== b) silent.push(dp);
    }
    let hp = 1;
    if (opts.headingA !== undefined && angDiff(g.edgeBearing(p.edges[0]), opts.headingA) > 60) hp = 0.15;
    return scorePath({ travelTimeS: p.t, dt, extraKm: (lens[i] - minLen) / 1000, silentDetectProbs: silent, headingPenalty: hp });
  });
  const probs = normalise(scores);
  let kept = paths.map((p, i) => ({ p, prob: probs[i] })).filter(x => x.prob >= 0.01);
  if (!kept.length) kept = [paths.map((p, i) => ({ p, prob: probs[i] })).sort((x, y) => y.prob - x.prob)[0]];
  const kp = normalise(kept.map(x => x.prob));
  const hyps: RouteHypothesis[] = kept
    .map((x, i) => ({
      edgeIds: x.p.edges.map(e => g.edges[e].id),
      nodeIds: [g.nodes[a].id, ...x.p.edges.map(e => g.nodes[g.ev[e]].id)],
      travelTimeS: x.p.t, prob: kp[i],
    }))
    .sort((x, y) => y.prob - x.prob);
  return {
    hyps, rawCount: paths.length, effective: effectiveRoutes(hyps.map(h => h.prob)),
    bestFitErr: Math.min(...paths.map(p => Math.abs(p.t - dt))), minTimeS: Math.min(...paths.map(p => p.t)),
  };
}
