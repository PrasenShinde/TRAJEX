import { describe, expect, it } from 'vitest';
import { camerasSaved } from '../src/track/eval';

const chart = [5, 10, 15, 20, 25].map((c, i) => ({ cameras: c, random: [40, 30, 24, 20, 18][i] }));

describe('cameras saved (interpolated from the random curve)', () => {
  it('interpolates linearly between camera counts', () => {
    const r = camerasSaved(chart, 8, 27, 33);
    // random: 30 @10, 24 @15 -> 27 is halfway => 12.5
    expect(r.status).toBe('ok');
    if (r.status === 'ok') { expect(r.m).toBeCloseTo(12.5); expect(r.saved).toBeCloseTo(4.5); }
  });
  it('hits a tested point exactly', () => {
    const r = camerasSaved(chart, 8, 24, 33);
    expect(r.status === 'ok' && r.m).toBeCloseTo(15);
  });
  it('uses the exact-N point when N is between chart counts', () => {
    const r = camerasSaved(chart, 7, 36, 35); // random@7 = 35 (better than the straight line), smart 36 -> match at < 7? no saving
    expect(r.status).toBe('none');
  });
  it('does not extrapolate past the largest tested count', () => {
    const r = camerasSaved(chart, 10, 10, 30);
    expect(r).toEqual({ status: 'beyond', n: 10, maxTested: 25 });
  });
  it('reports no saving when smart is not better than random at the same count', () => {
    expect(camerasSaved(chart, 10, 31, 30).status).toBe('none');
  });
  it('handles an empty chart and noisy non-monotone curves (first crossing wins)', () => {
    expect(camerasSaved([], 5, 10).status).toBe('none');
    const noisy = [{ cameras: 5, random: 40 }, { cameras: 10, random: 20 }, { cameras: 15, random: 25 }, { cameras: 20, random: 18 }];
    const r = camerasSaved(noisy, 5, 22, 40);
    expect(r.status === 'ok' && r.m).toBeCloseTo(5 + (40 - 22) / 20 * 5);
  });
});
