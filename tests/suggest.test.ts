import { describe, expect, it } from 'vitest';
import { Engine, DEFAULT_CONFIG } from '../src/sim/engine';
import { Graph } from '../src/sim/graph';
import { makeGridMap } from '../src/sim/gridMap';
import { bestCamera, expectedEntropyAfter, greedyPlacement, segEntropy, type SegModel } from '../src/track/suggest';

const g = new Graph(makeGridMap());
// two equally likely routes sharing only their ends; junction 10 is on route 1, 20 on route 2, 30 on both
const model: SegModel = { paths: [{ nodes: [10, 30], w: 0.5 }, { nodes: [20, 30], w: 0.5 }] };

describe('camera suggestion (6.4)', () => {
  it('a camera that splits the routes reduces expected entropy; one on every route does not', () => {
    const h0 = segEntropy(model, new Map());
    expect(h0).toBeCloseTo(Math.log(2));
    expect(expectedEntropyAfter(model, new Map(), 10, 0.9)).toBeLessThan(h0);
    expect(expectedEntropyAfter(model, new Map(), 30, 0.9)).toBeCloseTo(h0);
  });
  it('perfect camera removes all uncertainty; a blind camera (p=0) removes none', () => {
    expect(expectedEntropyAfter(model, new Map(), 10, 1)).toBeCloseTo(0);
    expect(expectedEntropyAfter(model, new Map(), 10, 0)).toBeCloseTo(Math.log(2));
  });
  it('bestCamera picks a splitting junction, not the shared one, and ignores existing cameras', () => {
    const s = bestCamera(g, [model], new Map(), 0.9)!;
    expect([10, 20]).toContain(s.nodeIdx);
    expect(s.gainPct).toBeGreaterThan(0);
    const s2 = bestCamera(g, [model], new Map([[10, 0.9]]), 0.9)!;
    expect(s2.nodeIdx).not.toBe(10);
  });
  it('greedy placement returns distinct junctions', () => {
    const p = greedyPlacement(g, [model, model], 5, 0.9);
    expect(new Set(p).size).toBe(p.length);
  });
});

describe('what-if camera replay', () => {
  it('adding a camera immediately yields sightings of cars that already passed it', () => {
    const e = new Engine(g, { ...DEFAULT_CONFIG, nCars: 60 });
    e.run(900);
    expect(e.sightings.length).toBe(0);
    e.addCamera('g3_3');
    expect(e.sightings.length).toBeGreaterThan(0);
    expect(e.sightings.every(s => s.nodeId === 'g3_3')).toBe(true);
    const n = e.sightings.length;
    e.removeCamera('g3_3');
    expect(e.sightings.length).toBe(0);
    e.addCamera('g3_3');
    expect(e.sightings.length).toBe(n); // deterministic
  });
});
