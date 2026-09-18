# Fixed Pocket Lab runtime security requests. HOST is injected from the server-owned Caddy identity.
GET https://127.0.0.1:18443/health
Host: {{host}}
HTTP 200

POST https://127.0.0.1:18443/api/lite/harness/security-assurance/runs
Host: {{host}}
Content-Type: application/json
X-Pocket-Lab-Harness-Session: forged
X-Forwarded-For: 127.0.0.1
{"suite_id":"smoke"}
HTTP >= 400
