import type { Graph } from '../sim/graph';
import { randomCameraNodes } from '../sim/placement';
import { buildEngine } from '../sim/scenario';
import { InferenceCache, traceTarget, type Trace } from '../track/link';
import { inferRoute } from '../track/routes';
import { bestCamera, modelFromHyps } from '../track/suggest';
import { camerasSaved, type Batch, type CamerasSaved, type EvalResult } from '../track/eval';
import type { Preset } from './presets';

export type BatchResult = Batch & { currentRandom: EvalResult; currentSmart: EvalResult };
export type PrecomputedEntry = { sig: string; nTrips: number; generated: string; result: BatchResult };
export type Precomputed = { version: 1; presets: Record<string, PrecomputedEntry> };

/** Camera junctions of a preset (random ones are seeded, so deterministic). */
export const presetCams = (g: Graph, p: Preset): string[] => (Array.isArray(p.cams) ? p.cams : randomCameraNodes(g, p.cams.random, p.seed));

/** Identifies the scenario a saved batch result belongs to; a mismatch means the result must not be reused. */
export const batchSig = (mapName: string, seed: number, cams: string[], miss: number, nTrips: number) =>
  `${mapName}|${seed}|${[...cams].sort().join(',')}|${miss.toFixed(3)}|${nTrips}`;

export const specOf = (g: Graph, p: Preset) => ({ ...p, cams: presetCams(g, p) });

/** Numbers the simulator computes for one preset; captions are written only from these. */
export type Facts = {
  id: number;
  cams?: number; // cameras in the scenario
  raw?: number; eff?: number; rank?: number; // first tracked segment
  sugg?: { node: string; gainPct: number };
  after?: { eff: number[]; ranks: number[]; linked: number };
  linksOurs?: number; linksNaive?: number; linksTrue?: number;
  rejected?: { reason: string; wrongLinks: number };
  batch?: { n: number; smart: number; random: number; saved: CamerasSaved };
};

const fx = (x: number) => (x >= 10 ? x.toFixed(0) : x.toFixed(1));

function rankOf(g: Graph, e: ReturnType<typeof buildEngine>, car: string, sg: Trace['segments'][number]) {
  const key = e.trueNodesBetween(car, sg.from.t, sg.to.t).map(n => g.nodes[n].id).join(',');
  return sg.inference.hyps.findIndex(h => h.nodeIds.join(',') === key) + 1; // 0 = not found
}

/** Compute the facts for a preset on a fresh engine (never touches the live one). */
export function gatherFacts(g: Graph, p: Preset, pre: PrecomputedEntry | null): Facts {
  const f: Facts = { id: p.id };
  const e = buildEngine(g, specOf(g, p));
  f.cams = e.cameras.size;
  const cache = new InferenceCache();
  if (p.car) {
    const c = e.carById.get(p.car)!.car;
    const target = { plate: c.plate, type: c.type, colour: c.colour };
    const ours = traceTarget(g, e.sightings, e.cameraList(), target, 'ours', cache);
    const naive = traceTarget(g, e.sightings, e.cameraList(), target, 'naive', cache);
    const sg = ours.segments[0];
    if (sg) { f.raw = sg.inference.rawCount; f.eff = sg.inference.effective; f.rank = rankOf(g, e, p.car, sg); }
    f.linksOurs = ours.linked.length; f.linksNaive = naive.linked.length; f.linksTrue = e.sightingsOf(p.car).length;
    const rej = ours.decisions.find(d => d.status === 'rejected' && d.reason.includes('impossible travel')) ?? ours.decisions.find(d => d.status === 'rejected');
    if (rej) f.rejected = { reason: rej.reason, wrongLinks: ours.linked.filter(x => x.trueCarId !== p.car).length };
    if (p.autoSuggest && sg) {
      const A = g.nodeIdx.get(sg.from.nodeId)!, B = g.nodeIdx.get(sg.to.nodeId)!;
      const models = [modelFromHyps(g, inferRoute(g, A, B, sg.from.t, sg.to.t, new Map(), { headingA: sg.from.heading }).hyps)];
      const S = new Map(e.cameraList().map(cm => [g.nodeIdx.get(cm.nodeId)!, cm.detectProb] as [number, number]));
      const s = bestCamera(g, models, S, 1 - p.miss);
      if (s) {
        f.sugg = { node: s.node, gainPct: s.gainPct };
        e.addCamera(s.node);
        const t2 = traceTarget(g, e.sightings, e.cameraList(), target, 'ours', cache);
        f.after = { eff: t2.segments.map(x => x.inference.effective), ranks: t2.segments.map(x => rankOf(g, e, p.car!, x)), linked: t2.linked.length };
      }
    }
  }
  if (p.autoBatch && pre) {
    const r = pre.result;
    const n = r.current.cameras;
    f.batch = { n, smart: r.currentSmart.avgRoutes, random: r.currentRandom.avgRoutes, saved: camerasSaved(r.chart, n, r.currentSmart.avgRoutes, r.currentRandom.avgRoutes) };
  }
  return f;
}

/** 1–2 sentence caption written from the computed numbers. */
export function captionFor(f: Facts | null, p: Preset): string {
  if (!f) return p.says;
  switch (f.id) {
    case 1:
      if (f.eff === undefined) break;
      return `With only ${f.cams} cameras the tracked car could have taken ${f.raw} feasible routes (about ${fx(f.eff)} effective). Our top guess is ${f.rank === 1 ? 'right' : 'wrong'} — the true route is ranked #${f.rank || 'not in the list'}.`;
    case 2:
      if (f.eff === undefined || !f.sugg || !f.after) break;
      return `Before: about ${fx(f.eff)} effective routes, true route ranked #${f.rank || '?'}. Adding the suggested junction ${f.sugg.node} (+${f.sugg.gainPct.toFixed(0)}% certainty) cuts it to ${f.after.eff.map(fx).join(' and ')} effective routes, with the true route at rank ${f.after.ranks.join(' and ')}.`;
    case 3: {
      if (!f.batch) return `${p.says} (No saved batch results found — run “npm run precompute”, or press Run batch evaluation.)`;
      const b = f.batch, s = b.saved;
      const tail = s.status === 'ok' ? `Random placement needs about ${s.m.toFixed(1)} cameras to match — ${s.saved.toFixed(1)} cameras saved.`
        : s.status === 'beyond' ? `Random placement does not match it even with ${s.maxTested} cameras.` : 'Here smart placement gives no saving over random.';
      return `With ${b.n} cameras, smart placement averages ${fx(b.smart)} effective routes against ${fx(b.random)} for random. ${tail}`;
    }
    case 4:
      if (f.linksOurs === undefined) break;
      return `The car was seen ${f.linksTrue} times. Our method linked ${f.linksOurs} of them; naive exact matching linked only ${f.linksNaive}, because a misread plate breaks its chain.`;
    case 5:
      if (!f.rejected) break;
      return `A look-alike plate was rejected (“${f.rejected.reason.split(':')[0]}”), leaving ${f.rejected.wrongLinks} wrong links in the tracked car’s chain.`;
  }
  return p.says;
}

/** Pure helper for the demo keyboard handling. */
export function demoKey(key: string, step: number, total: number): { step: number; exit?: boolean } | null {
  if (key === 'ArrowRight') return { step: Math.min(total - 1, step + 1) };
  if (key === 'ArrowLeft') return { step: Math.max(0, step - 1) };
  if (key === 'Escape') return { step, exit: true };
  return null;
}
