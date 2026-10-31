import { Engine, DEFAULT_CONFIG } from './engine';
import type { Graph } from './graph';

export type ScenarioSpec = {
  seed: number; nCars: number; lookalikes: boolean; ocr: number; partial: number; miss: number; warm: number;
  cams: string[]; camOcr?: Record<string, number>;
};

/** Build an engine exactly as the app does: cameras placed, traffic warmed up for `warm` seconds, log rebuilt. */
export function buildEngine(graph: Graph, s: ScenarioSpec): Engine {
  const eng = new Engine(graph, { ...DEFAULT_CONFIG, seed: s.seed, nCars: s.nCars, lookalikes: s.lookalikes, ocrError: s.ocr, partialRate: s.partial, detectProb: 1 - s.miss });
  eng.setCameras(s.cams.filter(id => graph.nodeIdx.has(id)));
  for (const [n, v] of Object.entries(s.camOcr ?? {})) { const c = eng.cameras.get(n); if (c) c.ocrError = v; }
  eng.run(s.warm);
  eng.rebuildLog();
  return eng;
}
