#!/usr/bin/env node
/**
 * End-to-end smoke test of the issue lifecycle through the real HTTP API (sessions + CSRF), using the
 * synthetic users from `node scripts/dev.mjs seed`. Requires Django running (`node scripts/dev.mjs api`).
 *   node scripts/smoke-lifecycle.mjs [baseUrl=http://127.0.0.1:8000]
 * Exits non-zero on the first unexpected response. Synthetic data only.
 */
const BASE = process.argv[2] ?? 'http://127.0.0.1:8000';
const PASSWORD = 'Demo-Pass-2026!'; // synthetic seed password (see seed_demo)

class Session {
  constructor(name) { this.name = name; this.cookies = new Map(); }
  async req(method, path, body) {
    const headers = { Accept: 'application/json' };
    if (this.cookies.size) headers.Cookie = [...this.cookies].map(([k, v]) => `${k}=${v}`).join('; ');
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (method !== 'GET' && this.cookies.has('csrftoken')) headers['X-CSRFToken'] = this.cookies.get('csrftoken');
    const res = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    for (const c of res.headers.getSetCookie?.() ?? []) {
      const [pair] = c.split(';'); const i = pair.indexOf('=');
      this.cookies.set(pair.slice(0, i).trim(), pair.slice(i + 1).trim());
    }
    const text = await res.text();
    let data = null; try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    return { status: res.status, data };
  }
  async login(username) {
    await this.req('GET', '/api/auth/csrf/');
    const r = await this.req('POST', '/api/auth/login/', { username, password: PASSWORD });
    expect(r, 200, `${username} login`);
    return this;
  }
}

let step = 0;
function expect(r, status, what) {
  step += 1;
  const ok = Array.isArray(status) ? status.includes(r.status) : r.status === status;
  const line = `${String(step).padStart(2)}. ${ok ? 'OK  ' : 'FAIL'} ${what} -> ${r.status}`;
  console.log(line);
  if (!ok) { console.error(JSON.stringify(r.data, null, 2).slice(0, 1500)); process.exit(1); }
  return r.data;
}

const officer = await new Session('officer').login('nwd.officer');
const verifier = await new Session('verifier').login('nwd.verifier');
const support = await new Session('support').login('ds.support');
const otherBank = await new Session('other').login('rsd.officer');

const products = expect(await officer.req('GET', '/api/products/'), 200, 'officer lists products');
const product = (products.results ?? products)[0];
const draft = expect(await officer.req('POST', '/api/issues/', {
  title: 'Smoke: fund transfer fails after OTP confirmation',
  description: 'After confirming OTP 482913 the transfer screen shows error E-4012.',
  request_type: 'BUG', priority: 'HIGH', product: product?.id ?? null, module: product?.modules?.[0]?.id ?? null,
  environment: 'UAT, web portal', steps_to_reproduce: '1. Start transfer 2. Confirm OTP',
  expected_result: 'Transfer succeeds', actual_result: 'Error E-4012',
}), 201, 'officer creates BUG draft');
const id = draft.id;
console.log(`    reference ${draft.reference ?? draft.readable_id ?? id}; OTP masked: ${!JSON.stringify(draft).includes('482913')}`);

const get = async (s, who) => expect(await s.req('GET', `/api/issues/${id}/`), 200, `${who} reads issue`);
const act = async (s, action, body, who, status = 200) => {
  const cur = await get(s, who);
  return expect(await s.req('POST', `/api/issues/${id}/${action}/`, { version: cur.version, ...body }), status, `${who} ${action} (from ${cur.status})`);
};

expect(await support.req('GET', `/api/issues/${id}/`), 404, 'DataSoft cannot see a DRAFT');
await act(officer, 'submit', {}, 'officer');
expect(await otherBank.req('GET', `/api/issues/${id}/`), 404, 'other bank cannot read it');
await act(verifier, 'accept', { tentative_delivery_later: true }, 'verifier', 403);
await act(support, 'accept', { tentative_delivery_later: true }, 'support');
const assignees = expect(await support.req('GET', '/api/issues/assignees/'), 200, 'support lists assignees');
const assignee = (assignees.results ?? assignees)[0];
await act(support, 'assign', { assignee: assignee.id }, 'support');
await act(support, 'start', {}, 'support');
await act(support, 'deliver', { delivery_note: 'Fixed OTP callback handling', deployment_details: 'v2.4.1 hotfix' }, 'support');
await act(support, 'close', {}, 'support', [400, 403, 409]); // cannot close before verification
await act(verifier, 'fail-verification', { reason: 'Still fails for joint accounts' }, 'verifier');
await act(support, 'deliver', { delivery_note: 'Joint accounts handled', deployment_details: 'v2.4.2' }, 'support');
await act(verifier, 'verify', {}, 'verifier');
await act(support, 'close', {}, 'support');
await act(officer, 'reopen', { reason: 'Issue returned after month-end batch' }, 'officer');

const stale = await get(officer, 'officer');
expect(await support.req('POST', `/api/issues/${id}/deliver/`, { version: stale.version - 1, delivery_note: 'x', deployment_details: 'y' }), 409, 'stale version is rejected');
const final = await get(officer, 'officer');
console.log(`\nLIFECYCLE OK: final status ${final.status}, ${final.events?.length ?? '?'} timeline events, version ${final.version}`);

// ---- P3/P4 features: comments, notifications, internal tasks, reports, CSV --------------------------
console.log('\n-- collaboration, notifications, reports --');
expect(await officer.req('POST', `/api/issues/${id}/comments/`, { body: 'Bank: still seeing it on joint accounts after OTP 556677.' }), 201, 'officer comments');
expect(await support.req('POST', `/api/issues/${id}/comments/`, { body: 'DataSoft: investigating the month-end batch.' }), 201, 'support comments');
const comments = expect(await officer.req('GET', `/api/issues/${id}/comments/`), 200, 'officer reads comments');
const list = comments.results ?? comments;
console.log(`    ${list.length} comments; OTP masked in comment: ${!JSON.stringify(list).includes('556677')}`);
expect(await otherBank.req('GET', `/api/issues/${id}/comments/`), 404, 'other bank cannot read comments');
expect(await officer.req('GET', '/api/tasks/'), [403, 404], 'bank user cannot see internal tasks');
expect(await support.req('GET', '/api/tasks/'), 200, 'support lists internal tasks');
const unread = expect(await verifier.req('GET', '/api/notifications/unread-count/'), 200, 'verifier unread notifications');
console.log(`    verifier unread notifications: ${unread.count}`);
if (!(unread.count > 0)) { console.error('expected delivery notifications for the verifier'); process.exit(1); }
const summary = expect(await officer.req('GET', '/api/reports/summary/'), 200, 'officer summary report');
const otherSummary = expect(await otherBank.req('GET', '/api/reports/summary/'), 200, 'other bank summary report');
console.log(`    bank A total ${summary.total} (by_bank present: ${'by_bank' in summary && summary.by_bank != null}); bank B total ${otherSummary.total}`);
const csv = await officer.req('GET', '/api/reports/detailed/csv/');
expect(csv, 200, 'officer exports detailed CSV');
if (!String(csv.data).includes('SR-')) { console.error('CSV missing request references'); process.exit(1); }
expect(await support.req('GET', '/api/reports/dashboard/'), 200, 'DataSoft dashboard counts');
console.log('\nALL SMOKE CHECKS OK');
