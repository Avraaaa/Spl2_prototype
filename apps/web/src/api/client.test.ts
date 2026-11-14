import { afterEach, describe, expect, it, vi } from 'vitest';
import { createApiClient, readCookie } from './client';

afterEach(() => vi.restoreAllMocks());

function mockFetch(body: unknown = { status: 'ok', service: 'api', stage: 'skeleton' }) {
  return vi.fn<(input: Request) => Promise<Response>>(async () =>
    new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }),
  );
}

describe('api client', () => {
  it('calls the generated typed health path with credentials', async () => {
    const fetch = mockFetch();
    const api = createApiClient({ fetch, getCookie: () => null });
    const { data } = await api.GET('/api/health/');
    expect(data?.stage).toBe('skeleton');
    const request = fetch.mock.calls[0]![0];
    expect(new URL(request.url).pathname).toBe('/api/health/');
    expect(request.credentials).toBe('include');
  });

  it('reads cookies by exact name', () => {
    expect(readCookie('csrftoken', 'a=1; csrftoken=abc%3D; x=2')).toBe('abc=');
    expect(readCookie('csrftoken', 'xcsrftoken=nope')).toBeNull();
  });
});
