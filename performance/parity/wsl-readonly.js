import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 3,
  duration: '60s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<800'],
    checks: ['rate>0.99'],
  },
};

const base = __ENV.LITE_BASE_URL || 'http://127.0.0.1:8443';
const paths = ['/api/lite/recovery/summary', '/api/lite/fleet'];

export default function () {
  for (const path of paths) {
    const response = http.get(`${base}${path}`, { tags: { parity: 'read-only-wsl' } });
    check(response, { [`${path} responds`]: (r) => r.status >= 200 && r.status < 500 });
    sleep(0.5);
  }
}
