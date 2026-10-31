# 07 · Running the project

## 1. Prerequisites

| Need | Version used when writing these docs | Required for |
|---|---|---|
| Node.js | v20.20.2 | Everything except the map export |
| npm | 10.8.2 | Installing and running scripts |
| A modern browser with **WebGL** | Chrome / Edge / Firefox | The map (deck.gl draws with WebGL) |
| Python 3 + `osmnx` 2.x | Python 3.10.12, osmnx 2.0.7 | **Only** re-exporting the Koramangala road data |

You do **not** need Python, an internet connection, a database or a server for normal use. The road data and the saved batch result are in `public/data/`.

## 2. Install and start

```bash
cd TRAJEX
npm install          # installs React, deck.gl, Vite, Vitest, tsx, TypeScript
npm run dev          # starts the dev server
```

Open the address that Vite prints (normally `http://localhost:5173`). We started the dev server on a test port and checked that the page, `data/koramangala.json` (671 351 bytes) and `data/precomputed.json` (1 603 bytes) are served with HTTP 200.

The first screen shows the Grid city with 8 random cameras and the clock running. Click a preset on the left to load a scenario, or press **▶ Demo (guided)**.

## 3. Every npm script

All scripts are defined in `package.json`.

| Command | What it runs | What it does | Time |
|---|---|---|---|
| `npm run dev` | `vite` | Development server with hot reload at port 5173. | instant |
| `npm run build` | `tsc --noEmit && vite build` | Type-checks all of `src`, `tests`, `scripts/*.ts`, `vite.config.ts` (strict mode), then writes the production site to `dist/`. | seconds |
| `npm run preview` | `vite preview` | Serves `dist/` locally (default port 4173) to test the production build. | instant |
| `npm test` | `vitest run` | Runs the 38 unit tests in `tests/`. | about 1 s |
| `npm run rehearse` | `tsx scripts/rehearse.ts` | Headless check of all six presets; see section 5. | about 4 minutes |
| `npm run batch [grid\|kor] [trips]` | `tsx scripts/batch.ts` | Runs `runBatch()` on a map (default `grid`, 200 trips, seed 2026, no starting cameras, detection 0.9) and prints the chart table and the metrics. | about 8 s for the grid; minutes for `kor` |
| `npm run precompute` | `tsx scripts/precompute.ts` | Runs the slow Koramangala batch for every preset that needs one (preset 3) and **overwrites** `public/data/precomputed.json`. | a few minutes |
| `npm run find-presets [digits] [seeds]` | `tsx scripts/find_presets.ts` | Searches seeds, cars and camera pairs for scenarios that show a preset's message. `digits` chooses which (`12` = presets 1–2, `4`, `5`; default `12`); `seeds` is comma-separated (default `2026,7,11,42,101`). | varies |
| `npm run export-osm` | `.venv/bin/python scripts/export_osm.py` | Downloads and rebuilds `public/data/koramangala.json`; see section 7. | many minutes |

Pass arguments to an npm script after `--`, for example `npm run batch -- kor 100`.

## 4. Tests

```bash
npm test
```

Real output of the last run:

```text
 ✓ tests/plates.test.ts (6 tests)
 ✓ tests/eval.test.ts (6 tests)
 ✓ tests/routes.test.ts (8 tests)
 ✓ tests/failure.test.ts (4 tests)
 ✓ tests/suggest.test.ts (5 tests)
 ✓ tests/demo.test.ts (5 tests)
 ✓ tests/engine.test.ts (4 tests)

 Test Files  7 passed (7)
      Tests  38 passed (38)
```

What they cover:

| File | Tests |
|---|---|
| `tests/plates.test.ts` | folding of each confusion pair; folded distance; accept ≤ 1, reject 2; partial plates must agree on known slots; simulated OCR substitution folds back to the truth; look-alikes differ by the requested number of characters. |
| `tests/routes.test.ts` | time-fit shape; negative evidence multiplies by `(1 − p)`; longer routes mildly penalised; normalise and effective routes; two equal routes → 50/50 and effective 2; a silent camera moves probability to the other route; impossible times → no route; Yen's paths are distinct, loop-free and non-decreasing in time. |
| `tests/suggest.test.ts` | entropy before/after for a splitting camera, shared camera, perfect camera, blind camera; `bestCamera` picks a splitting junction and ignores existing cameras; greedy picks are distinct; adding a camera replays old traffic and is deterministic. |
| `tests/eval.test.ts` | `camerasSaved`: interpolation, exact point, exact-N point, no extrapolation, no saving, empty and noisy charts. |
| `tests/engine.test.ts` | grid has 64 junctions and is strongly connected; results do not depend on step size; different seeds differ; misreads and partial reads occur. |
| `tests/failure.test.ts` | offline camera gives no sightings and restoring gives the identical log; `cameraList()` vs `allCameras()`; stepping respects offline; `bestCamera` excludes failed junctions. |
| `tests/demo.test.ts` | captions use the given facts; falls back to preset text; keyboard helper; batch signature ignores camera order. |

## 5. Rehearsal

```bash
npm run rehearse
```

`scripts/rehearse.ts` loads the Koramangala map and, for each preset in `PRESETS`:

1. builds the scenario **twice** with `buildEngine()` and checks the two runs produce identical results (determinism);
2. checks the claim of that preset;
3. at the end prints the six demo captions and checks the precomputed file.

Real output of the last run (abbreviated; every line was `PASS`):

```text
Preset 1: Two cameras
   PASS  two runs are identical (deterministic)
   PASS  2 linked sightings (n293>n73)
   PASS  20+ possible routes (feasible 40, effective 23.22)
   PASS  top-1 route is wrong (true route rank 7)

Preset 2: Add the right camera
   PASS  before: 23.22 routes, true rank 7
   PASS  after adding n231: n293>n231>n73
   PASS  routes collapse to 2.05 and 3.99 effective
   PASS  true route is rank #1 on every piece (1,1)

Preset 3: Random vs smart
   PASS  smart < random at every count [[5,31.56,25.86],[10,30.14,22.19],[15,28.67,19.66],[20,27.27,17.04],[25,25.75,16.34]]
   INFO  cameras saved: {"status":"beyond","n":10,"maxTested":25}
   PASS  same count (10): smart 22.19 < random 30.14

Preset 4: Misread plate
   PASS  ours links all 3 (n481>n52>n601)
   PASS  naive loses the middle one (n481>n601)

Preset 5: Look-alike
   PASS  look-alike rejected: car7: impossible travel: fastest route from n221 needs 369 s, only
   PASS  no look-alike sighting was linked

Preset 6: Camera failure
   PASS  with n231 down the car is linked only through the other cameras (n293>n73)
   PASS  offline camera produces 0 sightings (healthy one produces some)
   PASS  routes rise from 2.05 and 3.99 (healthy) to 23.22 (camera down)
   PASS  replacement n455 is not the failed junction n231
   PASS  adding n455 lowers routes 23.22 -> 21.07

ALL PRESET CHECKS PASSED
```

The command exits with code 0 when all checks pass and 1 otherwise. The set variable `TRIPS` changes the number of batch trips (`TRIPS=50 npm run rehearse`); the precomputed-file check always uses 200 trips, and the "smart < random" check can fail on a very small number of trips because the results become noisy.

## 6. Precompute

```bash
npm run precompute
```

Runs `runBatch()` with 200 trips for preset 3 on Koramangala and writes `public/data/precomputed.json` (progress prints on stderr, then "preset 3 done in N s" and "wrote public/data/precomputed.json"). **Run it again whenever** you change `eval.ts`, `suggest.ts`, `routes.ts`, the map data, or preset 3's seed, cameras or miss rate. Then run `npm run rehearse` to confirm "precomputed.json has a valid entry for preset 3". Details: [05-camera-placement-and-evaluation.md](05-camera-placement-and-evaluation.md), section 6.

## 7. Re-exporting the map with `scripts/export_osm.py`

You only need this to refresh or change the road data.

```bash
python3 -m venv .venv
.venv/bin/pip install osmnx          # osmnx 2.x (also installs networkx, geopandas, pandas, numpy)
npm run export-osm
```

What it does: downloads the OpenStreetMap drive network inside west 77.612, south 12.922, east 77.640, north 12.948; merges junctions within 15 m; keeps the largest strongly connected part; assigns speeds; writes `public/data/koramangala.json`. It retries up to 8 times across three public Overpass servers (waits of 5 s growing to 60 s). The download can take around ten minutes if the public servers are busy. The `cache/` folder next to `src/` holds osmnx's downloaded responses.

**Warning.** Node and edge ids (`n293`, `n231`, `e297`…) are numbered by the export. A new export from newer OpenStreetMap data can change the numbering and the layout. The presets use fixed junction ids and fixed cars, so after a re-export you must re-find the scenarios (`npm run find-presets`), update `src/ui/presets.ts`, run `npm run precompute` and `npm run rehearse`.

On Windows the path `.venv/bin/python` in `package.json` is different (`.venv\Scripts\python.exe`); run the Python script directly.

## 8. Production build for a demo

```bash
npm run build        # type-check + bundle into dist/
npm run preview      # serve dist/ at http://localhost:4173
```

- The build output is `dist/index.html`, `dist/assets/*.js` and `.css`, and a copy of `dist/data/*.json`. The main script is about 1.07 MB (deck.gl is large) and there is no code splitting.
- The app loads its data with `fetch()`, so it must be served over HTTP. Opening `dist/index.html` directly from the file system does not work.
- `vite.config.ts` has no `base` setting, so the site expects to be at the root of its host (`/`). To deploy in a sub-folder, set `base` in `vite.config.ts` and rebuild (the app already builds data URLs from `import.meta.env.BASE_URL`).
- For a stage demo: run `npm run build && npm run preview` on the presentation laptop, open `http://localhost:4173/?preset=1`, and keep the browser zoom at 100 %. No internet is needed.

## 9. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `npm run dev` prints a different port | 5173 is busy; Vite takes the next one. Use the printed address. |
| Map area is blank or black but panels work | WebGL is disabled or not available (for example software rendering in a remote or headless browser). Enable hardware acceleration in the browser, or use another browser. |
| "Could not load map: …" | `public/data/koramangala.json` was not found or not served (wrong base path, opened from `file://`). Serve over HTTP from the project root. The app falls back to the grid. |
| Preset 3 caption: "No saved batch results found" | `public/data/precomputed.json` is missing or its signature does not match the preset. Run `npm run precompute`. |
| Preset 3 starts a long live batch | The saved entry did not match, so a live run started (outside the demo). Wait, or run `npm run precompute` and reload. |
| Batch seems frozen | It yields to the browser every ~40 ms but takes minutes on Koramangala; watch the progress label on the button. |
| Sightings look different after moving a slider | Expected: noise sliders rebuild the log for the same traffic. |
| A failed camera comes back after moving the Count slider or pressing Random/Smart | These replace the camera set (see the observations in [10-viva-questions-and-limitations.md](10-viva-questions-and-limitations.md)). Fail the camera again after changing the count. |
| `npm run rehearse` takes minutes | It runs the Koramangala batch twice (determinism check). Set `TRIPS=50` for a quick smoke test. |
| `npm run export-osm`: "OpenStreetMap download failed" | Public Overpass servers were busy for all 8 attempts. Run it again later. |
| `npm run export-osm`: `.venv/bin/python: No such file` | Create the virtual environment first (section 7). |
| Type errors in `npm run build` | `tsc --noEmit` is strict. Fix the reported lines; tests and scripts are type-checked too. |
| Different numbers than in these docs | Different seed, car count, noise settings or camera set. Presets reproduce the documented numbers exactly because they fix all of those. |
