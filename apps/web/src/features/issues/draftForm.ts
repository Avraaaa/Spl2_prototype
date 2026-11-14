import type { components } from '../../api/generated/schema';

export type Draft = components['schemas']['IssueWriteRequest'];
type Issue = components['schemas']['Issue'];
export type DraftErrors = Partial<Record<keyof Draft, string>>;

export const blankDraft = (): Draft => ({
  title: '',
  description: '',
  request_type: 'SUPPORT',
  product: null,
  module: null,
  priority: 'MEDIUM',
  environment: '',
  steps_to_reproduce: '',
  expected_result: '',
  actual_result: '',
  related_request: null,
});

/** Initial form values: blank for a new request, the stored values when editing. */
export function draftFromIssue(row: Issue): Draft {
  return {
    title: row.title,
    description: row.description,
    request_type: row.request_type || 'SUPPORT',
    product: row.product,
    module: row.module,
    priority: row.priority || 'MEDIUM',
    environment: row.environment,
    steps_to_reproduce: row.steps_to_reproduce,
    expected_result: row.expected_result,
    actual_result: row.actual_result,
    related_request: row.related_request,
  };
}

export const FIELD_LABEL: Partial<Record<keyof Draft, string>> = {
  title: 'Title',
  description: 'Description',
  product: 'Product',
  environment: 'Environment',
  steps_to_reproduce: 'Steps to reproduce',
  expected_result: 'Expected result',
  actual_result: 'Actual result',
};

/** Fields the server requires before a request can be submitted. */
export function requiredFields(requestType: Draft['request_type']): Array<keyof Draft> {
  const base: Array<keyof Draft> = ['title', 'description', 'product'];
  return requestType === 'BUG' ? [...base, 'environment', 'steps_to_reproduce', 'expected_result', 'actual_result'] : base;
}

const isBlank = (value: unknown) => value === null || value === undefined || String(value).trim() === '';

/** Saving a draft needs a title; submitting needs every required field. */
export function validateDraft(draft: Draft, mode: 'save' | 'submit'): DraftErrors {
  const keys: Array<keyof Draft> = mode === 'save' ? ['title'] : requiredFields(draft.request_type);
  const errors: DraftErrors = {};
  for (const key of keys) {
    if (isBlank(draft[key])) errors[key] = `${FIELD_LABEL[key] ?? key} is required.`;
  }
  return errors;
}

export const hasErrors = (errors: DraftErrors) => Object.values(errors).some(Boolean);

/** Error carrying DRF field messages so the form can show them next to the inputs. */
export class FieldError extends Error {
  fields: DraftErrors;
  constructor(message: string, fields: DraftErrors) {
    super(message);
    this.fields = fields;
  }
}

/** Split a DRF error body into per-field messages and a general message. */
export function parseServerErrors(body: unknown): { fields: DraftErrors; general: string } {
  const fields: DraftErrors = {};
  const general: string[] = [];
  if (body && typeof body === 'object') {
    for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
      const text = Array.isArray(value) ? value.join(' ') : String(value);
      if (key in blankDraft()) fields[key as keyof Draft] = text;
      else general.push(text);
    }
  }
  return { fields, general: general.join(' ') };
}
