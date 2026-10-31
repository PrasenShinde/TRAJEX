import { Graph, bearing } from './graph';
import { hash01, hashInt, mulberry32, pick, randInt, range, rngFrom, type Rng } from './rng';
import { generatePlate, mutatePlate, ocrSubstitute, partialRead } from './plates';
import type { Camera, Car, Sighting, VehicleType } from './types';

export type EngineConfig = {
  seed: number;
  nCars: number;
  lookalikes: boolean;
  ocrError: number; // 0..1
  partialRate: number; // 0..1
  detectProb: number; // 0..1  (miss rate = 1 - detectProb)
};

export const DEFAULT_CONFIG: EngineConfig = {
  seed: 2026, nCars: 150, lookalikes: true, ocrError: 0.15, partialRate: 0.05, detectProb: 0.9,
};

export const COLOURS: Record<string, [number, number, number]> = {
  white: [240, 240, 240], black: [70, 70, 80], silver: [185, 190, 200], red: [235, 70, 70],
  blue: [70, 120, 240], yellow: [250, 210, 60], green: [70, 190, 110], grey: [130, 135, 145],
};
const COLOUR_NAMES = Object.keys(COLOURS);
const TYPES: VehicleType[] = ['car', 'car', 'car', 'suv', 'suv', 'auto', 'bike', 'bike', 'bus'];

type Visit = {
  seq: number;
  node: number;
  arr: number;
  dep: number;
  outEdge: number; // edge idx to next visit, -1 until the next trip is generated
  trip: number;
};

type CarState = {
  idx: number;
  car: Car;
  visits: Visit[];
  trips: number[][]; // edge idx lists per trip (for car.route)
  ptr: number; // next unprocessed visit (arr > t)
};

export class Engine {
  t = 0;
  cars: CarState[] = [];
  cameras = new Map<string, Camera>(); // nodeId -> camera
  sightings: Sighting[] = [];
  carById = new Map<string, CarState>();

  constructor(public graph: Graph, public cfg: EngineConfig) {
    this.buildCars();
  }

  // ---------- population ----------
  private buildCars() {
    const g = this.graph, cfg = this.cfg;
    const r = mulberry32(cfg.seed ^ 0xa5a5);
    for (let i = 0; i < cfg.nCars; i++) {
      const car: Car = {
        id: `car${i}`,
        plate: generatePlate(r),
        type: pick(r, TYPES),
        colour: pick(r, COLOUR_NAMES),
        route: [],
        speedFactor: range(r, 0.6, 1.0),
        departT: -range(r, 0, 900),
      };
      if (car.type === 'auto') car.colour = pick(r, ['yellow', 'green', 'yellow']);
      this.cars.push({ idx: i, car, visits: [], trips: [], ptr: 0 });
    }
    if (cfg.lookalikes) {
      for (let i = 1; i < cfg.nCars; i++) {
        if (r() < 0.05) {
          const j = randInt(r, 0, i - 1);
          const base = this.cars[j].car;
          const c = this.cars[i].car;
          c.type = base.type; c.colour = base.colour;
          c.plate = mutatePlate(r, base.plate, r() < 0.7 ? 1 : 2);
          c.lookalikeOf = base.id;
        }
      }
    }
    for (const cs of this.cars) {
      this.carById.set(cs.car.id, cs);
      const o = Math.floor(hash01(cfg.seed, cs.idx, 77) * g.N);
      cs.visits.push({ seq: 0, node: o, arr: cs.car.departT, dep: cs.car.departT, outEdge: -1, trip: -1 });
      this.extend(cs, 0);
    }
  }

  /** Generate trips until visits cover well past time `until`. */
  private extend(cs: CarState, until: number) {
    let guard = 0;
    while (guard++ < 50) {
      const last = cs.visits[cs.visits.length - 1];
      const ahead = cs.visits.length - cs.ptr;
      if (last.dep > until + 300 && ahead >= 3) break;
      this.newTrip(cs);
    }
  }

  private newTrip(cs: CarState) {
    const g = this.graph, cfg = this.cfg;
    const tripNo = cs.trips.length;
    const seedT = hashInt(cfg.seed, cs.idx, tripNo, 991);
    const r = mulberry32(seedT);
    const last = cs.visits[cs.visits.length - 1];
    const weight = (e: number) => g.timeS[e] * (0.8 + 0.6 * hash01(seedT, e));
    let path: number[] | undefined;
    for (let attempt = 0; attempt < 8; attempt++) {
      const dst = Math.floor(r() * g.N);
      if (dst === last.node) continue;
      const p = g.shortestPath(last.node, dst, weight);
      if (p && p.length >= (attempt < 7 ? 4 : 1)) { path = p; break; }
    }
    if (!path) path = g.out[last.node].length ? [g.out[last.node][0]] : [];
    cs.trips.push(path);
    cs.car.route = path.map(e => g.edges[e].id);
    // last visit: leaves after a junction delay
    last.dep = last.arr + range(r, 0, 20);
    let tcur = last.dep;
    let prev = last;
    const sf = cs.car.speedFactor;
    for (const e of path) {
      prev.outEdge = e;
      tcur += g.lengthM[e] / ((g.edges[e].speedKph * sf) / 3.6);
      const v: Visit = { seq: prev.seq + 1, node: g.ev[e], arr: tcur, dep: tcur, outEdge: -1, trip: tripNo };
      v.dep = tcur + range(r, 0, 20);
      tcur = v.dep;
      cs.visits.push(v);
      prev = v;
    }
  }

  // ---------- cameras ----------
  // Camera / noise changes replay the same traffic ("what-if"): the sightings log is rebuilt from history,
  // so a newly added camera immediately has sightings of cars that already passed it.
  private addRaw(nodeId: string, opts: Partial<Camera> = {}) {
    if (this.cameras.has(nodeId)) return;
    this.cameras.set(nodeId, { id: `cam_${nodeId}`, nodeId, detectProb: this.cfg.detectProb, ...opts });
  }
  addCamera(nodeId: string, opts: Partial<Camera> = {}) { this.addRaw(nodeId, opts); this.rebuildLog(); }
  removeCamera(nodeId: string) { this.cameras.delete(nodeId); this.rebuildLog(); }
  toggleCamera(nodeId: string) {
    if (this.cameras.has(nodeId)) this.removeCamera(nodeId); else this.addCamera(nodeId);
  }
  setCameras(nodeIds: string[], opts: Partial<Camera> = {}) {
    this.cameras.clear();
    nodeIds.forEach(n => this.addRaw(n, opts));
    this.rebuildLog();
  }
  setDetectProb(p: number) {
    if (p === this.cfg.detectProb) return;
    this.cfg.detectProb = p;
    for (const c of this.cameras.values()) c.detectProb = p;
    this.rebuildLog();
  }
  setNoise(ocrError: number, partialRate: number) {
    if (ocrError === this.cfg.ocrError && partialRate === this.cfg.partialRate) return;
    this.cfg.ocrError = ocrError; this.cfg.partialRate = partialRate;
    this.rebuildLog();
  }
  /** Regenerate the whole sightings log for [0, t] with the current cameras and noise settings. */
  rebuildLog() {
    const out: Sighting[] = [];
    for (const cs of this.cars)
      for (let i = 0; i < cs.ptr; i++) {
        const v = cs.visits[i];
        if (v.arr < 0) continue;
        const s = this.maybeSight(cs, v);
        if (s) out.push(s);
      }
    out.sort((a, b) => a.t - b.t);
    this.sightings = out;
  }
  cameraList(): Camera[] { return [...this.cameras.values()]; }

  // ---------- stepping ----------
  step(dt: number) {
    this.t += dt;
    const fresh: Sighting[] = [];
    for (const cs of this.cars) {
      this.extend(cs, this.t);
      while (cs.visits[cs.ptr].arr <= this.t) {
        const v = cs.visits[cs.ptr];
        if (v.arr >= 0) {
          const s = this.maybeSight(cs, v);
          if (s) fresh.push(s);
        }
        cs.ptr++;
        if (cs.ptr >= cs.visits.length) this.extend(cs, this.t);
      }
    }
    fresh.sort((a, b) => a.t - b.t);
    for (const s of fresh) this.sightings.push(s);
    return fresh;
  }

  private maybeSight(cs: CarState, v: Visit): Sighting | null {
    const g = this.graph;
    const nodeId = g.nodes[v.node].id;
    const cam = this.cameras.get(nodeId);
    if (!cam) return null;
    const key = hashInt(this.cfg.seed, cs.idx, v.seq, 4242);
    if (hash01(key, 1) >= cam.detectProb) return null;
    const r: Rng = rngFrom(key, 2);
    const car = cs.car;
    const ocr = cam.ocrError ?? this.cfg.ocrError;
    let plateRead: string = car.plate;
    let conf = range(r, 0.85, 0.99);
    const u = r(), w = r();
    if (u < this.cfg.partialRate) { plateRead = partialRead(r, car.plate); conf = range(r, 0.5, 0.7); }
    else if (w < ocr) { plateRead = ocrSubstitute(r, car.plate); conf = range(r, 0.45, 0.75); }
    // occasional attribute confusion
    let type: string = car.type, colour = car.colour;
    if (r() < 0.03) type = pick(r, TYPES);
    if (r() < 0.03) colour = pick(r, COLOUR_NAMES);
    let heading = 0;
    if (v.outEdge >= 0) heading = g.edgeBearing(v.outEdge);
    return {
      id: `s_${cs.idx}_${v.seq}`, cameraId: cam.id, nodeId, t: v.arr,
      plateRead, plateConf: conf, type, colour, heading, trueCarId: car.id,
    };
  }

  // ---------- positions ----------
  carPosition(cs: CarState): [number, number] {
    const g = this.graph;
    const p = Math.max(0, cs.ptr - 1);
    const v = cs.visits[p];
    if (this.t < v.dep || v.outEdge < 0 || p + 1 >= cs.visits.length) {
      const n = g.nodes[v.node];
      return [n.lon, n.lat];
    }
    const nx = cs.visits[p + 1];
    const f = Math.min(1, Math.max(0, (this.t - v.dep) / (nx.arr - v.dep || 1)));
    return g.pointAlong(v.outEdge, f);
  }

  positions(): { id: string; pos: [number, number]; colour: [number, number, number]; idx: number }[] {
    return this.cars.map(cs => ({
      id: cs.car.id, idx: cs.idx, pos: this.carPosition(cs), colour: COLOURS[cs.car.colour] ?? [200, 200, 200],
    }));
  }

  // ---------- ground truth (for reveal / evaluation ONLY; never used by the tracker) ----------
  trueEdgesBetween(carId: string, t1: number, t2: number): number[] {
    const cs = this.carById.get(carId)!;
    const out: number[] = [];
    for (let i = 0; i < cs.visits.length - 1; i++) {
      const v = cs.visits[i];
      if (v.dep >= t1 - 1e-6 && cs.visits[i + 1].arr <= t2 + 1e-6 && v.outEdge >= 0) out.push(v.outEdge);
    }
    return out;
  }
  trueNodesBetween(carId: string, t1: number, t2: number): number[] {
    const cs = this.carById.get(carId)!;
    return cs.visits.filter(v => v.arr >= t1 - 1e-6 && v.arr <= t2 + 1e-6).map(v => v.node);
  }
  /** Sightings produced by one car (ground truth). */
  sightingsOf(carId: string): Sighting[] {
    return this.sightings.filter(s => s.trueCarId === carId);
  }

  /** Fast-forward without rendering. */
  run(untilT: number, dt = 5) {
    while (this.t < untilT) this.step(Math.min(dt, untilT - this.t));
  }
}

export { bearing };
