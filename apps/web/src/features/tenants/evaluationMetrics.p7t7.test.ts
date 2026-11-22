import { describe, expect, it } from 'vitest';
import { evaluationMetric } from './evaluationMetrics';

describe('suggestion evaluation metrics', () => {
  it('normalizes generated dictionary payloads for readable display', () => {
    expect(evaluationMetric({ total: 4, accepted: 3, rejected: 1, acceptance_rate: 0.75 })).toEqual({
      total: 4,
      accepted: 3,
      rejected: 1,
      acceptance_rate: 0.75,
    });
  });

  it('uses safe defaults for incomplete metrics', () => {
    expect(evaluationMetric({ accepted: 'three' })).toEqual({
      total: 0,
      accepted: 0,
      rejected: 0,
      acceptance_rate: 0,
    });
  });
});
