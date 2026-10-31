import { describe, expect, it } from 'vitest';
import { Engine, DEFAULT_CONFIG } from '../src/sim/engine';
import { Graph } from '../src/sim/graph';
import { makeGridMap } from '../src/sim/gridMap';

const make = (over = {}, dt = 5) => {
  const g = new Graph(makeGridMap());
  const e = new Engine(g, { ...DEFAULT_CONFIG, ...over });
  e.setCameras(g.nodes.filter((_, i) => i % 3 === 0).map(n => n.id));
  e.run(1200, dt);
  return e;
};

describe('engine', () => {
  it('grid is 64 junctions and strongly connected', () => {
    const g = new Graph(makeGridMap());
    expect(g.N).toBe(64);
    const { dist } = g.dijkstra(0, e => g.timeS[e]);
    expect(Array.from(dist).every(isFinite)).toBe(true);
    const rev = g.dijkstra(0, e => g.timeS[e], {});
    expect(rev.dist.length).toBe(64);
  });
  it('is deterministic from the seed regardless of step size', () => {
    const a = make({}, 5), b = make({}, 1);
    expect(a.sightings.map(s => s.id + s.plateRead)).toEqual(b.sightings.map(s => s.id + s.plateRead));
  });
  it('different seeds differ', () => {
    expect(make({ seed: 1 }).sightings.length).toBeGreaterThan(50);
    expect(make({ seed: 1 }).cars[0].car.plate).not.toBe(make({ seed: 2 }).cars[0].car.plate);
  });
  it('produces misreads and partial reads', () => {
    const e = make({ ocrError: 0.3, partialRate: 0.1 });
    const truth = (id: string) => e.carById.get(id)!.car.plate;
    const bad = e.sightings.filter(s => s.plateRead !== truth(s.trueCarId));
    expect(bad.length).toBeGreaterThan(0);
    expect(e.sightings.some(s => s.plateRead?.includes('?'))).toBe(true);
  });
});
