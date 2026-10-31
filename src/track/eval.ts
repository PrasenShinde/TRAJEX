import type { Graph } from '../sim/graph';
import { hash01, mulberry32, range } from '../sim/rng';
import { inferRoute, type CamMap } from './routes';
import { bestCamera, greedyPlacement, modelFromHyps, type SegModel } from './suggest';

/** A simulated trip used by the batch evaluation (ground truth lives here, never in the tracker). */
export type Trip = { nodes: number[]; edges: number[]; arr: number[]; heading0: number[] };

export function sampleTrips(g: Graph, n: number, seed: number, minEdges = 6, maxEdges = 40): Trip[] {
  const r = mulberry32(seed * 31 + 7);
  const trips: Trip[] = [];
  let guard = 0;
  while (trips.length < n && guard++ < n * 40) {
    const o = Math.floor(r() * g.N), d = Math.floor(r() * g.N);
    if (o === d) continue;
    const ts = Math.floor(r() * 1e9);
    const w = (e: number) => g.timeS[e] * (0.8 + 0.6 * hash01(ts, e)); // same perturbed routing the cars use
    const edges = g.shortestPath(o, d, w);
    if (!edges || edges.length < minEdges || edges.length > maxEdges) continue;
    const sf = range(r, 0.6, 1.0);
    const nodes = [o], arr = [0], heading0: number[] = [];
    let t = 0;
    for (const e of edges) {
      t += g.lengthM[e] / ((g.edges[e].speedKph * sf) / 3.6);
      nodes.push(g.ev[e]); arr.push(t);
      heading0.push(g.edgeBearing(e));
      t += range(r, 0, 20);
    }
    // arrival times already include delays of previous junctions
    trips.push({ nodes, edges, arr, heading0 });
  }
  return trips;
}

/** Share of the true route's road length (by junction pairs) that also lies on the hypothesis path. */
export function routeShare(g: Graph, hypNodes: number[], trueNodes: number[]): number {
  const hyp = new Set<string>();
  for (let k = 0; k + 1 < hypNodes.length; k++) hyp.add(hypNodes[k] + '>' + hypNodes[k + 1]);
  let tot = 0, hit = 0;
  for (let k = 0; k + 1 < trueNodes.length; k++) {
    const e = g.edgeBetween(trueNodes[k], trueNodes[k + 1]);
    const len = e !== undefined ? g.lengthM[e] : 0;
    tot += len;
    if (hyp.has(trueNodes[k] + '>' + trueNodes[k + 1])) hit += len;
  }
  return tot ? hit / tot : 0;
}

const camMapFrom = (nodes: number[], p: number): CamMap => new Map(nodes.map(n => [n, p]));

/** Ambiguity models for sampled trips (origin & destination assumed observed). */
export async function buildModels(g: Graph, trips: Trip[]): Promise<SegModel[]> {
  const out: SegModel[] = [];
  for (const tr of trips) {
    await yieldIfLong();
    const inf = inferRoute(g, tr.nodes[0], tr.nodes[tr.nodes.length - 1], tr.arr[0], tr.arr[tr.arr.length - 1], new Map(), { headingA: tr.heading0[0] });
    if (inf.hyps.length) out.push(modelFromHyps(g, inf.hyps));
  }
  return out;
}

export type EvalResult = {
  cameras: number;
  trips: number;
  segments: number;
  avgRoutes: number; // mean effective routes per segment
  avgFeasible: number;
  routeAccuracy: number; // mean share of true road length on the top-1 hypothesis
  meanRank: number; // mean rank of the true route where it was found
  foundPct: number; // % segments where the true route was among the hypotheses
  top1Pct: number; // % segments where the true route is rank 1
};

/** Evaluate a camera placement on sampled trips: split each trip at camera detections, infer each piece. */
export async function evaluatePlacement(g: Graph, trips: Trip[], cameraNodes: number[], p: number, seed: number): Promise<EvalResult> {
  const cams = camMapFrom(cameraNodes, p);
  let segs = 0, effSum = 0, feasSum = 0, accSum = 0, rankSum = 0, found = 0, top1 = 0;
  for (let ti = 0; ti < trips.length; ti++) {
    await yieldIfLong();
    const tr = trips[ti];
    const obs: number[] = [0];
    for (let i = 1; i < tr.nodes.length - 1; i++)
      if (cams.has(tr.nodes[i]) && hash01(seed, ti, tr.nodes[i], 9) < p) obs.push(i);
    obs.push(tr.nodes.length - 1);
    for (let k = 0; k + 1 < obs.length; k++) {
      const i = obs[k], j = obs[k + 1];
      const inf = inferRoute(g, tr.nodes[i], tr.nodes[j], tr.arr[i], tr.arr[j], cams, { headingA: tr.heading0[i] });
      if (!inf.hyps.length) continue;
      segs++; effSum += inf.effective; feasSum += inf.rawCount;
      const trueNodes = tr.nodes.slice(i, j + 1).join(',');
      const rank = inf.hyps.findIndex(h => h.nodeIds.map(id => g.nodeIdx.get(id)).join(',') === trueNodes);
      if (rank >= 0) { found++; rankSum += rank + 1; if (rank === 0) top1++; }
      accSum += routeShare(g, inf.hyps[0].nodeIds.map(id => g.nodeIdx.get(id)!), tr.nodes.slice(i, j + 1));
    }
  }
  return {
    cameras: cameraNodes.length, trips: trips.length, segments: segs,
    avgRoutes: segs ? effSum / segs : 0, avgFeasible: segs ? feasSum / segs : 0,
    routeAccuracy: segs ? accSum / segs : 0, meanRank: found ? rankSum / found : 0,
    foundPct: segs ? (100 * found) / segs : 0, top1Pct: segs ? (100 * top1) / segs : 0,
  };
}

export type ChartPoint = { cameras: number; random: number; smart: number };
export type Batch = { current: EvalResult; chart: ChartPoint[]; suggestedFirst: string | null };

const tick = () => new Promise<void>(res => setTimeout(res, 0));
let lastYield = 0;
/** Let the browser paint / handle input during long computations. */
async function yieldIfLong() {
  const now = Date.now();
  if (now - lastYield > 40) { await tick(); lastYield = Date.now(); }
}

/**
 * Batch evaluation (spec §7): N random trips; (a) current cameras, (b) same number placed randomly,
 * (c) same number placed greedily; plus avg-routes-vs-camera-count for random vs smart.
 * Smart placement is learned on a *training* trip set and scored on a separate *test* set.
 */
export async function runBatch(
  g: Graph, current: number[], p: number, seed: number,
  opts: { nTrips?: number; counts?: number[]; onProgress?: (frac: number, label: string) => void } = {},
): Promise<Batch & { currentRandom: EvalResult; currentSmart: EvalResult }> {
  const { nTrips = 200, counts = [5, 10, 15, 20, 25], onProgress } = opts;
  const minE = g.N > 200 ? 8 : 6;
  const test = sampleTrips(g, nTrips, seed + 101, minE);
  const train = sampleTrips(g, nTrips, seed + 202, minE);
  onProgress?.(0.02, 'building route models');
  await tick();
  const models = await buildModels(g, train);
  const kMax = Math.max(...counts, current.length);
  const smartOrder = greedyPlacement(g, models, kMax, p);
  const rnd = mulberry32(seed + 303);
  const randomOrder = [...Array(g.N).keys()].sort(() => rnd() - 0.5);

  const total = counts.length * 2 + 3;
  let done = 0;
  const step = async (label: string) => { done++; onProgress?.(done / total, label); await tick(); };

  const cur = await evaluatePlacement(g, test, current, p, seed); await step('current cameras');
  const k = current.length;
  const currentRandom = await evaluatePlacement(g, test, randomOrder.slice(0, k), p, seed); await step('same count, random');
  const currentSmart = await evaluatePlacement(g, test, smartOrder.slice(0, k), p, seed); await step('same count, smart');
  const chart: ChartPoint[] = [];
  for (const c of counts) {
    const r = await evaluatePlacement(g, test, randomOrder.slice(0, c), p, seed); await step(`random ${c}`);
    const s = await evaluatePlacement(g, test, smartOrder.slice(0, c), p, seed); await step(`smart ${c}`);
    chart.push({ cameras: c, random: r.avgRoutes, smart: s.avgRoutes });
  }
  return { current: cur, currentRandom, currentSmart, chart, suggestedFirst: smartOrder.length ? g.nodes[smartOrder[0]].id : null };
}

export { bestCamera };
