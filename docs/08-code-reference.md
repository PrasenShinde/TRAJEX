# 08 · Code reference

Every source file, grouped by folder. For each: purpose, main exports, key functions (inputs → outputs), and which files use it. Line counts are from the current files.

Conventions: "node index" means the integer index inside `Graph`; "node id" means the string such as `n231`. A *time* is in seconds.

---

## `src/` (root)

### `src/main.tsx` (6 lines)
- **Purpose:** Browser entry point. Renders `<App/>` into `#root` and imports `styles.css`.
- **Used by:** `index.html` (as `/src/main.tsx`).

### `src/vite-env.d.ts` (1 line)
- **Purpose:** Vite's type declarations (gives `import.meta.env` its type).

---

## `src/sim/` — the simulated world

### `src/sim/types.ts` (38 lines)
- **Purpose:** The shared data shapes.
- **Exports:** `Node {id, lat, lon}`, `Edge {id, u, v, lengthM, speedKph, coords[[lon,lat]…], highway?, oneway?}`, `Camera {id, nodeId, detectProb, ocrError?, offline?}`, `VehicleType`, `Car {id, plate, type, colour, route, speedFactor, departT, lookalikeOf?}`, `Sighting {id, cameraId, nodeId, t, plateRead, plateConf, type, colour, heading, trueCarId}`, `RouteHypothesis {edgeIds, nodeIds, travelTimeS, prob}`, `MapData {name, nodes, edges}`.
- **Used by:** `graph.ts`, `gridMap.ts`, `engine.ts`, `link.ts`, `routes.ts`, `reach.ts`, `suggest.ts`, `App.tsx`, `tests/routes.test.ts`.

### `src/sim/rng.ts` (33 lines)
- **Purpose:** All randomness. No other file uses `Math.random()` except the Random button in `App.tsx`.
- **Exports:**
  - `type Rng = () => number` (returns a number in [0,1)).
  - `mulberry32(seed) → Rng`: seeded generator.
  - `hashInt(...numbers) → uint32`: mixes integers into one number.
  - `hash01(...numbers) → number in [0,1)`: `hashInt / 2³²`.
  - `rngFrom(...numbers) → Rng`: `mulberry32(hashInt(...))`.
  - `randInt(r, lo, hi)`, `pick(r, array)`, `range(r, lo, hi)`.
- **Used by:** `engine.ts`, `plates.ts`, `placement.ts`, `eval.ts`, `tests/plates.test.ts`.

### `src/sim/graph.ts` (193 lines)
- **Purpose:** The road graph and path searching.
- **Exports:**
  - `class MinHeap<T>`: min-heap with `push(key, value)`, `pop() → [key, value]`, `size`.
  - `TYPICAL_SPEED_FACTOR = 0.8`.
  - `class Graph(map: MapData)` with fields `nodes, edges, nodeIdx, edgeIdx, out, inn, eu, ev, lengthM, timeS, minLat/maxLat/minLon/maxLon` and:
    - `N` (number of nodes);
    - `edgeBetween(u, v) → edge index | undefined` (fastest edge u→v);
    - `dijkstra(src, weight, opts) → { dist, prevE }`; options: `target`, `blockedNodes`, `blockedEdges`, `maxCost`, `noExpand`, `h` (A* heuristic);
    - `distTo(dst, weight) → Float64Array` (exact distance from every node to `dst`, by reverse Dijkstra);
    - `pathEdges(prevE, src, t) → edge[] | undefined`;
    - `shortestPath(src, dst, weight) → edge[] | undefined`;
    - `pointAlong(edge, fraction) → [lon, lat]`;
    - `edgeBearing(edge, atEnd = false) → degrees`.
  - `bearing(lat1, lon1, lat2, lon2) → degrees` (0 = north, clockwise), `angDiff(a, b) → 0..180`.
- **Used by:** `engine.ts`, `scenario.ts`, `placement.ts`, all `src/track/*`, `App.tsx`, `overlays.ts`, `demoFacts.ts`, scripts, tests.

### `src/sim/gridMap.ts` (52 lines)
- **Purpose:** Builds the Grid city.
- **Exports:** `makeGridMap(size = 8, block = 300) → MapData` (name "Grid city"; 64 nodes; 196 edges for the defaults).
- **Used by:** `App.tsx`, `scripts/batch.ts`, `tests/engine`, `routes`, `suggest`, `failure`.

### `src/sim/plates.ts` (125 lines)
- **Purpose:** Plate text: creation, mistakes, folding, matching.
- **Exports:**
  - `RTO_CODES`, `CONFUSION_PAIRS`, `MIN_PARTIAL_KNOWN = 6`.
  - `confusablePartner(ch)`.
  - `fold(plate) → string`: replaces each character by its class representative.
  - `generatePlate(r) → "KA" + RTO + 2 letters + 4 digits`.
  - `formatPlate(p) → "KA 03 VY 9255"` (10-character plates only).
  - `mutatePlate(r, plate, n) → plate` with `n` characters changed (look-alikes).
  - `ocrSubstitute(r, plate) → plate` with one character misread.
  - `partialRead(r, plate) → plate` with 2–3 `?`.
  - `levenshtein(a, b)`, `foldedDistance(a, b)`.
  - `matchPlate(read, ref, maxDist = 1) → { ok, kind: 'exact'|'folded'|'near'|'partial'|'none', dist, known }`.
- **Used by:** `engine.ts` (generate, mutate, substitute, partial), `link.ts` (`matchPlate`), `App.tsx` (`fold` for search), `RightPanel.tsx` (`formatPlate`), `scripts/find_presets.ts` (`foldedDistance`), `tests/plates.test.ts`.

### `src/sim/engine.ts` (284 lines)
- **Purpose:** The simulation engine.
- **Exports:**
  - `EngineConfig {seed, nCars, lookalikes, ocrError, partialRate, detectProb}`, `DEFAULT_CONFIG` (`seed 2026, nCars 150, lookalikes true, ocrError 0.15, partialRate 0.05, detectProb 0.9`).
  - `COLOURS` (name → RGB) used to draw cars.
  - `class Engine(graph, cfg)`:
    - state: `t`, `cars`, `cameras`, `sightings`, `carById`;
    - private `buildCars()`, `extend(cs, until)`, `newTrip(cs)`;
    - cameras: `addCamera(nodeId, opts)`, `removeCamera`, `toggleCamera`, `setCameras(nodeIds, opts)`, `setDetectProb(p)`, `setNoise(ocr, partial)`, `rebuildLog()`, `cameraList()`, `allCameras()`, `setOffline`, `failCamera`, `restoreCamera`, `toggleFail`;
    - time: `step(dt) → fresh sightings`, `run(untilT, dt = 5)`;
    - private `maybeSight(cs, visit) → Sighting | null`;
    - drawing: `carPosition(cs)`, `positions() → [{id, pos, colour, idx}]`;
    - ground truth: `trueEdgesBetween(carId, t1, t2)`, `trueNodesBetween(carId, t1, t2)`, `sightingsOf(carId)`.
  - Also re-exports `bearing`.
- **Used by:** `scenario.ts`, `App.tsx` (default config), `MapView.tsx`, `RightPanel.tsx`, `CompareView.tsx` (types), `scripts/find_presets.ts`, `tests/engine`, `suggest`, `failure`.

### `src/sim/scenario.ts` (18 lines)
- **Purpose:** One shared way to build an engine so the app and the scripts get identical worlds.
- **Exports:**
  - `ScenarioSpec {seed, nCars, lookalikes, ocr, partial, miss, warm, cams, camOcr?, failed?}`.
  - `buildEngine(graph, spec) → Engine`: creates the engine with `detectProb = 1 − miss`; sets the cameras (ignoring unknown junction ids); applies per-camera OCR overrides; marks failed cameras offline; runs `warm` seconds; rebuilds the log.
- **Used by:** `App.tsx`, `CompareView.tsx`, `demoFacts.ts`, `scripts/rehearse.ts`. (A `Preset` can be passed as a `ScenarioSpec` because it has the same fields.)

### `src/sim/placement.ts` (11 lines)
- **Purpose:** Seeded random camera positions.
- **Exports:** `randomCameraNodes(graph, n, seed, exclude = new Set()) → node ids` (uses `mulberry32(seed × 7919 + n)`; never repeats a junction).
- **Used by:** `App.tsx`, `CompareView.tsx`, `demoFacts.ts`, `scripts/rehearse.ts`.

---

## `src/track/` — the tracker

### `src/track/routes.ts` (138 lines)
- **Purpose:** Route enumeration, scoring, probabilities, entropy.
- **Exports:**
  - `Path {edges, t, dev?}`.
  - `kPaths(g, src, dst, {minT, maxT, K = 40, maxGen = 150}) → Path[]`: Yen's algorithm with A* and Lawler's rule.
  - `scorePath({travelTimeS, dt, extraKm, silentDetectProbs, headingPenalty = 1}) → number`.
  - `entropyOf(probs)`, `effectiveRoutes(probs) = exp(entropy)` (0 for an empty list), `normalise(scores)`.
  - `Inference {hyps, rawCount, effective, bestFitErr, minTimeS}`; `CamMap = Map<nodeIdx, detectProb>`.
  - `inferRoute(g, a, b, tA, tB, cams, {headingA?, K?}) → Inference`.
- **Used by:** `link.ts`, `eval.ts`, `App.tsx` (suggestion), `demoFacts.ts`, `scripts/*`, `tests/routes.test.ts`.

### `src/track/link.ts` (145 lines)
- **Purpose:** Following one car through the sightings.
- **Exports:**
  - Types: `TrackTarget {plate, type, colour}`, `Mode = 'ours' | 'naive'`, `Decision {sighting, status, reason, score?}`, `Segment {from, to, inference}`, `Trace {mode, first, linked, decisions, segments}`.
  - `LINK_THRESHOLD = −7`.
  - `camMapOf(g, cameras) → CamMap`.
  - `class InferenceCache` with `get(g, a, b, cameras, sig?) → Inference`; handles same-camera returns, the `minT > 1.8·Δt` shortcut, and calls `inferRoute()`; clears itself above 5000 entries.
  - `traceTarget(g, sightings, cameras, target, mode, cache) → Trace`.
  - (private) `camSig`, `plateLL`.
- **Used by:** `App.tsx`, `CompareView.tsx`, `overlays.ts` (types), `RightPanel.tsx` (types), `presets.ts` (type `Mode`), `demoFacts.ts`, `scripts/rehearse.ts`, `scripts/find_presets.ts`.

### `src/track/reach.ts` (21 lines)
- **Purpose:** The "where could it be now" area.
- **Exports:** `reachableEdges(g, fromNodeId, elapsedSeconds, cameras) → edge indices`.
- **Used by:** `App.tsx`.

### `src/track/suggest.ts` (88 lines)
- **Purpose:** Choosing where to put cameras.
- **Exports:**
  - `SegModel {paths: [{nodes, w}]}`; `modelFromHyps(g, hyps) → SegModel`.
  - `segEntropy(m, S)`; `expectedEntropyAfter(m, S, j, p, w?)`.
  - `Suggestion {node, nodeIdx, gain, gainPct, baseEntropy}`.
  - `bestCamera(g, models, S, p, exclude = new Set()) → Suggestion | null`.
  - `greedyPlacement(g, models, k, p, existing = []) → node indices` in pick order.
- **Used by:** `eval.ts`, `App.tsx`, `demoFacts.ts`, `scripts/rehearse.ts`, `scripts/find_presets.ts`, `tests/suggest`, `tests/failure`.

### `src/track/eval.ts` (199 lines)
- **Purpose:** Batch evaluation and metrics.
- **Exports:**
  - `Trip {nodes, edges, arr, heading0}`; `sampleTrips(g, n, seed, minEdges = 6, maxEdges = 40) → Trip[]`.
  - `routeShare(g, hypNodes, trueNodes) → 0..1`.
  - `buildModels(g, trips) → Promise<SegModel[]>`.
  - `EvalResult`; `evaluatePlacement(g, trips, cameraNodes, p, seed) → Promise<EvalResult>`.
  - `ChartPoint {cameras, random, randomMin, randomMax, smart}`, `Batch {current, chart, suggestedFirst}`, `RANDOM_SEEDS = 5`.
  - `CamerasSaved` (union of `ok`, `beyond`, `none`); `camerasSaved(chart, n, smartAvg, randomAtN?)`.
  - `runBatch(g, current, p, seed, {nTrips = 200, counts = [5,10,15,20,25], onProgress}) → Promise<Batch & {currentRandom, currentSmart}>`.
  - Re-exports `bestCamera`.
- **Used by:** `App.tsx`, `BottomStrip.tsx` (`camerasSaved`, types), `CompareView.tsx`, `demoFacts.ts`, `scripts/batch.ts`, `scripts/precompute.ts`, `scripts/rehearse.ts`, `tests/eval.test.ts`.

---

## `src/ui/` — the user interface

### `src/ui/App.tsx` (375 lines)
- **Purpose:** Root component: all state, engine creation, tracker calls, layout, preset loading, demo control.
- **Exports:** `type MapMode = 'grid' | 'koramangala'`, `App()`.
- **Key internal functions:**
  - `loadMap(mode)`: grid built in code; Koramangala fetched from `data/koramangala.json`; cached in `mapCache`.
  - `loadPrecomputed()`: loads `data/precomputed.json` once.
  - `applyPreset(preset)`: sets every setting, loads the precomputed entry if its signature matches, starts `gatherFacts` for captions.
  - `demoStep(step)`, keyboard handler through `demoKey()`.
  - `setCameraCount`, `rerollCameras`, `smartPlace`, `doSuggest`, `addSuggested`, `toggleFail`, `onJunctionClick`, `runBatchEval`, `onSearch`.
  - `sampleModels()`: cached route models of sampled trips (80 on Koramangala, 150 on the grid).
  - `trueRank(i)`: rank of the true route for segment `i`.
  - the `live` metrics block.
- **Uses:** nearly everything. **Used by:** `main.tsx`, and `presets.ts` imports its type `MapMode`.

### `src/ui/MapView.tsx` (138 lines)
- **Purpose:** The deck.gl canvas and the animation loop.
- **Exports:** `MapViewProps`, `MapView(props)`.
- **Behaviour:** On each new `engine`, builds a `Deck` (pan/zoom controller), fits the map to the window, handles clicks (junction → `onJunctionClick`, car → `onCarClick`), right-click on a camera (`contextmenu` → `pickObject` on the junction layer → `onCameraContext`), then runs a `requestAnimationFrame` loop: steps the engine when playing, rebuilds the layers (roads, junctions, overlays, cameras, offline cameras and ✕, suggestion, cars, selected ring, top overlays), and calls `onTick` every 250 ms.
- **Used by:** `App.tsx`, `CompareView.tsx`.

### `src/ui/RightPanel.tsx` (111 lines)
- **Purpose:** Plate search, mode toggle, car card, sighting timeline, route lists.
- **Exports:** `RightPanelProps`, `RightPanel(props)`.
- **Used by:** `App.tsx`.

### `src/ui/BottomStrip.tsx` (103 lines)
- **Purpose:** Live metrics, batch controls, headline, table, chart.
- **Exports:** `LiveMetrics`, `BatchState`, `BottomStrip({live, batch, onRun, nTrips})`. Inside: `Chart` (inline SVG) and `SavedHeadline` (calls `camerasSaved`, optional cost box).
- **Used by:** `App.tsx`.

### `src/ui/CompareView.tsx` (73 lines)
- **Purpose:** Side-by-side random vs smart.
- **Exports:** `CompareView({base, mode, selectedId, playing, speed, cache, smartCameras, onCarClick})`.
- **Behaviour:** For the current camera count `n`, gets the smart set from `smartCameras(n)` (padding with random junctions if fewer were found) and a seeded random set; builds two engines with `buildEngine()` (same seed, cars, noise, warm-up = current time); then evaluates the same 60 sampled trips on both with `evaluatePlacement()`.
- **Used by:** `App.tsx`.

### `src/ui/overlays.ts` (68 lines)
- **Purpose:** Convert tracker output to deck.gl layers.
- **Exports:** `OverlayInput`, `buildOverlays({g, trace, reach, trueEdges, now}) → { under, over }`. `under` (below cars): the reach haze `reach`, the amber `hyps`. `over`: green `linked` rings, red `rejected` dots, green dashed `truth` line (`PathStyleExtension`).
- **Used by:** `App.tsx`, `CompareView.tsx`.

### `src/ui/presets.ts` (69 lines)
- **Purpose:** The six presets as data.
- **Exports:** `Preset` type; `PRESETS` array.
- **Used by:** `App.tsx`, `demoFacts.ts`, `scripts/rehearse.ts`, `scripts/precompute.ts`, `tests/demo.test.ts`.

### `src/ui/demoFacts.ts` (122 lines)
- **Purpose:** Demo captions and precomputed-file helpers.
- **Exports:**
  - Types: `BatchResult`, `PrecomputedEntry`, `Precomputed`, `Facts`.
  - `presetCams(g, preset) → string[]`; `batchSig(mapName, seed, cams, miss, nTrips) → string`; `specOf(g, preset) → ScenarioSpec`.
  - `gatherFacts(g, preset, precomputedEntry) → Facts`: builds a fresh engine and computes the numbers (routes, rank, suggestion, after-suggestion routes, links ours/naive, rejection reason, batch figures, healthy-routes for a failed-camera preset).
  - `captionFor(facts, preset) → string`.
  - `demoKey(key, step, total) → {step, exit?} | null`.
- **Used by:** `App.tsx`, `scripts/rehearse.ts`, `scripts/precompute.ts`, `tests/demo.test.ts`.

### `src/ui/styles.css` (37 lines)
- **Purpose:** Dark theme, grid layout (`270px 1fr 360px` columns, bottom row 200 px), panels, buttons, tables, chips, floating cards, demo card, compare layout.
- **Used by:** `main.tsx`.

---

## `scripts/`

| File | Purpose | Run with | Uses |
|---|---|---|---|
| `rehearse.ts` (112) | Loads each preset twice, runs checks, prints captions. | `npm run rehearse` | graph, placement, scenario, eval, link, routes, suggest, demoFacts, presets |
| `precompute.ts` (26) | Runs the Koramangala batch for preset 3 and writes `public/data/precomputed.json`. | `npm run precompute` | graph, eval, presets, demoFacts |
| `batch.ts` (13) | Runs the batch on a map and prints the table. | `npm run batch [grid\|kor] [trips]` | graph, gridMap, eval |
| `find_presets.ts` (124) | Searches for scenarios for presets 1/2, 4 and 5. | `npm run find-presets [digits] [seeds]` | engine, graph, link, routes, suggest, plates |
| `export_osm.py` (88) | Downloads and consolidates the OpenStreetMap network, writes `public/data/koramangala.json`. | `npm run export-osm` | osmnx, networkx |

## `tests/`

| File | Tests | Imports |
|---|---|---|
| `plates.test.ts` | 6 | plates, rng |
| `routes.test.ts` | 8 | graph, gridMap, types, routes |
| `suggest.test.ts` | 5 | engine, graph, gridMap, suggest |
| `eval.test.ts` | 6 | eval |
| `engine.test.ts` | 4 | engine, graph, gridMap |
| `failure.test.ts` | 4 | engine, graph, gridMap, suggest |
| `demo.test.ts` | 5 | demoFacts, presets |

## `public/data/`

| File | Content |
|---|---|
| `koramangala.json` | `{ nodes: [{id, lat, lon}], edges: [{id, u, v, lengthM, speedKph, highway, oneway, coords}] }` — 1117 nodes, 3230 edges. |
| `precomputed.json` | `{ version: 1, presets: { "3": { sig, nTrips, generated, result } } }` where `result` is a `Batch & {currentRandom, currentSmart}`. |

## Config files

| File | Purpose |
|---|---|
| `package.json` | Name `sparse-camera-tracker`, ES module project, scripts, dependencies. |
| `tsconfig.json` | Target ES2020, strict, `jsx: react-jsx`, `noEmit`; includes `src`, `tests`, `scripts/*.ts`, `vite.config.ts`. |
| `vite.config.ts` | React plugin; `test.include = ['tests/**/*.test.ts']`. |
| `index.html` | Page shell with title "Sparse-Camera Vehicle Tracking Simulator". |
| `.gitignore` | Ignores `node_modules`, `dist`, `.venv`, `*.log`. |

---

## To change X, edit Y

| # | To change… | Edit… |
|---|---|---|
| 1 | The default number of cars, OCR error, partial-read rate or miss rate | `DEFAULT_CONFIG` in `src/sim/engine.ts`. Slider ranges and steps are in the `<input type="range">` lines in `src/ui/App.tsx`. |
| 2 | Which characters are treated as look-alike (OCR confusion) | `CONFUSION_PAIRS` in `src/sim/plates.ts`. Update `tests/plates.test.ts` (it lists the pairs) and re-run `npm run precompute`. |
| 3 | The travel-time window, number of routes, or time-fit width | `0.7`, `1.8`, `K = 40` in `inferRoute()` and `kPaths()` (`src/track/routes.ts`); `σ = 0.25·dt` in `scorePath()`; the matching `1.8` shortcut and `60 s` rule in `InferenceCache.get()` (`src/track/link.ts`). |
| 4 | How sightings are scored or when they are rejected | `LINK_THRESHOLD`, `plateLL()`, and the `typeLL`/`colLL` lines in `src/track/link.ts`; the 30 s competing-group window in `traceTarget()`. |
| 5 | Road speeds or the "typical traffic" assumption | `TYPICAL_SPEED_FACTOR` in `src/sim/graph.ts`; speeds table `DEFAULT_KPH` in `scripts/export_osm.py` (then re-export); grid speeds in `speedFor` in `src/sim/gridMap.ts`. |
| 6 | How many look-alikes there are and how different they are | `0.05` and `r() < 0.7 ? 1 : 2` in `Engine.buildCars()` (`src/sim/engine.ts`); `mutatePlate()` in `src/sim/plates.ts`. |
| 7 | A preset's scenario or message | `PRESETS` in `src/ui/presets.ts`; captions in `captionFor()` and numbers in `gatherFacts()` (`src/ui/demoFacts.ts`). Then run `npm run find-presets`, `npm run precompute` (if preset 3) and `npm run rehearse`. |
| 8 | The batch (camera counts on the chart, number of trips, random seeds) | `counts` and `nTrips` defaults and `RANDOM_SEEDS` in `src/track/eval.ts`; `N_TRIPS` in `src/ui/App.tsx` **and** `scripts/precompute.ts` (they must match); then re-run `npm run precompute`. |
| 9 | Colours, line widths, markers, map layers | `src/ui/overlays.ts` (routes, haze, rings, truth line) and `src/ui/MapView.tsx` (roads, junctions, cameras, cars, suggestion); page colours in `src/ui/styles.css`. |
| 10 | The city or area | `WEST, SOUTH, EAST, NORTH` in `scripts/export_osm.py`, re-export, and update `loadMap()` in `src/ui/App.tsx` if the file name changes; then redo presets. |
