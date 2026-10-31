# Documentation: Sparse-Camera Vehicle Tracking Simulator

This folder explains the whole project as one finished system: what it is, how it is built, how the maths works, how to run it, how to present it and how to defend it.

## Files

| File | What it contains (one line) |
|---|---|
| [01-project-overview.md](01-project-overview.md) | The problem, the idea, what the simulator demonstrates, the main results, and how it relates to the full SIH 26127 system. |
| [02-system-architecture.md](02-system-architecture.md) | Folder structure, every module, dependency and data-flow diagrams, state management, tech stack. |
| [03-how-the-simulation-works.md](03-how-the-simulation-works.md) | Maps, cars, plates, look-alikes, cameras, mistake models and their defaults, the clock, the seed, and camera add/remove/fail. |
| [04-tracking-method.md](04-tracking-method.md) | The complete tracking method with formulas, rejection reasons, naive mode, routes, probabilities, and a worked example with real numbers. |
| [05-camera-placement-and-evaluation.md](05-camera-placement-and-evaluation.md) | Best-next-camera, smart vs random placement, batch metrics, the 5-seed baseline, cameras saved, camera failure, and the precomputed file. |
| [06-user-guide.md](06-user-guide.md) | Every panel, control, button, key, map marker and colour; the six presets; Demo mode; Compare view; failing cameras. |
| [07-running-the-project.md](07-running-the-project.md) | Prerequisites, install, every npm script, tests, rehearsal, precompute, map export, production build, troubleshooting. |
| [08-code-reference.md](08-code-reference.md) | Every file with purpose, exports, key functions and users, ending with "To change X, edit Y". |
| [09-demo-script.md](09-demo-script.md) | A complete 5–7 minute spoken demo with clicks, what appears, real numbers and what to say. |
| [10-viva-questions-and-limitations.md](10-viva-questions-and-limitations.md) | 42 questions with answers, then limitations, assumptions, observations about the code, and future work. |

## Suggested reading order

1. **Understand the idea:** `01` (10 minutes).
2. **See it running:** `07` (install and start), then `06` (what you are looking at).
3. **Understand the method:** `04`, then `03` (the world it is tested on), then `05` (placement and evaluation).
4. **Understand the code:** `02`, then `08`.
5. **Present it:** `09`.
6. **Defend it:** `10`.

If you have only 30 minutes before a presentation: read `01`, skim `04` section 5.5 (worked example), rehearse `09`, and read the questions in `10`.

## How these documents were checked

- Numbers were produced by running `npm test` (38 tests pass), `npm run rehearse` (all six presets pass), `npm run batch grid`, and small scripts that call the same functions as the interface (`traceTarget`, `inferRoute`, `bestCamera`, `runBatch`, `evaluatePlacement`).
- Numbers from the saved batch result come from `public/data/precomputed.json`.
- Where the code and `SIMULATION_SPEC.md` differ, these documents follow the code.
