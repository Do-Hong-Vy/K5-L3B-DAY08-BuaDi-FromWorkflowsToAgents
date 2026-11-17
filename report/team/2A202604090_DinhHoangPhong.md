# Báo cáo cá nhân — 2A202604090_DinhHoangPhong

## 1. Thông tin thành viên

- Họ tên: Đinh Hoàng Phong
- MSSV: 2A202604090
- Email: phong28112004fpt@gmail.com
- GitHub: Phog2811 (`phog2811`)

## 2. Phần việc phụ trách

- **Nhánh làm việc:** `feat/orchestrator`
- **Code chính:** Cài đặt **Shape C (`orchestrator`)** tại `src/lab8/shapes/orchestrator.py` (CP2 + CP3).
- **Bảo mật & Trace (CP4.3, CP4.4):** Thiết kế handoff allowlist (`handoff.v1`), rà soát không lộ secret/PII (`CANARY_SECRET_*`, `CANARY_INTERNAL_`, SĐT, địa chỉ, ghi chú nội bộ, tên hàng) trong trace, file phụ và stdout; đảm bảo không có trial nào vi phạm fail-closed (`missing_trace`, `stale_trace`, `invalid_trace`, `trace_run_id_mismatch`).
- **Test bổ sung:** Viết bộ test `src/tests/test_orchestrator_handoff_extra.py` (chạy trong cổng host `pytest -q`).
- **Báo cáo nhóm:** Phụ trách mục `## Trace và bằng chứng` trong `report/team/decision_adr.md`, và các mục `3 (Shape C — orchestrator)`, `6`, `7`, `8` trong `report/team/group_report.md`.

## 3. Đóng góp cụ thể

- **Triển khai `src/lab8/shapes/orchestrator.py`:**
  - Tách hàm `build_investigator_handoff` gọi `lab8.handoff.make_handoff` với danh sách tool chỉ đọc (`lookup_order`, `lookup_policy`, `lookup_refund_history`), không đưa `parent_secret`, `raw_headers`, lịch sử hay dòng claim thô vào `facts`.
  - Đọc claim qua `get_claim_view` (không dùng `SELECT *`), xử lý đúng mọi nhánh trạng thái theo `docs/contracts.md`: `unknown_claim` → `failed`, thiếu `order_id` (không rút từ text ticket) → `needs_info`, đơn ngoài phạm vi principal hoặc không tồn tại → `escalated`.
  - Giao cho investigator đọc qua `lab8.runtime.run_readonly_investigators` (chỉ có read tools, không có write registry).
  - Tiền hoàn do **code orchestrator** tính từ dữ liệu order có cấu trúc bằng `lab8.tools.compute_compensation` (bỏ qua số ngày/điều khoản khách tự ghi trong ticket, chỉ dùng policy `is_current` và `effective_date <= 2026-11-15`), rồi truyền **quote đầy đủ** vào `lab8.durability.issue_refund` để host kiểm `approval_id`, trừ phần đã hoàn của claim trước (T13/T14) và ghi ledger/audit idempotent theo khóa `refund:{claim_id}`.
  - Truyền `crash_at` vào `issue_refund`, ghi nhận sự kiện `crash` và flush trace trước khi để `InjectedCrash` lan truyền ra ngoài (CP3); bắt `HandoffError` và `ToolRejected` để không làm văng exception ngoài ý muốn.
  - Mọi nhánh return đều gọi `lab8.shapes.common.finish()` để ghi file trace mới theo chuẩn `trace.v1` và đồng bộ `refund_effects` / `committed_audit_count` từ SQLite.
- **Thêm bộ test `src/tests/test_orchestrator_handoff_extra.py` (13 test cases):**
  - Quét toàn bộ 14 claim public × 5 seed (`11, 22, 33, 44, 55`): kiểm `trial_pass`, `check_trace`, kiểm `handoff` trong trace chỉ chứa key thuộc `ALLOWED_FIELDS`, `facts` thuộc `FACT_KEYS`, `allowed_tools` thuộc `READONLY_TOOLS`, và không xuất hiện bất kỳ `CANARY_SECRET_*`, `CANARY_INTERNAL_*`, SĐT, địa chỉ, tên hàng nào trong trace hay stdout/stderr.
  - Kiểm `build_investigator_handoff` từ chối `issue_refund` / `append_audit` bằng `HandoffError` và loại bỏ các key nhạy cảm ngoài allowlist.
  - Kiểm `run_claim` bắt `HandoffError`, `ToolRejected`, xử lý `unknown_claim` trả `RunResult(status="failed")` kèm trace hợp lệ.
  - Kiểm nhánh `approval_claim_mismatch` và `approval_revoked` trả `denied` với `proposal_amount` đầy đủ và có audit `policy_denied`.
  - Kiểm crash & resume tại cả 3 điểm (`before_effect`, `after_effect_before_checkpoint`, `after_checkpoint`) chỉ tạo đúng 1 dòng `refund_ledger` và 1 audit `refund_committed`.
- **Commit chính:** `ed04930` (`feat/orchestrator` — `feat(orchestrator): implement shape C with sanitized handoff and extra tests`)

## 4. Bằng chứng

Tất cả lệnh chạy trong `src/` bằng `.venv`:

- `.\.venv\Scripts\python.exe -m pytest -q` (cổng host + `test_orchestrator_handoff_extra.py`): **`67 passed, 248 deselected`**.
- `.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= -k orchestrator`: **`62 passed, 253 deselected`** (đạt đủ 62/62 test ma trận T01–T14 của `orchestrator`).
- Kiểm tra benchmark riêng cho `orchestrator` trên `data/public_claims.jsonl` với 5 seed `11,22,33,44,55` (70 trials):
  - `pass_rate = 1.0`, `pass_5 = 1.0`, `seed_variance = 0.0`, `seed_min = 1.0`, `seed_max = 1.0`
  - `cost_per_success_vnd = 57.21` (tổng chi phí mô phỏng `4004.8` VND, `mean_model_calls = 2.0`, `mean_tool_calls = 5.57`, `mean_steps = 6.36`, `p95_steps = 7.0`)
- Kiểm tra quét toàn bộ 73 file `src/traces/R-orchestrator-*.json` sinh ra từ benchmark và test: `traces=73 leaks=0`, không có `missing_trace`, `stale_trace`, `invalid_trace`, hoặc `trace_run_id_mismatch`.

## 5. Công cụ AI đã dùng

- **Công cụ:** Google Antigravity (Gemini 4 Hydrogen).
- **Mục đích sử dụng:**
  - Tóm tắt tài liệu đề bài, contract (`docs/business_rules.md`, `docs/contracts.md`) và phân công trong `task.md`.
  - Hỗ trợ cài đặt môi trường `.venv`, triển khai `src/lab8/shapes/orchestrator.py`, viết bộ test `src/tests/test_orchestrator_handoff_extra.py` và soạn nháp các mục báo cáo được giao.
- **Cách tự kiểm tra kết quả:**
  - Đối chiếu trực tiếp từng nhánh xử lý của `orchestrator.py` với bảng contract trong `docs/contracts.md`, `handoff.py`, `runtime.py`, và `durability.py`.
  - Tự chạy toàn bộ cổng host (`pytest -q`), ma trận student (`pytest -q -m student -o addopts= -k orchestrator`), `lab8.benchmark` cho `orchestrator`, và kiểm tra nội dung JSON thực tế của các file `src/traces/R-orchestrator-*.json` (ví dụ `C-001`, `C-005`, `C-014`). Không bịa số liệu hay commit hash.

## 6. Tự đánh giá

- Hoàn thành đầy đủ code Shape C (`orchestrator`), tích hợp durability/crash safety (CP2 + CP3), bộ test bổ sung và kiểm tra rò rỉ secret/PII trên trace & stdout (CP4.3, CP4.4).
- Các phần phụ thuộc số liệu tổng hợp cả 4 shape và quyết định cuối cùng của nhóm (`decision_adr.md` phần thông số, `TEAM.md` bảng đóng góp, commit chốt) sẽ được phối hợp hoàn thiện sau khi các thành viên merge PR vào `main`.
