# 09 · Demo script (5–7 minutes)

A complete spoken demo using the Demo mode and the six presets. Every number below was produced by running the real code (`npm run rehearse`, `npm test`, and extra scripts that call the same functions the interface calls). The presets are fixed (seed 2026, 150 cars, Koramangala), so you will see exactly these numbers.

## Before you start (5 minutes of preparation)

1. `npm run build && npm run preview`, then open `http://localhost:4173/` in a full-screen browser at 100 % zoom. (Or `npm run dev` and `http://localhost:5173/`.)
2. Check the screen: the **Grid city** is shown with moving dots (cars) and some cyan rings (cameras).
3. Run `npm run rehearse` once on the same laptop. It should end with `ALL PRESET CHECKS PASSED`.
4. Make sure `public/data/precomputed.json` exists (step 3 of the demo depends on it).
5. Practise the keys: **→** next step, **←** back, **Esc** exit demo.

Timing plan:

| Time | Part | Preset |
|---|---|---|
| 0:00–0:50 | Opening: the problem | – (default screen) |
| 0:50–1:50 | Sparse cameras are blind | 1 |
| 1:50–2:50 | One good camera | 2 |
| 2:50–3:50 | Where, not only how many | 3 |
| 3:50–4:40 | Misread plate | 4 |
| 4:40–5:30 | Look-alike car | 5 |
| 5:30–6:30 | Camera failure | 6 |
| 6:30–7:00 | Closing and honesty | – |

To make it a 5-minute demo: shorten the opening to 30 s, skip step 5 (look-alike), and cut each remaining step to about 45 s.

---

## 0:00 — Opening (default screen, nothing clicked yet)

**On screen.** The Grid city: 64 grey junctions, small coloured dots moving (cars), cyan rings (8 random cameras). Left panel, map, right panel, bottom strip.

**Say.**
"A city cannot put a camera on every road. Here the dots are cars and the cyan rings are cameras. Imagine we see one car at one camera, and later at another camera. In between, it could have taken many different roads. The fewer cameras we have, the more possible routes, and the less sure we are.

This simulator shows that effect and measures it. It also shows a method that gets more out of the cameras we do have. It does not use real video. It models what a number-plate camera network would report, and runs the tracking method on that list. Let me show you on a real map, Koramangala in Bengaluru."

**Click.** **▶ Demo (guided)** (top of the left panel).

---

## 0:50 — Step 1 of 6: "Two cameras" (preset 1)

**What appears.**
- The map changes to **Koramangala**: 1117 junctions, 3230 road pieces. The clock is paused at `t = 25:00`.
- Two cyan rings: junctions `n293` and `n73`. A yellow ring around the tracked car `car38`.
- Amber lines between the two cameras: many routes.
- Right panel: plate `KA 03 VY 9255`, grey car. Timeline with two green ✓ rows: **19:18 n293** and **22:00 n73**, both read `KA03VY9255`. One route card: **n293 → n73 (162 s)**, chips **40 feasible** and **≈ 23.2 effective routes**, and the top route `#1 10 % · 162 s · 9 roads`.
- Caption card at the bottom of the map: *"With only 2 cameras the tracked car could have taken 40 feasible routes (about 23 effective). Our top guess is wrong — the true route is ranked #7."*

**Say.**
"This is a grey car. Camera n293 saw it at 19:18 and camera n73 saw it again at 22:00, 162 seconds later. There is no camera in between. The tracker finds 40 roads that fit the time. Their probabilities are spread out. The effective number of routes, which is a measure of how undecided we are, is about 23. So with two cameras, we are almost blind between them."

**Click.** **Reveal true route** in the right panel.

**What appears.** A green dashed line on the map. The route card shows a red chip **true route rank: 7**. Bottom strip (second block): *Route accuracy 63 %*, *True route rank 7.0*, link accuracy ours 100 % and naive 100 %.

**Say.**
"The green dashed line is where the car really went. Our best guess was wrong: the real route is only our seventh choice, with a probability of 6 percent. The real route is the fastest road on paper (124 seconds), but the car lost time waiting at junctions and took 162 seconds, so the tracker preferred roads that take about 162 seconds. This is honest: with so little information, no method could be sure."

(Optional, 10 s: click **Where now?** to show the cyan haze. 180 s after the last sighting the car could be on any of 1160 of the 3230 roads.)

**Press** **→** (Next).

---

## 1:50 — Step 2 of 6: "Add the right camera" (preset 2)

**What appears.** The same car and cameras. A **pulsing yellow ring** on junction `n231`, and a card: *"Suggested camera: n231 +16 % certainty"* with **Add suggested camera**. Caption: *"Before: about 23 effective routes, true route ranked #7. Adding the suggested junction n231 (+16% certainty) cuts it to 2.0 and 4.0 effective routes, with the true route at rank 1 and 1."*

**Say.**
"The simulator can also suggest where to add the next camera. For every junction it asks: if there were a camera here, how much would my uncertainty fall on average? Junction n231 lies on 19 of the 36 likely routes, which hold 55 percent of the probability. So it splits the possibilities nearly in half. The expected improvement is 16 percent."

**Click.** **Add suggested camera**.

**What appears.** A cyan ring at `n231`. The timeline now has three green ✓ rows: 19:18 n293, **20:25 n231 (read `KA03?Y9??5`, confidence 0.54)**, 22:00 n73. Two route cards: **n293 → n231 (67 s): 8 feasible, ≈ 2.0 effective** and **n231 → n73 (95 s): 11 feasible, ≈ 4.0 effective**. Bottom strip *Avg possible routes* shows **3.0**.

**Say.**
"With one extra camera, 23 effective routes become 2 and 4. Notice the middle sighting. The camera only read part of the plate: question marks for three characters, with confidence 0.54. Our method still links it, because the characters it did read agree with our plate. This partial read is also why the naive method will lose this sighting."

**Click.** **Reveal true route**.

**What appears.** Both chips turn green: **true route rank: 1**. Bottom strip: *Route accuracy 100 %*, *True route rank 1.0*, *Link accuracy ours 100 % (recall 100 %)*, *naive 100 % (recall 67 %)*.

**Say.**
"Now the real route is our first choice on both pieces, and our method links all three sightings while the naive exact-match method finds only two. One well-placed camera did more than any amount of guessing."

**Press** **→**.

---

## 2:50 — Step 3 of 6: "Random vs smart" (preset 3)

**What appears.** Ten cyan rings spread around the map; no car is tracked. The bottom strip fills in **instantly** (it loads the precomputed batch, labelled *precomputed … not run live*):

- Headline: *"Smart placement with 10 cameras beats random even with 25 cameras (more than 15 saved; not extrapolated)"*.
- Table for 10 cameras:

| placement | avg routes | route acc. | true rank | top-1 |
|---|---|---|---|---|
| current | 30.0 | 66 % | 26.9 | 3 % |
| random | 30.1 | 65 % | 26.6 | 4 % |
| smart | 22.2 | 65 % | 19.8 | 4 % |

- Chart: the red line (random, mean of 5 random placements) goes from 31.6 at 5 cameras to 25.7 at 25; the green line (smart) from 25.9 to 16.3.
- Caption: *"With 10 cameras, smart placement averages 22 effective routes against 30 for random. Random placement does not match it even with 25 cameras."*

**Say.**
"This is the key result. We simulated 200 random trips across Koramangala. Take 10 cameras. If you put them at random, the average trip stays about 30 routes uncertain. If you place them with our method, it is about 22. The red line is the average of five random placements, and the pale band shows the best and worst of those five. The green line, our placement, is below the band at every camera count. In fact, 10 smart cameras do better than 25 random ones. So the question is not only how many cameras, but where.

I want to be fair: the route accuracy is about 65 percent for all three. We do not claim to know the exact road. We claim to reduce how uncertain we are. And the smart cameras were chosen on one set of 200 trips and tested on a different set."

**Optional, 20 s.** Click **⇆ Compare random vs smart**. After a few seconds the map splits. Each side shows a floating box. The line *"60 sampled trips: avg … effective routes"* reads **29.1** (random) and **21.9** (smart). Click **⇆ Compare** again to close.

**Say.** "Same cars, same number of cameras. On the left the cameras are random, on the right they are placed by the tracker. Over the same 60 trips: 29 against 22."

**Press** **→**.

---

## 3:50 — Step 4 of 6: "Misread plate" (preset 4)

**What appears.** Three cameras (`n481`, `n52`, `n601`), tracked car `car0` (a black SUV, `KA 01 UG 3544`). Timeline with three green ✓ rows: **2:11 n481** (`KA01UG3544`, 0.96), **3:55 n52** (`KA01UG35A4`, **0.49**), **5:51 n601** (`KA01UG3544`, 0.88). Caption: *"The car was seen 3 times. Our method linked 3 of them; naive exact matching linked only 2, because a misread plate breaks its chain."*

**Say.**
"Cameras make mistakes. The middle camera read this plate as KA01UG35A4 instead of 3544: the last-but-one character, a 4, was read as the letter A. These two are on our list of look-alike characters. Our method treats 4 and A as the same when it compares plates, then checks that the travel time makes sense. So it links all three sightings, with a lower confidence of 0.49 for the middle one."

**Click.** **Naive (exact plate)** in the right panel.

**What appears.** The middle row disappears; the timeline shows only the first and last sightings.

**Say.** "A plain exact-match search loses the car at the misread. Then it cannot say anything about the road between the first and last cameras."

(Click **Our method** again if you want to keep the view clean.) Press **→**.

---

## 4:40 — Step 5 of 6: "Look-alike" (preset 5)

**What appears.** Three cameras (`n221`, `n64`, `n219`), tracked car `car6` (a blue bike, `KA 05 YE 0047`). Timeline: **✓ 1:41 n221**, **✗ 2:29 n64** (`KA05YL0047`, 0.86), **✓ 5:04 n219**, **✗ 22:03 n64** (`KA06YE0047`). A red dot on the map at `n64`. Caption: *"A look-alike plate was rejected (“impossible travel”), leaving 0 wrong links in the tracked car’s chain."*

**Say.**
"Here is a trap. Another blue bike with the plate KA05YL0047, only one letter different, passes camera n64 just 48 seconds after our bike was seen at n221. The plate is close enough to match. But the fastest road from n221 to n64 takes 369 seconds. So the car could not have been the same car. The tracker says: *impossible travel: fastest route from n221 needs 369 s, only 48 s elapsed*, and rejects it. The red dot is that twin. The last red row is another plate, KA06YE0047, seen 17 minutes later: the reason is 'gap too long'."

**Press** **→**.

---

## 5:30 — Step 6 of 6: "Camera failure" (preset 6)

**What appears.** The same car as in step 1, but three cameras, and the middle one, `n231`, is shown as a **grey ring with a red ✕**. Only two sightings are linked (19:18 and 22:00). A yellow pulsing ring at `n455` and a card: *"If camera n231 were down — replacement: n455 +16 % certainty"*. Caption: *"If camera n231 were down, the effective routes would rise from 2.0 and 4.0 to 23, and the car could no longer be linked through it. The best replacement junction is n455 (+16% certainty), which would bring it to 21."*

**Say.**
"Cameras fail. This is the same scenario as step 2, but the middle camera is offline. The tracker has lost its anchor. The uncertainty jumps back from 2 and 4 effective routes to 23. The simulator also suggests the best replacement junction, n455. Let's try it."

**Click.** **Add suggested camera**.

**What appears.** A new ring at `n455`. The route card now shows **≈ 21.1 effective routes**.

**Say.**
"Only a small improvement: 23 down to 21. A lost, well-placed camera is not easily replaced. That is a useful message for planning: protect the cameras that matter most. You can right-click any camera on the map to take it offline, and right-click again to restore it."

**Press** **Esc** (or **Exit**) to leave the demo.

---

## 6:30 — Closing and honesty (stop at the map)

**Say.**
"To summarise. One: with few cameras, many routes fit, and we can measure that uncertainty. Two: our method handles misread plates and rejects look-alike cars, using plate folding, travel time, direction, and the cameras that did not see the car. Three: where cameras go matters. A well-placed camera is worth more than several random ones.

Please keep in mind what this is. It is a simulation of the tracking method. The roads are real, but the traffic is simulated, and the camera error rates are settings, not measurements of a real ANPR product. In a real system, the number-plate readers would produce the list of sightings, and the same tracker would run on it."

---

## Cheat sheet of numbers

| Item | Value |
|---|---|
| Map | Koramangala: 1117 junctions, 3230 roads |
| Preset 1 | 40 feasible, 23.22 effective; true route rank 7 (6.42 % probability) |
| Preset 2 | `n231` +16 %; after: 2.05 and 3.99 effective; true rank 1 and 1 |
| Preset 3 (10 cameras) | smart 22.19 vs random 30.14 effective routes; random at 25 cameras: 25.75 |
| Preset 3 (compare view, 60 trips) | random 29.1 vs smart 21.9 |
| Preset 4 | 3 sightings; ours links 3, naive links 2; middle read `KA01UG35A4` (conf 0.49) |
| Preset 5 | twin rejected: fastest route 369 s, only 48 s elapsed |
| Preset 6 | with `n231` down: 23.22 effective; replacement `n455` (+16 %) → 21.07 |
| Tests | 38 pass |

## If something goes wrong

| Problem | Fix |
|---|---|
| The map area is black | Browser has no WebGL. Switch browser or enable hardware acceleration. |
| Step 3 says "No saved batch results found" | `public/data/precomputed.json` is missing; run `npm run precompute` beforehand (a few minutes) or press **Run batch evaluation** and wait. |
| A step shows "Loading scenario…" for long | Wait 1–2 s; the caption is computed on the spot. Press **→** then **←** to reload the step. |
| You clicked something and the scene changed | Press **←** then **→** (or click the preset button) to reload the scene exactly. |
