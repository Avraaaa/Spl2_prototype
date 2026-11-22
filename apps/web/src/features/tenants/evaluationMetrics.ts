export type EvaluationMetric = {
  total: number;
  accepted: number;
  rejected: number;
  acceptance_rate: number;
};

export function evaluationMetric(value: Record<string, unknown>): EvaluationMetric {
  const numberAt = (key: keyof EvaluationMetric) => {
    const candidate = value[key];
    return typeof candidate === 'number' && Number.isFinite(candidate) ? candidate : 0;
  };
  return {
    total: numberAt('total'),
    accepted: numberAt('accepted'),
    rejected: numberAt('rejected'),
    acceptance_rate: numberAt('acceptance_rate'),
  };
}
