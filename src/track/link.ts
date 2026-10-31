import type { Graph } from '../sim/graph';
import { matchPlate } from '../sim/plates';
import type { Camera, Sighting } from '../sim/types';
import { inferRoute, type CamMap, type Inference } from './routes';

export type TrackTarget = { plate: string; type: string; colour: string };
export type Mode = 'ours' | 'naive';

export type Decision = {
  sighting: Sighting;
  status: 'linked' | 'rejected';
  reason: string;
  score?: number;
};
export type Segment = { from: Sighting; to: Sighting; inference: Inference };
export type Trace = {
  mode: Mode;
  first: Sighting | null;
  linked: Sighting[];
  decisions: Decision[]; // time-ordered, includes linked + rejected look-alikes
  segments: Segment[];
};

export const LINK_THRESHOLD = -7;

export function camMapOf(g: Graph, cameras: Camera[]): CamMap {
  const m: CamMap = new Map();
  for (const c of cameras) { const i = g.nodeIdx.get(c.nodeId); if (i !== undefined) m.set(i, c.detectProb); }
  return m;
}

const camSig = (cameras: Camera[]) => cameras.map(c => c.nodeId + ':' + c.detectProb.toFixed(2)).sort().join('|');

/** Cache of segment inferences, keyed by sighting pair + camera set. */
export class InferenceCache {
  private m = new Map<string, Inference>();
  private sp = new Map<number, Float64Array>();
  private spOf(g: Graph, n: number): Float64Array {
    let d = this.sp.get(n);
    if (!d) { d = g.dijkstra(n, e => g.timeS[e]).dist; this.sp.set(n, d); }
    return d;
  }
  get(g: Graph, a: Sighting, b: Sighting, cameras: Camera[], sig = camSig(cameras)): Inference {
    const k = `${a.id}>${b.id}@${sig}`;
    let r = this.m.get(k);
    if (!r) {
      const ia = g.nodeIdx.get(a.nodeId)!, ib = g.nodeIdx.get(b.nodeId)!;
      const minT = this.spOf(g, ia)[ib];
      if (ia === ib) {
        // same camera again: the car looped round the block(s); route is unknowable but a return is plausible
        const ok = b.t - a.t >= 60;
        r = { hyps: [], rawCount: ok ? 1 : 0, effective: ok ? 1 : 0, bestFitErr: 0, minTimeS: 0 };
      } else if (minT > 1.8 * (b.t - a.t)) {
        r = { hyps: [], rawCount: 0, effective: 0, bestFitErr: Infinity, minTimeS: minT };
      } else r = inferRoute(g, g.nodeIdx.get(a.nodeId)!, g.nodeIdx.get(b.nodeId)!, a.t, b.t, camMapOf(g, cameras), { headingA: a.heading });
      this.m.set(k, r);
      if (this.m.size > 5000) this.m.clear();
    }
    return r;
  }
}

function plateLL(read: string | null, conf: number, ref: string): { ll: number; ok: boolean; note: string } {
  const m = matchPlate(read, ref, 1);
  if (!m.ok) return { ll: -Infinity, ok: false, note: 'plate mismatch' };
  if (m.kind === 'exact' || m.kind === 'folded') return { ll: Math.log(Math.max(0.05, conf)), ok: true, note: m.kind === 'exact' ? 'exact plate' : 'plate matches after folding O/D, 8/B…' };
  if (m.kind === 'partial') return { ll: Math.log(0.5) + Math.log(m.known / ref.length), ok: true, note: `partial read agrees on ${m.known} slots` };
  return { ll: Math.log(Math.max(0.02, 1 - conf) * 0.3), ok: true, note: 'plate 1 char off' };
}

/**
 * Follow the target through the sightings log. Only reads `sightings` (never ground truth).
 */
export function traceTarget(
  g: Graph, sightings: Sighting[], cameras: Camera[], target: TrackTarget, mode: Mode, cache: InferenceCache,
): Trace {
  const trace: Trace = { mode, first: null, linked: [], decisions: [], segments: [] };
  if (mode === 'naive') {
    const exact = sightings.filter(s => s.plateRead === target.plate);
    trace.linked = exact;
    trace.first = exact[0] ?? null;
    trace.decisions = exact.map(s => ({ sighting: s, status: 'linked', reason: 'exact plate string match' }));
  } else {
    // first sighting: earliest clean match (distance 0), else earliest within distance 1
    const close = sightings.map(s => ({ s, m: matchPlate(s.plateRead, target.plate, 1) })).filter(x => x.m.ok);
    const first = (close.find(x => x.m.dist === 0 && x.m.kind !== 'partial') ?? close.find(x => x.m.dist === 0) ?? close[0])?.s;
    if (!first) return trace;
    trace.first = first;
    trace.linked = [first];
    const reasons = new Map<string, Decision>();
    reasons.set(first.id, { sighting: first, status: 'linked', reason: 'start: plate matches selected car' });
    const sig = camSig(cameras);
    let last = first;
    for (let iter = 0; iter < 200; iter++) {
      type Cand = { s: Sighting; score: number; inf: Inference; notes: string[] };
      const cands: Cand[] = [];
      let stopT = Infinity;
      for (const x of close) {
        const s = x.s;
        if (s.t <= last.t || s.id === last.id) continue;
        if (s.t > stopT) break; // lazily evaluate: later sightings are handled after this link
        if (reasons.get(s.id)?.status === 'linked') continue;
        const dt = s.t - last.t;
        const inf = cache.get(g, last, s, cameras, sig);
        if (!inf.rawCount) {
          const same = s.nodeId === last.nodeId;
          const need = isFinite(inf.minTimeS) ? `${Math.round(inf.minTimeS)} s` : 'no road route';
          reasons.set(s.id, { sighting: s, status: 'rejected', reason: same
            ? `impossible: same camera again after only ${Math.round(dt)} s`
            : inf.minTimeS < 0.7 * dt
              ? `gap too long for one trip: fastest route from ${last.nodeId} is ${need} but ${Math.round(dt)} s elapsed (car stopped / made other trips)`
              : `impossible travel: fastest route from ${last.nodeId} needs ${need}, only ${Math.round(dt)} s elapsed` });
          continue;
        }
        const p = plateLL(s.plateRead, s.plateConf, target.plate);
        const sigma = 0.25 * dt;
        const timeLL = -(inf.bestFitErr ** 2) / (2 * sigma * sigma);
        const typeLL = s.type === target.type ? Math.log(0.97) : Math.log(0.03 / 4);
        const colLL = s.colour === target.colour ? Math.log(0.97) : Math.log(0.03 / 7);
        const score = p.ll + timeLL + typeLL + colLL;
        if (score < LINK_THRESHOLD) {
          reasons.set(s.id, { sighting: s, status: 'rejected', score, reason: `score too low (${score.toFixed(1)}): ${s.type !== target.type ? 'type differs; ' : ''}${s.colour !== target.colour ? 'colour differs; ' : ''}${p.note}` });
          continue;
        }
        cands.push({ s, score, inf, notes: [p.note] });
        if (stopT === Infinity) stopT = s.t + 30;
      }
      if (!cands.length) break;
      cands.sort((a, b) => a.s.t - b.s.t);
      const tmin = cands[0].s.t;
      const group = cands.filter(c => c.s.t <= tmin + 30);
      const best = group.reduce((a, b) => (b.score > a.score ? b : a));
      for (const c of group) if (c !== best)
        reasons.set(c.s.id, { sighting: c.s, status: 'rejected', score: c.score, reason: `competing sighting at same time scored lower (${c.score.toFixed(1)} vs ${best.score.toFixed(1)})` });
      reasons.set(best.s.id, { sighting: best.s, status: 'linked', score: best.score, reason: `${best.notes[0]}; travel time fits (${best.inf.rawCount} feasible routes)` });
      trace.linked.push(best.s);
      last = best.s;
    }
    trace.decisions = [...reasons.values()].sort((a, b) => a.sighting.t - b.sighting.t);
  }
  const sig = camSig(cameras);
  for (let i = 0; i + 1 < trace.linked.length; i++)
    trace.segments.push({ from: trace.linked[i], to: trace.linked[i + 1], inference: cache.get(g, trace.linked[i], trace.linked[i + 1], cameras, sig) });
  return trace;
}
