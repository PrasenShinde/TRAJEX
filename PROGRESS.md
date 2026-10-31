# Progress

## Phase 1 — Grid city + cars + cameras: DONE (with caveat)
Built: Vite/React/TS scaffold; 8×8 grid (300 m blocks, one-way rows 1/6 & cols 2/5, arterials row 3 / col 4);
seeded deterministic engine (`src/sim/engine.ts`: trips on perturbed shortest paths, speedFactor, junction delays,
respawn, Bengaluru plates, ~5% look-alikes, cameras with detectProb, OCR/partial/miss noise, sightings log);
deck.gl map with click-to-toggle cameras; control panel; sightings table.
Verified: `tsc` + `vite build` pass; 4 engine tests pass (determinism independent of step size, misreads occur); dev server served HTTP 200.
Known issues: the Chrome extension was not connected, so the rendered map was NOT visually checked in a browser.

(Phase 1 visual check was later done with headless Chrome screenshots — layout and map render fine.)

## Phase 2 — Tracker: DONE
Built: `src/track/link.ts` (§6.1: folded edit distance ≤1, partial plates agreeing on known slots, time–space feasibility
0.7–1.8Δt, log-likelihood score with plate/time/type/colour, rejected look-alikes with reasons, naive exact-match mode, same-camera revisits),
`src/track/routes.ts` (§6.2: Yen K=40, Gaussian time fit σ=0.25Δt, negative evidence ×(1−detectProb), shorter-path prior, ≥1% filter,
effective routes = exp(entropy), raw count; heading penalty on first edge), `src/track/reach.ts` (§6.3 reachable cloud),
UI: click/search a car, timeline with ✓/✗ + reasons, ranked routes with probabilities, Reveal true route (green dashed) + true-route rank, "Where now?" cloud.
Tests (`npm test`): 18 passing — plate folding/matching (`tests/plates.test.ts`), route scoring/inference/Yen (`tests/routes.test.ts`), engine determinism.
Headless probe (60 cars, 13 cams, 1 h): our method links 92% of true sightings vs 78% for naive; precision 93% (look-alike twins cause the wrong links), naive 100%.
Known issues / notes:
- Travel-time typical speed = free speed × 0.8 (assumed typical traffic factor, `TYPICAL_SPEED_FACTOR`); window rule from the spec rejects very long gaps (car did other trips) — shown as "gap too long".
- Debug URL params: `?seed=&warm=<sec>&pause=1&sel=<carId>&reveal=1`.

## Phase 3 — Koramangala map: DONE
Built: `scripts/export_osm.py` (osmnx 2.0.7 in `.venv`; bbox W77.612 S12.922 E77.640 N12.948; `consolidate_intersections(15)`; largest strongly-connected component;
default speeds primary 35 / secondary 30 / tertiary 25 / residential 20; retries + mirror fallback for the busy Overpass API) →
`public/data/koramangala.json` (1117 junctions, 3230 directed edges, 655 KB, bundled so it runs offline). Map toggle (Grid / Koramangala) in the left panel.
Install took ~2 min, download ~10 min of retries (public Overpass servers were at capacity) — inside the 15-minute budget.
Verified: tracker, reveal, cloud and camera toggling work on the real map (headless screenshot); e.g. a segment with 40 feasible / ≈15 effective routes.
Notes: true-route rank compares node sequences (consolidated graph has parallel edges). Camera slider capped at 80.

## Phase 4 — Suggestion + metrics: DONE
Built: `src/track/suggest.ts` (§6.4: expected route-entropy after adding a camera — "seen / not seen" split weighted by probability mass and detectProb;
`bestCamera`, `greedyPlacement`), UI: "Suggest next camera" (pulsing yellow marker, "+X% certainty", **Add suggested camera**), **Smart** auto-placement;
`src/track/eval.ts` (200 simulated trips; each trip is split at camera detections and each piece inferred; metrics avg effective routes, route accuracy,
true-route rank, top-1 %), batch evaluation (current vs same-count random vs same-count smart + avg-routes-vs-cameras chart for 5/10/15/20/25; smart placement is
learned on one trip set and scored on a different one); bottom strip with live metrics (cameras/%, avg routes over last 5 tracked segments; route accuracy, rank,
link accuracy ours vs naive after Reveal).
Camera/noise changes now **replay the same traffic** ("what-if"): the sightings log is rebuilt from history, so a newly added camera immediately has sightings.
Verified: 23 tests pass; batch on grid (200 trips, ~7 s): smart 3.9 vs random 9.8 routes @5 cameras, 1.25 vs 1.86 @25; on Koramangala (~67 s, UI stays responsive,
progress bar): smart 25.9 vs 31.985 @5, 16.3 vs 28.3 @25.
Notes: Yen sped up with an exact A* heuristic + Lawler's spur rule. Suggestion for a tracked car uses that car's segments, otherwise a sample of trips (80 on Koramangala, 150 on grid).
Cut-list items NOT cut: all of §7 incl. chart was built.

## Phase 5 — Presets + rehearsal: DONE
Built: `src/ui/presets.ts` (presets 1–5, all five), one-click loading (`Demo presets` in the left panel, floating "Add suggested camera" card over the map),
`src/sim/scenario.ts` (shared engine construction used by the app and the scripts), `scripts/find_presets.ts` (scenario search) and `scripts/rehearse.ts`
(loads every preset twice; checks the claim of each + determinism). Rehearsal result: ALL PRESET CHECKS PASSED
(P1: 40 feasible / ≈23 effective routes, true rank 7; P2: n231 → ≈2 and ≈4 effective routes, rank 1/1; P3: smart < random at every count; P4: ours 3 links vs naive 2;
P5: twin rejected for impossible travel, 0 wrong links). UI checked with headless-Chrome screenshots for presets 2, 4, 5.
`README.md` written (how to run, UI guide, what each preset shows, honesty notes).

## Improvement 1 — Cameras saved: DONE (awaiting your test)
Built: `camerasSaved()` in `src/track/eval.ts` (linear interpolation on the random-placement mean curve, using the chart counts plus the exact-N point;
never extrapolates: if random does not match smart within 25 cameras it says "beats random even with 25", and if smart is no better it says 0 saved).
Random baseline is now the **mean of 5 random seeds** per camera count (`RANDOM_SEEDS`); chart has a light min–max band. Metrics strip shows the headline
"Smart placement with N cameras = random with M cameras (saved)" plus an optional "cost per camera (₹)" input (empty by default; total shown only if filled).
Rehearsal (all 5 presets pass; preset 3 now 5-seed mean): smart@10 = 22.2 routes vs random mean 30.1@10 and 25.8@25, so the headline reads
"beats random even with 25 cameras" (>15 saved, not extrapolated). On the grid the interpolated M/saved numbers appear.
Tests: 29 pass (6 new in `tests/eval.test.ts`). Batch is ~2.5× slower (5 random seeds): expect a few minutes on Koramangala.

## Overall status
All 5 phases done; nothing from the cut list was cut. No git commands were run.
Known issues / limitations:
- Not tested on a real GPU/display (headless Chrome with software GL only); expect 60 FPS on a normal laptop but this was not measured.
- Koramangala batch evaluation takes ~1 min (progress bar; UI stays responsive).
- The spec's 0.7–1.8Δt window rejects very long gaps ("gap too long"), so tracking chains break when cameras are sparse and the car makes other trips in between.
- On Koramangala K=40 candidate routes can miss the true route when the gap between sightings is long (shown as "true route rank: not found").
- Presets 1/2/4/5 depend on seed 2026 + 150 cars + look-alikes on; changing those in the UI after loading a preset changes the scenario.
- Bundle is ~1 MB (deck.gl); no code splitting.
