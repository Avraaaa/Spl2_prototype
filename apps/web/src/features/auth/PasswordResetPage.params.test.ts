import { describe, expect, it } from 'vitest';
import { readResetParams } from './PasswordResetPage';

describe('password reset URL parameters', () => {
  it('prefers a token in the fragment', () => {
    expect(readResetParams('https://portal.example/reset?uid=abc&token=query#token=fragment')).toEqual({
      uid: 'abc',
      token: 'fragment',
    });
  });

  it('falls back to a token in the query string', () => {
    expect(readResetParams('https://portal.example/reset?uid=abc&token=query')).toEqual({
      uid: 'abc',
      token: 'query',
    });
  });

  it('returns empty values when reset parameters are missing', () => {
    expect(readResetParams('https://portal.example/reset')).toEqual({ uid: '', token: '' });
  });
});
