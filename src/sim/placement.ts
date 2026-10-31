import type { Graph } from './graph';
import { mulberry32 } from './rng';

/** n random junctions (seeded), excluding some. */
export function randomCameraNodes(graph: Graph, n: number, seed: number, exclude: Set<string> = new Set()): string[] {
  const r = mulberry32(seed * 7919 + n);
  const pool = graph.nodes.map(x => x.id).filter(id => !exclude.has(id));
  const out: string[] = [];
  while (out.length < n && pool.length) out.push(pool.splice(Math.floor(r() * pool.length), 1)[0]);
  return out;
}
