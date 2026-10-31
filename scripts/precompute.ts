// Runs the (slow) batch evaluation for every preset that needs it and saves public/data/precomputed.json.
// Demo mode and preset 3 load this file instantly; the UI labels the numbers "precomputed".
import { readFileSync, writeFileSync } from 'node:fs';
import { Graph } from '../src/sim/graph';
import { PRESETS } from '../src/ui/presets';
import { runBatch } from '../src/track/eval';
import { batchSig, presetCams, type Precomputed } from '../src/ui/demoFacts';

const N_TRIPS = 200; // must match App.tsx
const out: Precomputed = { version: 1, presets: {} };
const maps: Record<string, Graph> = {};
const koramangala = () => (maps.koramangala ??= new Graph({ name: 'Bengaluru – Koramangala', ...JSON.parse(readFileSync('public/data/koramangala.json', 'utf8')) }));

for (const p of PRESETS.filter(x => x.autoBatch)) {
  if (p.map !== 'koramangala') continue;
  const g = koramangala();
  const cams = presetCams(g, p);
  const t0 = Date.now();
  const result = await runBatch(g, cams.map(c => g.nodeIdx.get(c)!), 1 - p.miss, p.seed, {
    nTrips: N_TRIPS, onProgress: (f, l) => process.stderr.write(`\rpreset ${p.id}: ${(f * 100).toFixed(0)}% ${l}          `),
  });
  out.presets[p.id] = { sig: batchSig(g.map.name, p.seed, cams, p.miss, N_TRIPS), nTrips: N_TRIPS, generated: new Date().toISOString(), result };
  console.log(`\npreset ${p.id} done in ${((Date.now() - t0) / 1000).toFixed(0)} s`);
}
writeFileSync('public/data/precomputed.json', JSON.stringify(out));
console.log('wrote public/data/precomputed.json');
