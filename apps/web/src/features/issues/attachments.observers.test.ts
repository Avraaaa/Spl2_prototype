import { describe, expect, it } from 'vitest';
import { attachmentKind, attachmentServerError, formatFileSize, validateAttachment } from './attachments';

describe('attachment helpers', () => {
  it('accepts supported bank-document formats and rejects unsafe metadata', () => {
    expect(validateAttachment({ name: 'evidence.docx', size: 4096 })).toBeNull();
    expect(validateAttachment({ name: 'transactions.XLSX', size: 8192 })).toBeNull();
    expect(validateAttachment({ name: 'payload.exe', size: 100 })).toContain('allowed types');
    expect(validateAttachment({ name: 'empty.pdf', size: 0 })).toContain('empty');
    expect(validateAttachment({ name: 'large.pdf', size: 10 * 1024 * 1024 + 1 })).toContain('10 MB');
  });

  it('formats sizes and chooses stable file kinds', () => {
    expect(formatFileSize(980)).toBe('980 B');
    expect(formatFileSize(1536)).toBe('1.5 KB');
    expect(formatFileSize(2 * 1024 * 1024)).toBe('2 MB');
    expect(attachmentKind('photo.jpeg')).toBe('image');
    expect(attachmentKind('report.pdf')).toBe('pdf');
    expect(attachmentKind('evidence.docx')).toBe('document');
    expect(attachmentKind('archive.zip')).toBe('archive');
  });

  it('extracts useful field errors from failed uploads', () => {
    expect(attachmentServerError({ file: ['File type is not allowed.'] }, 400)).toBe(
      'File type is not allowed.',
    );
    expect(attachmentServerError({ detail: 'Upload refused.' }, 403)).toBe('Upload refused.');
    expect(attachmentServerError(null, 500)).toBe('Upload failed (500).');
  });
});
