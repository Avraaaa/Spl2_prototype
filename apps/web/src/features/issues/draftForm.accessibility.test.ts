import { describe, expect, it } from 'vitest';
import { fieldAccessibility } from './draftForm';

describe('draft field accessibility', () => {
  it('connects invalid controls to their error message', () => {
    expect(fieldAccessibility('title', 'Title is required.')).toEqual({
      'aria-invalid': true,
      'aria-describedby': 'draft-title-error',
    });
  });

  it('does not mark valid controls as invalid', () => {
    expect(fieldAccessibility('title', undefined)).toEqual({
      'aria-invalid': undefined,
      'aria-describedby': undefined,
    });
  });
});
