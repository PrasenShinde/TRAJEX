import type { Edge, MapData, Node } from './types';

/** Min-heap keyed by number. */
export class MinHeap<T> {
  private k: number[] = [];
  private v: T[] = [];
  get size() { return this.k.length; }
  push(key: number, val: T) {
    const k = this.k, v = this.v;
    let i = k.length;
    k.push(key); v.push(val);
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (k[p] <= key) break;
      k[i] = k[p]; v[i] = v[p]; i = p;
    }
    k[i] = key; v[i] = val;
  }
  pop(): [number, T] | undefined {
    const k = this.k, v = this.v;
    if (!k.length) return undefined;
    const rk = k[0], rv = v[0];
    const lk = k.pop()!, lv = v.pop()!;
    const n = k.length;
    if (n) {
      let i = 0;
      for (;;) {
        let c = 2 * i + 1;
        if (c >= n) break;
        if (c + 1 < n && k[c + 1] < k[c]) c++;
        if (k[c] >= lk) break;
        k[i] = k[c]; v[i] = v[c]; i = c;
      }
      k[i] = lk; v[i] = lv;
    }
    return [rk, rv];
  }
}

export const TYPICAL_SPEED_FACTOR = 0.8;

/** Directed road graph with integer indices internally. */
export class Graph {
  nodes: Node[];
  edges: Edge[];
  nodeIdx = new Map<string, number>();
  edgeIdx = new Map<string, number>();
  out: number[][]; // node idx -> edge idxs
  inn: number[][];
  eu: Int32Array; // edge idx -> from node idx
  ev: Int32Array;
  lengthM: Float64Array;
  /** Typical travel time (s): free-flow x typical traffic factor. */
  timeS: Float64Array;
  between = new Map<number, number>(); // u*N+v -> edge idx (fastest)
  minLat: number; maxLat: number; minLon: number; maxLon: number;

  constructor(public map: MapData) {
    this.nodes = map.nodes;
    this.edges = map.edges;
    const N = this.nodes.length, E = this.edges.length;
    this.nodes.forEach((n, i) => this.nodeIdx.set(n.id, i));
    this.edges.forEach((e, i) => this.edgeIdx.set(e.id, i));
    this.out = Array.from({ length: N }, () => []);
    this.inn = Array.from({ length: N }, () => []);
    this.eu = new Int32Array(E); this.ev = new Int32Array(E);
    this.lengthM = new Float64Array(E); this.timeS = new Float64Array(E);
    this.edges.forEach((e, i) => {
      const u = this.nodeIdx.get(e.u)!, v = this.nodeIdx.get(e.v)!;
      this.eu[i] = u; this.ev[i] = v;
      this.out[u].push(i); this.inn[v].push(i);
      this.lengthM[i] = e.lengthM;
      this.timeS[i] = e.lengthM / ((e.speedKph * TYPICAL_SPEED_FACTOR) / 3.6);
      const key = u * N + v;
      const prev = this.between.get(key);
      if (prev === undefined || this.timeS[i] < this.timeS[prev]) this.between.set(key, i);
    });
    this.minLat = Math.min(...this.nodes.map(n => n.lat));
    this.maxLat = Math.max(...this.nodes.map(n => n.lat));
    this.minLon = Math.min(...this.nodes.map(n => n.lon));
    this.maxLon = Math.max(...this.nodes.map(n => n.lon));
  }

  get N() { return this.nodes.length; }
  edgeBetween(u: number, v: number): number | undefined { return this.between.get(u * this.N + v); }

  /**
   * Dijkstra. weight(edgeIdx) gives cost. `blockedNodes`/`blockedEdges` are skipped.
   * Returns dist array and prev-edge array.
   */
  dijkstra(
    src: number,
    weight: (e: number) => number,
    opts: { target?: number; blockedNodes?: Set<number>; blockedEdges?: Set<number>; maxCost?: number; noExpand?: Set<number>; h?: Float64Array } = {},
  ) {
    const N = this.N;
    const dist = new Float64Array(N).fill(Infinity);
    const prevE = new Int32Array(N).fill(-1);
    const heap = new MinHeap<number>();
    dist[src] = 0;
    heap.push(0, src);
    const { target, blockedNodes, blockedEdges, maxCost, noExpand, h } = opts;
    while (heap.size) {
      const [key, u] = heap.pop()!;
      const d = dist[u];
      if (key > d + (h ? h[u] : 0) + 1e-9) continue;
      if (u === target) break;
      if (maxCost !== undefined && key > maxCost) break;
      if (noExpand && u !== src && noExpand.has(u)) continue;
      for (const e of this.out[u]) {
        if (blockedEdges && blockedEdges.has(e)) continue;
        const v = this.ev[e];
        if (blockedNodes && blockedNodes.has(v)) continue;
        const nd = d + weight(e);
        if (nd < dist[v]) {
          if (h && !isFinite(h[v])) continue;
          dist[v] = nd; prevE[v] = e; heap.push(h ? nd + h[v] : nd, v);
        }
      }
    }
    return { dist, prevE };
  }

  /** Exact distance-to-`dst` for every node (reverse Dijkstra) — an admissible A* heuristic. */
  distTo(dst: number, weight: (e: number) => number): Float64Array {
    const dist = new Float64Array(this.N).fill(Infinity);
    const heap = new MinHeap<number>();
    dist[dst] = 0; heap.push(0, dst);
    while (heap.size) {
      const [d, v] = heap.pop()!;
      if (d > dist[v]) continue;
      for (const e of this.inn[v]) {
        const u = this.eu[e], nd = d + weight(e);
        if (nd < dist[u]) { dist[u] = nd; heap.push(nd, u); }
      }
    }
    return dist;
  }

  /** Reconstruct edge path src->t from a prevE array; undefined if unreachable. */
  pathEdges(prevE: Int32Array, src: number, t: number): number[] | undefined {
    if (src === t) return [];
    if (prevE[t] < 0) return undefined;
    const p: number[] = [];
    let c = t;
    while (c !== src) { const e = prevE[c]; if (e < 0) return undefined; p.push(e); c = this.eu[e]; }
    return p.reverse();
  }

  shortestPath(src: number, dst: number, weight: (e: number) => number): number[] | undefined {
    const { prevE, dist } = this.dijkstra(src, weight, { target: dst });
    if (!isFinite(dist[dst])) return undefined;
    return this.pathEdges(prevE, src, dst);
  }

  private cum = new Map<number, Float64Array>();
  /** Point at fraction f (0..1, by distance) along an edge polyline, as [lon, lat]. */
  pointAlong(e: number, f: number): [number, number] {
    const c = this.edges[e].coords;
    if (c.length === 2) return [c[0][0] + (c[1][0] - c[0][0]) * f, c[0][1] + (c[1][1] - c[0][1]) * f];
    let cum = this.cum.get(e);
    if (!cum) {
      cum = new Float64Array(c.length);
      for (let i = 1; i < c.length; i++)
        cum[i] = cum[i - 1] + Math.hypot((c[i][0] - c[i - 1][0]) * 0.97, c[i][1] - c[i - 1][1]);
      this.cum.set(e, cum);
    }
    const total = cum[c.length - 1] || 1;
    const target = f * total;
    let i = 1;
    while (i < c.length - 1 && cum[i] < target) i++;
    const seg = cum[i] - cum[i - 1] || 1;
    const g = Math.min(1, Math.max(0, (target - cum[i - 1]) / seg));
    return [c[i - 1][0] + (c[i][0] - c[i - 1][0]) * g, c[i - 1][1] + (c[i][1] - c[i - 1][1]) * g];
  }

  /** Bearing (deg, 0=N, cw) of an edge's first segment. */
  edgeBearing(e: number, atEnd = false): number {
    const c = this.edges[e].coords;
    const [a, b] = atEnd ? [c[c.length - 2], c[c.length - 1]] : [c[0], c[1]];
    return bearing(a[1], a[0], b[1], b[0]);
  }
}

export function bearing(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dx = (lon2 - lon1) * Math.cos(((lat1 + lat2) / 2) * Math.PI / 180);
  const dy = lat2 - lat1;
  return ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360;
}
export const angDiff = (a: number, b: number) => {
  const d = Math.abs(a - b) % 360;
  return d > 180 ? 360 - d : d;
};
