import { describe, expect, it } from 'vitest';
import { captionFor, demoKey, batchSig, type Facts } from '../src/ui/demoFacts';
import { PRESETS } from '../src/ui/presets';

const p = (id: number) => PRESETS.find(x => x.id === id)!;

describe('demo captions come from computed numbers', () => {
  it('preset 1 uses the facts it is given', () => {
    const a = captionFor({ id: 1, cams: 3, raw: 37, eff: 12.4, rank: 5 } as Facts, p(1));
    const b = captionFor({ id: 1, raw: 52, eff: 31, rank: 1 } as Facts, p(1));
    expect(a).toContain('3 cameras'); expect(a).toContain('37'); expect(a).toContain('12'); expect(a).toContain('#5'); expect(a).toContain('wrong');
    expect(b).toContain('52'); expect(b).toContain('right'); expect(b).not.toContain('37');
  });
  it('preset 3 reflects the saved batch, including the beyond-range case', () => {
    const f = { id: 3, batch: { n: 10, smart: 22.19, random: 30.14, saved: { status: 'beyond', n: 10, maxTested: 25 } } } as Facts;
    const c = captionFor(f, p(3));
    expect(c).toContain('22'); expect(c).toContain('30'); expect(c).toContain('25');
    expect(captionFor({ id: 3, batch: { ...f.batch!, saved: { status: 'ok', n: 10, m: 14.5, saved: 4.5 } } } as Facts, p(3))).toContain('14.5');
  });
  it('falls back to the preset text when facts are missing', () => {
    expect(captionFor(null, p(2))).toBe(p(2).says);
  });
});

describe('demo keys and signatures', () => {
  it('right = next, left = back, clamped; escape exits', () => {
    expect(demoKey('ArrowRight', 0, 5)).toEqual({ step: 1 });
    expect(demoKey('ArrowRight', 4, 5)).toEqual({ step: 4 });
    expect(demoKey('ArrowLeft', 0, 5)).toEqual({ step: 0 });
    expect(demoKey('Escape', 2, 5)).toEqual({ step: 2, exit: true });
    expect(demoKey('a', 2, 5)).toBeNull();
  });
  it('batch signature ignores camera order but not the scenario', () => {
    expect(batchSig('m', 1, ['b', 'a'], 0.1, 200)).toBe(batchSig('m', 1, ['a', 'b'], 0.1, 200));
    expect(batchSig('m', 1, ['a'], 0.1, 200)).not.toBe(batchSig('m', 2, ['a'], 0.1, 200));
  });
});
