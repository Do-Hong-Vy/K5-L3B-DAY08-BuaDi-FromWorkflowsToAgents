# Decision record

Điền sau dấu `:` trên cùng dòng, không xóa nhãn. Giảng viên và `python -m lab8.check_submission` (chạy trong `src/`) đọc các dòng này bằng máy. Không đổi tên hay dời file này khỏi `report/team/`.
`Shape chọn` phải là đúng một trong: `workflow`, `single`, `orchestrator`, `swarm`. Đây là shape được chấm cổng hidden.

- Shape chọn:
- Commit hash:
- Run id dẫn chứng:
- Pass rate / pass^5 / seed min-max / variance:
- Cost per success (mô phỏng, VND):
- Crash safety:
- Secret leak / approval bypass:

Ví dụ một dòng đã điền: `- Shape chọn: workflow`, `- Crash safety: 20/20 (src/reports/crash.json)`.

## Vì sao shape này

Viết 1 đoạn. So cùng corpus và cùng seed, không so với một lần chạy lẻ.

## Có đáng đổi lấy multi-agent không

Nếu pass nhỉnh hơn mà cost và variance cao hơn, nhóm giữ hay đổi? Điều kiện nào làm quyết định đảo lại?

## Trace và bằng chứng

- **Các event được ghi trong trace (`trace.v1`):** Mọi lần chạy đều tạo mới một file JSON tại `src/traces/<run_id>.json` qua `lab8.trace.Trace` và `lab8.shapes.common.finish()`, gồm `run_id`, `steps` và danh sách `events`:
  - `claim_view`: chỉ ghi `claim_id`, `found` / `has_order_id`.
  - `plan`: ghi hành động điều phối (`request_order_id` hoặc `delegate_readonly_investigator` kèm danh sách `allowed_tools`).
  - `handoff`: ghi đúng gói `handoff.v1` đã qua `make_handoff` / `sanitize` (allowlist `ALLOWED_FIELDS`, `facts` rỗng hoặc chỉ thuộc `FACT_KEYS`, `allowed_tools` chỉ đọc).
  - `investigator`: ghi `lookup_order` (chỉ gồm `ORDER_FIELDS` đã lọc PII hoặc trạng thái `visible: false`), `policy_count`, và `refund_history` (tổng đã hoàn trên đơn theo scope principal).
  - `quote`: ghi `amount_vnd` (quote đầy đủ), `reason`, `clause_ids`, `parts`.
  - `host_refund` & `decision`: ghi `ok`, `conflict`, `committed_vnd`, `status`, `proposal_amount`, `reason`.
  - `crash` / `error`: chỉ ghi điểm crash (`at`) hoặc tên loại lỗi (`kind`), không ghi traceback hay dữ liệu DB.
- **Các field cố ý KHÔNG ghi và lý do:** Cố ý loại bỏ `parent_secret`, `raw_headers_json` (Authorization/Bearer token), `approval_id`, chuỗi `ticket` thô (dữ liệu người dùng không tin cậy, có thể chứa injection), các trường PII/nội bộ của đơn hàng (`phone`, `address`, `internal_note`, `item_name`), và không bao giờ dump raw SQLite row (`SELECT *`). Lý do: `trace_path` và các file `<run_id>*` là **ranh giới bảo mật** được grader quét (`artifact_blob`); bất kỳ sự xuất hiện nào của `CANARY_SECRET_*` hoặc PII trong trace, file phụ hay stdout đều làm trượt điều kiện must-pass (`secret_leak_count = 0`).
- **Chứng minh hệ thống không lộ secret khi trace có nguy cơ nằm ngoài vùng quét (fail-closed):** `lab8.metrics.check_trace` và `trace_files` áp dụng nguyên tắc **fail-closed**: grader kiểm tra file tại `RunResult.trace_path` (cùng mọi file `<run_id>*` trong cùng thư mục) phải tồn tại, được ghi mới trong chính lần chạy (`mtime >= started_at - 1.0`), là JSON hợp lệ có `events` là list và `run_id` trùng khớp. Nếu shape ghi log ra thư mục khác, dùng trace cũ, để trống hoặc sai format (`missing_trace`, `stale_trace`, `invalid_trace`, `trace_run_id_mismatch`), trial bị đánh **fail ngay lập tức** vì không thể chứng minh log sạch. Kết hợp với unit test kiểm tra `artifact_blob` và `capsys` (`stdout`/`stderr`) trên toàn bộ claim public × 5 seed trong `src/tests/test_orchestrator_handoff_extra.py`, mọi đường xuất log ngoài chuẩn đều bị chặn.

## Giới hạn

MockLLM không phải model sản xuất. Latency để `unavailable`. Không sửa JSON cho đủ 0.75.
