/**
 * Phase 10 — /chat/stream load test (local gateway :8000).
 *
 * Usage:
 *   k6 run scripts/load/phase10_chat_stream.js
 *
 * Env:
 *   OOA_API_BASE     default http://127.0.0.1:8000
 *   SUPER_ADMIN_FILE_ID  default 2721 (dev pre-auth via /auth/login)
 *   OOA_JWT          optional — skip login when set
 */
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';
import { QUERIES } from './queries.js';

const BASE_URL = __ENV.OOA_API_BASE || 'http://127.0.0.1:8000';
const FILE_ID = __ENV.SUPER_ADMIN_FILE_ID || '2721';

const streamDuration = new Trend('ooa_chat_stream_duration_ms', true);
const streamErrors = new Counter('ooa_chat_stream_errors');

export const options = {
  scenarios: {
    concurrent_chat: {
      executor: 'constant-vus',
      vus: 10,
      duration: '5m',
    },
  },
  thresholds: {
    ooa_chat_stream_duration_ms: ['p(50)<3000', 'p(95)<8000'],
    ooa_chat_stream_errors: ['count<50'],
    http_req_failed: ['rate<0.01'],
  },
};

export function setup() {
  if (__ENV.OOA_JWT) {
    return { token: __ENV.OOA_JWT };
  }
  const loginRes = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ file_id: FILE_ID }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: 'auth_login' } },
  );
  check(loginRes, {
    'login status 200': (r) => r.status === 200,
    'login has token': (r) => Boolean(r.json('access_token')),
  });
  if (loginRes.status !== 200) {
    throw new Error(`Login failed: ${loginRes.status} ${loginRes.body}`);
  }
  return { token: loginRes.json('access_token') };
}

function parseStream(body) {
  let done = null;
  let errorMessage = null;
  const lines = String(body || '').split('\n');
  for (const line of lines) {
    if (!line.startsWith('data: ')) continue;
    try {
      const payload = JSON.parse(line.slice(6));
      if (payload.type === 'done') done = payload;
      if (payload.type === 'error') errorMessage = payload.message || 'stream error';
    } catch (_) {
      // ignore malformed SSE lines
    }
  }
  return { done, errorMessage };
}

export default function (data) {
  const query = QUERIES[__ITER % QUERIES.length];
  const sessionId = `k6-${__VU}-${__ITER}-${Date.now()}`;
  const headers = {
    Authorization: `Bearer ${data.token}`,
    'Content-Type': 'application/json',
  };
  const payload = JSON.stringify({
    message: query.message,
    session_id: sessionId,
  });

  const started = Date.now();
  const res = http.post(`${BASE_URL}/chat/stream`, payload, {
    headers,
    timeout: '180s',
    tags: { name: 'chat_stream', complexity: query.complexity, query: query.label },
  });
  const elapsed = Date.now() - started;
  streamDuration.add(elapsed);

  const okStatus = check(res, {
    'stream HTTP 200': (r) => r.status === 200,
  });

  const { done, errorMessage } = parseStream(res.body);
  const streamOk = check(null, {
    'stream done event': () => Boolean(done),
    'no stream error event': () => !errorMessage,
  });

  if (!okStatus || !streamOk || errorMessage) {
    streamErrors.add(1);
  }

  sleep(Math.random() * 2 + 1);
}

export function handleSummary(data) {
  const p50 = data.metrics.ooa_chat_stream_duration_ms?.values?.['p(50)'];
  const p95 = data.metrics.ooa_chat_stream_duration_ms?.values?.['p(95)'];
  const errors = data.metrics.ooa_chat_stream_errors?.values?.count || 0;
  return {
    stdout: [
      '',
      '=== Phase 10 k6 summary ===',
      `p50: ${p50 != null ? (p50 / 1000).toFixed(2) + 's' : 'n/a'}`,
      `p95: ${p95 != null ? (p95 / 1000).toFixed(2) + 's' : 'n/a'}`,
      `stream errors: ${errors}`,
      `pass p50<3s: ${p50 != null && p50 < 3000}`,
      `pass p95<8s: ${p95 != null && p95 < 8000}`,
      '',
    ].join('\n'),
    'reports/phase10_k6_summary.json': JSON.stringify(data, null, 2),
  };
}
