import { describe, expect, it } from 'vitest';
import { Graph } from '../src/sim/graph';
import { makeGridMap } from '../src/sim/gridMap';
import type { Edge, MapData } from '../src/sim/types';
import { effectiveRoutes, inferRoute, kPaths, normalise, scorePath } from '../src/track/routes';

/** Diamond: A -> X -> B and A -> Y -> B, equal lengths (two-way). */
function diamond(): Graph {
  const nodes = ['A', 'X', 'Y', 'B'].map((id, i) => ({ id, lat: 12 + i * 0.001, lon: 77 }));
  const mk = (u: string, v: string): Edge => ({ id: `${u}>${v}`, u, v, lengthM: 500, speedKph: 30, coords: [[77, 12], [77, 12.001]] });
  const edges = [mk('A', 'X'), mk('X', 'B'), mk('A', 'Y'), mk('Y', 'B')];
  return new Graph({ name: 'diamond', nodes, edges } as MapData);
}

describe('route scoring', () => {
  it('time fit peaks at dt and decays', () => {
    const f = (T: number) => scorePath({ travelTimeS: T, dt: 100, extraKm: 0, silentDetectProbs: [] });
    expect(f(100)).toBeCloseTo(1);
    expect(f(130)).toBeLessThan(f(110));
    expect(f(70)).toBeCloseTo(f(130));
  });
  it('negative evidence multiplies by (1 - detectProb) per silent camera', () => {
    const base = scorePath({ travelTimeS: 100, dt: 100, extraKm: 0, silentDetectProbs: [] });
    expect(scorePath({ travelTimeS: 100, dt: 100, extraKm: 0, silentDetectProbs: [0.9] })).toBeCloseTo(base * 0.1);
    expect(scorePath({ travelTimeS: 100, dt: 100, extraKm: 0, silentDetectProbs: [0.9, 0.5] })).toBeCloseTo(base * 0.05);
  });
  it('longer routes are mildly penalised', () => {
    const a = scorePath({ travelTimeS: 100, dt: 100, extraKm: 0, silentDetectProbs: [] });
    expect(scorePath({ travelTimeS: 100, dt: 100, extraKm: 1, silentDetectProbs: [] })).toBeCloseTo(a * Math.exp(-0.1));
  });
  it('normalise sums to 1; effective routes = N for uniform, 1 for certain', () => {
    expect(normalise([1, 3]).reduce((a, b) => a + b)).toBeCloseTo(1);
    expect(effectiveRoutes([0.25, 0.25, 0.25, 0.25])).toBeCloseTo(4);
    expect(effectiveRoutes([1])).toBeCloseTo(1);
    expect(effectiveRoutes([0.9, 0.1])).toBeLessThan(2);
  });
});

describe('route inference', () => {
  const g = diamond();
  const A = g.nodeIdx.get('A')!, B = g.nodeIdx.get('B')!, X = g.nodeIdx.get('X')!;
  const T = g.timeS[0] + g.timeS[1];

  it('two equal routes -> 50/50, effective routes = 2', () => {
    const r = inferRoute(g, A, B, 0, T, new Map());
    expect(r.rawCount).toBe(2);
    expect(r.hyps.map(h => h.prob)).toEqual([0.5, 0.5]);
    expect(r.effective).toBeCloseTo(2);
  });
  it('a silent camera on one route shifts probability to the other', () => {
    const r = inferRoute(g, A, B, 0, T, new Map([[X, 0.9]]));
    const viaX = r.hyps.find(h => h.nodeIds.includes('X'))!;
    const viaY = r.hyps.find(h => h.nodeIds.includes('Y'))!;
    expect(viaX.prob).toBeCloseTo(0.1 / 1.1, 2);
    expect(viaY.prob).toBeGreaterThan(0.9);
    expect(r.effective).toBeLessThan(1.5);
  });
  it('impossible travel time -> no feasible route', () => {
    expect(inferRoute(g, A, B, 0, T / 4, new Map()).rawCount).toBe(0);
    expect(inferRoute(g, A, B, 0, T * 4, new Map()).rawCount).toBe(0);
  });
});

describe('Yen k-shortest paths on the grid', () => {
  const g = new Graph(makeGridMap());
  it('returns distinct loop-free paths in non-decreasing time', () => {
    const a = g.nodeIdx.get('g0_0')!, b = g.nodeIdx.get('g4_4')!;
    const sp = g.shortestPath(a, b, e => g.timeS[e])!;
    const T = sp.reduce((s, e) => s + g.timeS[e], 0);
    const ps = kPaths(g, a, b, { maxT: T * 1.5, K: 40 });
    expect(ps.length).toBeGreaterThan(5);
    expect(ps[0].t).toBeCloseTo(T);
    expect(new Set(ps.map(p => p.edges.join(','))).size).toBe(ps.length);
    for (let i = 1; i < ps.length; i++) expect(ps[i].t).toBeGreaterThanOrEqual(ps[i - 1].t - 1e-9);
    for (const p of ps) {
      const nodes = [a, ...p.edges.map(e => g.ev[e])];
      expect(new Set(nodes).size).toBe(nodes.length);
      expect(nodes[nodes.length - 1]).toBe(b);
    }
  });
});
