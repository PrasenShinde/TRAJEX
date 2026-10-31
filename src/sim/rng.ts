/** Seeded deterministic randomness. Same seed -> same everything. */
export type Rng = () => number;

export function mulberry32(seed: number): Rng {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Mix integers into a uint32 hash. */
export function hashInt(...n: number[]): number {
  let h = 0x9e3779b9;
  for (const x of n) {
    h ^= (x | 0) + 0x7f4a7c15 + (h << 6) + (h >>> 2);
    h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
    h ^= h >>> 13;
    h = Math.imul(h, 0xc2b2ae35);
    h ^= h >>> 16;
  }
  return h >>> 0;
}

export const hash01 = (...n: number[]) => hashInt(...n) / 4294967296;
export const rngFrom = (...n: number[]): Rng => mulberry32(hashInt(...n));

export const randInt = (r: Rng, lo: number, hi: number) => lo + Math.floor(r() * (hi - lo + 1));
export const pick = <T,>(r: Rng, a: readonly T[]): T => a[Math.floor(r() * a.length)];
export const range = (r: Rng, lo: number, hi: number) => lo + r() * (hi - lo);
