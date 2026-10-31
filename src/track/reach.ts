import type { Graph } from '../sim/graph';
import type { Camera } from '../sim/types';

/**
 * Edges the car could be on `elapsed` seconds after being seen at `fromNode`,
 * without having passed an (unseeing) camera. Speed margin 1.25 = fastest car vs typical speed.
 */
export function reachableEdges(g: Graph, fromNode: string, elapsed: number, cameras: Camera[]): number[] {
  const src = g.nodeIdx.get(fromNode);
  if (src === undefined || elapsed <= 0) return [];
  const cams = new Set<number>();
  for (const c of cameras) { const i = g.nodeIdx.get(c.nodeId); if (i !== undefined) cams.add(i); }
  const maxCost = elapsed * 1.25;
  const { dist } = g.dijkstra(src, e => g.timeS[e], { maxCost, noExpand: cams });
  const out: number[] = [];
  for (let e = 0; e < g.edges.length; e++) {
    const u = g.eu[e];
    if (dist[u] <= maxCost && (u === src || !cams.has(u))) out.push(e);
  }
  return out;
}
