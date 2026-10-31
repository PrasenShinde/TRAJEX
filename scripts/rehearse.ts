// Headless rehearsal: loads every preset twice, checks the claim each one makes, and checks the runs are identical.
import { readFileSync } from 'node:fs';
import { Graph } from '../src/sim/graph';
import { randomCameraNodes } from '../src/sim/placement';
import { buildEngine } from '../src/sim/scenario';
import { PRESETS, type Preset } from '../src/ui/presets';
import { InferenceCache, traceTarget, type Trace } from '../src/track/link';
import { inferRoute } from '../src/track/routes';
import { bestCamera, modelFromHyps } from '../src/track/suggest';
import { camerasSaved, runBatch } from '../src/track/eval';

const g = new Graph({ name: 'kor', ...JSON.parse(readFileSync('public/data/koramangala.json', 'utf8')) });
let failures = 0;
const check = (ok: boolean, msg: string) => { console.log(`   ${ok ? 'PASS' : 'FAIL'}  ${msg}`); if (!ok) failures++; };

const spec = (p: Preset) => ({ ...p, cams: Array.isArray(p.cams) ? p.cams : randomCameraNodes(g, p.cams.random, p.seed) });
const rank = (e: ReturnType<typeof buildEngine>, car: string, sg: Trace['segments'][number]) => {
  const key = e.trueNodesBetween(car, sg.from.t, sg.to.t).map(n => g.nodes[n].id).join(',');
  return sg.inference.hyps.findIndex(h => h.nodeIds.join(',') === key) + 1;
};

async function run(p: Preset) {
  const s = spec(p);
  const e = buildEngine(g, s);
  const cache = new InferenceCache();
  const out: any = { sightings: e.sightings.length };
  if (p.car) {
    const c = e.carById.get(p.car)!.car;
    const target = { plate: c.plate, type: c.type, colour: c.colour };
    const ours = traceTarget(g, e.sightings, e.cameraList(), target, 'ours', cache);
    const naive = traceTarget(g, e.sightings, e.cameraList(), target, 'naive', cache);
    out.ours = ours.linked.map(x => x.nodeId).join('>');
    out.naive = naive.linked.map(x => x.nodeId).join('>');
    out.eff = ours.segments.map(x => +x.inference.effective.toFixed(2));
    out.raw = ours.segments.map(x => x.inference.rawCount);
    out.ranks = ours.segments.map(x => rank(e, p.car!, x));
    out.rejected = ours.decisions.filter(d => d.status === 'rejected').map(d => `${d.sighting.trueCarId}: ${d.reason.slice(0, 60)}`);
    out.wrongLinks = ours.linked.filter(x => x.trueCarId !== p.car).length;
    if (p.autoSuggest && ours.segments.length) {
      const sg = ours.segments[0];
      const A = g.nodeIdx.get(sg.from.nodeId)!, B = g.nodeIdx.get(sg.to.nodeId)!;
      const models = [modelFromHyps(g, inferRoute(g, A, B, sg.from.t, sg.to.t, new Map(), { headingA: sg.from.heading }).hyps)];
      const sug = bestCamera(g, models, new Map(e.cameraList().map(cm => [g.nodeIdx.get(cm.nodeId)!, cm.detectProb] as [number, number])), 1 - p.miss)!;
      e.addCamera(sug.node);
      const t2 = traceTarget(g, e.sightings, e.cameraList(), target, 'ours', cache);
      out.suggested = sug.node;
      out.after = { linked: t2.linked.map(x => x.nodeId).join('>'), eff: t2.segments.map(x => +x.inference.effective.toFixed(2)), ranks: t2.segments.map(x => rank(e, p.car!, x)) };
    }
  }
  if (p.autoBatch) {
    const b = await runBatch(g, e.cameraList().map(c => g.nodeIdx.get(c.nodeId)!), 1 - p.miss, p.seed, { nTrips: +(process.env.TRIPS ?? 200) });
    out.chart = b.chart.map(r => [r.cameras, +r.random.toFixed(2), +r.smart.toFixed(2)]);
    out.saved = camerasSaved(b.chart, e.cameras.size, b.currentSmart.avgRoutes, b.currentRandom.avgRoutes);
    out.currentRandom = +b.currentRandom.avgRoutes.toFixed(2); out.currentSmart = +b.currentSmart.avgRoutes.toFixed(2);
  }
  return out;
}

for (const p of PRESETS) {
  console.log(`\nPreset ${p.id}: ${p.title}`);
  const a = await run(p), b = await run(p);
  check(JSON.stringify(a) === JSON.stringify(b), 'two runs are identical (deterministic)');
  if (p.id === 1) {
    check(a.ours.split('>').length === 2, `2 linked sightings (${a.ours})`);
    check(a.raw[0] >= 20 && a.eff[0] >= 20, `20+ possible routes (feasible ${a.raw[0]}, effective ${a.eff[0]})`);
    check(a.ranks[0] !== 1, `top-1 route is wrong (true route rank ${a.ranks[0] || 'not in list'})`);
  }
  if (p.id === 2) {
    check(a.eff[0] >= 20 && a.ranks[0] !== 1, `before: ${a.eff[0]} routes, true rank ${a.ranks[0]}`);
    check(a.after.linked.split('>').length === 3, `after adding ${a.suggested}: ${a.after.linked}`);
    check(Math.max(...a.after.eff) <= 5, `routes collapse to ${a.after.eff.join(' and ')} effective`);
    check(a.after.ranks.every((r: number) => r === 1), `true route is rank #1 on every piece (${a.after.ranks})`);
  }
  if (p.id === 3) {
    check(a.chart.every((r: number[]) => r[2] < r[1]), `smart < random at every count ${JSON.stringify(a.chart)}`);
    console.log(`   INFO  cameras saved: ${JSON.stringify(a.saved)}`);
    check(a.currentSmart < a.currentRandom, `same count (10): smart ${a.currentSmart} < random ${a.currentRandom}`);
  }
  if (p.id === 4) {
    check(a.ours.split('>').length === 3 && a.wrongLinks === 0, `ours links all 3 (${a.ours})`);
    check(a.naive.split('>').length === 2, `naive loses the middle one (${a.naive})`);
  }
  if (p.id === 5) {
    check(a.rejected.some((r: string) => r.includes('impossible travel')), `look-alike rejected: ${a.rejected[0]}`);
    check(a.wrongLinks === 0, 'no look-alike sighting was linked');
  }
}
console.log(failures ? `\n${failures} CHECK(S) FAILED` : '\nALL PRESET CHECKS PASSED');
process.exit(failures ? 1 : 0);
