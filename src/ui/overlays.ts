import { PathLayer, ScatterplotLayer } from '@deck.gl/layers';
import { PathStyleExtension } from '@deck.gl/extensions';
import type { Graph } from '../sim/graph';
import type { Trace } from '../track/link';

const coordsOf = (g: Graph, edgeIdxs: number[]) => {
  const out: [number, number][] = [];
  for (const e of edgeIdxs) for (const c of g.edges[e].coords) out.push(c);
  return out;
};

export type OverlayInput = {
  g: Graph;
  trace: Trace | null;
  reach: number[];
  trueEdges: number[] | null; // set when "Reveal" is on
  now: number;
};

export function buildOverlays(inp: OverlayInput): { under: any[]; over: any[] } {
  const { g, trace, reach, trueEdges } = inp;
  const under: any[] = [];
  const over: any[] = [];
  if (reach.length) {
    under.push(new PathLayer({
      id: 'reach', data: reach.map(e => ({ path: g.edges[e].coords })), getPath: (d: any) => d.path,
      getColor: [76, 201, 240, 70], getWidth: 14, widthUnits: 'meters', widthMinPixels: 4,
    }));
  }
  if (trace) {
    const data: { path: [number, number][]; prob: number; best: boolean }[] = [];
    for (const sg of trace.segments) {
      const hs = sg.inference.hyps;
      hs.forEach((h, i) => data.push({
        path: coordsOf(g, h.edgeIds.map(id => g.edgeIdx.get(id)!)), prob: h.prob, best: i === 0,
      }));
    }
    under.push(new PathLayer({
      id: 'hyps', data, getPath: (d: any) => d.path,
      getColor: (d: any) => [251, 191, 36, Math.round(45 + 210 * Math.min(1, d.prob * 1.2))] as any,
      getWidth: (d: any) => (d.best ? 9 : 5), widthUnits: 'meters', widthMinPixels: 2,
    }));
    const linkedPts = trace.linked.map(s => {
      const n = g.nodes[g.nodeIdx.get(s.nodeId)!];
      return { pos: [n.lon, n.lat] as [number, number] };
    });
    over.push(new ScatterplotLayer({
      id: 'linked', data: linkedPts, getPosition: (d: any) => d.pos, getRadius: 9, radiusUnits: 'pixels',
      filled: false, stroked: true, getLineColor: [74, 222, 128, 255], lineWidthMinPixels: 3,
    }));
    const rejPts = trace.decisions.filter(d => d.status === 'rejected').map(d => {
      const n = g.nodes[g.nodeIdx.get(d.sighting.nodeId)!];
      return { pos: [n.lon, n.lat] as [number, number] };
    });
    over.push(new ScatterplotLayer({
      id: 'rejected', data: rejPts, getPosition: (d: any) => d.pos, getRadius: 6, radiusUnits: 'pixels',
      filled: true, getFillColor: [248, 113, 113, 220],
    }));
  }
  if (trueEdges && trueEdges.length) {
    over.push(new PathLayer({
      id: 'truth', data: trueEdges.map(e => ({ path: g.edges[e].coords })), getPath: (d: any) => d.path,
      getColor: [74, 222, 128, 255], getWidth: 6, widthUnits: 'meters', widthMinPixels: 3,
      getDashArray: [6, 4], dashJustified: true, extensions: [new PathStyleExtension({ dash: true })],
    } as any));
  }
  return { under, over };
}
