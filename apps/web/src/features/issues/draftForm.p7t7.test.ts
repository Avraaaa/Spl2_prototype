import { describe, expect, it } from 'vitest';
import { blankDraft, draftFromIssue } from './draftForm';
import type { components } from '../../api/generated/schema';

describe('acceptance criteria draft state', () => {
  it('starts empty and restores saved criteria when editing', () => {
    expect(blankDraft().acceptance_criteria).toBe('');
    const issue = {
      title: 'Request',
      description: 'Details',
      acceptance_criteria: 'Verifier can reproduce the result',
      request_type: 'SUPPORT',
      product: 1,
      module: null,
      priority: 'MEDIUM',
      environment: '',
      steps_to_reproduce: '',
      expected_result: '',
      actual_result: '',
      related_request: null,
      recurring_of: 42,
    } as components['schemas']['Issue'];
    expect(draftFromIssue(issue).acceptance_criteria).toBe('Verifier can reproduce the result');
    expect(draftFromIssue(issue).recurring_of).toBe(42);
  });
});
