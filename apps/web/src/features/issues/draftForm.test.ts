import { describe, expect, it } from 'vitest';
import { blankDraft, draftFromIssue, hasErrors, parseServerErrors, requiredFields, validateDraft } from './draftForm';
import type { components } from '../../api/generated/schema';

describe('draft validation', () => {
  it('requires only a title to save', () => {
    expect(validateDraft(blankDraft(), 'save')).toEqual({ title: 'Title is required.' });
    expect(hasErrors(validateDraft({ ...blankDraft(), title: 'Login fails' }, 'save'))).toBe(false);
  });

  it('requires title, description and product to submit', () => {
    const errors = validateDraft(blankDraft(), 'submit');
    expect(Object.keys(errors).sort()).toEqual(['description', 'product', 'title']);
  });

  it('treats whitespace as blank', () => {
    const errors = validateDraft({ ...blankDraft(), title: '   ', description: ' ', product: 1 }, 'submit');
    expect(Object.keys(errors).sort()).toEqual(['description', 'title']);
  });

  it('requires bug evidence only for BUG requests', () => {
    expect(requiredFields('SUPPORT')).not.toContain('environment');
    expect(requiredFields('BUG')).toEqual(
      expect.arrayContaining(['environment', 'steps_to_reproduce', 'expected_result', 'actual_result']),
    );
    const bug = { ...blankDraft(), request_type: 'BUG' as const, title: 't', description: 'd', product: 2 };
    expect(Object.keys(validateDraft(bug, 'submit'))).toHaveLength(4);
    expect(hasErrors(validateDraft({ ...bug, request_type: 'CHANGE' }, 'submit'))).toBe(false);
  });
});

describe('draft state', () => {
  it('starts blank for new requests and keeps typed values', () => {
    const draft = { ...blankDraft(), title: 'Typed' };
    expect(draft.title).toBe('Typed');
    expect(blankDraft().title).toBe('');
  });

  it('initialises from a stored issue', () => {
    const row = {
      title: 'Stored',
      description: 'Body',
      request_type: 'BUG',
      product: 3,
      module: null,
      priority: '',
      environment: 'prod',
      steps_to_reproduce: 's',
      expected_result: 'e',
      actual_result: 'a',
      related_request: null,
    } as components['schemas']['Issue'];
    const draft = draftFromIssue(row);
    expect(draft.title).toBe('Stored');
    expect(draft.priority).toBe('MEDIUM');
    expect(draft.product).toBe(3);
  });
});

describe('server errors', () => {
  it('maps field errors next to inputs and keeps the rest general', () => {
    const { fields, general } = parseServerErrors({ title: ['Required before submission.'], detail: 'Nope' });
    expect(fields.title).toBe('Required before submission.');
    expect(general).toBe('Nope');
  });
});
