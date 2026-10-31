# Sparse-Camera Vehicle Tracking Simulator

SIH 2026 · PS 26127 (BEL) — a browser-only demo of the *method*: tracking a vehicle across a city with few cameras.

**Idea.** A car is seen at camera A and later at camera D; in between it could have taken many roads.
*Fewer cameras → more possible routes → less certainty.* The tracker combines the road graph, travel time, direction,
"cameras that did **not** see the car", and fuzzy plate matching to narrow the possibilities and keep linking the car even when plates are misread.
The simulator also suggests the best next camera and shows that **where** cameras go matters as much as **how many**.

## Run it

```bash
npm install
npm run dev          # http://localhost:5173  (works offline; road network is bundled)
npm run build        # type-check + production build into dist/
npm test             # unit tests (plate folding, route scoring, k-shortest paths, suggestion, engine)
npm run rehearse     # headless run of all 5 demo presets (twice each) with pass/fail checks (~3 min, includes the 200-trip batch)
```

Everything is deterministic from the **seed** shown in the left panel (same seed → same cars, same demo).
No backend, no database, no basemap tiles: roads are drawn from JSON on a dark background.

Optional — regenerate the Koramangala road data (already included in `public/data/koramangala.json`):

```bash
python3 -m venv .venv && .venv/bin/pip install osmnx     # osmnx 2.x
npm run export-osm                                       # downloads from OpenStreetMap (public Overpass servers can be busy; the script retries)
```

## Using the app

* **Left panel** – demo presets, map (Grid city / Koramangala), play/pause, speed 1–30×, seed, number of cars, look-alike toggle,
  camera count, **Random** / **Smart** placement, **Suggest next camera**, and the camera-mistake sliders (OCR error, partial reads, miss rate).
* **Map** – click any junction to add/remove a camera (cyan ring). Click a car (or search a plate on the right) to track it.
  Amber = route hypotheses (opacity ∝ probability, thickest = best), cyan haze = "where could it be now", green ring = linked sighting,
  red dot = rejected look-alike, green dashed = true route (after **Reveal**), pulsing yellow = suggested camera.
  Adding or removing a camera *replays the same traffic* ("what-if"), so the new camera immediately has sightings.
* **Right panel** – the tracked car, the sighting timeline (✓ linked / ✗ rejected, with the reason), and for each segment the ranked routes
  with probabilities, the number of feasible routes and the *effective* number of routes (`exp(entropy)`). **Our method / Naive** switches
  between fuzzy+travel-time linking and exact plate matching.
* **Bottom strip** – live metrics, and **Run batch evaluation** (200 random trips: current cameras vs the same number placed randomly vs smartly,
  plus a chart of average possible routes vs number of cameras for random vs smart placement; ~10 s on the grid, ~1 min on Koramangala).

## Demo presets (Koramangala, seed 2026)

| # | Preset | What it shows | What to click |
|---|---|---|---|
| 1 | **Two cameras** | Only 2 cameras: the tracked car could have taken 40 feasible routes (≈23 effective) and our top-1 guess is wrong (true route is rank 7). *Sparse = blind.* | Read the routes; press **Reveal true route**. |
| 2 | **Add the right camera** | Same scenario; the suggested camera (junction n231, "+16% certainty") pulses on the map. Adding it collapses the uncertainty to ≈2 and ≈4 effective routes and the true route becomes rank 1 on both pieces. | **Add suggested camera**, then **Reveal true route**. |
| 3 | **Random vs smart** | Same camera count, random vs smart placement: smart is better at every count (e.g. ≈22 vs ≈30 effective routes with 10 cameras; ≈16 vs ≈28 with 25). | Wait for the batch to finish (auto-starts, ~1 min); read the table and chart. |
| 4 | **Misread plate** | The middle camera misreads the plate (`KA01UG3544` read as `KA01UG35A4`). Our method folds look-alike characters (4/A…) and links all 3 sightings; naive exact matching loses the middle one. | Click **Naive (exact plate)** and compare the timelines. |
| 5 | **Look-alike** | A same-type, same-colour car with a one-character-different plate (`KA05YL0047` vs `KA05YE0047`) is seen 48 s after our car — but the fastest route from the previous camera needs 369 s, so it is rejected for *impossible travel*. | Read the red ✗ row in the timeline; the red dot on the map is the twin. |

`npm run rehearse` loads each preset twice and checks these claims and that both runs are identical. The scenarios were found with `npm run find-presets`.

## How it works (short)

* `src/sim/` – deterministic engine: cars follow shortest paths on perturbed travel times (speed factor 0.6–1.0, 0–20 s junction delays), Bengaluru plates
  (`KA DD LL NNNN`), ~5% look-alike plates, cameras with detection probability, OCR misreads (0↔D, 8↔B, 5↔S, 2↔Z, 6↔G, 7↔T, 4↔A), partial reads, misses.
* `src/track/` – the tracker. It only reads the sightings log (never the true routes or hidden car ids).
  `link.ts` (§6.1 linking, rejection reasons, naive mode), `routes.ts` (§6.2 Yen K=40 routes, time fit, negative evidence, entropy),
  `reach.ts` (§6.3 reachable cloud), `suggest.ts` (§6.4 expected-entropy camera suggestion, greedy placement), `eval.ts` (§7 batch evaluation).
* `scripts/` – `export_osm.py` (road data), `rehearse.ts`, `find_presets.ts`, `batch.ts`.

Debug URL parameters: `?preset=N`, `?map=kor`, `?seed=`, `?warm=<sec>`, `?pause=1`, `?sel=<carId>`, `?reveal=1`.

## Honesty notes

* This is a **simulation of the method**, not the full ANPR system. Car movement, camera errors and road speeds are modelled.
* Error rates are configurable assumptions, not measured accuracy. Typical travel time is assumed to be 0.8 × the (city-traffic) road speed.
* Look-alike twins are genuinely confusable: the tracker rejects them only when travel time rules them out, so some wrong links remain in busy scenes.
* The same tracker logic (linking + route inference + suggestion) is what a real system would run on real sightings.
