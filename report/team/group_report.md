# Báo cáo nhóm — Lab 8 LogiX-VN

Tối đa 5 trang ngoài phụ lục. Số liệu lấy từ file trong `src/reports/`, không chép tay từ terminal.

## 1. Thông tin nhóm

- Tên nhóm:
- Thành viên: xem `TEAM.md`
- Commit chốt (trùng `report/team/decision_adr.md`):

## 2. Mục tiêu và cách tiếp cận

Nhóm hiểu bài toán thế nào, chia việc ra sao, thứ tự làm bốn shape.

...

## 3. Giải pháp

Mô tả ba shape nhóm viết (workflow, single, orchestrator): mỗi shape đọc gì, quyết định gì, gọi host ra sao. Chỉ rõ ranh giới code / model (tham khảo [docs/architecture.md](../../docs/architecture.md)), cách handoff được sanitize và trace ghi những event nào.

### Shape A — Workflow (M1)

*(Đợi M1 bổ sung sau khi hoàn thiện `workflow.py`)*

### Shape B — Single ReAct Agent (M2)

*(Đợi M2 bổ sung sau khi hoàn thiện `single.py`)*

### Shape C — Orchestrator & Read-only Investigators (M3 — Đinh Hoàng Phong)

- **Đọc dữ liệu & lập kế hoạch:** Orchestrator mở SQLite store, đọc thông tin claim qua `lab8.tools.get_claim_view` (chỉ lấy `claim_id`, `principal_id`, `order_id`, `ticket`; không truy vấn `SELECT *`, không đọc `parent_secret` hay `raw_headers_json`). Nếu thiếu `claim_id` trả `failed` (`unknown_claim`); nếu thiếu `order_id` trả `needs_info` (tuyệt đối không tách mã đơn từ chữ trong `ticket`).
- **Handoff & Sanitization:** Orchestrator dùng `lab8.handoff.make_handoff` tạo gói `handoff.v1` chứa các trường trong allowlist (`ALLOWED_FIELDS`), `facts` rỗng (không chứa context của parent, header, hay thông tin cá nhân) và `allowed_tools` chỉ gồm 3 tool đọc (`lookup_order`, `lookup_policy`, `lookup_refund_history`). Sau đó `lab8.runtime.run_readonly_investigators` thực thi các tool này với `worker=True` và kiểm tra scope `principal_id`; investigator không có write registry và bị chặn nếu nhận `WRITE_TOOLS` (`ToolRejected` / `HandoffError`).
- **Ranh giới Code / Model & Tính tiền:** `MockLLM` chỉ tham gia bước `plan` và `draft` câu trả lời trên metadata an toàn. Nếu đơn không hiển thị hoặc ngoài phạm vi principal → trả `escalated`. Nếu hợp lệ, **code của orchestrator** gọi `lab8.tools.compute_compensation` trên `order` có cấu trúc (chỉ dùng policy `is_current=1` và `effective_date <= 2026-11-15`, bỏ qua số ngày/clause giả mạo trong `ticket`).
- **Gọi Host & Durability:** Nếu quote `<= 0`, shape tự từ chối (`denied`, `proposal_amount=0`) và không gọi `issue_refund`. Nếu quote `> 0`, orchestrator truyền **quote đầy đủ** và `crash_at` vào `lab8.durability.issue_refund` (không tự trừ phần đã hoàn trước đó và **không** bắt `InjectedCrash`, chỉ flush trace trước khi re-raise). Host kiểm `approval_id` thuộc đúng claim, trừ phần đã hoàn theo đơn (T13/T14), đảm bảo idempotency theo `refund:{claim_id}`, và trả kết quả qua `lab8.shapes.common.finish()`.
- **Trace an toàn (`trace.v1`):** Ghi lần lượt các event `claim_view`, `plan`, `handoff` (đã sanitize), `investigator` (order theo `ORDER_FIELDS`, `policy_count`, `refund_history`), `quote`, `host_refund`, `decision` (và `crash`/`error` khi có sự cố), tuyệt đối không ghi `CANARY_SECRET_*`, `ticket` thô, SĐT, địa chỉ, tên hàng hay ghi chú nội bộ.

## 4. Kết quả

Bảng so sánh 4 shape trên bộ public (từ `src/reports/benchmark.json`): pass rate, pass^5, seed min–max, variance, cost/success, mean/p95 steps. Kèm crash safety (`src/reports/crash.json`) và, nếu có, kết quả tự kiểm trên `student_drop/`.

...

Quyết định kiến trúc và lý do: xem `report/team/decision_adr.md`. Phiếu nghiên cứu và ablation: xem `report/team/research_card.md`.

## 5. Khó khăn và cách xử lý

Lỗi gặp phải (kèm lệnh, output hoặc ảnh chụp) và cách nhóm xử lý.

...

## 6. Tổng hợp đóng góp

Chi tiết đóng góp (commit hash, test đã thêm/sửa) và bằng chứng của cả 4 thành viên được tổng hợp tại bảng đóng góp trong [TEAM.md](../../TEAM.md) và 4 báo cáo cá nhân:

- **M1 — Đỗ Hồng Vỹ** (`2A202604107`): [2A202604107_DoHongVy.md](2A202604107_DoHongVy.md) — Shape A `workflow`, tích hợp repo/PR, ADR và hoàn thiện nộp bài.
- **M2 — Nguyễn Ánh Dương** (`2A202604087`): [2A202604087_NguyenAnhDuong.md](2A202604087_NguyenAnhDuong.md) — Shape B `single` (ReAct), `research_card.md`, tổng hợp mục 5.
- **M3 — Đinh Hoàng Phong** (`2A202604090`): [2A202604090_DinhHoangPhong.md](2A202604090_DinhHoangPhong.md) — Shape C `orchestrator`, handoff sanitize (`handoff.v1`), `test_orchestrator_handoff_extra.py`, kiểm tra trace/secret/PII (CP4.3–4.4), mục 3 (Shape C), 6, 7, 8 và mục Trace trong ADR.
- **M4 — Phạm Văn Chiêu** (`2A202604033`): [2A202604033_PhamVanChieu.md](2A202604033_PhamVanChieu.md) — Rà soát durability/approval, `crash_test`, `benchmark`, `hidden_selfcheck`, ablation và mục 4.

## 7. Hạn chế và hướng cải thiện

- **Giới hạn của MockLLM và số đo:** `MockLLM` là mô hình giả lập cố định theo seed (`complete`), không phải LLM sản xuất nên không phản ánh được năng lực hiểu ngôn ngữ tự nhiên thực tế hoặc các lỗi suy luận/hallucination đa dạng ngoài quy luật lập trình sẵn. Tương tự, chi phí là đơn vị mô phỏng từ `config/pricing.yaml` (không phải hóa đơn API thật) và độ trễ luôn là `unavailable`.
- **Giới hạn tập dữ liệu kiểm chứng:** Tập public chỉ gồm 14 claim (bao phủ các mẫu bẫy T01–T14), còn tập `student_drop/` không kèm nhãn nên nhóm chỉ tự kiểm tra được tính ổn định (`status != error`), chuẩn trace và dấu hiệu rò rỉ trước khi giảng viên chấm hidden 40 claim × 5 seed.
- **Điều kiện làm kết luận thay đổi:** Trong môi trường giả lập hiện tại, phần tính tiền và kiểm tra luật nằm hoàn toàn trong code nên chi phí điều phối nhiều bước không làm tăng độ chính xác nghiệp vụ. Kết luận này có thể đảo ngược nếu bài toán thực tế có yêu cầu trích xuất ngữ nghĩa phức tạp từ chứng từ/ticket không có cấu trúc mà vẫn giữ code làm lớp xác minh cuối (verifier) và host làm lớp ghi duy nhất.
- **Hướng cải thiện:**
  1. Bổ sung bước **verifier bằng code** hoặc cơ chế kiểm tra chéo nếu triển khai với LLM thật để chặn triệt để sai lệch giữa văn bản ticket và dữ liệu có cấu trúc.
  2. Tối ưu thời gian thực thi khi có I/O thật bằng cách chạy song song các investigator đọc độc lập (`lookup_order`, `lookup_policy`, `lookup_refund_history`) trước bước tổng hợp quote.
  3. Mở rộng cơ chế reconciliation hai pha nếu tích hợp với cổng thanh toán bên ngoài ngoài SQLite nội bộ.

## 8. Tài liệu tham khảo

1. Tài liệu nội bộ Lab 8 LogiX-VN: [README.md](../../README.md), [docs/business_rules.md](../../docs/business_rules.md), [docs/contracts.md](../../docs/contracts.md), [docs/architecture.md](../../docs/architecture.md), [docs/metrics.md](../../docs/metrics.md), [docs/bonus_topics.md](../../docs/bonus_topics.md).
2. Google Research (2026), *Towards a Science of Scaling Agent Systems* (tài liệu tham khảo bài giảng N8 về parallelization & error amplification).
3. MAST, NeurIPS (2025), *Why Do Multi-Agent LLM Systems Fail?* (taxonomy lỗi hệ thống đa tác tử).
4. AgentArch, AACL (2026) & EMNLP (2026), *Rethinking Evaluation of MAS Efficiency* (chuẩn đối chứng công bằng và kiểm toán bộ đo).
5. DBOS, *Durable Workflows and Steps* (nguyên lý idempotency và phục hồi sau crash).
