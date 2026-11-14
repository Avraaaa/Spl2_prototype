import { describe, expect, it } from 'vitest';
import { hasErrors } from './draftForm';

describe('hasErrors', () => {
  it('ignores keys whose message was cleared to undefined', () => {
    expect(hasErrors({ title: undefined })).toBe(false);
  });
  it('counts real messages', () => {
    expect(hasErrors({ title: 'Required' })).toBe(true);
  });
});
