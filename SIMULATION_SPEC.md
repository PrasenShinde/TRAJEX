# Sparse-Camera Vehicle Tracking Simulator — Build Spec

SIH 2026 · PS 26127 (BEL) · demo simulator, browser-only, built in one night with Claude Code.

## 1. What it demonstrates

A city has few cameras. A car is seen at camera A, then later at camera D; between them it could have taken many roads.
**Fewer cameras → more possible routes → less certainty.** Our method (road graph + travel time + direction +
"cameras that did *not* see it" + fuzzy plate matching) narrows the possibilities and links the car even when plates are misread.

The audience should leave with three points:
1. Route uncertainty grows when cameras are sparse — and we can **measure** it.
2. Our method recovers the true route far better than naive plate matching.
3. **Where** cameras go matters as much as **how many** — the simulator suggests the best next camera.

## 2. Scope rules

- Frontend only: React + Vite + TypeScript. No backend, no database, no real video.
- Everything deterministic from a **seed** (same seed → same cars, same demo). Seed shown in the UI.
- Must run offline on a laptop (road network bundled as a JSON file; basemap optional).
- Target: ~300 cars, ~1,000–2,000 road nodes, 60 FPS on a normal laptop.

## 3. Maps

| Mode | Purpose | Source |
|---|---|---|
| **Grid city** | Explain the idea in 30 s | Generated in code: 8×8 junctions, 300 m blocks, a few one-way streets and two arterials |
| **Bengaluru – Koramangala** | Realistic demo | OpenStreetMap drive network, bbox approx. W 77.612, S 12.922, E 77.640, N 12.948 (adjust to taste) |

Why Koramangala: dense, grid-like Bengaluru neighbourhood with many parallel alternative routes (ideal for showing route ambiguity),
BEL is headquartered in Bengaluru, Koramangala hosts the KA-01 RTO, and Bengaluru's Safe City CCTV is the source of the UVH-26 dataset.

### Road data export (one-time, Python)
`scripts/export_osm.py` using `osmnx` (2.x):
- `graph_from_bbox(bbox=(west, south, east, north), network_type="drive")`
- project, `consolidate_intersections(tolerance=15)` to merge complex junctions, keep one-way directions
- export `public/data/koramangala.json`:
  `{ nodes: [{id, lat, lon}], edges: [{id, u, v, lengthM, speedKph, highway, oneway, coords: [[lon,lat],...]}] }`
- default speeds when missing: primary 35, secondary 30, tertiary 25, residential 20 km/h (city traffic, not limits)

## 4. Data model (TypeScript)

```ts
type Node = { id: string; lat: number; lon: number };
type Edge = { id: string; u: string; v: string; lengthM: number; speedKph: number; coords: [number, number][] };
type Camera = { id: string; nodeId: string; detectProb: number };          // placed on junctions
type Car = { id: string; plate: string; type: 'car'|'suv'|'auto'|'bike'|'bus'; colour: string;
             route: string[] /* edge ids */; speedFactor: number; departT: number };
type Sighting = { id: string; cameraId: string; t: number; plateRead: string | null; plateConf: number;
                  type: string; colour: string; heading: number; trueCarId: string /* hidden from tracker */ };
type RouteHypothesis = { edgeIds: string[]; travelTimeS: number; prob: number };
```

## 5. Simulation engine

- **Clock** with play/pause and speed 1×–30×.
- **Cars**: random origin/destination; route = shortest path on *perturbed* travel times (each car multiplies edge times by
  random 0.8–1.4) so cars don't all take the shortest route. Per-car `speedFactor` 0.6–1.0, plus 0–20 s random junction delay.
  Respawn on arrival.
- **Plates**: realistic Bengaluru format `KA DD LL NNNN` (RTO codes 01, 02, 03, 04, 05, 41, 50, 51, 53). ~5% of cars are
  **look-alikes**: same type + colour, plate differing by 1–2 characters from another car.
- **Cameras**: when a car passes a camera junction it is detected with `detectProb` (default 0.9).
- **Camera mistakes (sliders)**:
  - OCR error rate (default 15%): substitute 1 character using the confusion pairs 0↔D, 8↔B, 5↔S, 2↔Z, 6↔G, 7↔T, 4↔A;
    confidence drawn lower (0.45–0.75) when an error occurs, higher (0.85–0.99) when correct.
  - Partial read rate (default 5%): 2–3 characters replaced by `?`.
  - Miss rate = 1 − detectProb.
- Sightings go to a **sightings log**. The tracker may only read the log (never `Car.route` or `trueCarId`).

## 6. Our method (the tracker)

### 6.1 Linking sightings of the selected car
The operator selects a car (click on map or search plate). Starting from its first sighting, for each later sighting S:
- Candidate only if plate is close: **folded** edit distance ≤ 1 (fold confusion pairs first), or partial plate agreeing on known slots.
- Time–space check: at least one road route from previous camera to S's camera with travel time compatible with Δt
  (`0.7·Δt ≤ T_route ≤ 1.8·Δt` using free speeds); otherwise reject ("impossible travel").
- Score = sum of log-likelihood terms: plate (by confidence and distance), travel-time fit, type, colour.
  Link the best candidate above threshold; show the rejected look-alikes and **why**.
- **Naive mode** (comparison): exact plate string match only. Misreads break the chain — show it.

### 6.2 Route inference between two linked sightings A(t1) → B(t2)
1. Enumerate up to **K = 40** loop-free paths A→B with Yen's k-shortest paths on travel time, limited to `T ≤ 1.8·Δt`.
2. Score each path:
   - travel-time fit: `exp(-(T_path − Δt)² / (2σ²))`, σ = 0.25·Δt
   - **negative evidence**: for each camera on the path (excluding A, B) that did *not* see the car in the window, multiply by `(1 − detectProb)`
   - mild prior for shorter paths: `exp(−0.1 · extraKm)`
3. Normalise to probabilities. Keep paths with prob ≥ 1%.
4. **Uncertainty**: effective number of routes = `exp(entropy)` of the path distribution. Also report raw count of feasible paths.

### 6.3 "Where could it be now?"
Between sightings (and after the last one): highlight all edges reachable from the last camera within elapsed time, minus edges
that would have forced passing a camera that hasn't seen it. Grows as time passes, collapses at the next sighting.

### 6.4 Best next camera (suggestion)
For the current set of ambiguous segments (all tracked cars, or a batch of 200 sampled trips):
for each candidate junction without a camera, compute expected entropy after adding it (split each segment's paths into
"passes this junction" vs "doesn't", weighted by their probability mass). Suggest the junction with the largest total
entropy reduction; show it pulsing on the map with "+X% certainty". Button: **Add suggested camera**.

## 7. Metrics panel (live)

| Metric | Definition |
|---|---|
| Cameras | count; % of junctions covered |
| Avg possible routes | mean effective routes per segment over last N tracked segments |
| Route accuracy | share of the true route's road length covered by the top-1 hypothesis (after reveal / batch eval) |
| True route rank | position of the true path in the ranked list (1 = best) |
| Link accuracy | correct links / all links, ours vs naive |

**Batch evaluation** button: simulate 200 random trips, compute the metrics above for (a) current cameras,
(b) the same number placed randomly, (c) the same number placed by the greedy suggestion. Chart: *avg possible routes vs
number of cameras* for random vs smart placement (recompute for 5, 10, 15, 20, 25 cameras).

## 8. UI layout

- **Left panel — controls:** map mode (Grid / Koramangala), seed, play/pause, speed, number of cars, camera-count slider with
  "Random" / "Smart" auto-placement, OCR error slider, miss-rate slider, look-alike toggle, Naive vs Our-method toggle.
- **Centre — map:** deck.gl over an optional MapLibre basemap (OpenFreeMap, no key) or plain dark background.
  Roads (thin grey), cameras (icons; tap any junction to add/remove), cars (small dots, coloured by vehicle colour),
  selected car highlighted. Route hypotheses drawn with opacity ∝ probability; best route bold; reachable cloud as a soft
  overlay; suggested camera pulsing.
- **Right panel — tracked car:** plate, type, colour; sighting timeline (camera, time, read plate, confidence, ✓ linked /
  ✗ rejected look-alike + reason); for each segment the ranked route list with probabilities; **Reveal true route** button
  (true route drawn in green dashed).
- **Bottom strip:** metrics + the random-vs-smart chart.

## 9. Build order for tonight — solo, one person + Claude Code

Built **grid-first**: every phase ends with something you could show if you had to stop there. Koramangala comes after the core
works, so a slow OpenStreetMap download can never block the demo. One Claude Code prompt per phase; test in the browser and
`git commit` after each.

| Phase | Time | Done when | If you stop here you can show |
|---|---|---|---|
| 1. Grid city + cars + cameras | ~1 h | Vite app runs; 8×8 grid renders; ~150 cars move; tapping a junction toggles a camera; sightings log fills with misreads | Cars, cameras, imperfect detections |
| 2. Tracker (the core idea) | ~1.5 h | Select a car → linked sightings with reasons; possible routes drawn with probabilities and a route count; Reveal true route | **The full message on a grid** |
| 3. Koramangala map | ~45 min | `scripts/export_osm.py` produces the JSON; map toggle switches to real roads; everything from phases 1–2 works there | The message on a real city |
| 4. Suggestion + metrics | ~1 h | Live metrics panel; best-next-camera suggestion with "Add" button; random vs smart chart | Why placement matters, with numbers |
| 5. Presets + rehearsal | ~45 min | Presets 1, 2 and 4 from section 10 load in one click; demo run through twice | A smooth 5-minute demo |

Total ~5 h of building. Take a 10-minute break after phase 2.

**Solo time savers**
- If `osmnx` fails to install or download within 15 minutes, skip phase 3 and present on the grid — the method is the same.
- No basemap tiles; draw roads from the JSON on a dark background (fewer things to break offline).
- Don't hand-polish UI until phase 5; use plain panels until then.
- Ask Claude Code for small unit tests only for route inference and plate folding — those are the parts that must be right.

**Cut list if behind** (in this order): random-vs-smart chart → reachable cloud (6.3) → naive comparison mode → Koramangala map.
Never cut: tap-to-add cameras, possible-routes display with count, reveal true route.

## 10. Demo presets (seeded)

1. **"Two cameras"** — Koramangala, 2 cameras far apart: track a car → 20+ possible routes, top-1 wrong. Message: sparse = blind.
2. **"Add the right camera"** — accept the suggestion → routes collapse to 2–3, true route now rank 1.
3. **"Random vs smart"** — same camera count, random vs smart placement side by side in the chart.
4. **"Misread plate"** — OCR error at a middle camera: naive mode loses the car, our method links it and shows why.
5. **"Look-alike"** — a same-colour, near-identical plate car nearby is rejected for impossible travel time.

## 11. Honesty notes for the presentation

- This is a **simulation of the method**, not the full ANPR system. Car movement, camera errors and road speeds are modelled.
- Error rates are configurable assumptions, not measured accuracy.
- The same tracker logic (linking + route inference + suggestion) is what the real system would run on real sightings.
