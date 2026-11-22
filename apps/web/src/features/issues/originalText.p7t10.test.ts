import { describe, expect, it } from 'vitest';
import { originalTextAction, canRequestOriginalText } from './originalText';

describe('original text access flow', () => {
  it('requires a deliberate confirmation before the component can request original text, and supports cancel and hide', () => {
    expect(originalTextAction('hidden', 'show')).toBe('confirm');
    expect(originalTextAction('confirm', 'cancel')).toBe('hidden');
    expect(originalTextAction('confirm', 'hide')).toBe('confirm');
    expect(originalTextAction('confirm', 'reveal')).toBe('revealed');
    expect(originalTextAction('revealed', 'hide')).toBe('hidden');
    expect(canRequestOriginalText('hidden')).toBe(false);
    expect(canRequestOriginalText('confirm')).toBe(true);
    expect(canRequestOriginalText('revealed')).toBe(false);
  });
});
