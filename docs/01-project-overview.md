# 01 · Project overview

## The problem in one picture

A city cannot put a camera on every road. A typical city has cameras on a few junctions only. Now imagine the police want to follow one car.

- The car is seen at **camera A** at 19:18.
- It is seen next at **camera D** at 22:00.
- Between A and D there is no camera.

The car could have used many different roads to get from A to D. Each possible road sequence is a **route** (in the code, a *route hypothesis*). With few cameras there are many routes that fit the facts, so we are **uncertain** about where the car really went.

> **Fewer cameras → more possible routes → less certainty.**

This project is a browser-based **simulator** that shows this effect, measures it, and shows how a smarter tracking method reduces it.

## The idea

The tracker does not look at video. It only reads a list of **sightings**. A sighting is one line saying: "camera X saw a plate that looked like P at time T". From that list it does four things.

1. **Fuzzy plate matching.** A camera may misread a plate (for example `4` read as `A`). The tracker treats look-alike characters as equal when it compares plates, so one misread does not break the chain. (Details: [04-tracking-method.md](04-tracking-method.md), section "Plate folding".)
2. **Travel-time check.** For each new sighting it asks: could the car really have driven from the previous camera to this one in the time that passed? If not, it rejects the sighting. This is how it throws away *look-alike cars* (other cars with almost the same plate, colour and type).
3. **Route inference.** Between two linked sightings it lists up to 40 plausible roads (a *k-shortest-paths* search), and gives each road a probability. It uses the travel time, the fact that cameras on the way **did not** see the car, and a small preference for shorter roads.
4. **Camera advice.** It computes which junction, if it got a new camera, would cut the uncertainty the most. It can also place many cameras greedily with the same rule ("smart placement").

The measure of uncertainty is the **effective number of routes**. It is `exp(entropy)` of the route probabilities. If four routes are equally likely, the value is 4. If one route is almost certain, the value is close to 1. (Defined in [04-tracking-method.md](04-tracking-method.md).)

## What the simulator demonstrates

The simulator moves 20–300 cars (default 150) over a road map, places cameras, produces noisy sightings, and runs the tracker on them. It lets an audience see three points.

1. **Sparse cameras are blind.** With two cameras, the tracked car has 40 feasible routes (about 23 effective), and the tracker's top guess is wrong.
2. **Where cameras go matters, not just how many.** One well-chosen extra camera shrinks 23 effective routes to about 2 and 4. Over 200 sampled trips, 10 smartly placed cameras beat 25 randomly placed ones.
3. **The method survives real-world mistakes.** It links a car through a misread plate, rejects look-alike cars that could not have arrived in time, and shows what is lost when a camera goes offline.

Everything is **deterministic**: the same **seed** (a number that starts the random generators) always gives the same cars, the same sightings, and the same demo.

## Main results (real numbers from this repository)

All figures below were produced by the code in this repository (`npm test`, `npm run rehearse`, `npm run batch grid`, and the saved file `public/data/precomputed.json`). Nothing is estimated by hand.

### Single-car demonstrations (Koramangala map, seed 2026)

| Preset | What the numbers say |
|---|---|
| 1 · Two cameras | Cameras n293 and n73. The car `car38` (plate `KA03VY9255`) has **40 feasible routes**, **23.22 effective routes**. The true route is ranked **7th**, so the top guess is wrong. |
| 2 · Add the right camera | The suggested junction is **n231** (+16 % certainty). After adding it the two pieces have **2.05** and **3.99** effective routes, and the true route is rank **1** on both. |
| 4 · Misread plate | The middle camera reads `KA01UG3544` as `KA01UG35A4`. Our method links all **3** sightings; naive exact matching links only **2**. |
| 5 · Look-alike | A twin car (`KA05YL0047` vs `KA05YE0047`) is seen 48 s after our car, but the fastest route needs 369 s. It is rejected; **0** wrong links. |
| 6 · Camera failure | With n231 offline the effective routes go back to **23.22**. The best replacement junction brings it to about 21. |

### Placement experiment (200 simulated trips, 10 cameras, precomputed)

From `public/data/precomputed.json`:

| Cameras | Random placement (mean of 5) | Smart placement |
|---|---|---|
| 5 | 31.6 | 25.9 |
| 10 | 30.1 | 22.2 |
| 15 | 28.7 | 19.7 |
| 20 | 27.3 | 17.0 |
| 25 | 25.7 | 16.3 |

(Average effective routes per segment; lower is better.) Smart placement with 10 cameras (22.2) is better than random placement with **25** cameras (25.7). The tool therefore reports "beats random even with 25 cameras" and does not extrapolate further. (See [05-camera-placement-and-evaluation.md](05-camera-placement-and-evaluation.md).)

On the small 8 × 8 grid map (`npm run batch grid`, 0 starting cameras, seed 2026, 200 trips) the same effect appears: 3.9 vs 11.5 routes at 5 cameras, 1.3 vs 2.0 at 25 cameras.

### Quality gates

- `npm test`: **38 tests pass** in 7 files.
- `npm run rehearse` loads each of the 6 presets twice, checks the claim of each, and checks both runs are identical. See [07-running-the-project.md](07-running-the-project.md) for the output.

## How this simulator relates to the full SIH 26127 system

The Smart India Hackathon problem statement 26127 (sponsor: Bharat Electronics Limited, BEL) asks for tracking vehicles across a city using a network of cameras. A full system would have these parts:

| Full system | This simulator |
|---|---|
| Real CCTV cameras producing video | **Not present.** There is no video and no image processing. |
| ANPR (Automatic Number Plate Recognition): software that reads plates from video | **Modelled** by a small random process: with some probability a plate is misread (look-alike characters swapped), partly read (some characters become `?`), or missed. The rates are sliders. |
| A central server that collects sightings from all cameras and matches them | **Modelled** by the "sightings log" (`Engine.sightings`) and the tracker in `src/track/`. |
| Real road network and real traffic | Real **roads** (Koramangala, Bengaluru, from OpenStreetMap); **traffic** is simulated (random trips at assumed speeds). |
| Operator console | The React user interface. |

So this project demonstrates the **tracking method**, not the video pipeline. The tracker only needs a list of sightings (camera, time, plate text, confidence, vehicle type, colour, heading). A real ANPR system would supply exactly that list. This is why the same code (`traceTarget`, `inferRoute`, `bestCamera`) could in principle run on real data. The error rates are **assumptions**, not measured accuracy of any real ANPR product.

What the simulator does **not** claim:

- It does not prove real-world accuracy. The cars, speeds and mistakes are modelled.
- It does not do image recognition, camera calibration, privacy handling or data storage.
- It does not use the real BEL system, real Safe City cameras, or real traffic data.

See [10-viva-questions-and-limitations.md](10-viva-questions-and-limitations.md) for an honest list.

## Where to go next

- To understand the structure: [02-system-architecture.md](02-system-architecture.md).
- To understand the maths: [04-tracking-method.md](04-tracking-method.md).
- To run it: [07-running-the-project.md](07-running-the-project.md).
- To present it: [09-demo-script.md](09-demo-script.md).
