export type AuditSummary = {
  status: 'ok' | 'broken';
  recordsChecked: number | null;
  firstBrokenRecordId: number | string | null;
  firstBrokenRecordTime: string | null;
  organizations: { code: string; valid: boolean; recordsChecked: number | null; firstInvalidSequence: number | null; firstBrokenRecordId: number | string | null; firstBrokenRecordTime: string | null }[];
};

type UnknownRecord = Record<string, unknown>;

export function auditSummary(value: unknown): AuditSummary {
  const result = (value && typeof value === 'object' ? value : {}) as UnknownRecord;
  const organizations = (result.organizations && typeof result.organizations === 'object' ? result.organizations : {}) as UnknownRecord;
  const rows = Object.entries(organizations).map(([code, raw]) => {
    const organization = (raw && typeof raw === 'object' ? raw : {}) as UnknownRecord;
    const sequence = Number(organization.first_invalid_sequence);
    const recordsChecked = Number(organization.records_checked);
    const firstBrokenRecordId = organization.first_invalid_record_id;
    return {
      code,
      valid: organization.valid === true,
      recordsChecked: Number.isFinite(recordsChecked) && recordsChecked >= 0 ? recordsChecked : null,
      firstInvalidSequence: Number.isFinite(sequence) && sequence > 0 ? sequence : null,
      firstBrokenRecordId: typeof firstBrokenRecordId === 'number' || typeof firstBrokenRecordId === 'string' ? firstBrokenRecordId : null,
      firstBrokenRecordTime: typeof organization.first_invalid_record_time === 'string' ? organization.first_invalid_record_time : null,
    };
  });
  const aggregateChecked = Number(result.records_checked);
  const broken = rows.find(row => !row.valid);
  return {
    status: result.valid === true ? 'ok' : 'broken',
    recordsChecked: Number.isFinite(aggregateChecked) && aggregateChecked >= 0 ? aggregateChecked : rows.every(row => row.recordsChecked !== null) ? rows.reduce((total, row) => total + (row.recordsChecked ?? 0), 0) : null,
    firstBrokenRecordId: broken?.firstBrokenRecordId ?? null,
    firstBrokenRecordTime: broken?.firstBrokenRecordTime ?? null,
    organizations: rows,
  };
}

export function topicRepresentativeRows(values: UnknownRecord[], topicTerms: string[] = []) {
  return values.map((value, index) => ({
    reference: String(value.reference ?? value.issue_reference ?? value.title ?? `Representative ${index + 1}`),
    snippet: String(value.snippet ?? value.title ?? value.text ?? 'No representative text available.'),
    topTerms: Array.isArray(value.top_terms) ? value.top_terms.map(String) : topicTerms,
  }));
}

export async function addTopicLabelRetrySafe<TLabel>(
  name: string,
  findLabel: (name: string) => Promise<TLabel | null>,
  createLabel: (name: string) => Promise<TLabel>,
  acceptTopic: () => Promise<void>,
) {
  const existing = await findLabel(name);
  if (!existing) await createLabel(name);
  await acceptTopic();
}
