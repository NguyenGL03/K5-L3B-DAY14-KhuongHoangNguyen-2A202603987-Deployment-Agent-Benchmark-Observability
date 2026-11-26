# Day 14 Lab - Mission Answers

> **Họ và tên:** Khuong Hoang Nguyen  
> **MSSV:** 2A202603987  
> **Lớp:** K5-L3B

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns trong `01-localhost-vs-production/develop/app.py`

1. **Hardcode secrets trong source code (`develop/app.py` dòng 17–18):**
   - `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`
   - `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`
   - *Rủi ro:* Khi push lên GitHub (nhất là repo public), API key và mật khẩu database bị lộ ngay lập tức và tồn tại vĩnh viễn trong git history.
2. **Không có config management, bật debug cứng (`develop/app.py` dòng 21–22, 53):**
   - `DEBUG = True`, `MAX_TOKENS = 500`, `reload=True`.
   - *Rủi ro:* Không thể thay đổi cấu hình giữa các môi trường (`development`, `staging`, `production`) nếu không sửa code; `reload=True` gây tốn tài nguyên và rủi ro treo/khởi động lại bất thường trên production.
3. **Dùng `print()` thay cho structured logging và in trực tiếp secret ra log (`develop/app.py` dòng 33–34, 38):**
   - `print(f"[DEBUG] Got question: {question}")`
   - `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`
   - *Rủi ro:* Log dạng text tự do rất khó parse/lọc trên hệ thống thu thập log (Loki, Datadog, CloudWatch), đồng thời làm lộ API key ra stdout/log file.
4. **Không có health check / readiness endpoint (`develop/app.py` dòng 42–43):**
   - Thiếu hoàn toàn `GET /health` và `GET /ready` (gọi `/health` trả `404 Not Found`).
   - *Rủi ro:* Cloud platform hoặc load balancer không kiểm tra được app còn sống (liveness) hay đã sẵn sàng nhận request (readiness) để tự động restart hoặc điều hướng traffic.
5. **Bind `host="localhost"` và cố định `port=8000` (`develop/app.py` dòng 51–52):**
   - `uvicorn.run("app:app", host="localhost", port=8000, reload=True)`
   - *Rủi ro:* `localhost` (`127.0.0.1`) chỉ nhận kết nối nội bộ từ chính máy/container đó, nên trong Docker hoặc cloud sẽ không truy cập được từ ngoài; `port=8000` cố định không nhận biến môi trường `PORT` do Railway/Render cấp.
6. **Không xử lý graceful shutdown (`SIGTERM` / `lifespan`):**
   - App không bắt `SIGTERM` và không có lifespan shutdown hook. Khi container bị dừng hoặc deploy bản mới, tiến trình bị ngắt đột ngột, dễ cắt ngang request đang xử lý.

---

### Exercise 1.2: Chạy và kiểm tra bản `develop`

Chạy `python app.py` trong `01-localhost-vs-production/develop/` (WSL2 Ubuntu):

```text
$ curl -sS -i -X POST "http://localhost:8000/ask?question=Hello"
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:45:07 GMT
server: uvicorn
content-length: 126
content-type: application/json

{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}

$ curl -sS -i "http://localhost:8000/health"
HTTP/1.1 404 Not Found
date: Thu, 26 Nov 2026 07:45:07 GMT
server: uvicorn
content-length: 22
content-type: application/json

{"detail":"Not Found"}
```

Log quan sát được từ server `develop`:

```text
Starting agent on localhost:8000...
INFO:     127.0.0.1:53918 - "GET / HTTP/1.1" 200 OK
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
[DEBUG] Response: Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.
INFO:     127.0.0.1:53924 - "POST /ask?question=Hello HTTP/1.1" 200 OK
INFO:     127.0.0.1:53940 - "GET /health HTTP/1.1" 404 Not Found
```

**Nhận xét:** Bản `develop` chạy được trên localhost nhưng **không sẵn sàng cho production**: nhận input qua query param thay vì JSON body chuẩn, log làm lộ API key (`sk-hardcoded-fake-key-never-do-this`), không có `/health`, bind `localhost` và bật `reload=True`.

---

### Exercise 1.3: Chạy bản `production` và so sánh Develop vs Production

Chạy `python app.py` trong `01-localhost-vs-production/production/` (sau khi copy `.env.example` → `.env`):

```text
$ curl -sS -i "http://localhost:8000/health"
HTTP/1.1 200 OK
content-type: application/json

{"status":"ok","uptime_seconds":0.7,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T07:45:12.146390+00:00"}

$ curl -sS -i "http://localhost:8000/ready"
HTTP/1.1 200 OK
content-type: application/json

{"ready":true}

$ curl -sS -i -X POST "http://localhost:8000/ask" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 200 OK
content-type: application/json

{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","model":"gpt-4o-mini"}
```

#### Bảng so sánh Develop vs Production

| Feature | Develop (`develop/app.py`) | Production (`production/app.py` + `config.py`) | Tại sao quan trọng? |
| :--- | :--- | :--- | :--- |
| **Config & Secrets** | Hardcode `OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG = True` (`develop/app.py:17-22`) | Đọc từ biến môi trường qua `Settings` (`production/config.py:14-35`), kiểm tra bắt buộc `AGENT_API_KEY` khi `ENVIRONMENT=production` (`config.py:42-43`) | Tránh lộ secret lên Git, thay đổi cấu hình linh hoạt giữa dev/staging/prod mà không sửa code, và fail-fast nếu thiếu config quan trọng. |
| **Host & Port** | Cố định `host="localhost"`, `port=8000`, `reload=True` (`develop/app.py:51-53`) | `host=settings.host` (`0.0.0.0`), `port=settings.port` (từ `PORT`), `reload=settings.debug` (`production/app.py:196-198`, `config.py:17-19`) | `0.0.0.0` cho phép nhận kết nối từ bên ngoài container; đọc `PORT` giúp tương thích với port động do nền tảng cloud cấp; tắt `reload` giúp ổn định và tiết kiệm CPU/RAM. |
| **Health & Readiness** | Không có `/health` và `/ready` (`GET /health` → `404`) | Có `GET /health` (`production/app.py:135-149`) và `GET /ready` trả `503` nếu `not is_ready` (`production/app.py:152-161`) | Platform dựa vào `/health` (liveness) để tự restart container lỗi; load balancer dựa vào `/ready` (readiness) để chỉ route traffic khi app sẵn sàng. |
| **Logging** | Dùng `print("[DEBUG] ...")`, in thẳng `OPENAI_API_KEY` (`develop/app.py:33-38`) | Structured JSON logging (`logging.basicConfig` + `json.dumps` tại `production/app.py:28-32, 49-55, 111-122`), chỉ log metadata (`question_length`, `client_ip`), không log secret | Dễ parse, truy vấn và cảnh báo trên hệ thống log tập trung (Loki, Datadog), đồng thời bảo vệ dữ liệu nhạy cảm. |
| **Shutdown** | Tắt đột ngột, không có signal hay lifespan hook | Dùng `lifespan` đóng/đợi in-flight requests (`production/app.py:39-68`) và đăng ký `signal.signal(signal.SIGTERM, handle_sigterm)` (`production/app.py:180-189`) | Khi rolling deploy hoặc scale down, container nhận `SIGTERM` và hoàn thành request đang xử lý trước khi thoát, tránh trả lỗi 502/504 cho người dùng. |
| **API Contract & CORS** | Nhận `question` qua query param (`POST /ask?question=...`), không có CORS | Nhận JSON body `{"question": "..."}` và trả `422` nếu rỗng (`production/app.py:102-108`), có `CORSMiddleware` giới hạn `allowed_origins` (`production/app.py:77-82`) | Validate input rõ ràng, chuẩn REST JSON và kiểm soát domain frontend được phép gọi API. |

**Ví dụ anti-pattern cụ thể đã được sửa từ `develop` sang `production`:**
- Trong `01-localhost-vs-production/develop/app.py` (dòng 17 và 34), `OPENAI_API_KEY` bị hardcode ngay trong file và in thẳng ra console bằng `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`.
- Sang `01-localhost-vs-production/production/config.py` (dòng 27, 32, 42–43) và `production/app.py` (dòng 111–115), toàn bộ key được chuyển sang đọc từ biến môi trường (`os.getenv`), fail-fast nếu thiếu `AGENT_API_KEY` ở môi trường production, và log chỉ ghi `question_length` và `client_ip` dưới dạng JSON mà không log bất kỳ secret nào.

---

## Part 2: Docker

### Exercise 2.1: Phân tích `02-docker/develop/Dockerfile`

1. **Base image:** `python:3.11` (`FROM python:3.11` — bản Python đầy đủ dựa trên Debian, chứa sẵn Python runtime cùng nhiều công cụ hệ thống và trình biên dịch).
2. **Working directory:** `/app` (`WORKDIR /app`).
3. **Tại sao `COPY 02-docker/develop/requirements.txt .` và `RUN pip install` đứng trước `COPY 02-docker/develop/app.py .`:**  
   Docker build cache từng layer từ trên xuống dưới; khi một layer thay đổi, mọi layer phía sau nó đều bị vô hiệu hóa cache (invalidate) và phải build lại. File `requirements.txt` ít thay đổi hơn mã nguồn `app.py`. Đặt bước `COPY requirements.txt` + `RUN pip install` trước giúp Docker tái sử dụng layer đã cài sẵn thư viện mỗi khi chỉ sửa code ứng dụng, rút ngắn thời gian build rất nhiều.
4. **Sự khác nhau giữa `CMD` và `ENTRYPOINT`:**
   - `CMD` định nghĩa lệnh/tham số mặc định khi container chạy và **dễ dàng bị ghi đè** nếu người dùng truyền lệnh mới vào cuối `docker run <image> <command>`.
   - `ENTRYPOINT` cố định chương trình thực thi chính của container; các tham số truyền thêm ở `docker run` (hoặc khai báo trong `CMD`) sẽ được nối vào làm đối số cho `ENTRYPOINT` thay vì thay thế hoàn toàn.

---

### Exercise 2.2: Build và chạy container `my-agent:develop`

Build từ thư mục gốc repo:

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --name test-agent-develop -p 8000:8000 my-agent:develop
```

Kết quả gọi container (`develop/app.py` nhận `question` qua query parameter):

```text
$ curl -sS -i "http://localhost:8000/health"
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 08:01:21 GMT
server: uvicorn
content-length: 53
content-type: application/json

{"status":"ok","uptime_seconds":2.5,"container":true}

$ curl -sS -i -X POST "http://localhost:8000/ask?question=What%20is%20Docker%3F"
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 08:01:21 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

---

### Exercise 2.3: Multi-stage build & So sánh kích thước image

Phân tích `02-docker/production/Dockerfile`:
- **Stage 1 (`builder` — `FROM python:3.11-slim AS builder`):** Cài đặt build tools (`gcc`, `libpq-dev`), sau đó chạy `pip install --no-cache-dir --user -r requirements.txt` để cài các thư viện vào `/root/.local`. Stage này không được dùng để chạy production.
- **Stage 2 (`runtime` — `FROM python:3.11-slim AS runtime`):** Tạo user non-root `appuser`, dùng `COPY --from=builder /root/.local /home/appuser/.local` để chỉ lấy các Python packages đã cài, copy `main.py` và `utils/mock_llm.py`, thiết lập `HEALTHCHECK` và chạy `uvicorn` với `USER appuser`.
- **Tại sao image nhỏ hơn nhiều:** Toàn bộ `gcc`, `binutils`, `cpp`, `libpq-dev`, file header và dữ liệu trung gian khi build đều nằm lại ở stage `builder` và bị loại bỏ khỏi image cuối (`runtime`).

**Kết quả đo kích thước thực tế bằng `docker images my-agent`:**

```text
IMAGE               ID             DISK USAGE   CONTENT SIZE   EXTRA
my-agent:advanced   a0c55b9d7b0f        240MB         57.4MB
my-agent:develop    79b6c809fdd7       1.67GB          426MB
```

- **Develop (`my-agent:develop`):** `1,667,792,151 bytes` (**1.67 GB** disk usage / ~1,590.5 MiB)
- **Production (`my-agent:advanced`):** `239,815,359 bytes` (**240 MB** disk usage / ~228.7 MiB)
- **Chênh lệch:** Giảm **85.6%** (`(1,667,792,151 - 239,815,359) / 1,667,792,151 = 85.62%`), đạt chuẩn `< 500 MB`.

---

### Exercise 2.4: Docker Compose Stack (`02-docker/production/docker-compose.yml`)

#### Sơ đồ kiến trúc các service

```text
                         network: internal (bridge)
┌────────┐   :80 / :443   ┌─────────┐   :8000 (internal)   ┌─────────┐
│ Client │ ─────────────► │  nginx  │ ───────────────────► │  agent  │
└────────┘  rate limit    └─────────┘    proxy_pass        └────┬────┘
            10 req/s                                            │
            security headers                     ┌──────────────┴──────────────┐
                                                 ▼ :6379                       ▼ :6333
                                          ┌─────────────┐               ┌─────────────┐
                                          │    redis    │               │   qdrant    │
                                          │ (redis_data)│               │(qdrant_data)│
                                          └─────────────┘               └─────────────┘
```

- **4 services khởi chạy:** `redis` (`redis:7-alpine`, cache/rate limit), `qdrant` (`qdrant/qdrant:v1.9.0`, vector DB), `agent` (build target `runtime`, chỉ lắng nghe nội bộ cổng `8000`, `depends_on` `redis` và `qdrant` ở trạng thái `service_healthy`), và `nginx` (`nginx:alpine`, expose cổng `80`/`443`, làm reverse proxy + rate limit `10r/s` + thêm security headers).
- **Giao tiếp nội bộ:** Cùng nằm trong bridge network `internal`, gọi nhau qua service DNS name (`REDIS_URL=redis://redis:6379/0`, `QDRANT_URL=http://qdrant:6333`, `proxy_pass http://agent_backend` trỏ tới `agent:8000`).

#### Kết quả chạy stack và test qua Nginx

```text
$ docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml ps
NAME                       IMAGE                   COMMAND                  SERVICE   CREATED          STATUS                            PORTS
k5-day14-docker-agent-1    k5-day14-docker-agent   "uvicorn main:app --…"   agent     12 seconds ago   Up 1 second (health: starting)    8000/tcp
k5-day14-docker-nginx-1    nginx:alpine            "/docker-entrypoint.…"   nginx     12 seconds ago   Up 1 second                       0.0.0.0:80->80/tcp, [::]:80->80/tcp, 0.0.0.0:443->443/tcp, [::]:443->443/tcp
k5-day14-docker-qdrant-1   qdrant/qdrant:v1.9.0    "./entrypoint.sh"        qdrant    13 seconds ago   Up 11 seconds (healthy)           6333-6334/tcp
k5-day14-docker-redis-1    redis:7-alpine          "docker-entrypoint.s…"   redis     13 seconds ago   Up 11 seconds (healthy)           6379/tcp
```

Test qua cổng 80 của Nginx:

```text
$ curl -sS -i "http://localhost/health"
HTTP/1.1 200 OK
Server: nginx
Date: Thu, 26 Nov 2026 08:02:56 GMT
Content-Type: application/json
Content-Length: 95
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"status":"ok","uptime_seconds":0.4,"version":"2.0.0","timestamp":"2026-11-26T08:02:56.215771"}

$ curl -sS -i -X POST "http://localhost/ask" -H "Content-Type: application/json" -d '{"question":"Explain microservices"}'
HTTP/1.1 200 OK
Server: nginx
Date: Thu, 26 Nov 2026 08:02:56 GMT
Content-Type: application/json
Content-Length: 126
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Sau khi kiểm tra xong đã chạy `docker compose -p k5-day14-docker -f 02-docker/production/docker-compose.yml down` để giải phóng cổng 80.

---

## Part 3: Cloud Deployment

### Exercise 3.2: Deploy agent Part 6 lên Render

- **URL public:** https://ai20k-cohort5-lab14.onrender.com
- **Kết quả kiểm tra live endpoint trên Render:**
  - `GET /health` → **`200`** (`{"status":"ok","environment":"production"}`)
  - `GET /ready` → **`200`** (`{"ready":true}` — đã kết nối Redis trên Render)
  - `POST /ask` (không có `X-API-Key`) → **`401`** (`{"detail":"Invalid or missing API key"}`)
  - `POST /ask` (có `X-API-Key: $AGENT_API_KEY`) → **`200`** *(chạy kiểm tra trực tiếp cùng ảnh chụp `screenshots/test.png`)*
- **Screenshots:** `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`

---

### So sánh `railway.toml` và `render.yaml`

| Tiêu chí | `railway.toml` | `render.yaml` | Vì sao khác nhau? |
| :--- | :--- | :--- | :--- |
| **Định dạng & Phạm vi** | **TOML**, cấu hình cho **1 service** qua 2 section `[build]` và `[deploy]`. | **YAML (Render Blueprint / IaC)**, khai báo được **nhiều service** dưới `services:` (`type: web`, `type: redis`, `disk`, `region`, `plan`). | Railway tách phần tạo DB/Redis và biến môi trường ra Dashboard/CLI, còn Render cho phép mô tả toàn bộ hạ tầng nhiều service trong một file YAML để đồng bộ qua Blueprint. |
| **Build & Runtime** | Dùng `builder = "DOCKERFILE"` hoặc `"NIXPACKS"`, kèm `startCommand`. | Dùng `runtime: docker` (hoặc `runtime: python` kèm `buildCommand` và `startCommand`). | Phản ánh cơ chế build của từng nền tảng (Railway hỗ trợ Nixpacks tự nhận diện ngôn ngữ hoặc Dockerfile; Render chọn runtime rõ ràng trên mỗi service). |
| **Health check & Restart** | Có `healthcheckPath = "/health"`, `healthcheckTimeout = 30`, `restartPolicyType = "ON_FAILURE"`, `restartPolicyMaxRetries = 3`. | Có `healthCheckPath: /health`, `autoDeploy: true`; chính sách restart do Render tự quản lý theo health check. | Railway cho phép tinh chỉnh trực tiếp chính sách retry/timeout khi crash ngay trong `railway.toml`. |
| **Biến môi trường & Secret** | Không khai báo trong file; đặt qua Railway Dashboard hoặc CLI (`railway variables set ...`). | Khai báo ngay trong `envVars:` của service; secret dùng `sync: false` hoặc `generateValue: true` để không ghi giá trị thật vào Git. | `render.yaml` là file IaC nên cần cơ chế placeholder (`sync: false` / `generateValue`) để vẫn khai báo tên biến mà không lộ secret trên repository. |

---

### Exercise 3.3: Pipeline CI/CD GCP Cloud Run (`03-cloud-deployment/production-cloud-run/`)

Dựa trên `cloudbuild.yaml` và `service.yaml`, pipeline CI/CD khi push code lên nhánh `main` đi qua 4 bước tuần tự (`waitFor`):
1. **Test (`test`):** Chạy container `python:3.11-slim`, cài `requirements.txt` + `pytest` và thực thi `pytest tests/ -v --tb=short`; chỉ tiếp tục nếu toàn bộ test pass.
2. **Build (`build`):** Dùng `gcr.io/cloud-builders/docker` build image gắn tag `$COMMIT_SHA` và `latest`, tận dụng `--cache-from` từ image `latest` trước đó để giảm thời gian build.
3. **Push (`push`):** Đẩy toàn bộ các tag của image lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **Deploy (`deploy` + `service.yaml`):** Chạy `gcloud run deploy ai-agent` triển khai bản `$COMMIT_SHA` lên Cloud Run (`asia-southeast1`, `min-instances=1` tránh cold start, `max-instances=10`, `containerConcurrency=80`), nạp secret an toàn từ Secret Manager (`secretKeyRef` / `--set-secrets`) và cấu hình `livenessProbe` (`/health`) cùng `startupProbe` (`/ready`).

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop/app.py`)

- **API key được kiểm tra ở đâu:** Tại dependency `verify_api_key` (`04-api-gateway/develop/app.py:39-54`), đọc header `X-API-Key` qua `APIKeyHeader(name="X-API-Key", auto_error=False)` và inject vào endpoint `POST /ask` bằng `_key: str = Depends(verify_api_key)` (`app.py:70`). Các endpoint `/health` và `/` không gắn dependency này nên vẫn truy cập công khai.
- **Nếu thiếu hoặc sai key:**
  - Thiếu header `X-API-Key`: trả `401 Unauthorized` (`Missing API key. Include header: X-API-Key: <your-key>`).
  - Sai giá trị key: trả `403 Forbidden` (`Invalid API key.`).
- **Cách rotate key:** Giá trị `API_KEY` được đọc từ biến môi trường `AGENT_API_KEY` (`app.py:35`), nên khi rotate chỉ cần cập nhật `AGENT_API_KEY` trên nền tảng và restart/redeploy (trong production thực tế có thể chấp nhận đồng thời danh sách `[new_key, old_key]` trong thời gian chuyển tiếp để tránh ngắt kết nối client cũ).

**Kết quả test thực tế (`AGENT_API_KEY=secret-key-123 python app.py`):**

```text
# Không có key → 401
$ curl -sS -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 401 Unauthorized
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

# Sai key → 403
$ curl -sS -i -X POST http://localhost:8000/ask -H "X-API-Key: wrong-key" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 403 Forbidden
content-type: application/json

{"detail":"Invalid API key."}

# Đúng key → 200
$ curl -sS -i -X POST http://localhost:8000/ask -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 200 OK
content-type: application/json

{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

---

### Exercise 4.2 & 4.3: JWT Authentication & Rate Limiting (`04-api-gateway/production/`)

- **JWT flow (`auth.py`):**
  1. Client gửi `username` / `password` (`student` / `demo123`) tới `POST /auth/token` (`app.py:105-118`).
  2. Server xác thực bằng `authenticate_user()` (`auth.py:70-75`), tạo JWT ký bằng `HS256` chứa `sub`, `role`, `iat`, `exp` (hết hạn 60 phút, `auth.py:35-43`).
  3. Khi gọi `POST /ask`, dependency `verify_token` (`auth.py:46-67`) giải mã token trong `Authorization: Bearer <token>`; thiếu token trả `401`, token hết hạn trả `401`, token sai chữ ký/hỏng trả `403`.
- **Rate limiter (`rate_limiter.py`):**
  - **Thuật toán:** **Sliding Window Counter** dùng `deque` lưu timestamp các request hợp lệ (`rate_limiter.py:7, 27, 38-40`); mỗi request mới sẽ loại bỏ timestamp cũ hơn `now - window_seconds`.
  - **Giới hạn:** `rate_limiter_user` = **10 requests / 60 giây**, `rate_limiter_admin` = **100 requests / 60 giây** (`rate_limiter.py:86-87`).
  - **Tăng / bypass limit cho admin:** Trong `app.py:141`, chọn limiter theo `role` (`rate_limiter_admin if role == "admin" else rate_limiter_user`), hoặc bỏ qua bước `limiter.check()` nếu `role == "admin"`.

**Kết quả test thực tế (đã che token JWT):**

```text
# 1. Lấy token (student / demo123)
$ curl -sS -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" -d '{"username":"student","password":"demo123"}'
# Token: eyJhbGciOiJIUzI1NiIs...<MASKED>

# 2. Không có token → 401
$ curl -sS -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY

{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

# 3. Token hợp lệ (request 1) → 200
$ curl -sS -i -X POST http://localhost:8000/ask -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs...<MASKED>" -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
HTTP/1.1 200 OK
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY

{"question":"Explain JWT","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","usage":{"requests_remaining":9,"budget_remaining_usd":1.6e-05}}

# 4. Vòng lặp 12 request liên tiếp: request 1..10 trả 200, từ request 11 trả 429
Request 2  -> HTTP 200 | requests_remaining: 8
...
Request 10 -> HTTP 200 | requests_remaining: 0
$ curl -sS -i -X POST http://localhost:8000/ask -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs...<MASKED>" -H "Content-Type: application/json" -d '{"question":"Test 11"}'
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795680339
retry-after: 59
content-type: application/json

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

---

### Exercise 4.4: Cost Guard (`04-api-gateway/production/cost_guard.py`)

- **Cách hoạt động trong `production/cost_guard.py`:**
  1. **Kiểm tra trước khi gọi LLM (`check_budget(username)` tại `app.py:145`, `cost_guard.py:60-91`):**
     - Nếu tổng chi phí toàn hệ thống vượt `global_daily_budget_usd` ($10/ngày) → raise `503 Service Unavailable`.
     - Nếu chi phí trong ngày của user đạt/vượt `daily_budget_usd` ($1/ngày) → raise **`402 Payment Required`**.
     - Nếu đạt ≥ 80% budget (`warn_at_pct = 0.8`) → ghi `logger.warning`.
  2. **Ghi nhận chi phí sau khi gọi LLM (`record_usage` tại `app.py:151-153`, `cost_guard.py:93-110`):**
     - Quy đổi số token input/output theo đơn giá (`PRICE_PER_1K_INPUT_TOKENS = 0.00015`, `PRICE_PER_1K_OUTPUT_TOKENS = 0.0006` ở `cost_guard.py:20-21`) và cộng dồn vào `UsageRecord` cũng như `_global_cost`.
  3. **Kiểm tra thực tế qua `GET /me/usage` sau 10 request:**
     `{"user_id":"student","date":"2026-11-26","requests":10,"input_tokens":40,"output_tokens":276,"cost_usd":0.000172,"budget_usd":1.0,"budget_remaining_usd":0.999828,"budget_used_pct":0.0}`
- **Cách triển khai với Redis ở production (cho multi-instance & Part 6):**
  - Không lưu `_records` trong RAM (mất khi restart và không đồng bộ giữa nhiều container). Thay vào đó lưu tổng chi tiêu vào Redis theo key gắn chu kỳ (ví dụ `budget:{user_id}:{YYYY-MM}` hoặc `{YYYY-MM-DD}`).
  - Trước khi gọi LLM đọc `current = float(r.get(key) or 0)`; nếu `current + estimated_cost > limit` thì trả HTTP `402`. Sau khi gọi LLM dùng `r.incrbyfloat(key, actual_cost)` và đặt `r.expire(key, ttl)` để tự reset khi sang chu kỳ mới.
- **Vì sao cần cả Rate Limit và Cost Guard:** Rate limit kiểm soát **tốc độ gọi** (request/phút, chống spam/quá tải server), còn Cost guard kiểm soát **chi phí tiền** (USD/ngày hoặc tháng, chống trường hợp gọi ít request nhưng mỗi prompt rất dài làm cạn ngân sách LLM).

---

## Part 5: Scaling & Reliability

### Exercise 5.1 & 5.2: Health Checks & Graceful Shutdown (`05-scaling-reliability/develop/app.py`)

- **Phân biệt Liveness (`/health`) và Readiness (`/ready`):**
  - `GET /health` (**Liveness probe**): Kiểm tra tiến trình app còn sống hay không (`status`, `uptime_seconds`, `memory.used_percent`). Nếu fail, nền tảng sẽ restart container.
  - `GET /ready` (**Readiness probe**): Kiểm tra app đã sẵn sàng phục vụ traffic hay chưa (`_is_ready`, `in_flight_requests`). Khi đang khởi động, đang shutdown, hoặc dependency (như Redis) mất kết nối, `/ready` trả `503 Service Unavailable` để Load Balancer ngừng đẩy request mới vào instance đó (trong khi `/health` vẫn có thể trả `200` nếu process chưa chết).
- **Kết quả kiểm thử thực tế (`/health`, `/ready`, và Graceful Shutdown với `SIGTERM`):**
  - `GET /health` → `200 OK`: `{"status":"ok","uptime_seconds":1.2,"version":"1.0.0","environment":"development","timestamp":"2026-06-10...","checks":{"memory":{"status":"ok","used_percent":8.4}}}` *(đo tại `2026-11-26T08:08:55Z`)*
  - `GET /ready` → `200 OK`: `{"ready":true,"in_flight_requests":1}`
  - Gửi 2 request `POST /ask?question=hello` song song rồi gửi `kill -SIGTERM <PID>` ngay sau `0.2s`:
    - Cả 2 request đang xử lý đều hoàn thành với **`REQ1_CODE=200`** và **`REQ2_CODE=200`** (không bị cắt ngang).
    - Log server ghi nhận đúng luồng: `Shutting down` → hoàn tất 2 request `200 OK` → `Waiting for application shutdown` → `Graceful shutdown initiated...` → `Shutdown complete` → `Received signal 15 — uvicorn will handle graceful shutdown` → process thoát với `EXIT_CODE=0`.

---

### Exercise 5.3 – 5.5: Stateless Design & Load Balancing (`05-scaling-reliability/production/`)

- **Vì sao state lưu trong RAM hỏng khi scale nhiều instance:**  
  Khi chạy 3 instance (`--scale agent=3`) sau Nginx load balancer (round-robin), request 1 của user có thể vào `instance-1` và lưu lịch sử chat vào RAM riêng của `instance-1`, nhưng request 2 lại bị Nginx chuyển sang `instance-2` vốn không có session đó trong bộ nhớ → mất ngữ cảnh hội thoại.
- **Giải pháp Stateless với Redis:**  
  Toàn bộ `session:{session_id}` (bao gồm `history`, tối đa 20 messages, TTL 3600 giây) được lưu tập trung trong Redis (`_redis.setex` / `_redis.get`), nên mọi instance đều đọc/ghi cùng một state.
- **Chạy thực tế stack với 3 instance agent (`docker compose -p k5-day14-scaling up -d --build --scale agent=3`):**
  - Vì cổng `8080` trên máy host đang bị tiến trình `AgentService` (PID `5788`) chiếm dụng nên container `nginx-1` mặc định báo lỗi bind port `8080`; đã ánh xạ Nginx tạm thời trên network `k5-day14-scaling_agent_net` qua cổng `18080` để chạy `test_stateless.py` kiểm chứng thực tế qua 3 instance `agent-1`, `agent-2`, `agent-3` + `redis-1` (tất cả ở trạng thái `healthy`).
  - **Kết quả `python test_stateless.py`:**

```text
============================================================
Stateless Scaling Demo
============================================================

Session ID: 92368a5c-79f0-4630-aa3a-a6f299ec4e41

Request 1: [instance-f8cae2]
Request 2: [instance-324ea5]
Request 3: [instance-53dcf8]
Request 4: [instance-f8cae2]
Request 5: [instance-324ea5]

------------------------------------------------------------
Total requests: 5
Instances used: {'instance-53dcf8', 'instance-324ea5', 'instance-f8cae2'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
  ... (đủ 5 turns / 10 messages)
✅ Session history preserved across all instances via Redis!
```

- **Giải thích kết quả:** 5 request trong cùng một `session_id` được Nginx phân tán luân phiên tới cả 3 instance khác nhau (`instance-f8cae2`, `instance-324ea5`, `instance-53dcf8`), nhưng khi gọi `GET /chat/{session_id}/history` vẫn nhận đủ 10 messages (5 câu hỏi + 5 câu trả lời) nhờ toàn bộ lịch sử được lưu tập trung trong Redis. Sau khi test xong đã chạy `docker compose -p k5-day14-scaling down` để dọn sạch stack.

---

## Part 6: Final Project — Checklist Deliverable

Chạy `python check_production_ready.py` (chế độ đầy đủ trong Ubuntu WSL2 với Docker):

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 42/42 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

- Kích thước Docker image thực tế: **238 MB** (`python:3.11-slim` multi-stage, user non-root `appuser`, `HEALTHCHECK`, `exec uvicorn` làm PID 1, `docker stop` thoát với exit code `0` trong `0.7s`).
- Structured logging: `12` dòng JSON hợp lệ được ghi bởi app trong lần chạy kiểm thử.

---

## AI Log

- **CP1:** Dùng AI để chạy kiểm chứng `01-localhost-vs-production/develop/app.py` và `01-localhost-vs-production/production/app.py` trong Ubuntu WSL2, đối chiếu các dòng code giữa hai phiên bản để tổng hợp bảng so sánh và anti-patterns vào `MISSION_ANSWERS.md`. Đã tự kiểm tra lại output `curl` (200/404 trên `develop`, 200 trên `/health`, `/ready`, `/ask` của `production`) và số dòng tham chiếu chính xác trong các file nguồn.
- **CP2:** Dùng AI hỗ trợ chạy build 2 image (`my-agent:develop`, `my-agent:advanced`), kiểm tra container và chạy Compose stack `-p k5-day14-docker` qua Nginx; tổng hợp phân tích Dockerfile, sơ đồ stack và số đo kích thước vào `MISSION_ANSWERS.md`. Đã kiểm tra thực tế kích thước image bằng `docker images` / `docker image inspect` và kết quả `200 OK` qua `curl` trước khi `down` stack.
- **CP3:** Dùng AI hỗ trợ chạy và test `04-api-gateway/develop/app.py` và `04-api-gateway/production/app.py` trong Ubuntu WSL2; tổng hợp cơ chế API Key, JWT, Sliding Window Rate Limiter và Cost Guard vào `MISSION_ANSWERS.md`. Đã tự kiểm tra các mã HTTP thực tế (`401`, `403`, `200`, `429`), che JWT token trước khi lưu và đối chiếu dòng code trong `auth.py`, `rate_limiter.py`, `cost_guard.py`.
- **CP4:** Dùng AI hỗ trợ test `/health`, `/ready` và graceful shutdown (`SIGTERM`) trên `05-scaling-reliability/develop/app.py` trong WSL2, và test stack `--scale agent=3` (`k5-day14-scaling`) qua Nginx (map tạm cổng `18080` do cổng `8080` host bận bởi `AgentService`) với `test_stateless.py`. Đã kiểm tra thực tế cả 3 `instance_id` xử lý round-robin, đủ 10 messages trong Redis history, và dọn stack bằng `docker compose down`.
- **CP5:** Dùng AI hỗ trợ hoàn thiện các `TODO` trong `06-lab-complete/` (`app/config.py`, `app/redis_client.py`, `app/auth.py`, `app/rate_limiter.py`, `app/cost_guard.py`, `app/main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, kết hợp cùng `render.yaml` đã cấu hình). Đã tự chạy `python check_production_ready.py` bản đầy đủ trong Ubuntu WSL2 và kiểm tra kết quả đạt `PASS 12/12` (`42/42 checks passed`, image `238 MB`, `docker stop` `0.7s`).
- **CP6 (phần chuẩn bị & phân tích):** Dùng AI đối chiếu `03-cloud-deployment/railway/railway.toml`, `render.yaml` và `03-cloud-deployment/production-cloud-run/` (`cloudbuild.yaml`, `service.yaml`) để tổng hợp bảng so sánh và mô tả pipeline CI/CD vào `MISSION_ANSWERS.md`, cùng khung `DEPLOYMENT.md`.
- **CP7:** Dùng AI hỗ trợ thêm metric `agent_question_length_chars` vào `develop/app.py`, chạy các kịch bản `load_test.py` (`c=1,10,50,100` và `MOCK_SLOW_RATE=0, 0.03, 0.1`), chạy `eval/run_eval.py`, cập nhật `KNOWLEDGE_BASE` trong `mock_llm.py` (đạt `23/23` không regression) và tạo `.github/workflows/eval.yml`. Mọi số liệu trong `BENCHMARK_REPORT.md` đều đã được đối chiếu khớp trực tiếp với các file JSON trong `reports/`.
- **CP8:** Dùng AI hỗ trợ sửa `PYTHONUSERBASE=/home/agent/.local` trong `benchmark-observability/production/Dockerfile`, chạy `promtool test rules`, chạy Locust headless `--no-deps` cho `scale_1` (1 instance) và `scale_3` (3 instances), truy xuất span/trace_id/log JSON trong Jaeger và chạy thí nghiệm phá hệ thống (`MOCK_ERROR_RATE=0.2`, `MOCK_SLOW_RATE=0.3`) ghi nhận `AgentHighErrorRate` (`70s`) và `AgentHighLatencyP95` (`130s`) firing đồng thời. Đã đối chiếu toàn bộ số liệu trong `BENCHMARK_REPORT.md` khớp với `scale_1_stats.csv`, `scale_3_stats.csv`, Prometheus và Jaeger.
