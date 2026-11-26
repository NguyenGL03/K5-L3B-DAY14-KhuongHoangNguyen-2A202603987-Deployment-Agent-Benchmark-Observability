# Deployment Information

## Public URL
https://ai20k-cohort5-lab14.onrender.com

## Platform
Render (Web Service - Docker + Render Key Value / Redis)

## Test Commands

```bash
BASE="https://ai20k-cohort5-lab14.onrender.com"
```

### 1. Health Check (`/health` → 200)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
# Output: 200  ({"status":"ok","environment":"production"})
```

### 2. Readiness Check (`/ready` → 200)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
# Output: 200  ({"ready":true})
```

### 3. Auth Check without API Key (`/ask` → 401)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
# Output: 401
```

### 4. API Test with API Key (`/ask` → 200)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
# Output: 200
```

## Environment Variables Set
- `PORT` (injected automatically by Render)
- `ENVIRONMENT` (`production`)
- `REDIS_URL` (Internal Redis URL from Render Key Value / Redis)
- `AGENT_API_KEY` (set via Render Dashboard, not committed to Git)
- `RATE_LIMIT_PER_MINUTE` (`10`)
- `DAILY_BUDGET_USD` (`10.0`)

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
