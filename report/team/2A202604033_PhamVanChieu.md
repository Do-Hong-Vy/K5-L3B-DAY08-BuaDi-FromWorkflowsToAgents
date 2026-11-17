# Báo cáo cá nhân — 2A202604033_PhamVanChieu

## 1. Thông tin thành viên

- Họ tên: Phạm Văn Chiêu
- MSSV: 2A202604033
- Email: 26ai.chieupv@vinuni.edu.vn / chieupham1011@gmail.com
- GitHub: pvchiu

## 2. Phần việc phụ trách

- **Vai trò:** Ledger/durability/crash + approval audit + benchmark/evaluation (M4).
- **Trách nhiệm kỹ thuật:**
  - Kiểm soát tính toàn vẹn của giao dịch hoàn tiền (idempotency, ACID qua SQLite transaction, chống hoàn tiền kép khi crash).
  - Viết bộ test kiểm thử độ bền hệ thống: `src/tests/test_durability_extra.py`.
  - Giám sát 3 điều kiện Must-pass: không hoàn tiền sai approval (`approval_bypass_count = 0`), crash safety đạt `20/20`, không lộ `CANARY_SECRET_*`.
  - Phụ trách đo đạc thực nghiệm: chạy suite `crash_test`, chạy benchmark 4 shapes × 5 seeds tạo `src/reports/crash.json` và `src/reports/benchmark.json`.
  - Đóng góp báo cáo: Cung cấp số liệu cho `decision_adr.md`, chạy thực nghiệm ablation cho `research_card.md`, và viết Mục 4 (Kết quả) trong `group_report.md`.

## 3. Đóng góp cụ thể

**Commit chính:** `68d2a19` — `feat(durability): add durability test suite, T01-T14 checklist, and personal report for Pham Van Chieu`

**Kiểm soát giao dịch & Độ bền (Durability & Idempotency):**
- Xác minh và bảo đảm quy tắc idempotency: Khóa `refund:{claim_id}` đảm bảo khi replay/retry nhiều lần cùng một claim thì chỉ duy nhất một bản ghi được ghi vào `refund_ledger` và một sự kiện `refund_committed` trong `audit_events`.
- Kiểm tra cơ chế chống conflict amount: Nếu cùng một claim gọi lại với số tiền khác số tiền đã commit trước đó, hệ thống lập tức phát hiện xung đột (`conflict: True`), giữ nguyên dữ liệu gốc và trả về trạng thái `failed`.
- Khẳng định tính an toàn khi gặp sự cố (Crash Recovery): Với 3 điểm inject crash (`before_effect`, `after_effect_before_checkpoint`, `after_checkpoint`), khi hệ thống crash và tiến hành resume trên cùng database, giao dịch luôn phục hồi chính xác, không bao giờ sinh ra khoản hoàn tiền kép.

**Bộ test đã thêm (`src/tests/test_durability_extra.py`, 14 test):**
1. `test_idempotent_replays_never_duplicate_ledger_entry`: Replay 3 lần cùng một claim $\rightarrow$ duy nhất 1 dòng ledger, 1 audit `refund_committed`.
2. `test_idempotency_key_strictly_matches_contract`: Kiểm tra idempotency key luôn có định dạng `refund:{claim_id}`.
3. `test_different_amount_replay_triggers_conflict_and_leaves_ledger_intact`: Gọi lại claim với số tiền khác $\rightarrow$ xung đột, không ghi đè số tiền cũ.
4. `test_issue_refund_crash_and_resume_durability` (parametrize 3 điểm): InjectedCrash tại `before_effect`, `after_effect_before_checkpoint`, `after_checkpoint` $\rightarrow$ resume luôn đúng 1 refund.
5. `test_crash_after_effect_before_checkpoint_resumes_via_ledger`: Minh chứng checkpoint mất không ảnh hưởng vì ledger đã cam kết (ACID).
6. `test_workflow_shape_never_swallows_injected_crash`: Đảm bảo shape không nuốt ngoại lệ `InjectedCrash`.
7. `test_expired_approval_is_rejected_without_refund`: Approval hết hạn $\rightarrow$ không tạo ledger.
8. `test_revoked_approval_is_rejected_without_refund`: Approval bị thu hồi $\rightarrow$ bị từ chối an toàn.
9. `test_mismatched_claim_approval_is_rejected`: Approval thuộc về claim khác $\rightarrow$ host từ chối (`approval_claim_mismatch`).
10. `test_outside_principal_scope_rejected`: Đơn không thuộc principal sở hữu $\rightarrow$ từ chối an toàn.
11. `test_order_cap_enforced_against_prior_refunds`: Đơn đã hoàn đủ $\rightarrow$ bị chặn bởi trần đơn hàng (`order_already_refunded`).
12. `test_partial_order_refund_caps_amount_correctly`: Host cho phép hoàn bù phần chênh lệch tới trần đơn hàng.

**Đo đạc & Đánh giá (Evaluation):**
- Thiết lập checklist 14 ca kiểm thử chuẩn (T01–T14) từ `docs/business_rules.md` để các thành viên code shape bám sát.
- Chạy tự động crash test suite và benchmark matrix, trích xuất dữ liệu pass rate, pass^5, variance và cost per success cho ADR.

## 4. Bằng chứng

- Bộ test độ bền: `src/tests/test_durability_extra.py` (14 test).
- Lệnh chạy test: `python -m pytest -q -k durability` $\rightarrow$ `14 passed`.
- Crash safety suite: `python -m lab8.crash_test --count 20 --out reports/crash.json` $\rightarrow$ đạt **`crash_safety = 20/20`**.
- File benchmark: `src/reports/benchmark.json` (đủ 4 shape, 14 claims, 5 seeds: 11, 22, 33, 44, 55).
- Báo cáo kết quả: Mục 4 trong `report/team/group_report.md`.

## 5. Công cụ AI đã dùng

- **Công cụ:** Antigravity (Google DeepMind - Gemini 3.8 Flash).
- **Mục đích sử dụng:**
  - Hỗ trợ xây dựng các kịch bản test độ bền góc cạnh (edge cases: crash tại các ranh giới transaction, replay lệch amount, approval mismatch).
  - Hỗ trợ tổng hợp checklist 14 claims chuẩn hóa từ bộ quy tắc nghiệp vụ.
  - Phân tích cơ chế ACID transaction của SQLite đối chiếu với checkpoint đơn lẻ.
- **Cách tự kiểm tra và thẩm định:**
  - Chạy thực tế toàn bộ test suite trên cổng host và cổng student bằng `pytest`.
  - Soi trực tiếp bảng `refund_ledger` và `audit_events` trong file SQLite để xác nhận cơ chế idempotency hoạt động chính xác.
  - Đối chiếu số liệu trong các báo cáo hoàn toàn từ file JSON do script sinh ra, không can thiệp thủ công.

## 6. Tự đánh giá

- Hoàn thành đầy đủ các tiêu chuẩn về tính toàn vẹn dữ liệu và độ bền theo yêu cầu của Rubric (C3 - Durability 20 điểm).
- Đảm bảo hệ thống tuân thủ nghiêm ngặt 3 điều kiện Must-Pass: Không bao giờ refund khi thiếu approval hợp lệ, đạt 20/20 crash safety, và bảo vệ an toàn bí mật canary.
- Nắm vững ranh giới giữa Ledger ACID và Checkpoint ứng dụng, giải thích tự tin trong buổi vấn đáp.
