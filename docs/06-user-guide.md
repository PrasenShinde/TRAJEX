# 06 · User guide

This guide describes every part of the screen, every control, every map marker and colour, the six presets, the guided Demo, the Compare view, and how to fail and restore cameras. Everything here is read from `src/ui/App.tsx`, `MapView.tsx`, `RightPanel.tsx`, `BottomStrip.tsx`, `CompareView.tsx`, `overlays.ts` and `presets.ts`.

## 1. The screen layout

```text
┌──────────────┬───────────────────────────────────────┬──────────────────┐
│              │                                       │                  │
│  LEFT PANEL  │             MAP (centre)              │   RIGHT PANEL    │
│  controls    │  roads, junctions, cars, cameras,     │   tracked car:   │
│  (270 px)    │  routes, overlays, demo caption card  │   timeline,      │
│              │                                       │   routes (360 px)│
│              ├───────────────────────────────────────┴──────────────────┤
│              │  BOTTOM STRIP: live metrics · batch evaluation · chart   │
└──────────────┴──────────────────────────────────────────────────────────┘
```

The page uses the full browser window. A dark theme is used. The bottom strip is 200 px high.

## 2. Left panel (controls)

### 2.1 Demo presets

| Control | What it does |
|---|---|
| **▶ Demo (guided)** | Starts the guided demo at preset 1. When the demo is running the button reads **Exit demo**. See section 6. |
| **1. Two cameras** … **6. Camera failure** | Six preset buttons. Each loads a complete scenario (map, seed, cameras, tracked car, settings). The active preset is highlighted. Hovering shows the one-line message. |
| Preset card | Below the buttons: the preset's title, the sentence to say (`says`) and the instruction of what to click (`steps`). |

Loading a preset: sets the map to Koramangala, applies the settings, **pauses** the clock, turns the "Where now?" haze off, switches to Our method, hides the true route, clears the previous batch, and selects the preset's car (if any).

### 2.2 Map

**Grid city** (8 × 8 test city) or **Koramangala** (real roads). Switching rebuilds the simulation. If the Koramangala file cannot be loaded, the panel shows "Could not load map: …" and returns to the grid. While the other map is loading it shows "Loading …".

### 2.3 Simulation

| Control | Range / default | Effect |
|---|---|---|
| **Play / Pause** | default playing | Starts or stops the clock. Pause keeps the display; you can still click. |
| `t = m:ss` | – | Simulated time since the start (including warm-up). |
| **Speed** | 1×–30×, default 10× | How many simulated seconds pass per real second. |
| **Seed** | any number, default 2026 | Rebuilds the world with a new seed. |
| **Cars** | 20–300 in steps of 10, default 150 | Number of cars. Rebuilds the world. |
| **Look-alike plates (~5 %)** | on | Whether about 5 % of cars become look-alikes of another car. Rebuilds the world. |

### 2.4 Cameras

| Control | Effect |
|---|---|
| **Count** slider | 0 to the smaller of the junction count and 80. Shows the count and % of junctions. Lowering it keeps the first cameras in the list; raising it adds random junctions. |
| **Random** | Replaces all cameras by the same number of random junctions (each press gives a new set). |
| **Smart** | Replaces all cameras by the same number placed by `greedyPlacement()` (hover text: "Greedy: each camera placed where it removes the most route uncertainty"). Shows "Placing cameras greedily…" while working. |
| **Suggest next camera** | Computes the best next junction (`bestCamera()`). A card shows "Suggested: junction nX" and "+N % certainty (expected route-entropy reduction over …)" and a button **Add suggested camera**. If nothing helps: "No junction would reduce uncertainty further." |
| **⇆ Compare random vs smart** | Toggles the Compare view (section 7). |
| Hint | "Click any junction on the map to add / remove a camera." |

### 2.5 Fail a camera

| Control | Effect |
|---|---|
| Drop-down "select camera…" | Lists every camera (offline ones marked "(offline)"). |
| **Simulate camera down** / **Restore camera** | Takes the chosen camera offline, or brings it back. The button is disabled until a camera is chosen. |
| Hint | "…or right-click a camera on the map." The camera is offline for the whole replayed log. |

When you fail a camera the app automatically runs the suggestion, so the card reads "If camera nX were down, best replacement: junction nY".

### 2.6 Camera mistakes

| Slider | Range | Default | Meaning |
|---|---|---|---|
| **OCR error rate** | 0–60 % | 15 % | Chance that a fully-read plate has one wrong character. |
| **Partial read rate** | 0–50 % | 5 % | Chance that 2–3 characters come back as `?`. |
| **Miss rate** | 0–80 % | 10 % | Chance that the camera does not detect the car at all. |

Changing these re-creates the sightings log for the same traffic (no new cars), so the effect on the tracker is visible immediately. (Presets set their own values.)

## 3. The map (centre)

### 3.1 Mouse

| Action | Result |
|---|---|
| Drag | Pan the map. |
| Scroll wheel | Zoom. |
| Click a **junction** | Adds a camera there, or removes the camera that is there. Hover shows "Junction nX / click: add/remove camera". |
| Click a **car** | Tracks that car (right panel fills). Hover shows the car id. |
| **Right-click a camera** | Takes it offline / brings it back (section 8). |

The cursor is a hand ("grab") on empty ground and a pointer when over something clickable.

### 3.2 Markers and colours

| What you see | Meaning |
|---|---|
| Thin grey-blue lines | Roads. Slightly lighter and thicker for `primary`/`trunk` roads. |
| Small dark dots | Junctions (clickable). |
| Small coloured dots | Cars. Colour = the car's colour (white, black, silver, red, blue, yellow, green, grey). |
| **Yellow ring** around a car | The tracked car. |
| **Cyan ring** (translucent fill) | An online camera. |
| **Grey ring with a red outline and a red ✕** | An offline camera. |
| **Pulsing yellow ring** | The suggested junction for a new camera (or best replacement). |
| **Amber lines** | Route hypotheses between linked sightings. Opacity grows with probability; the most likely route is the widest (9 m vs 5 m). |
| **Cyan haze along roads** | "Where could it be now?" (visible when **Where now?** is on and a car is tracked). |
| **Green ring** | A junction where a sighting was **linked** to the tracked car. |
| **Red dot** | A junction where a look-alike sighting was **rejected**. |
| **Green dashed line** | The true route between the first and the last linked sighting (only after **Reveal true route**). |

### 3.3 Floating cards on the map

- The **suggestion card** (top left): "Suggested camera: nX +N % certainty" with **Add suggested camera**.
- The **demo card** (bottom centre) during the guided demo.

## 4. Right panel (tracked car)

| Part | What it shows |
|---|---|
| **Plate search** + **Find** | Type a plate (spaces and case are ignored; look-alike characters are folded, and it matches any car whose plate *contains* the text). Press Enter or **Find**. |
| **Our method / Naive (exact plate)** | Switches the linking mode (section 4 of [04-tracking-method.md](04-tracking-method.md)). |
| Empty hint | "Click a car on the map (or search a plate) to track it." |
| **Car card** | Plate formatted as `KA 03 VY 9255`, type and colour, and a chip "has a look-alike twin" if this car was created as a look-alike. Buttons: **Reveal true route / Hide true route**, **Where now?** (toggles the haze), **Clear** (stop tracking). |
| "No sighting of this plate yet" | Shown if no camera has produced a matching sighting. Add cameras or let time run. |
| **Sighting timeline (N linked)** | One row per candidate sighting: ✓ (green) linked or ✗ (red) rejected; time `m:ss`; camera junction; plate as read; confidence; and the reason text. After Reveal each row adds "· this car" or "· actually carNN". |
| **Possible routes between sightings** | One card per pair of consecutive linked sightings: `A → B (N s)`, chips "N feasible" and "≈ X effective routes", after Reveal "true route rank: k" (green if 1, red otherwise, or "not found"). Then the top 5 routes: `#1 10 % · 162 s · 9 roads` with a bar; "+N more routes" if more. |
| Legend | A summary of the map colours and the number of junctions. |

"Need at least two linked sightings." is shown when there is no segment yet. "Returned to the same camera (route unknowable)." is shown when a segment starts and ends at the same junction.

## 5. Bottom strip

| Block | Content |
|---|---|
| **Live** | **Cameras**: number online (and "(N offline)", and % of junctions). **Avg possible routes**: mean effective routes over the last up to 5 segments of the tracked car ("—" if none). |
| **Tracked car vs truth (after Reveal)** | **Route accuracy** (share of true road length on the top-ranked route), **True route rank** (average, 1 = best), **Link accuracy ours** and **naive** as precision (and recall): precision = correct links ÷ all links; recall = correct links ÷ all real sightings of that car. All show "—" until you press Reveal. |
| **Batch evaluation (200 random trips)** | Button **Run batch evaluation** (becomes **Recompute live (takes minutes)** after a precomputed result, or shows progress while running). A small label says "precomputed" or "computed live". Then the **cameras-saved headline** card with an optional **cost per camera (₹)** box; a table of *current / random / smart* for the current camera count (avg routes, route accuracy, true rank, top-1); and the chart. |
| **Chart** | Average possible routes (vertical) against number of cameras (horizontal, 5–25). Red line = random (mean of 5); light red band = min–max of those 5; green line = smart; dashed cyan vertical line = your current camera count. A footnote says whether the data is precomputed (with its saved date) or computed live. |

## 6. Guided Demo mode

Press **▶ Demo (guided)**. The app loads preset 1 and shows a caption card at the bottom of the map: "Step n / 6 · <title>", the caption, and the buttons **← Back**, **Next →**, **Exit**.

- Keyboard: **→** next, **←** back, **Esc** exit. The keys are ignored while the cursor is in a text box, number box or drop-down.
- Each step loads the corresponding preset (so the left panel, map, right panel and bottom strip all change).
- The caption says "Loading scenario…" for a moment and is then written from numbers computed on the spot by `gatherFacts()` / `captionFor()` (`src/ui/demoFacts.ts`), not typed text. The captions are quoted, with real numbers, in [09-demo-script.md](09-demo-script.md).
- During the demo, preset 3 never starts a live batch; it uses the precomputed file. If that file is missing or does not match, the caption says so.

## 7. Compare view

Press **⇆ Compare random vs smart** (it highlights when on; also `?compare=1` in the URL).

- The centre area splits into two maps. **Left = Random placement**, **right = Smart placement**. Both have the same number of cameras as the main scene, the same seed, same cars, same noise settings, and the same tracked car. Each side has its own engine, running at the chosen speed.
- Each side draws its own route hypotheses and linked-sighting rings, and shows a floating box: "**Random placement** · N cameras", then "this car: avg X effective routes over S segments (K sightings linked)" or "car linked K× — no route segment yet", then "60 sampled trips: avg Y effective routes".
- The **60-trip sample average** is the fairer comparison, because one car may be seen by only one side. It is computed with `evaluatePlacement()` on the same 60 trips for both sides.
- Junction clicks are disabled inside the compare maps (the cameras are fixed). Click a car on either map to track it. Turn off Compare to return to the normal map.
- With 0 cameras it shows "Add some cameras first …". While preparing: "Placing N cameras randomly and smartly…".

## 8. Failing and restoring cameras

1. **Right-click** a camera on the map, **or** pick it in "Fail a camera" and press **Simulate camera down**.
2. It becomes a grey ring with a red ✕. It produces no sightings in the whole replayed log.
3. The best replacement junction is calculated automatically and shown (pulsing yellow ring and card).
4. Press **Add suggested camera** to place a camera there, or right-click the offline camera again (or press **Restore camera**) to bring it back.

Effects you can see: the car may no longer be linked through that camera; the segment around it gets more routes; metrics show "(N offline)". Clicking a junction that holds an offline camera removes it entirely.

## 9. The six presets

All six use the Koramangala map, seed 2026, 150 cars, look-alikes on, 1500 s of warm-up, and Our method. They start paused.

| # | Title | OCR / partial / miss | Cameras | Tracked car | Extras |
|---|---|---|---|---|---|
| 1 | Two cameras | 10 % / 3 % / 10 % | `n293`, `n73` | `car38` | – |
| 2 | Add the right camera | 10 % / 3 % / 10 % | `n293`, `n73` | `car38` | Suggestion runs automatically |
| 3 | Random vs smart | 15 % / 5 % / 10 % | 10 random junctions (seeded) | none | Loads the precomputed batch |
| 4 | Misread plate | 0 % / 0 % / 10 % | `n481`, `n52`, `n601` | `car0` | `n52` has OCR error 100 % |
| 5 | Look-alike | 0 % / 0 % / 0 % | `n221`, `n64`, `n219` | `car6` | – |
| 6 | Camera failure | 10 % / 3 % / 10 % | `n293`, `n73`, `n231` | `car38` | `n231` offline; suggestion runs automatically |

What each one shows and what to do (the numbers are from the real run):

1. **Two cameras.** `car38` has 40 feasible / 23.22 effective routes between the cameras. Press **Reveal true route**: the true route is ranked 7th, so the top guess is wrong.
2. **Add the right camera.** Same scene; the pulsing yellow ring is `n231` (+16 %). Press **Add suggested camera**. Now two segments with 2.05 and 3.99 effective routes. **Reveal true route**: rank 1 on both.
3. **Random vs smart.** Read the headline, table and chart. At 10 cameras: smart 22.2 vs random 30.1 effective routes; the headline says smart beats random even with 25 cameras.
4. **Misread plate.** `car0` (`KA01UG3544`) is linked at all three cameras; the middle one read `KA01UG35A4`. Click **Naive (exact plate)**: only two sightings remain.
5. **Look-alike.** A red ✗ row says "impossible travel: fastest route from n221 needs 369 s, only 48 s elapsed". The red dot on the map is the rejected twin.
6. **Camera failure.** `n231` is a grey ✕. The car can only be linked through `n293` and `n73`; routes jump back to 23.22. The best replacement is `n455` (+16 %). Press **Add suggested camera** to see it only reach 21.07.

## 10. URL parameters (for debugging or direct links)

| Parameter | Effect |
|---|---|
| `?preset=N` | Opens preset N (1–6) at start-up. |
| `?map=kor` | Starts on Koramangala. |
| `?seed=NNNN` | Sets the seed. |
| `?warm=SECONDS` | Sets the warm-up (default 900). |
| `?pause=1` | Starts paused. |
| `?sel=carNN` | Selects a car. |
| `?reveal=1` | Starts with the true route shown. |
| `?compare=1` | Starts in Compare view. |

Example: `http://localhost:5173/?preset=2`.
