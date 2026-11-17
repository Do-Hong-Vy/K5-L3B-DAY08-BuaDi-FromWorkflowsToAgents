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

Trace của workflow dùng `lab8.trace.Trace`, ghi ra `src/traces/<run_id>.json` (đúng contract v1: có `run_id` trùng `RunResult.run_id`, `events` là list, được ghi ở **mọi** nhánh return kể cả `needs_info`, `escalated`, `failed`, và được flush trước khi `InjectedCrash` lan ra ngoài). Các event:

| Event | Nội dung |
| --- | --- |
| `tool` (`get_claim_view`) | Chỉ `found` (true/false) |
| `tool` (`lookup_order`) | `visible` và `reason` (`ok`, `not_found`, `outside_principal_scope`) |
| `order_view` | Chỉ các field allowlist của `lookup_order`: `order_id`, `status`, `delay_days`, `shipping_fee_vnd`, `paid_vnd`, `damage_verified`, `carrier` |
| `quote` | Kết quả `compute_compensation`: `amount_vnd`, `reason`, `clause_ids`, `parts` |
| `issue_refund` | `proposed_vnd` (quote đầy đủ truyền cho host) |
| `host_result` | `ok`, `reason`, `conflict`, `amount_vnd` host đã ghi |
| `crash` | Điểm crash, chỉ khi có `crash_at` |
| `decision` | `status`, `proposal_amount`, `reason` cuối cùng |

Field cố ý **không** ghi: nội dung `ticket` (dữ liệu người dùng, có thể chứa injection hoặc thông tin cá nhân), `principal_id`, `parent_secret`, header thô, SĐT, địa chỉ, tên hàng, ghi chú nội bộ của order, và mọi claim row / order row thô. Shape không tự `SELECT *`; chỉ đọc qua `get_claim_view` và `lookup_order` nên những field này không bao giờ vào bộ nhớ của trace. Shape cũng không in gì ra stdout và không ghi file nào khác ngoài trace.

Nếu trace nằm ngoài chỗ scanner quét được thì không chứng minh được hệ thống sạch, vì scanner không đọc được log thì không thể nói log đó không lộ. Vì vậy nhóm giữ mọi output trong `traces/<run_id>*` để grader quét, và thêm test `tests/test_workflow_extra.py::test_trace_and_result_hold_no_forbidden_strings` quét trace và `RunResult` của cả 14 claim public tìm `CANARY_SECRET_`, `parent_secret` và các chuỗi cấm trong nhãn (SĐT, địa chỉ, tên hàng, `CANARY_INTERNAL_*`).

## Giới hạn

- MockLLM không phải model sản xuất; kết quả cố định theo seed nên variance của workflow bằng 0 là do thiết kế, không chứng minh model thật cũng ổn định như vậy.
- Latency để `unavailable`; không có số latency nào trong ADR này.
- Cost là giá mô phỏng trong `config/pricing.yaml`, không phải hóa đơn API.
- Bộ public chỉ có 14 claim; pass 1.000 trên public chưa chứng minh pass trên hidden 40 claim × 5 seed. Không sửa JSON cho đủ 0.75.
