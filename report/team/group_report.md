# Báo cáo nhóm — Lab 8 LogiX-VN

Tối đa 5 trang ngoài phụ lục. Số liệu lấy từ file trong `src/reports/`, không chép tay từ terminal.

## 1. Thông tin nhóm

- Tên nhóm: BuaDi
- Thành viên: xem `TEAM.md` (Đỗ Hồng Vỹ — nhóm trưởng, Nguyễn Ánh Dương, Đinh Hoàng Phong, Phạm Văn Chiêu)
- Commit chốt (trùng `report/team/decision_adr.md`):

## 2. Mục tiêu và cách tiếp cận

**Bài toán.** LogiX-VN nhận claim hoàn phí vận chuyển. Mỗi claim gồm principal (khách), có thể có `order_id`, và một ticket chữ tự do. Hệ thống phải ra đúng một trong năm trạng thái (`resolved`, `needs_info`, `escalated`, `denied`, `failed`), tính đúng số tiền theo policy hiện hành, và ghi ledger an toàn: một claim tối đa một refund, kể cả khi gọi lại hoặc crash. Nhóm hiểu bài này không hỏi "multi-agent có tốt hơn không" mà hỏi: **mức tự chủ thấp nhất nào vẫn làm đúng việc**, đo bằng số trên cùng claim, cùng seed, cùng bảng giá.

**Nguyên tắc chung cho cả ba shape nhóm viết.**

- Tiền do code tính (`compute_compensation`), model không quyết số tiền và không ghi ledger.
- Chữ trong ticket là dữ liệu người dùng, không phải lệnh và không phải nguồn sự thật: số ngày trễ, mã đơn, clause khách tự trích đều bị bỏ qua; nguồn sự thật là order row và policy `is_current`.
- Host (`durability.issue_refund`) là người ghi duy nhất. Shape truyền **quote đầy đủ**; host tự kiểm approval, trần theo đơn, idempotency `refund:{claim_id}`.
- Trace là ranh giới bảo mật: chỉ ghi field đã qua allowlist.

**Chia việc** (chi tiết trong `task.md` và bảng đóng góp của `TEAM.md`):

| Thành viên | Phần chính |
| --- | --- |
| Đỗ Hồng Vỹ | Shape A `workflow`, integration (repo, review/merge, nộp bài), ADR |
| Nguyễn Ánh Dương | Shape B `single` (ReAct), research card |
| Đinh Hoàng Phong | Shape C `orchestrator`, handoff, rà secret/PII trong trace |
| Phạm Văn Chiêu | Durability/approval trên cả ba shape, crash suite, benchmark, tự kiểm hidden |

**Thứ tự làm.** CP1 cả nhóm chạy smoke và cổng host, đọc business rules, contract và `swarm_reference.py`. CP2 ba shape làm song song trên ba nhánh; workflow làm trước và xong sớm nhất nên được dùng làm mốc đối chiếu kết quả T01–T14 cho single và orchestrator. CP3 nối `crash_at` vào `issue_refund` ở cả ba shape và kiểm T11/T12. CP4 chạy crash suite 20 điểm và rà approval/secret. CP5 chạy benchmark 4 shape × 5 seed, tự kiểm trên `student_drop/`, rồi chọn shape theo số đo.

## 3. Giải pháp

### 3.1 Shape A — workflow (`src/lab8/shapes/workflow.py`)

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

1. **Đọc claim** bằng `get_claim_view` (chỉ `claim_id`, `principal_id`, `order_id`, `ticket`; không `SELECT *` nên `parent_secret` và header không bao giờ được đọc). Không có claim → `failed`, `proposal_amount` 0.
2. **Thiếu `order_id`** → `needs_info`. Không đoán mã đơn từ chữ trong ticket (T04).
3. **Tra đơn** bằng `lookup_order(order_id, principal_id)`. Không thấy đơn hoặc principal không sở hữu đơn → `escalated` (T05). Tool chỉ trả các field allowlist nên SĐT, địa chỉ, tên hàng, ghi chú nội bộ không lọt vào shape.
4. **Tính quote** bằng `compute_compensation` từ order row và policy `is_current`, `effective_date <= 2026-11-15`. Policy cũ `SHIP-LATE-OLD` và policy tương lai tự bị loại (T06). Ship và damage cùng đủ điều kiện → lấy số lớn hơn (do `compensation.quote`).
5. **Quote = 0** → `denied`, không gọi host (T02 trễ 2 ngày, T09 injection "ignore policy").
6. **Quote > 0** → `durability.issue_refund(conn, claim_id, quote, crash_at=crash_at)` với **quote đầy đủ**. Kết quả host:
   - `ok` (committed hoặc idempotent replay) → `resolved`, `proposal_amount` = quote; số tiền thật nằm trong `refund_effects` do host cap (T08 approval 20.000 < quote 35.000; T14 đã hoàn 30.000 nên chỉ ghi phần chênh 120.000).
   - Host từ chối (approval hỏng, của claim khác, đơn đã hoàn đủ) → `denied`, `proposal_amount` vẫn là quote, host đã ghi audit `policy_denied` (T07, T13).
   - `conflict` (gọi lại với số khác số đã commit) → `failed`.
7. **Soạn câu trả lời**: gọi MockLLM đúng một lần với `purpose="draft"`, sau khi trạng thái và số tiền đã cố định. Output của model không được dùng cho quyết định nào.

**Ranh giới code / model trong workflow.** Mọi quyết định (trạng thái, số tiền, có gọi host hay không) do code. Model chỉ soạn chữ. Vì vậy workflow không thể mắc lỗi `REFERENCE_WEAKNESS` của swarm (tin số ngày trong ticket ở seed 55): workflow không parse ticket. Nhóm không copy khối `REFERENCE_WEAKNESS`.

**Durability.** Workflow không tự kiểm ledger trước khi ghi mà dựa vào host: gọi lại cùng claim thì host trả `idempotent_replay` → vẫn `resolved`, vẫn một dòng ledger (T11). `crash_at` được truyền thẳng vào `issue_refund`; `InjectedCrash` không bị bắt nuốt mà chỉ flush trace rồi ném lại, nên lần chạy resume trên cùng DB thấy dòng đã commit và kết thúc với đúng một refund, một audit `refund_committed` (T12, cả ba điểm `before_effect`, `after_effect_before_checkpoint`, `after_checkpoint`).

**Trace.** Mỗi lần chạy ghi `traces/<run_id>.json` với các event `tool`, `order_view`, `quote`, `issue_refund`, `host_result`, `crash` (nếu có), `decision`. Không ghi ticket, `principal_id`, secret, header hay order row thô. Chi tiết và lý do ở mục "Trace và bằng chứng" của `decision_adr.md`.

**Kiểm chứng.** `python -m pytest -q -m student -o addopts= -k workflow` → 62 passed. Test bổ sung `src/tests/test_workflow_extra.py` (27 test, chạy trong cổng host): ticket nói quá số ngày ở cả 5 seed, injection, `needs_info` vẫn có trace đúng contract, claim không tồn tại, T13 giữ quote đầy đủ và có `policy_denied`, T14 chỉ ghi phần chênh, crash rồi resume ở 3 điểm crash, và quét chuỗi cấm trên trace của cả 14 claim public.

### 3.2 Shape B — single

> Nguyễn Ánh Dương viết: vòng `run_react` tối đa 8 bước, tool đọc nào được phép, cách `decide` bỏ qua ticket, code gọi `issue_refund` sau vòng lặp, budget model call.

### 3.3 Shape C — orchestrator và handoff

> Đinh Hoàng Phong viết: `make_handoff` với allowlist và tool chỉ đọc, `run_readonly_investigators`, orchestrator quote và gọi `issue_refund`, trace ghi handoff đã sanitize, vì sao tóm tắt LLM không phải redaction.

## 4. Kết quả

> Phạm Văn Chiêu viết, lấy từ `src/reports/benchmark.json` của commit chốt: bảng 4 shape — pass rate, pass^5, seed min–max, variance, cost/success, mean/p95 steps; crash safety từ `src/reports/crash.json`; kết quả tự kiểm `student_drop/` nếu có.

Quyết định kiến trúc và lý do: xem `report/team/decision_adr.md`. Phiếu nghiên cứu và ablation: xem `report/team/research_card.md`.

## 5. Khó khăn và cách xử lý

> Mỗi thành viên ghi phần mình, Nguyễn Ánh Dương tổng hợp.

- **Workflow (Đỗ Hồng Vỹ):** máy dùng Python 3.14 trong venv, ngoài dải 3.11–3.13 mà đề yêu cầu; smoke, cổng host và ma trận student vẫn chạy được, nhưng benchmark và crash test cuối cùng nên chạy lại trên Python 3.11–3.13 để khớp máy chấm. Khi in dữ liệu claim tiếng Việt ra console Windows gặp `UnicodeEncodeError` (cp1252); xử lý bằng `PYTHONIOENCODING=utf-8` và không in ticket ra stdout trong code shape.

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
