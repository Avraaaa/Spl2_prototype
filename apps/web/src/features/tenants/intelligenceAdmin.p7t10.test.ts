import { describe, expect, it, vi } from 'vitest';
import { auditSummary, topicRepresentativeRows, addTopicLabelRetrySafe } from './intelligenceAdmin';

describe('intelligence admin polish', () => {
  it('formats successful and broken audit results for a panel', () => {
    expect(auditSummary({ valid: true, records_checked: 42, organizations: { NWD: { valid: true, records_checked: 21, first_invalid_sequence: null }, RSD: { valid: true, records_checked: 21, first_invalid_sequence: null } } })).toEqual({ status: 'ok', recordsChecked: 42, firstBrokenRecordId: null, firstBrokenRecordTime: null, organizations: [{ code: 'NWD', valid: true, recordsChecked: 21, firstInvalidSequence: null, firstBrokenRecordId: null, firstBrokenRecordTime: null }, { code: 'RSD', valid: true, recordsChecked: 21, firstInvalidSequence: null, firstBrokenRecordId: null, firstBrokenRecordTime: null }] });
    expect(auditSummary({ valid: false, records_checked: 32, organizations: { NWD: { valid: false, records_checked: 22, first_invalid_sequence: 17, first_invalid_record_id: 503, first_invalid_record_time: '2026-11-22T08:00:00Z' }, RSD: { valid: true, records_checked: 10 } } })).toEqual({ status: 'broken', recordsChecked: 32, firstBrokenRecordId: 503, firstBrokenRecordTime: '2026-11-22T08:00:00Z', organizations: [{ code: 'NWD', valid: false, recordsChecked: 22, firstInvalidSequence: 17, firstBrokenRecordId: 503, firstBrokenRecordTime: '2026-11-22T08:00:00Z' }, { code: 'RSD', valid: true, recordsChecked: 10, firstInvalidSequence: null, firstBrokenRecordId: null, firstBrokenRecordTime: null }] });
  });

  it('turns topic representatives into readable request rows', () => {
    expect(topicRepresentativeRows([{ issue_id: 12, title: 'Login timeout', snippet: 'Masked request excerpt' }], ['login', 'timeout'])).toEqual([
      { reference: 'Login timeout', snippet: 'Masked request excerpt', topTerms: ['login', 'timeout'] },
    ]);
  });

  it('reuses a created label on retry after topic acceptance fails', async () => {
    let label: { id: number } | null = null;
    const findLabel = vi.fn(async () => label);
    const createLabel = vi.fn(async () => { label = { id: 3 }; return label; });
    const acceptTopic = vi.fn().mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce(undefined);
    await expect(addTopicLabelRetrySafe('Network latency', findLabel, createLabel, acceptTopic)).rejects.toThrow('network');
    await addTopicLabelRetrySafe('Network latency', findLabel, createLabel, acceptTopic);
    expect(createLabel).toHaveBeenCalledTimes(1);
    expect(findLabel).toHaveBeenCalledTimes(2);
    expect(acceptTopic).toHaveBeenCalledTimes(2);
  });
});
