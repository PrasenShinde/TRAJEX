import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PRESETS, type Preset } from './presets';
import type { MapData } from '../sim/types';
import { MapView } from './MapView';
import { DEFAULT_CONFIG } from '../sim/engine';
import { buildEngine } from '../sim/scenario';
import { Graph } from '../sim/graph';
import { makeGridMap } from '../sim/gridMap';
import { fold } from '../sim/plates';
import { RightPanel } from './RightPanel';
import { buildOverlays } from './overlays';
import { InferenceCache, traceTarget, type Mode } from '../track/link';
import { reachableEdges } from '../track/reach';
import { BottomStrip, type BatchState, type LiveMetrics } from './BottomStrip';
import { buildModels, routeShare, runBatch, sampleTrips } from '../track/eval';
import { bestCamera, greedyPlacement, modelFromHyps, type SegModel, type Suggestion } from '../track/suggest';
import { inferRoute } from '../track/routes';
import { randomCameraNodes } from '../sim/placement';

const fmtT = (t: number) => {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
};

export type MapMode = 'grid' | 'koramangala';
const mapCache: Partial<Record<MapMode, MapData>> = {};
async function loadMap(mode: MapMode): Promise<MapData> {
  if (mapCache[mode]) return mapCache[mode]!;
  const m: MapData = mode === 'grid' ? makeGridMap()
    : { name: 'Bengaluru – Koramangala', ...(await (await fetch(`${import.meta.env.BASE_URL}data/koramangala.json`)).json()) };
  mapCache[mode] = m;
  return m;
}

const Q = new URLSearchParams(typeof location !== 'undefined' ? location.search : '');

export function App() {
  const [mapMode, setMapMode] = useState<MapMode>(Q.get('map') === 'kor' ? 'koramangala' : 'grid');
  const [mapData, setMapData] = useState<MapData | null>(null);
  const [mapErr, setMapErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setMapErr(null);
    loadMap(mapMode).then(m => { if (live) setMapData(m); }).catch(e => { if (live) { setMapErr(String(e)); setMapMode('grid'); } });
    return () => { live = false; };
  }, [mapMode]);
  const [seed, setSeed] = useState(+(Q.get('seed') ?? DEFAULT_CONFIG.seed));
  const [nCars, setNCars] = useState(DEFAULT_CONFIG.nCars);
  const [lookalikes, setLookalikes] = useState(true);
  const [playing, setPlaying] = useState(Q.get('pause') !== '1');
  const [speed, setSpeed] = useState(10);
  const [ocr, setOcr] = useState(DEFAULT_CONFIG.ocrError);
  const [partial, setPartial] = useState(DEFAULT_CONFIG.partialRate);
  const [miss, setMiss] = useState(1 - DEFAULT_CONFIG.detectProb);
  const [, setTick] = useState(0);
  const camNodes = useRef<string[] | null>(null);
  const [selected, setSelected] = useState<string | null>(Q.get('sel'));
  const [mode, setMode] = useState<Mode>('ours');
  const [reveal, setReveal] = useState(Q.get('reveal') === '1');
  const [showReach, setShowReach] = useState(true);
  const [search, setSearch] = useState('');
  const cache = useRef(new InferenceCache());
  const [sugg, setSugg] = useState<{ key: string; s: Suggestion | null; basis: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [batch, setBatch] = useState<BatchState>({ running: false, progress: 0, label: '', result: null });
  const N_TRIPS = 200;
  const [warm, setWarm] = useState(+(Q.get('warm') ?? 900));
  const [nonce, setNonce] = useState(0); // bumps to force a fresh engine (e.g. re-clicking a preset)
  const camOcr = useRef<Record<string, number>>({});
  const [presetId, setPresetId] = useState<number | null>(null);
  const [wantSuggest, setWantSuggest] = useState(false);
  const [wantBatch, setWantBatch] = useState(false);
  const modelCache = useRef<{ key: string; models: SegModel[] } | null>(null);

  const engine = useMemo(() => {
    const graph = new Graph(mapData ?? mapCache.grid ?? makeGridMap());
    let ids = (camNodes.current ?? []).filter(id => graph.nodeIdx.has(id));
    if (!ids.length) ids = randomCameraNodes(graph, 8, seed);
    camNodes.current = ids;
    return buildEngine(graph, { seed, nCars, lookalikes, ocr, partial, miss, warm, cams: ids, camOcr: camOcr.current });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed, nCars, lookalikes, mapData, warm, nonce]);

  // live-tunable noise params
  engine.setNoise(ocr, partial);
  engine.setDetectProb(1 - miss);

  const syncCams = () => { camNodes.current = engine.cameraList().map(c => c.nodeId); setTick(t => t + 1); };
  const onJunctionClick = useCallback((id: string) => { engine.toggleCamera(id); syncCams(); }, [engine]);
  const applyPreset = async (pr: Preset) => {
    const m = await loadMap(pr.map);
    const graph = new Graph(m);
    camNodes.current = Array.isArray(pr.cams) ? pr.cams : randomCameraNodes(graph, pr.cams.random, pr.seed);
    camOcr.current = pr.camOcr ?? {};
    modelCache.current = null;
    setBatch({ running: false, progress: 0, label: '', result: null });
    setSugg(null);
    setMapMode(pr.map); setMapData(m);
    setSeed(pr.seed); setNCars(pr.nCars); setLookalikes(pr.lookalikes);
    setOcr(pr.ocr); setPartial(pr.partial); setMiss(pr.miss); setWarm(pr.warm);
    setSelected(pr.car); setMode(pr.mode); setReveal(false); setShowReach(false);
    setPlaying(false); setPresetId(pr.id); setNonce(n => n + 1);
    setWantSuggest(!!pr.autoSuggest); setWantBatch(!!pr.autoBatch);
  };
  useEffect(() => { const id = +(Q.get('preset') ?? 0); const pr = PRESETS.find(x => x.id === id); if (pr) applyPreset(pr); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const setCameraCount = (n: number) => {
    camOcr.current = {};
    const cur = engine.cameraList().map(c => c.nodeId);
    if (n < cur.length) engine.setCameras(cur.slice(0, n));
    else engine.setCameras([...cur, ...randomCameraNodes(engine.graph, n - cur.length, seed + cur.length, new Set(cur))]);
    syncCams();
  };
  const rerollCameras = () => { camOcr.current = {}; engine.setCameras(randomCameraNodes(engine.graph, engine.cameras.size, seed + Math.floor(Math.random() * 1e6))); syncCams(); };

  const sampleModels = async (): Promise<SegModel[]> => {
    const key = `${engine.graph.map.name}|${seed}`;
    if (modelCache.current?.key !== key) {
      const n = engine.graph.N > 200 ? 80 : 150; // live-sized sample; the batch evaluation uses 200
      modelCache.current = { key, models: await buildModels(engine.graph, sampleTrips(engine.graph, n, seed + 202, engine.graph.N > 200 ? 8 : 6)) };
    }
    return modelCache.current.models;
  };
  const camMapNow = () => new Map(engine.cameraList().map(c => [engine.graph.nodeIdx.get(c.nodeId)!, c.detectProb] as [number, number]));
  const camKey = engine.cameraList().map(c => c.nodeId).sort().join(',') + '|' + selected + '|' + mode;

  const selCar = selected ? engine.carById.get(selected) : undefined;
  const trace = selCar
    ? traceTarget(engine.graph, engine.sightings, engine.cameraList(), { plate: selCar.car.plate, type: selCar.car.type, colour: selCar.car.colour }, mode, cache.current)
    : null;
  const g = engine.graph;
  const naiveTrace = selCar
    ? traceTarget(g, engine.sightings, engine.cameraList(), { plate: selCar.car.plate, type: selCar.car.type, colour: selCar.car.colour }, 'naive', cache.current)
    : null;
  const lastLinked = trace && trace.linked.length ? trace.linked[trace.linked.length - 1] : null;
  const reach = showReach && lastLinked ? reachableEdges(g, lastLinked.nodeId, engine.t - lastLinked.t, engine.cameraList()) : [];
  const trueEdges = reveal && selCar && trace?.first ? engine.trueEdgesBetween(selCar.car.id, trace.first.t, lastLinked!.t) : null;
  const ov = buildOverlays({ g, trace, reach, trueEdges, now: engine.t });

  const trueRank = (i: number): number | null => {
    if (!trace || !selCar) return null;
    const sg = trace.segments[i];
    const te = engine.trueNodesBetween(selCar.car.id, sg.from.t, sg.to.t).map(n => g.nodes[n].id).join(',');
    const k = sg.inference.hyps.findIndex(h => h.nodeIds.join(',') === te);
    return k >= 0 ? k + 1 : null;
  };
  const doSuggest = () => {
    setBusy('Finding the best next camera…');
    setTimeout(async () => {
      let models: SegModel[]; let basis: string;
      if (trace && trace.segments.length) {
        models = trace.segments.map(sg => modelFromHyps(g, inferRoute(g, g.nodeIdx.get(sg.from.nodeId)!, g.nodeIdx.get(sg.to.nodeId)!, sg.from.t, sg.to.t, new Map(), { headingA: sg.from.heading }).hyps));
        basis = 'the tracked car’s ambiguous segments';
      } else { models = await sampleModels(); basis = 'sampled trips'; }
      setSugg({ key: camKey, s: bestCamera(g, models, camMapNow(), 1 - miss), basis });
      setBusy(null);
    }, 20);
  };
  const addSuggested = () => {
    if (!sugg?.s) return;
    engine.addCamera(sugg.s.node); syncCams(); setSugg(null);
  };
  const smartPlace = () => {
    setBusy('Placing cameras greedily…');
    setTimeout(async () => {
      camOcr.current = {};
      const n = Math.max(1, engine.cameras.size);
      const picks = greedyPlacement(g, await sampleModels(), n, 1 - miss);
      engine.setCameras(picks.map(i => g.nodes[i].id)); syncCams(); setSugg(null); setBusy(null);
    }, 20);
  };
  const runBatchEval = async () => {
    setBatch(b => ({ ...b, running: true, progress: 0, label: 'starting' }));
    const cur = engine.cameraList().map(c => g.nodeIdx.get(c.nodeId)!);
    const result = await runBatch(g, cur, 1 - miss, seed, { nTrips: N_TRIPS, onProgress: (f, l) => setBatch(b => ({ ...b, progress: f, label: l })) });
    setBatch({ running: false, progress: 1, label: '', result });
  };

  useEffect(() => {
    if (wantSuggest) { setWantSuggest(false); doSuggest(); }
    if (wantBatch) { setWantBatch(false); runBatchEval(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wantSuggest, wantBatch, engine]);

  const live: LiveMetrics = (() => {
    const lastSegs = trace ? trace.segments.slice(-5) : [];
    const avgRoutes = lastSegs.length ? lastSegs.reduce((a, sg) => a + sg.inference.effective, 0) / lastSegs.length : null;
    let acc: number | null = null, rank: number | null = null;
    let lo: LiveMetrics['linkOurs'] = null, ln: LiveMetrics['linkNaive'] = null;
    if (reveal && selCar && trace) {
      const accs: number[] = [], ranks: number[] = [];
      for (const sg of lastSegs) {
        if (!sg.inference.hyps.length) continue;
        const tn = engine.trueNodesBetween(selCar.car.id, sg.from.t, sg.to.t);
        accs.push(routeShare(g, sg.inference.hyps[0].nodeIds.map(id => g.nodeIdx.get(id)!), tn));
        const key = tn.map(n => g.nodes[n].id).join(',');
        const k = sg.inference.hyps.findIndex(h => h.nodeIds.join(',') === key);
        if (k >= 0) ranks.push(k + 1);
      }
      acc = accs.length ? accs.reduce((a, b) => a + b, 0) / accs.length : null;
      rank = ranks.length ? ranks.reduce((a, b) => a + b, 0) / ranks.length : null;
      const total = engine.sightingsOf(selCar.car.id).length;
      const stat = (tr: typeof trace) => {
        const ok = tr!.linked.filter(x => x.trueCarId === selCar.car.id).length;
        return { precision: tr!.linked.length ? ok / tr!.linked.length : 0, recall: total ? ok / total : 0, n: tr!.linked.length };
      };
      lo = stat(trace); ln = naiveTrace ? stat(naiveTrace) : null;
    }
    return { cameras: engine.cameras.size, junctions: g.N, avgRoutes, segCount: lastSegs.length, routeAccuracy: acc, meanRank: rank, linkOurs: lo, linkNaive: ln };
  })();
  const activeSugg = sugg && sugg.key === camKey ? sugg : null;

  const onSearch = () => {
    const q = fold(search.toUpperCase().replace(/\s+/g, ''));
    if (!q) return;
    const hit = engine.cars.find(c => fold(c.car.plate).includes(q));
    if (hit) setSelected(hit.car.id);
  };

  return (
    <div className="app">
      <div className="panel left">
        <h3>Demo presets</h3>
        <div className="row">
          {PRESETS.map(pr => (
            <button key={pr.id} className={presetId === pr.id ? 'on' : ''} onClick={() => applyPreset(pr)} title={pr.says}>{pr.id}. {pr.title}</button>
          ))}
        </div>
        {presetId && (() => { const pr = PRESETS.find(x => x.id === presetId)!; return (
          <div className="card"><b>{pr.title}</b><div>{pr.says}</div><div className="dim" style={{ marginTop: 4 }}>{pr.steps}</div></div>
        ); })()}
        <h3>Map</h3>
        <div className="row">
          <button className={mapMode === 'grid' ? 'on' : ''} onClick={() => setMapMode('grid')}>Grid city</button>
          <button className={mapMode === 'koramangala' ? 'on' : ''} onClick={() => setMapMode('koramangala')}>Koramangala</button>
        </div>
        {mapErr && <div className="no">Could not load map: {mapErr}</div>}
        {mapData && mapData.name !== engine.graph.map.name && <div className="warn">Loading {mapData.name}…</div>}
        <h3>Simulation</h3>
        <div className="row">
          <button className={playing ? 'on' : ''} onClick={() => setPlaying(p => !p)}>{playing ? '❚❚ Pause' : '▶ Play'}</button>
          <span className="mono">t = {fmtT(engine.t)}</span>
        </div>
        <label>Speed <span className="v">{speed}×</span></label>
        <input type="range" min={1} max={30} value={speed} onChange={e => setSpeed(+e.target.value)} />
        <label>Seed</label>
        <input type="number" value={seed} onChange={e => setSeed(+e.target.value || 0)} />
        <label>Cars <span className="v">{nCars}</span></label>
        <input type="range" min={20} max={300} step={10} value={nCars} onChange={e => setNCars(+e.target.value)} />
        <label><input type="checkbox" checked={lookalikes} onChange={e => setLookalikes(e.target.checked)} /> Look-alike plates (~5%)</label>

        <h3>Cameras</h3>
        <label>Count <span className="v">{engine.cameras.size} ({Math.round((100 * engine.cameras.size) / engine.graph.N)}% of junctions)</span></label>
        <input type="range" min={0} max={Math.min(engine.graph.N, 80)} value={engine.cameras.size} onChange={e => setCameraCount(+e.target.value)} />
        <div className="row">
          <button onClick={rerollCameras}>Random</button>
          <button onClick={smartPlace} title="Greedy: each camera placed where it removes the most route uncertainty">Smart</button>
        </div>
        <div className="row"><button className="primary" onClick={doSuggest}>Suggest next camera</button></div>
        {busy && <div className="warn">{busy}</div>}
        {activeSugg && (activeSugg.s ? (
          <div className="card">
            <b>Suggested: junction {activeSugg.s.node}</b>
            <div className="ok">+{activeSugg.s.gainPct.toFixed(0)}% certainty <span className="dim">(expected route-entropy reduction over {activeSugg.basis})</span></div>
            <button className="primary" onClick={addSuggested}>Add suggested camera</button>
          </div>
        ) : <div className="dim">No junction would reduce uncertainty further.</div>)}
        <div className="dim">Click any junction on the map to add / remove a camera.</div>

        <h3>Camera mistakes</h3>
        <label>OCR error rate <span className="v">{Math.round(ocr * 100)}%</span></label>
        <input type="range" min={0} max={0.6} step={0.01} value={ocr} onChange={e => setOcr(+e.target.value)} />
        <label>Partial read rate <span className="v">{Math.round(partial * 100)}%</span></label>
        <input type="range" min={0} max={0.5} step={0.01} value={partial} onChange={e => setPartial(+e.target.value)} />
        <label>Miss rate <span className="v">{Math.round(miss * 100)}%</span></label>
        <input type="range" min={0} max={0.8} step={0.01} value={miss} onChange={e => setMiss(+e.target.value)} />
      </div>

      <MapView
        engine={engine} playing={playing} speed={speed} overlays={ov.under} topOverlays={ov.over} selectedCarId={selCar ? selCar.car.id : null} suggestedNode={activeSugg?.s?.node ?? null}
        onJunctionClick={onJunctionClick} onCarClick={(id) => { setSelected(id); setReveal(false); }} onTick={() => setTick(t => t + 1)}
      >
        {activeSugg?.s && (
          <div className="floating">
            <b>Suggested camera: {activeSugg.s.node}</b> <span className="ok">+{activeSugg.s.gainPct.toFixed(0)}% certainty</span>
            <div><button className="primary" onClick={addSuggested}>Add suggested camera</button></div>
          </div>
        )}
      </MapView>

      <RightPanel
        engine={engine} carId={selCar ? selCar.car.id : null} trace={trace} mode={mode} setMode={setMode}
        reveal={reveal} setReveal={setReveal} showReach={showReach} setShowReach={setShowReach}
        search={search} setSearch={setSearch} onSearch={onSearch} onDeselect={() => { setSelected(null); setReveal(false); }}
        trueRank={trueRank}
      />

      <BottomStrip live={live} batch={batch} onRun={runBatchEval} nTrips={N_TRIPS} />
    </div>
  );
}
