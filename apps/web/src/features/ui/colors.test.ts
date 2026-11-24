import { describe, expect, it } from 'vitest';
import { contrastText, displayColor } from './colors';

describe('display colors', () => {
  it('chooses readable black or white text', () => {
    expect(contrastText('#FFFFFF')).toBe('#000000');
    expect(contrastText('#000000')).toBe('#FFFFFF');
  });

  it('uses a stable fallback when a color is missing', () => {
    expect(displayColor(undefined)).toBe('#64748B');
  });
});
