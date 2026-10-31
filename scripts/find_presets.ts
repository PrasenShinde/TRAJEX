// Searches seeds/cars/camera placements on Koramangala for scenarios that demonstrate each preset's message.
import { readFileSync } from 'node:fs';
import { Engine, DEFAULT_CONFIG } from '../src/sim/engine';
import { Graph } from '../src/sim/graph';
import { InferenceCache, traceTarget, type Trace } from '../src/track/link';
import { inferRoute } from '../src/track/routes';
import { bestCamera, modelFromHyps } from '../src/track/suggest';

const g = new Graph({ name: 'kor', ...JSON.parse(readFileSync('public/data/koramangala.json', 'utf8')) });
const which = process.argv[2] ?? '12';
const seeds = (process.argv[3] ?? '2026,7,11,42,101').split(',').map(Number);
const cache = new InferenceCache();
const tgt = (e: Engine, id: string) => { const c = e.carById.get(id)!.car; return { plate: c.plate, type: c.type, colour: c.colour }; };
const rankOf = (e: Engine, car: string, sg: Trace['segments'][number]) => {
  const key = e.trueNodesBetween(car, sg.from.t, sg.to.t).map(n => g.nodes[n].id).join(',');
  return sg.inference.hyps.findIndex(h => h.nodeIds.join(',') === key) + 1; // 0 = not found
};

if (which.includes('1') || which.includes('2')) {
  let found = 0;
  for (const seed of seeds) {
    const e = new Engine(g, { ...DEFAULT_CONFIG, seed, nCars: 150, ocrError: 0.1, partialRate: 0.03, detectProb: 0.9 });
    e.run(1500);
    for (const cs of e.cars) {
      const v = cs.visits;
      for (let i = 0; i < v.length; i++) {
        if (v[i].arr < 100) continue;
        for (let j = i + 6; j < Math.min(v.length, i + 13); j++) {
          if (v[j].arr > 1450 || v[j].arr - v[i].arr < 100) continue;
          if (v[j].node === v[i].node) continue;
          const A = g.nodes[v[i].node].id, B = g.nodes[v[j].node].id;
          e.setCameras([A, B]);
          const tr = traceTarget(g, e.sightings, e.cameraList(), tgt(e, cs.car.id), 'ours', cache);
          if (tr.linked.length < 2 || tr.linked[0].nodeId !== A || tr.linked[1].nodeId !== B || tr.segments.length !== 1) continue;
          const sg = tr.segments[0];
          if (sg.inference.rawCount < 20 || sg.inference.effective < 8) continue;
          const r1 = rankOf(e, cs.car.id, sg);
          if (r1 === 1) continue;
          // preset 2: accept the suggestion for this car
          const models = [modelFromHyps(g, inferRoute(g, g.nodeIdx.get(A)!, g.nodeIdx.get(B)!, sg.from.t, sg.to.t, new Map(), { headingA: sg.from.heading }).hyps)];
          const sug = bestCamera(g, models, new Map([[g.nodeIdx.get(A)!, 0.9], [g.nodeIdx.get(B)!, 0.9]]), 0.9);
          if (!sug) continue;
          e.setCameras([A, B, sug.node]);
          const tr2 = traceTarget(g, e.sightings, e.cameraList(), tgt(e, cs.car.id), 'ours', cache);
          const eff = tr2.segments.map(s => +s.inference.effective.toFixed(1));
          const ranks = tr2.segments.map(s => rankOf(e, cs.car.id, s));
          if (tr2.segments.length < 2 || ranks.some(r => r !== 1) || Math.max(...eff) > 5) continue;
          console.log(JSON.stringify({ seed, car: cs.car.id, A, B, raw: sg.inference.rawCount, eff1: +sg.inference.effective.toFixed(1), rank1: r1, sug: sug.node, pct: +sug.gainPct.toFixed(0), linked2: tr2.linked.length, eff2: eff, ranks2: ranks }));
          if (++found >= 6) process.exit(0);
          break;
        }
      }
    }
  }
}

// ---- preset 4: misread at a middle camera ----
if (which.includes('4')) {
  let found = 0;
  for (const seed of seeds) {
    const e = new Engine(g, { ...DEFAULT_CONFIG, seed, nCars: 150, ocrError: 0, partialRate: 0, detectProb: 0.9 });
    e.run(1500);
    for (const cs of e.cars) {
      const v = cs.visits;
      for (let i = 0; i < v.length && found < 6; i++) {
        if (v[i].arr < 100) continue;
        for (let k = i + 4; k < Math.min(v.length, i + 9); k++) {
          const j = k + 5;
          if (j >= v.length || v[j].arr > 1450) continue;
          const A = g.nodes[v[i].node].id, M = g.nodes[v[k].node].id, B = g.nodes[v[j].node].id;
          if (new Set([A, M, B]).size < 3) continue;
          e.setCameras([A, B]); e.addCamera(M, { ocrError: 1 });
          const ours = traceTarget(g, e.sightings, e.cameraList(), tgt(e, cs.car.id), 'ours', cache);
          const naive = traceTarget(g, e.sightings, e.cameraList(), tgt(e, cs.car.id), 'naive', cache);
          const on = ours.linked.map(s => s.nodeId).join('>'), nn = naive.linked.map(s => s.nodeId).join('>');
          if (on !== `${A}>${M}>${B}` || nn !== `${A}>${B}`) continue;
          const mRead = ours.linked[1].plateRead;
          console.log(JSON.stringify({ preset: 4, seed, car: cs.car.id, plate: cs.car.plate, A, M, B, mRead, ours: on, naive: nn, eff: ours.segments.map(s => +s.inference.effective.toFixed(1)) }));
          found++; break;
        }
      }
      if (found >= 6) break;
    }
    if (found >= 6) break;
  }
}

// ---- preset 5: look-alike rejected for impossible travel (constructed camera placement) ----
if (which.includes('5')) {
  const { foldedDistance } = await import('../src/sim/plates');
  let found = 0;
  for (const seed of seeds) {
    const e = new Engine(g, { ...DEFAULT_CONFIG, seed, nCars: 150, ocrError: 0, partialRate: 0, detectProb: 1 });
    e.run(1500);
    for (const t of e.cars.filter(c => c.car.lookalikeOf)) {
      const o = e.carById.get(t.car.lookalikeOf!)!;
      if (foldedDistance(t.car.plate, o.car.plate) !== 1) continue;
      for (const [me, tw] of [[o, t], [t, o]]) {
        let done = false;
        for (let i = 0; i < me.visits.length && !done; i++) {
          const va = me.visits[i]; if (va.arr < 100) continue;
          const dA = g.dijkstra(va.node, e2 => g.timeS[e2]).dist;
          for (const vx of tw.visits) {
            const dt = vx.arr - va.arr;
            if (dt < 20 || dt > 150 || vx.arr > 1400 || vx.node === va.node) continue;
            if (dA[vx.node] < 2.2 * dt) continue; // must be clearly unreachable in time
            for (const vb of me.visits) {
              if (vb.arr < vx.arr + 120 || vb.arr > 1450 || vb.node === va.node || vb.node === vx.node) continue;
              const A = g.nodes[va.node].id, X = g.nodes[vx.node].id, B = g.nodes[vb.node].id;
              e.setCameras([A, X, B]);
              const tr = traceTarget(g, e.sightings, e.cameraList(), tgt(e, me.car.id), 'ours', cache);
              const rej = tr.decisions.filter(d => d.status === 'rejected' && d.sighting.trueCarId === tw.car.id && d.reason.startsWith('impossible travel'));
              if (tr.linked.map(s => s.nodeId).join('>') !== `${A}>${B}` || !rej.length || tr.linked.some(s => s.trueCarId !== me.car.id)) continue;
              console.log(JSON.stringify({ preset: 5, seed, car: me.car.id, twin: tw.car.id, plate: me.car.plate, twinPlate: tw.car.plate, A, X, B, eff: tr.segments.map(s => +s.inference.effective.toFixed(1)), reason: rej[0].reason }));
              found++; done = true; break;
            }
            if (done) break;
          }
        }
        if (found >= 6) process.exit(0);
      }
    }
  }
}
