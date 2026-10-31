import { type Rng, pick, randInt } from './rng';

export const RTO_CODES = ['01', '02', '03', '04', '05', '41', '50', '51', '53'];
/** OCR confusion pairs (both directions). */
export const CONFUSION_PAIRS: [string, string][] = [
  ['0', 'D'], ['8', 'B'], ['5', 'S'], ['2', 'Z'], ['6', 'G'], ['7', 'T'], ['4', 'A'],
];
const PARTNER = new Map<string, string>();
for (const [a, b] of CONFUSION_PAIRS) { PARTNER.set(a, b); PARTNER.set(b, a); }
/** Canonical representative (the digit) of each confusion class. */
const FOLD = new Map<string, string>();
for (const [a, b] of CONFUSION_PAIRS) { FOLD.set(a, a); FOLD.set(b, a); }

const LETTERS = 'ABCDEFGHJKLMNPRSTUVWXYZ'; // no I, O, Q
const DIGITS = '0123456789';

export const confusablePartner = (ch: string) => PARTNER.get(ch);

/** Replace every char with its confusion-class representative. */
export function fold(plate: string): string {
  let s = '';
  for (const ch of plate) s += FOLD.get(ch) ?? ch;
  return s;
}

export function generatePlate(r: Rng): string {
  const rto = pick(r, RTO_CODES);
  const l = pick(r, [...LETTERS]) + pick(r, [...LETTERS]);
  const n = String(randInt(r, 1, 9999)).padStart(4, '0');
  return `KA${rto}${l}${n}`;
}

export function formatPlate(p: string): string {
  return p.length === 10 ? `${p.slice(0, 2)} ${p.slice(2, 4)} ${p.slice(4, 6)} ${p.slice(6)}` : p;
}

const isDigitSlot = (i: number) => i >= 2 && i <= 3 || i >= 6;
const isLetterSlot = (i: number) => i >= 4 && i <= 5;

/** Change `n` distinct characters (same character class, different char). Used for look-alikes. */
export function mutatePlate(r: Rng, plate: string, n: number): string {
  const chars = plate.split('');
  const slots = [3, 4, 5, 6, 7, 8, 9]; // keep "KA" and first RTO digit
  const chosen = new Set<number>();
  while (chosen.size < n) chosen.add(pick(r, slots));
  for (const i of chosen) {
    const pool = [...(isLetterSlot(i) ? LETTERS : DIGITS)].filter(c => c !== chars[i]);
    chars[i] = pick(r, pool);
  }
  return chars.join('');
}

/** OCR error: substitute one char via a confusion pair if possible, else another same-class char. */
export function ocrSubstitute(r: Rng, plate: string): string {
  const chars = plate.split('');
  const confusable = chars.map((c, i) => (PARTNER.has(c) && i >= 2 ? i : -1)).filter(i => i >= 0);
  if (confusable.length) {
    const i = pick(r, confusable);
    chars[i] = PARTNER.get(chars[i])!;
  } else {
    const i = pick(r, [3, 4, 5, 6, 7, 8, 9]);
    const pool = [...(isLetterSlot(i) ? LETTERS : DIGITS)].filter(c => c !== chars[i]);
    chars[i] = pick(r, pool);
  }
  return chars.join('');
}

/** Replace 2-3 characters with '?'. */
export function partialRead(r: Rng, plate: string): string {
  const chars = plate.split('');
  const k = randInt(r, 2, 3);
  const idx = new Set<number>();
  while (idx.size < k) idx.add(randInt(r, 0, chars.length - 1));
  for (const i of idx) chars[i] = '?';
  return chars.join('');
}

export function levenshtein(a: string, b: string): number {
  const m = a.length, n = b.length;
  let prev = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++)
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    prev = cur;
  }
  return prev[n];
}

/** Edit distance after folding OCR confusion pairs together. */
export function foldedDistance(a: string, b: string): number {
  return levenshtein(fold(a), fold(b));
}

export type PlateMatch = {
  ok: boolean;
  kind: 'exact' | 'folded' | 'near' | 'partial' | 'none';
  dist: number; // folded edit distance (known slots only for partial)
  known: number; // number of known (non-?) characters for partial
};

export const MIN_PARTIAL_KNOWN = 6;

/**
 * Does a read plate (possibly containing '?') plausibly belong to the reference plate?
 *  - full read: folded edit distance <= maxDist (default 1)
 *  - partial read: known slots must agree after folding (at least MIN_PARTIAL_KNOWN known)
 */
export function matchPlate(read: string | null, ref: string, maxDist = 1): PlateMatch {
  if (!read) return { ok: false, kind: 'none', dist: Infinity, known: 0 };
  if (read.includes('?')) {
    if (read.length !== ref.length) return { ok: false, kind: 'none', dist: Infinity, known: 0 };
    let known = 0, bad = 0;
    for (let i = 0; i < read.length; i++) {
      if (read[i] === '?') continue;
      known++;
      if (fold(read[i]) !== fold(ref[i])) bad++;
    }
    return { ok: bad === 0 && known >= MIN_PARTIAL_KNOWN, kind: 'partial', dist: bad, known };
  }
  if (read === ref) return { ok: true, kind: 'exact', dist: 0, known: read.length };
  const d = foldedDistance(read, ref);
  const kind = d === 0 ? 'folded' : 'near';
  return { ok: d <= maxDist, kind: d <= maxDist ? kind : 'none', dist: d, known: read.length };
}
