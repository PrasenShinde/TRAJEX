import type { MapMode } from './App';
import type { Mode } from '../track/link';

/**
 * Seeded demo presets (spec §10). Scenarios (seed, car, camera junctions) were found with scripts/find_presets.ts
 * and are re-checked by scripts/rehearse.ts.
 */
export type Preset = {
  id: number;
  title: string;
  says: string; // one-line message to say out loud
  steps: string; // what to click
  map: MapMode;
  seed: number;
  nCars: number;
  lookalikes: boolean;
  ocr: number;
  partial: number;
  miss: number;
  warm: number; // seconds of simulated traffic before the demo starts
  cams: string[] | { random: number }; // junction ids, or N random junctions
  camOcr?: Record<string, number>; // per-camera OCR error override
  car: string | null; // car to track
  mode: Mode;
  autoSuggest?: boolean;
  autoBatch?: boolean;
};

const BASE = { map: 'koramangala' as MapMode, seed: 2026, nCars: 150, lookalikes: true, warm: 1500, mode: 'ours' as Mode };

export const PRESETS: Preset[] = [
  {
    ...BASE, id: 1, title: 'Two cameras',
    says: 'Sparse = blind: with only two cameras, the car could have taken 20+ different routes — and our best guess is wrong.',
    steps: 'The car is already tracked. Look at the amber routes and the route count, then press “Reveal true route”.',
    ocr: 0.1, partial: 0.03, miss: 0.1, cams: ['n293', 'n73'], car: 'car38',
  },
  {
    ...BASE, id: 2, title: 'Add the right camera',
    says: 'One well-placed camera collapses the uncertainty: a handful of routes, and the true route is now ranked #1.',
    steps: 'Same car and cameras as preset 1. The suggested camera is pulsing — press “Add suggested camera”, then “Reveal true route”.',
    ocr: 0.1, partial: 0.03, miss: 0.1, cams: ['n293', 'n73'], car: 'car38', autoSuggest: true,
  },
  {
    ...BASE, id: 3, title: 'Random vs smart',
    says: 'Same number of cameras, very different certainty: smart placement beats random at every camera count.',
    steps: 'Runs the batch evaluation (~1 min on Koramangala, progress shown); read the chart and table at the bottom.',
    ocr: 0.15, partial: 0.05, miss: 0.1, cams: { random: 10 }, car: null, autoBatch: true,
  },
  {
    ...BASE, id: 4, title: 'Misread plate',
    says: 'The middle camera misreads the plate. Exact matching loses the car; folding look-alike characters (0/D, 4/A…) keeps it.',
    steps: 'Our method is on: all 3 sightings are linked. Click “Naive (exact plate)” — the middle sighting disappears.',
    ocr: 0, partial: 0, miss: 0.1, cams: ['n481', 'n52', 'n601'], camOcr: { n52: 1 }, car: 'car0',
  },
  {
    ...BASE, id: 5, title: 'Look-alike',
    says: 'A same-colour car with a one-character-different plate is seen — but it could not have got there in time, so it is rejected.',
    steps: 'Read the red ✗ row in the timeline: “impossible travel”. Red dot on the map = the rejected twin.',
    ocr: 0, partial: 0, miss: 0, cams: ['n221', 'n64', 'n219'], car: 'car6',
  },
];
