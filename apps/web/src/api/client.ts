import createClient, { type Middleware } from 'openapi-fetch';
import type { paths } from './generated/schema';

/** Read one cookie value by exact name (Django's CSRF cookie is `csrftoken`). */
export function readCookie(name: string, source: string = document.cookie): string | null {
  for (const part of source.split(';')) {
    const [key, ...rest] = part.trim().split('=');
    if (key === name) return decodeURIComponent(rest.join('='));
  }
  return null;
}

const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

interface ClientOptions {
  fetch?: (input: Request) => Promise<Response>;
  getCookie?: (name: string) => string | null;
  baseUrl?: string;
}

/**
 * Typed client generated from contracts/openapi.yaml. Session cookies are sent on every call;
 * unsafe methods carry Django's CSRF token. Authorization is enforced by Django, never here.
 */
export function createApiClient(options: ClientOptions = {}) {
  const getCookie = options.getCookie ?? ((name: string) => readCookie(name));
  const client = createClient<paths>({
    baseUrl: options.baseUrl ?? globalThis.location?.origin ?? 'http://localhost',
    credentials: 'include',
    ...(options.fetch ? { fetch: options.fetch } : {}),
  });
  const csrf: Middleware = {
    onRequest({ request }) {
      if (UNSAFE.has(request.method)) {
        const token = getCookie('csrftoken');
        if (token) request.headers.set('X-CSRFToken', token);
      }
      return request;
    },
  };
  client.use(csrf);
  return client;
}

export const api = createApiClient();
