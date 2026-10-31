# 10 · Viva questions, limitations and future work

Part A has 42 questions that a professor or a BEL judge might ask, with short answers based on the code. Part B lists honest limitations and assumptions. Part C lists observations about the current code. Part D lists future work.

All numbers come from the real runs described in the other pages.

---

# Part A · Questions and answers

## A1. The problem and the method

**Q1. What problem does this project solve?**
A city has cameras at only a few junctions. If a car is seen at camera A and later at camera D, many different roads could connect them. The project measures how uncertain that is, reduces the uncertainty with a better tracking method, and advises where to put the next camera. It shows this on a simulator, not on real video.

**Q2. Why not just search for the exact plate number in the database?**
Because plate readers make mistakes. In the simulator, 15 % of reads have one wrong character and 5 % are partial. An exact search loses the car at every misread: in preset 4 it links 2 of 3 sightings, in preset 2 (after adding a camera) it links 2 of 3 because one read is partial. Our method links all of them (`traceTarget()` in `src/track/link.ts`).

**Q3. What is "plate folding"?**
It is a way to treat characters that look alike as equal. The code has seven pairs (0↔D, 8↔B, 5↔S, 2↔Z, 6↔G, 7↔T, 4↔A). `fold()` in `src/sim/plates.ts` replaces each character by one representative, so `KA01UG35A4` and `KA01UG3544` become the same string, and then an edit distance of at most 1 is allowed.

**Q4. Does folding have a risk?**
Yes. Two different cars whose plates differ only by a look-alike pair become identical after folding, so the plate cannot separate them. In that case only travel time, vehicle type and colour can separate them. The simulator's look-alike generator (`mutatePlate`) can produce such a pair, although the preset search only chose twins with folded distance exactly 1.

**Q5. How do you reject a look-alike car that has a very similar plate?**
The plate gate lets the twin through, then the **time-space check** tests whether a route from the previous camera exists with `0.7·Δt ≤ T ≤ 1.8·Δt`. If not, the twin is rejected with the reason text. In preset 5 the twin appears 48 s after our car but the fastest road needs 369 s, so it is rejected for "impossible travel".

**Q6. What if a look-alike could really have reached the camera in time?**
Then it can be linked wrongly. The score uses plate, time fit, type and colour, but nothing else, so a same-type, same-colour car with a near plate that fits the time is a genuine ambiguity. The code says so in the README: "some wrong links remain in busy scenes".

**Q7. Why do you use k-shortest paths instead of all paths?**
The number of loop-free paths between two junctions grows very fast, so listing all of them is impossible. Yen's algorithm (`kPaths()`) gives the best paths in order of travel time, and we stop at 40 paths inside the allowed time window. The remaining ones are less likely anyway because they fit the time less well.

**Q8. Why K = 40, and what happens if the true route is outside the top 40?**
40 is a compromise between accuracy and speed (a limit, not a fitted number). If the true route is not in the list, it gets no probability. The batch metric `foundPct` shows how often the true route was inside the list: 37–45 % of segments for the 10-camera Koramangala placements. That is a real weakness, discussed in Part B.

**Q9. Why the time window 0.7·Δt to 1.8·Δt?**
Cars in the simulator have speed factors from 0.6 to 1.0 and wait 0–20 s at junctions, so a trip can take much longer or somewhat shorter than the model's typical time. The window accepts all routes that are plausible under that variation. It is an assumption taken from the design brief, and it is also the reason very long gaps are rejected ("gap too long for one trip").

**Q10. How is the probability of a route computed?**
Each route gets a score = time fit × negative evidence × length preference × heading penalty. The scores are divided by their sum (`normalise`). Routes below 1 % are dropped and the rest renormalised. The formulas are in section 5.2 of [04-tracking-method.md](04-tracking-method.md).

**Q11. What is "negative evidence"?**
It is the information in a camera that did **not** report the car. If a route passes a camera with detection probability 0.9 and the car was not seen, the route's score is multiplied by `1 − 0.9 = 0.1`. The test `negative evidence multiplies by (1 - detectProb) per silent camera` checks this. It is why adding cameras also removes routes that merely pass them.

**Q12. What does "effective number of routes" mean and why `exp(entropy)`?**
Entropy `H = −Σ p ln p` measures how spread out the probabilities are, and `exp(H)` turns that into a count that is easy to read. Four equal routes give exactly 4; one certain route gives 1; a 90 %/10 % split gives 1.38. We show it next to the plain count of feasible routes (for preset 1: 40 feasible, 23.2 effective).

**Q13. Why σ = 0.25·Δt in the time fit?**
It means a route whose time is 25 % away from the observed time scores 0.61 relative to a perfect match. It is a tolerance chosen by the designers, not a fitted value. If it were smaller, the tracker would be more confident but more often wrong, because real cars vary by more than that.

**Q14. Why a heading penalty, and why 0.15 beyond 60°?**
The first camera records the direction the car was heading. A route that starts in a very different direction is unlikely, but a car can turn at the next junction, so the penalty is a soft factor (0.15), not a rule. The numbers 60° and 0.15 are assumptions. In preset 1, 32 of the 40 candidate routes received this penalty.

**Q15. How does the best-next-camera suggestion work?**
For each junction on a candidate route, the code splits the routes into those that pass the junction and those that do not, and computes the *expected* entropy after the camera reports "seen" or "not seen" (`expectedEntropyAfter`). It suggests the junction with the largest total expected drop (`bestCamera`). In preset 1 it is `n231`: 19 of 36 routes, 55.1 % of the probability, expected gain 16.34 %.

**Q16. Is greedy placement optimal?**
No. Greedy picks the best junction one at a time given the earlier ones, which is fast but does not guarantee the best set. The project does not prove any optimality bound; it shows empirically that greedy beats random at every tested camera count.

**Q17. How do you make sure smart placement is not just memorising the test data?**
`runBatch` chooses the cameras using one set of 200 *training* trips (`seed + 202`) and evaluates all placements on a different set of 200 *test* trips (`seed + 101`).

**Q18. Why is the random baseline the mean of 5 placements?**
A single random placement can be lucky or unlucky. `RANDOM_SEEDS = 5` gives a mean and a min–max band. For 10 cameras the random values range from 27.8 to 31.0, and smart is 22.2, below the whole band.

**Q19. What does "cameras saved" mean and why does it not go past 25?**
It is the number of random cameras needed to match what smart placement achieves with `n` cameras, found by linear interpolation on the measured random curve (`camerasSaved`). The curve was measured only up to 25 cameras, so the code refuses to extrapolate and reports "beats random even with 25 cameras" instead of inventing a number.

**Q20. What is the "Where now?" haze?**
It is the set of roads the car could be on now, given the time since its last sighting: everything reachable within `1.25 × elapsed` seconds from the last camera, without going beyond another camera (`reachableEdges`). In preset 1, 180 s after the last sighting it covers 1160 of the 3230 roads.

**Q21. How are partial plate reads handled?**
A read with `?` characters matches if all its known characters agree with the plate after folding and at least 6 characters are known (`MIN_PARTIAL_KNOWN`). Its plate score is `ln(0.5) + ln(known/10)`. In preset 2 the middle read `KA03?Y9??5` (7 known characters, confidence 0.54) is linked this way.

**Q22. How is a linking decision made, and what is the threshold?**
The score is `plateLL + timeLL + typeLL + colourLL` (all natural logs). A candidate must have `score ≥ −7`. A single vehicle-type mismatch costs ln(0.03/4) = −4.9 and a colour mismatch ln(0.03/7) = −5.5, so one attribute mismatch alone does not reject a sighting (the simulator makes such mistakes 3 % of the time), but both together (−10.3) do.

**Q23. What happens when a camera fails?**
`Engine.failCamera()` marks it offline; the log is rebuilt without it. Every consumer uses `cameraList()` (online only), so it produces no sightings and no negative evidence. In preset 6 the effective routes go from 2.05 and 3.99 back to 23.22, and the suggestion proposes a replacement (`n455`, +16 %), which only brings it to 21.07.

## A2. Mathematics and evaluation

**Q24. How do you evaluate quality? Which metrics?**
In `evaluatePlacement()`: average effective routes per segment (main), average feasible routes, route accuracy (share of the true road length on the top-1 route), mean rank of the true route, % of segments where the true route is found, and top-1 %. In the interface, after Reveal: route accuracy, true-route rank, and link precision and recall (ours and naive).

**Q25. Smart placement only reduced the average from 30 to 22 and top-1 is 4 %. Is that impressive?**
It is a 26 % reduction of uncertainty at the same number of cameras, and smart with 10 cameras beats random with 25. But top-1 is low in both cases and route accuracy is about 65 % for both, so the claim is "less uncertain", not "knows the road". We state this on purpose.

**Q26. Are the compared averages like-for-like?**
Not exactly. The average is per segment, and smart placement creates more segments (275 against 172 for random in the 10-camera run), because more trips pass a camera. Segments without any feasible route are also not counted. Both effects are explained in section 3.6 of [05-camera-placement-and-evaluation.md](05-camera-placement-and-evaluation.md).

**Q27. Is the result repeatable?**
Yes. Everything comes from the seed. `mulberry32` gives repeatable sequences, and `hash01` gives order-independent decisions, so changing the step size does not change the sightings (tested). `npm run rehearse` runs each preset twice and compares the results.

**Q28. How do you know the code is correct?**
38 unit tests check the key maths: folding, route scoring, entropy, Yen's paths (distinct, loop-free, sorted), suggestion extremes, cameras-saved, determinism and camera failure. The rehearsal checks the claims of the six presets against the real code. These are checks of internal consistency, not validation against real data.

## A3. Design choices

**Q29. Why a browser-only application with no backend?**
Simplicity and reliability on a demo laptop: no server, database or network at run time. The road network and the saved batch result are static files in `public/data/`.

**Q30. Why deck.gl and no map tiles?**
deck.gl draws thousands of roads and moving cars with WebGL at a good frame rate. Drawing roads from the JSON on a dark background avoids tile servers, so the demo works offline.

**Q31. Why Koramangala?**
It is a dense, grid-like Bengaluru neighbourhood with many parallel alternative roads, which is exactly where route ambiguity is easy to see. The bounding box is lon 77.612–77.640, lat 12.922–12.948: 1117 junctions and 3230 directed roads.

**Q32. Why does adding a camera "replay" history?**
The engine keeps every car's visits, so `rebuildLog()` can regenerate the sightings for the cameras you have now. A new camera immediately has sightings, which makes what-if demonstrations instant. The price is that "camera down" means "down for the whole log", not "down from now".

**Q33. Why use a precomputed batch? Is that cheating?**
No. The slow batch (minutes on Koramangala) is run beforehand by the same `runBatch()` code (`npm run precompute`) and saved with a signature of the scenario. The interface labels it "precomputed (saved date) — not run live" and offers **Recompute live**. If the signature does not match, the file is ignored.

**Q34. Why does the tracker not see the true route? How do you guarantee it?**
`src/track/*` never imports `engine.ts`. It receives only the sightings list, the graph and the camera list. The hidden `trueCarId` exists in each sighting object, but no function in `src/track/` reads it. The ground-truth functions (`trueNodesBetween`, `trueEdgesBetween`, `sightingsOf`) are used only by the interface after Reveal, by the scripts and by tests.

## A4. Realism and scale

**Q35. How realistic are the traffic and the camera errors?**
Roads are real (OpenStreetMap). Traffic is a model: random trips on shortest paths with perturbed times, speed factors 0.6–1.0, 0–20 s junction waits, no traffic lights, queues, parking or stops. Camera error rates are settings (15 % OCR, 5 % partial, 10 % miss), not measurements. The character confusion pairs are plausible but assumed.

**Q36. The tracker assumes 0.8 of road speed and the cars use 0.6–1.0 of it. Isn't that circular?**
The tracker's model is deliberately not identical to the world: the mean is the same (0.8) but cars vary and wait at junctions, which the tracker's model does not include. Even so, both come from the same simulator, so real accuracy would probably be lower. Real tuning would need real travel-time data.

**Q37. Why is the top-1 route rarely right?**
With few cameras there are many routes with nearly equal time fit, so the probability is spread out, and the real car's timing includes waits the model does not know about (in preset 1 the car lost 45.6 s at junctions). Also, the true route is inside the top-40 list in only 37–45 % of the Koramangala segments.

**Q38. Will it scale to a whole city with thousands of cameras and vehicles?**
It has not been tested beyond 1117 junctions and 300 cars. The cost per segment is a handful of A* searches limited by a time window, so it grows with the size of the neighbourhood between two cameras, not with the whole city (about 28 ms per full-trip inference on Koramangala: 200 trips in 5.6 s). Tracking many targets, millions of sightings per day, and maintaining indexes would need a real database and parallelism.

**Q39. How long do the computations take?**
Opening a preset and tracking a car are instant. The 200-trip batch takes about 8 s on the 8 × 8 grid and a few minutes on Koramangala. Running `npm run rehearse` (which runs the Koramangala batch twice and everything else) took about 4 minutes.

**Q40. Does it track several vehicles at once?**
The tracker follows one selected car at a time (`traceTarget`). The batch evaluation processes 200 trips independently, which is a different question: how uncertain trips are, not how to track many cars simultaneously.

## A5. Link to the real system

**Q41. How would this connect to real ANPR cameras?**
The tracker needs a list of records like `Sighting`: camera junction, time, plate text, confidence, vehicle type, colour and heading. A real ANPR system supplies all of these. The work to do is: map each camera to a road-graph junction, use the same OSM exporter for the road graph, replace the assumed speeds by live or historical travel times, calibrate the plate-confusion pairs and the confidence from real data, and keep the camera clocks synchronised.

**Q42. How would you validate it on real data, and what is not covered?**
Use vehicles with known paths (GPS traces or a controlled test fleet), run the same metrics (true-route rank, top-1, route accuracy, link precision and recall) and compare with the simulator's figures. Not covered: image recognition, lanes and multiple plates in one frame, privacy and legal rules for storing plates, authentication, data volume and retention.

---

# Part B · Limitations and assumptions

## B1. Assumptions (all are settings or constants, not facts about a real city)

| Assumption | Where |
|---|---|
| Typical traffic moves at 80 % of the road speed. | `TYPICAL_SPEED_FACTOR` in `graph.ts` |
| Road speeds by type (20–35 km/h in the city). | `scripts/export_osm.py`, `gridMap.ts` |
| Car speed factor 0.6–1.0, junction wait 0–20 s, route perturbation 0.8–1.4. | `engine.ts` |
| Camera detection 90 %, OCR error 15 %, partial reads 5 %, wrong type/colour 3 % each. | `engine.ts` |
| Seven plate confusion pairs. | `plates.ts` |
| Cameras are at junctions and see every car passing through. | `Engine.maybeSight` |
| Route window 0.7–1.8 × the observed time; K = 40; σ = 0.25·Δt; length preference 0.1 per km; heading penalty 0.15 beyond 60°. | `routes.ts` |
| Link threshold −7; type agreement 97 %; colour agreement 97 %. | `link.ts` |
| The origin and destination of every evaluation trip are observed. | `eval.ts` (`obs = [0, …, last]`) |

## B2. Limitations

1. **It is a simulation of the method.** There is no video, no real ANPR and no real traffic.
2. **Error rates are not measured accuracy.** They are sliders with plausible defaults.
3. **Sparse truth coverage of the top-40 list.** The true route is in the candidate list in only 37–45 % of the Koramangala segments (10 cameras). If it is missing, the tracker cannot rank it.
4. **Top-1 accuracy is low (3–4 % at 10 cameras on Koramangala).** The method reduces uncertainty; it does not identify the road.
5. **The metric averages over segments that have a feasible route.** About 39 % of full-trip inferences (78 of 200 training trips) return no route, and those segments are not counted.
6. **Averages compare different segment sets** (smart placement creates more segments than random).
7. **Long gaps are rejected.** A car that stops, parks or makes several trips between two cameras is not linked (reason "gap too long").
8. **Look-alikes with only a confusable-pair difference cannot be separated by the plate.**
9. **Camera failure is a what-if over the entire log**, not a failure at one moment.
10. **One tracked car at a time.**
11. **The "Where now?" area treats cameras as perfect blockers** (ignores missed detections) and is computed only after the last linked sighting.
12. **Tested only on two maps** (an 8 × 8 grid and 1117 junctions of Koramangala) and up to 300 cars.
13. **No visual verification of every map marker in an automated test.** The tests cover logic; the map drawing relies on manual checking.
14. **The bundle is large (about 1.07 MB main script)**, with no code splitting.
15. **No privacy, security or legal handling.** Plates in the simulator are synthetic.

## B3. Where the code differs from `SIMULATION_SPEC.md`

The code is the reference. Differences noted while reading:

| Spec | Code |
|---|---|
| Optional MapLibre basemap under deck.gl | No basemap; roads drawn from JSON on a dark background. |
| Route scoring: time fit, silent cameras, length preference | Same, plus a **heading penalty** (×0.15 beyond 60°). |
| "Where could it be now?" between sightings and after the last | Only after the last linked sighting. |
| Tracker types without `nodeId`, `offline`, `ocrError` | Sighting has `nodeId`; Camera has `ocrError?` and `offline?`. |
| Batch chart "for 5, 10, 15, 20, 25 cameras", random vs smart | Same, with the random value being the mean of 5 random placements plus a min–max band, and a "cameras saved" headline. |
| The spec lists five presets | The code has six presets; the sixth is camera failure. |

---

# Part C · Observations about the current code

These are things that are unclear or possibly unintended. They were found while documenting. They have **not** been changed.

1. **Biased shuffle for random placement.** In `runBatch()` (`src/track/eval.ts`) the random orders are made with `[...Array(g.N).keys()].sort(() => rnd() - 0.5)`. A random comparator does not give a uniform shuffle in JavaScript, so the "random" baseline might not be a uniformly random choice of junctions. The result is still repeatable.
2. **Failed cameras are silently restored** when the camera count slider moves or Random/Smart is pressed: `App.tsx` calls `engine.setCameras(...)`, which builds new camera records without the `offline` flag, and `camFailed` is then synchronised from the engine.
3. **The Random button is not repeatable** (`rerollCameras()` uses `Math.random()`), unlike everything else.
4. **OCR slider is not the real rate.** Because the partial-read branch is checked first in `maybeSight()`, the real rate of OCR-substituted reads is `ocr × (1 − partialRate)` (14.25 % with the defaults), not the displayed 15 %.
5. **Side effects during render.** `App.tsx` calls `engine.setNoise(...)` and `engine.setDetectProb(...)` in the render body; each can rebuild the log. It works because it only acts when values change.
6. **A displayed batch can go stale.** `batch` is set only by `applyPreset` and `runBatchEval`; after changing cameras or the miss rate, an old (possibly "precomputed") result stays on screen with its old label.
7. **The 30-second "competing sighting" rule** (`traceTarget`) rejects all but the best-scoring candidate within 30 s of the earliest candidate. If a car truly passes two cameras on neighbouring junctions less than 30 s apart, one of two real sightings may be rejected as "competing". (Not tested here; Koramangala roads average about 95 m.)
8. **Segments with no feasible route are dropped from the metrics** (`evaluatePlacement` skips them; `buildModels` skips them), so averages are conditional on a route being found. 78 of 200 training trips give no model.
9. **`greedyPlacement` can return fewer than `k` junctions** if no candidate has a positive gain. `smartPlace()` then sets fewer cameras than the count shown; `runBatch` would evaluate fewer than `c` cameras. `CompareView` pads with random junctions. In a check on the 200 training trips, Koramangala returned the full 25 and 80 requested, and the grid returned all 64 of its junctions, so it did not occur there.
10. **Look-alike generation is unrestricted:** `mutatePlate` can produce a twin that differs only by a confusable pair (folded distance 0); the preset search avoided these.
11. **`cache/` folder** (about 1.1 MB, osmnx HTTP cache) is not listed in `.gitignore`; it is not used at run time.
12. **Type-only circular import:** `presets.ts` imports `MapMode` from `App.tsx` and `App.tsx` imports `presets.ts`. It disappears at build time but is easy to misread.
13. **`.venv/bin/python` in `package.json`** is a Unix path; the `export-osm` script will not run unchanged on Windows.
14. **Documentation numbers in older notes** (for example `PROGRESS.md`, `README.md`) were not all re-checked; the numbers in these docs were re-run from the code.

---

# Part D · Future work

1. **Real data interface.** Read sightings from a file or API in the same schema as `Sighting`; map camera ids to junctions; replace assumed speeds by observed travel times per road and hour of day.
2. **Learn the error model.** Estimate plate confusion pairs, per-camera OCR error and confidence calibration from real ANPR logs, instead of the seven assumed pairs and flat rates.
3. **Better route model.** Include traffic lights, turn penalties and queueing; learn σ and the window from data; replace the fixed K = 40 by a bound that adapts to the gap; raise the share of segments where the true route is inside the list.
4. **Time-varying failure.** Make camera failure start at a chosen moment instead of applying to the whole log.
5. **Joint tracking of many vehicles** and global assignment (a car cannot be at two places) instead of one target at a time.
6. **Better placement.** Compare greedy to other optimisers, include cost and coverage constraints (power, line of sight, budget) and weight junctions by traffic volume.
7. **Uncertainty beyond routes.** Report calibrated probabilities that a link is correct, and evaluate calibration.
8. **Fix the observations in Part C** where the team agrees they are defects, with tests.
9. **Performance:** web workers for the batch, code splitting for the bundle.
10. **Privacy and governance:** access control, audit logs, retention limits for plate data.
