import { describe, expect, it } from 'vitest';
import { fold, foldedDistance, generatePlate, levenshtein, matchPlate, mutatePlate, ocrSubstitute, partialRead } from '../src/sim/plates';
import { mulberry32 } from '../src/sim/rng';

describe('plate folding', () => {
  it('folds each confusion pair to the same string', () => {
    for (const [a, b] of [['0', 'D'], ['8', 'B'], ['5', 'S'], ['2', 'Z'], ['6', 'G'], ['7', 'T'], ['4', 'A']])
      expect(fold(`KA01${a}X1234`)).toBe(fold(`KA01${b}X1234`));
  });
  it('folded distance ignores confusion substitutions but counts others', () => {
    expect(foldedDistance('KA01AB1234', 'KA01AB1234')).toBe(0);
    expect(foldedDistance('KA01AB1234', 'KA01A81234')).toBe(0); // B<->8
    expect(foldedDistance('KA01AB1234', 'KA01AB1235')).toBe(1);
    expect(foldedDistance('KA01AB1234', 'KA01CD1234')).toBe(2);
    expect(levenshtein('abc', 'abd')).toBe(1);
  });
  it('accepts distance <= 1 and rejects 2', () => {
    expect(matchPlate('KA01AB1235', 'KA01AB1234').ok).toBe(true);
    expect(matchPlate('KA01AB1255', 'KA01AB1234').ok).toBe(false);
    expect(matchPlate('KA0DAB1234', 'KA00AB1234').kind).toBe('folded');
    expect(matchPlate(null, 'KA01AB1234').ok).toBe(false);
  });
  it('partial plates must agree on known slots', () => {
    expect(matchPlate('KA01??1234', 'KA01AB1234').ok).toBe(true);
    expect(matchPlate('KA01??1299', 'KA01AB1234').ok).toBe(false);
    expect(matchPlate('KA0D??1234', 'KA00AB1234').ok).toBe(true); // folded
    expect(matchPlate('??????????', 'KA01AB1234').ok).toBe(false); // too little info
  });
  it('simulated OCR substitution on confusable chars folds back to the truth', () => {
    const r = mulberry32(5);
    for (let i = 0; i < 100; i++) {
      const p = generatePlate(r);
      expect(p).toMatch(/^KA\d\d[A-Z]{2}\d{4}$/);
      const read = ocrSubstitute(r, p);
      expect(foldedDistance(read, p)).toBeLessThanOrEqual(1);
      expect(matchPlate(partialRead(r, p), p).dist).toBe(0);
    }
  });
  it('look-alikes differ by the requested number of chars', () => {
    const r = mulberry32(9);
    const p = generatePlate(r);
    expect(levenshtein(mutatePlate(r, p, 1), p)).toBe(1);
    expect(levenshtein(mutatePlate(r, p, 2), p)).toBe(2);
  });
});
