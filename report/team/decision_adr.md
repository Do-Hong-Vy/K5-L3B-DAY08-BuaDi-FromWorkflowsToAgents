# Decision record

Điền sau dấu `:` trên cùng dòng, không xóa nhãn. Giảng viên và `python -m lab8.check_submission` (chạy trong `src/`) đọc các dòng này bằng máy. Không đổi tên hay dời file này khỏi `report/team/`.
`Shape chọn` phải là đúng một trong: `workflow`, `single`, `orchestrator`, `swarm`. Đây là shape được chấm cổng hidden.

- Shape chọn: workflow
- Commit hash:
- Run id dẫn chứng: R-workflow-C-014-s11, R-workflow-C-013-s11, R-workflow-C-002-s55 (đối chứng R-swarm-C-002-s55) trong src/reports/benchmark.json
- Pass rate / pass^5 / seed min-max / variance: 1.000 / 1.000 / 1.000–1.000 / 0.000000 (workflow, 14 claim public × 5 seed = 70 trial, src/reports/benchmark.json)
- Cost per success (mô phỏng, VND): 28.79 (workflow) so với 49.57 (swarm), src/reports/benchmark.json
- Crash safety: 20/20 (src/reports/crash.json)
- Secret leak / approval bypass: 0 / 0 (0 trial leak_suspect trong src/reports/benchmark.json; T07, T13 bị host chặn và có audit policy_denied)

Ví dụ một dòng đã điền: `- Shape chọn: workflow`, `- Crash safety: 20/20 (src/reports/crash.json)`.

## Vì sao shape này

Trên cùng corpus public (14 claim T01–T14), cùng 5 seed `11,22,33,44,55`, cùng MockLLM và cùng bảng giá `config/pricing.yaml`, workflow đạt pass rate 1.000 và pass^5 1.000, variance giữa các seed bằng 0. Swarm tham chiếu đạt 0.986 / 0.929, variance 0.000816 (seed min 0.929 ở seed 55). Workflow cũng rẻ hơn: 28.79 VND mô phỏng mỗi lần thành công, so với 49.57 của swarm, vì chỉ gọi model 1 lần mỗi trial (soạn câu trả lời) và trung bình 2.79 tool call, trong khi swarm gọi model 3 lần và 4.66 tool call. Bài toán claim hoàn phí là chuỗi tuần tự, có luật rõ: đọc claim → kiểm đơn và principal → tính quote theo policy hiện hành → host kiểm approval, trần theo đơn, idempotency. Không có bước nào cần model suy luận mở để quyết định, nên shape ít tự chủ nhất là workflow đã làm được việc. Thêm tự chủ chỉ làm tăng cost và mở thêm chỗ để model tin chữ trong ticket, như lỗi của swarm ở `R-swarm-C-002-s55`: ticket ghi trễ 5 ngày, order ghi 2 ngày, swarm trả 20.000 VND thay vì từ chối. Workflow không đọc số trong ticket nên `R-workflow-C-002-s55` vẫn `denied`.

Số của `single` và `orchestrator` lấy từ cùng file `src/reports/benchmark.json` của commit chốt (xem bảng ở mục 4 của `group_report.md`). Vì workflow đã đạt trần 1.000 trên public, hai shape này nhiều nhất chỉ bằng workflow về pass rate, và tốn thêm model call cho vòng ReAct hoặc investigator.

## Có đáng đổi lấy multi-agent không

Không, với dữ liệu hiện có. Không có mức pass rate nào nhỉnh hơn để đổi lấy cost và variance cao hơn: workflow đã ở 1.000 với variance 0, còn swarm vừa tốn hơn khoảng 72% cost/success vừa có variance khác 0. Nhóm giữ workflow.

Quyết định sẽ đảo lại nếu:

- Ticket thật chứa dữ kiện **chỉ có trong chữ** mà không có cột có cấu trúc nào thay thế (ví dụ mô tả hư hỏng cần phân loại, nhiều đơn trong một ticket). Khi đó cần model đọc hiểu, và single hoặc orchestrator đo được pass cao hơn workflow trên bộ có nhãn mới là lý do để đổi.
- Việc điều tra chia được thành nhiều nhánh độc lập (nhiều nguồn dữ liệu, nhiều hệ thống ngoài) và latency thật trở thành ràng buộc. Lúc đó orchestrator với investigator song song có thể đáng tiền. Trên LogiX hiện tại quote phụ thuộc order nên không song song được.
- Pass rate hidden của workflow dưới 0.75 vì các case mà luật cố định không bao được, trong khi shape khác qua được với cùng must-pass.

Trong mọi trường hợp, số tiền, approval và idempotency vẫn do code của host quyết; đổi shape chỉ đổi ai đọc và soạn chữ.

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

- MockLLM không phải model sản xuất; kết quả cố định theo seed nên variance của workflow bằng 0 là do thiết kế, không chứng minh model thật cũng ổn định như vậy.
- Latency để `unavailable`; không có số latency nào trong ADR này.
- Cost là giá mô phỏng trong `config/pricing.yaml`, không phải hóa đơn API.
- Bộ public chỉ có 14 claim; pass 1.000 trên public chưa chứng minh pass trên hidden 40 claim × 5 seed. Không sửa JSON cho đủ 0.75.
