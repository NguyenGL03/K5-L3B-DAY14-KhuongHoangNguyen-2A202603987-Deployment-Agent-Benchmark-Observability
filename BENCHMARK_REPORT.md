# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Khuong Hoang Nguyen  
**Ngày chạy:** 2026-11-26  
**Môi trường:** Windows 11 + Ubuntu WSL2 (`16` logical CPUs, `23.8 GB` RAM, Python 3.14.4 trong WSL2, Docker Desktop 29.9.2)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo 95% người dùng nhận phản hồi dưới 0.5 giây ở mức tải thông thường, tránh che giấu tail latency như average. |
| Error rate `/ask` | < 2.0 % | Cho phép sai số nhỏ từ upstream mock LLM (`MOCK_ERROR_RATE=0.01` mặc định) nhưng chặn lỗi hệ thống bất thường. |
| Accuracy trên golden dataset | ≥ 85 % (không regression) | Đảm bảo chất lượng RAG v2 trên 23 câu hỏi chuẩn và không làm hỏng các câu đã đúng ở phiên bản trước. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.91 | 193.1 | 225.6 | 1721.2 | 1.67% | PASS |
| 10 | 39.08 | 187.4 | 221.6 | 1695.1 | 2.00% | PASS |
| 50 | 57.76 | 350.5 | 1913.7 | 2691.8 | 1.33% | FAIL (p95 > 500ms) |
| 100 | 49.59 | 678.0 | 3852.3 | 4433.6 | 0.33% | FAIL (p95 > 500ms) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Không. Từ concurrency `1` lên `10`, RPS tăng gần 10 lần (`3.91` → `39.08` req/s) và `p95` giữ ổn định quanh `221–226ms` vì app xử lý async tốt khi chưa bão hòa. Tuy nhiên khi tăng lên `50` và `100`, RPS đạt đỉnh `57.76` rồi giảm xuống `49.59` req/s trong khi `p95` vọt lên `1913.7ms` và `3852.3ms` do tiến trình Python đơn worker bị bão hòa hàng đợi kết nối và chi phí context-switching trên event loop.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 191.5 | 220.3 | 233.2 |
| 0.03 (mặc định) | 223.7 | 224.0 | 1701.7 |
| 0.1 | 320.8 | 1695.3 | 1710.9 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

`p99` (và `p95` khi tỉ lệ chậm đạt ~10%) nhạy nhất với tail latency: khi `MOCK_SLOW_RATE` tăng từ `0` lên `0.03`, `avg` chỉ tăng nhẹ từ `191.5ms` lên `223.7ms` (+16.8%) và `p95` gần như đứng yên (`220.3ms` → `224.0ms`), nhưng `p99` nhảy vọt hơn 7 lần (`233.2ms` → `1701.7ms`). Ở mức `0.1`, `p95` vọt lên `1695.3ms` làm rớt SLO. Nếu đặt SLO theo `average`, 90–97% request nhanh sẽ che giấu trải nghiệm chờ gần 2 giây của nhóm user gặp tail latency.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 58.2 | 109.0 | 113.8 |
| Tổng cost (USD) | $0.000419 | $0.000759 | $0.000792 |
| Cost / câu đúng (USD) | $0.00041895 | $0.00003616 | $0.00003443 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `(["jwt"], ...)` giải thích JWT (token có chữ ký số, có thời điểm hết hạn) so với API key vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` (và đồng bộ sang `production/utils/mock_llm.py`). |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `(["hpa", "kubernetes", "autoscal"], ...)` mô tả Kubernetes HPA scale pod theo CPU, memory và custom metrics vào `KNOWLEDGE_BASE`. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

So với v1, agent v2 tốn gần gấp đôi token mỗi câu (`113.8` vs `58.2`) do chèn thêm ngữ cảnh từ knowledge base vào prompt, và latency `p95` tăng thêm khoảng ~25ms (`211.0ms` vs `186.6ms`) cho bước retrieval. Tuy nhiên, độ chính xác tăng vượt trội từ `4.3%` lên `100.0%`, nhờ đó **cost / câu trả lời đúng** của v2 (`$0.00003443`) rẻ hơn **~12 lần** so với v1 (`$0.00041895`).

**CI Quality Gate (`.github/workflows/eval.yml`):**

Workflow chạy `python eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85` trên pull request; khi accuracy thấp hơn ngưỡng hoặc có bất kỳ câu regression nào so với baseline (ví dụ khi kiểm thử chạy v1 so với baseline v2 đạt `4.3%` với `20` câu regression), script trả về **exit code `1`**, khiến GitHub Actions đánh dấu job failed và chặn merge PR.

---

## 4. Observability stack (production)

### 4.1 Screenshot & Kiểm tra Exercise 7.4

- `screenshots/grafana-dashboard.png`: Dashboard Grafana (`Day 14 — AI Agent Overview`) khi đang có tải (hiển thị 4 Golden Signals).
- `screenshots/jaeger-slow-trace.png`: Trace chậm trong Jaeger (`chat mock-llm-small` chiếm ~98.8% tổng latency).
- `screenshots/jaeger-error-trace.png`: Trace lỗi (`error=true`) trong Jaeger có event `exception`.
- `screenshots/prometheus-alert-firing.png`: Trang Alerts của Prometheus hiển thị cả `AgentHighErrorRate` và `AgentHighLatencyP95` đang **firing**.

**Trả lời câu hỏi Exercise 7.4 (quan sát stack production):**
1. **p95 và avg:** Ở tải bình thường, `avg` chỉ ~`220–250ms` nhưng `p95`/`p99` nhảy lên `260–1700ms` (khi bật fault injection `MOCK_SLOW_RATE=0.3`, `avg = 584.9ms` còn `p95 = 1896.9ms`) — khoảng cách lớn phản ánh **tail latency** do ~3–30% request chậm bất thường.
2. **Phân bổ traffic giữa các instance:** Nginx chia tải đều bằng round-robin; truy vấn Prometheus `sum by (instance) (rate(http_requests_total{route="/ask"}[2m]))` khi chạy 3 instance cho thấy 3 container nhận lưu lượng gần như bằng nhau (`19.85`, `20.07`, `19.67` req/s).
3. **Vì sao input tokens/s lớn hơn output tokens/s:** `input = 4586.05 tokens/s` so với `output = 2402.24 tokens/s` (gần gấp đôi) vì agent v2 dùng RAG: mỗi prompt gửi lên LLM gồm `SYSTEM_PROMPT + tài liệu retrieve được + câu hỏi`, dài hơn nhiều so với câu trả lời ngắn gọn.
4. **`GET /metrics` qua Nginx trả về gì:** Trả về **`404 Not Found`** vì `nginx.conf` chặn truy cập `/metrics` từ bên ngoài, chỉ cho phép Prometheus scrape trực tiếp trong network nội bộ `obs_net` để tránh lộ thông tin hệ thống và tránh bị spam.

### 4.2 Thí nghiệm "phá hệ thống" & Unit test Alert Rules

- **Unit test (`promtool test rules /p/alert_rules_test.yml`):** `SUCCESS` (toàn bộ 4 rule pass test).

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (`for: 1m`) | **70 giây** (error rate đo được ~`19.52%` > `5%`) | Error rate (`/ask`), HTTP req/s theo status (`5xx`) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (`for: 2m`) | **130 giây** (`p95` đo được ~`1896.9ms` > `1000ms`) | Latency & Traffic (`p95`, `p99`), LLM Latency `p95` |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` *(không chạy trực tiếp)* | *(tham chiếu: `for: 2m`, giá đắt hơn ~16 lần)* | Cost USD/giờ, LLM Latency `p95` |
| D | `docker pause` 1 instance | `AgentInstanceDown` *(không chạy trực tiếp)* | *(tham chiếu: `for: 30s` khi `up == 0`)* | Instances up, Nginx có thể báo 504 |
| E | `AGENT_VERSION=v1` | **Không có alert nào firing** *(chỉ thấy qua bảng version & retrieval hit ratio)* | Không firing | Bảng version (`v1`), Retrieval hit ratio = 0 |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Alert hạ tầng chỉ đo *tốc độ, lỗi HTTP và chi phí*, không biết nội dung trả lời đúng hay sai (như khi thử `eval` bản `v1` ở CP7: latency nhanh hơn `186.6ms` nhưng accuracy tụt từ `100%` xuống `4.3%`). Để phát hiện sự cố chất lượng trên production cần: (1) chạy **eval trên golden dataset** trong CI/CD (quality gate) trước khi deploy, (2) theo dõi các **product/quality metrics** như `retrieval_hit_ratio`, tỷ lệ user thumbs-down/retry, và (3) lấy mẫu traffic thật để đánh giá định kỳ bằng **LLM-as-a-judge** hoặc kiểm tra thủ công.

### 4.3 Debug bằng trace

Chọn trace chậm nhất tìm được trong Jaeger (`service=observable-agent`):

- `trace_id`: `1fdc07544520872d9015f6e9c12f3b51`
- Tổng thời gian: **1717.18 ms**
- Span chiếm nhiều thời gian nhất: **`chat mock-llm-small`** (**1697.34 ms**, **98.8%** tổng thời gian; `POST /ask` = `1717.18 ms`, `agent.run` = `1714.64 ms`, `agent.retrieve_context` = `16.99 ms` = `1.0%`)
- Dòng log tương ứng (lọc theo `trace_id` từ `docker compose -p k5-day14-observability logs agent`):

```json
{"ts": "2026-11-26T10:32:17.869592+00:00", "level": "INFO", "service": "observable-agent", "instance": "aaa6c1c2d617", "event": "llm_call", "trace_id": "1fdc07544520872d9015f6e9c12f3b51", "span_id": "ca933937ce6e4aa2", "request_id": "797a0f2d01ed", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 95, "output_tokens": 55, "cost_usd": 4.7e-05, "llm_ms": 1696.8}
{"ts": "2026-11-26T10:32:17.870069+00:00", "level": "INFO", "service": "observable-agent", "instance": "aaa6c1c2d617", "event": "http_request", "trace_id": "1fdc07544520872d9015f6e9c12f3b51", "span_id": "ca933937ce6e4aa2", "request_id": "797a0f2d01ed", "method": "POST", "route": "/ask", "status": 200, "ms": 1716.2}
```

Ví dụ trace lỗi (`event: "llm_error"`) và dòng log JSON tương ứng (`trace_id: 058d38512002a39921330933c2e30b7a`):

```json
{"ts": "2026-11-26T10:31:57.381838+00:00", "level": "INFO", "service": "observable-agent", "instance": "3e310d339525", "event": "llm_error", "trace_id": "058d38512002a39921330933c2e30b7a", "span_id": "1d04fda1140be474", "request_id": "7ae5ee7aa4e2", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Số liệu `Aggregated` trích trực tiếp từ `benchmark-results/scale_1_stats.csv` và `benchmark-results/scale_3_stats.csv` (trong ngoặc là dòng `POST /ask`):

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 64.23 (`58.18`) | 200 (`200`) | 510 (`550`) | 1700 (`1700`) | 63 (`0.82%`) |
| 3 | 65.19 (`59.37`) | 190 (`200`) | 260 (`260`) | 1700 (`1700`) | 74 (`0.96%`) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

- **Cải thiện `p95` rõ rệt:** Khi scale từ 1 lên 3 instance, `p95` giảm gần một nửa (từ `510ms` xuống `260ms` ở `Aggregated`; `550ms` → `260ms` ở `POST /ask`), đồng thời độ trễ tối đa (`max`) giảm từ `3185.9ms` xuống `1791.8ms` và `GET /health` `p95` giảm từ `87ms` xuống `18ms`, vì tải được chia đều (~`20 req/s/instance`) nên không còn nghẽn event loop ở một container duy nhất.
- **RPS tổng và `p99` gần như không đổi (`64.23` → `65.19 req/s`, `p99 = 1700ms`):** Vì kịch bản cố định 100 user có `wait_time` và **nút thắt nằm ở thời gian chờ LLM upstream** (`~120–180ms` + `3%` slow `+1500ms`) cùng tỷ lệ lỗi `MOCK_ERROR_RATE=0.01` từ phía LLM — tăng thêm instance agent không làm LLM trả lời nhanh hơn hoặc bớt lỗi upstream.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **Latency trung bình che giấu tail latency:** Chỉ cần 3% request chậm là `p99` tăng vọt gấp 7 lần dù `avg` hầu như không đổi; vì vậy SLO và alert phải đặt theo `p95`/`p99`.
  2. **Chỉ đo hạ tầng là không đủ cho AI Agent:** Dashboard xanh không đảm bảo câu trả lời đúng — cần kết hợp **Eval trên golden dataset (quality gate)** trong CI cùng **cost/câu đúng** để đánh giá trade-off của RAG/model.
  3. **3 trụ cột Metrics – Traces – Logs liên kết chặt với nhau:** Prometheus/Grafana báo *khi nào* có vấn đề, Jaeger chỉ ra *span nào* gây chậm (98.8% do LLM call), và `trace_id` trong JSON log giúp truy ngược chi tiết request lỗi.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - Thêm **Time-To-First-Token (TTFT)** & tokens/giây cho streaming, **retrieval hit rate / empty-context rate**, **rate-limit (`429`) & budget-exceeded (`402`) counter**, **Redis connection/latency metric**, và **synthetic evaluation canary** chạy định kỳ trên tập câu hỏi chuẩn để báo alert khi chất lượng giảm.
