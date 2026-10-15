import { describe, it, expect } from 'vitest';
import { zoomPunch } from './ClipPreview';

describe('zoomPunch (kembar dengan punch.py)', () => {
  const titik = [{ t: 2, dur: 1, skala: 1.2 }];
  it('tanpa titik = 1', () => { expect(zoomPunch([], 3)).toBe(1); });
  it('sebelum titik = 1, puncak di tengah', () => {
    expect(zoomPunch(titik, 1.9)).toBe(1);
    expect(zoomPunch(titik, 2.5)).toBeCloseTo(1.2);
  });
  it('naik 0,12 dtk dan turun 0,35 dtk', () => {
    expect(zoomPunch(titik, 2.06)).toBeCloseTo(1.1);
    expect(zoomPunch(titik, 3.175)).toBeCloseTo(1.1);
    expect(zoomPunch(titik, 3.4)).toBe(1);
  });
});
