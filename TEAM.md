# Team

## Thông tin nhóm

- Tên nhóm: BuaDi
- Lớp: L3B
- Repo nhóm: `K5-L3B-DAY08-BuaDi-FromWorkflowsToAgents` (xem [SUBMISSION.md](SUBMISSION.md))
- URL repo, nhánh nộp, commit chốt: https://github.com/Do-Hong-Vy/K5-L3B-DAY08-BuaDi-FromWorkflowsToAgents, nhánh `main`, commit chốt:

## Thành viên

| STT | Họ tên           | MSSV        | Email                   | GitHub        | Vai trò     |
| --: | ---------------- | ----------- | ----------------------- | ------------- | ----------- |
|   1 | Đỗ Hồng Vỹ       | 2A202604107 | 26ai.vydh@vinuni.edu.vn | Do-Hong-Vy    | Nhóm trưởng — workflow + integration |
|   2 | Nguyễn Ánh Dương | 2A202604087 |                         | nganhduong123 | Single (ReAct) |
|   3 | Đinh Hoàng Phong | 2A202604090 |                         | phog2811      | Orchestrator + handoff |
|   4 | Phạm Văn Chiêu   | 2A202604033 | 26ai.chieupv@vinuni.edu.vn | pvchiu        | Ledger/crash + evaluation |

Gợi ý chia vai:

- Nhóm 6 người: integration; workflow; single agent; orchestrator; ledger/policy/crash; eval/report.
- Nhóm 4 người: workflow + integration; single; orchestrator + handoff; ledger + evaluation.

## Bảng đóng góp

`python -m lab8.check_submission` đọc bảng này bằng máy: giữ nguyên tiêu đề `## Bảng đóng góp` và các cột. Mỗi người một dòng: commit có nội dung và ít nhất một test đã thêm hoặc sửa.

| Người | Vai | Commit | Test đã thêm hoặc sửa |
| ----- | --- | ------ | --------------------- |
| Đỗ Hồng Vỹ | Workflow + integration | bd65064 | `tests/test_workflow_extra.py` (27 test) |
| Nguyễn Ánh Dương | Single (ReAct) | dc851fb | `tests/test_single_extra.py` (43 test) |
| Đinh Hoàng Phong | Orchestrator + handoff | ed04930 | `tests/test_orchestrator_handoff_extra.py` (30 test) |
| Phạm Văn Chiêu | Ledger/crash + evaluation | ad2241a | `tests/test_durability_extra.py` (14 test) |

## Cá nhân

Mỗi thành viên đồng thời tạo một báo cáo riêng trong `report/` theo dạng:

```text
report/team/MSSV_HoTen.md
```

Ví dụ: `report/team/20241234_NguyenVanAn.md`.

Sao chép mục dưới đây cho từng thành viên.

## 2A202604087_NguyenAnhDuong

### Phần việc phụ trách

- Shape B `single`: `src/lab8/shapes/single.py` (CP2 + CP3).
- Test riêng: `src/tests/test_single_extra.py` (43 test).
- Báo cáo: `report/team/research_card.md` (viết phiếu, chạy ablation R2); mục 3.2 và tổng hợp mục 5 của `report/team/group_report.md`.

### Đóng góp cụ thể

- Cài đặt agent ReAct chạy trong `lab8.runtime.run_react` với `MAX_STEPS = 8`.
- Registry chỉ chứa tool đọc; `decide` chỉ đọc từ tool view và bỏ qua ticket.
- Quote lấy từ `compute_compensation`, truyền quote đầy đủ vào `durability.issue_refund`.

### Bằng chứng

- `python -m pytest -q -m student -o addopts= -k "single and not workflow and not orchestrator and not swarm"` → 62 passed.
- `report/team/2A202604087_NguyenAnhDuong.md`.

## 2A202604090_DinhHoangPhong

### Phần việc phụ trách

- Shape C `orchestrator`: `src/lab8/shapes/orchestrator.py` (CP2 + CP3).
- Test riêng: `src/tests/test_orchestrator_handoff_extra.py` (30 test).
- Rà soát secret/PII, bảo đảm Trace contract v1 và fail-closed (CP4.3, CP4.4).
- Mục 3 (Shape C), 6, 7, 8 trong `group_report.md` và mục Trace trong ADR.

### Đóng góp cụ thể

- Dựng handoff an toàn qua `make_handoff` với allowlist `handoff.v1`.
- Giao investigator chạy các tool chỉ đọc; orchestrator trực tiếp tính quote và gọi `durability.issue_refund`.
- Rà soát không để lộ secret / PII trên 14 claims public × 5 seed.

### Bằng chứng

- `python -m pytest -q -m student -o addopts= -k orchestrator` → 62 passed.
- `report/team/2A202604090_DinhHoangPhong.md`.

## 2A202604107_DoHongVy

### Phần việc phụ trách

- Nhóm trưởng, integration: tạo repo, chia việc (`task.md`), review/merge PR, nộp bài.
- Shape A `workflow` (`src/lab8/shapes/workflow.py`), ADR, mục 1–2–3.1 của `group_report.md`.

### Đóng góp cụ thể

- Viết workflow theo các bước cố định; tiền do `compute_compensation` tính từ order row và policy hiện hành; truyền quote đầy đủ và `crash_at` vào `durability.issue_refund`.
- Thêm `src/tests/test_workflow_extra.py` (27 test chạy trong cổng host).
- Viết `report/team/decision_adr.md` (chọn `workflow`).

### Bằng chứng

- `python -m pytest -q -m student -o addopts= -k workflow` → 62 passed.
- `R-workflow-C-002-s55`, `R-workflow-C-014-s11` trong `src/reports/benchmark.json`.
- Báo cáo cá nhân: `report/team/2A202604107_DoHongVy.md`.

## 2A202604033_PhamVanChieu

### Phần việc phụ trách

- Ledger, durability, crash test suite; approval & policy audit; benchmark và evaluation.
- Rà soát tính đúng đắn về tiền & approval của cả 3 shape; chạy crash suite 20 kịch bản; chạy benchmark 4 shape × 5 seed.
- Phối hợp ablation cho `research_card.md` và viết Mục 4 Kết quả của `group_report.md`.

### Đóng góp cụ thể

- Thêm bộ test độ bền `src/tests/test_durability_extra.py` (12 test kiểm tra idempotency, crash-recovery tại 3 điểm inject, bảo toàn audit log, ngăn chặn conflict amount).
- Lập checklist ma trận 14 public claims (T01–T14) đối chiếu luật bồi thường và approval để nhóm bám sát.
- Chạy và kiểm soát `src/reports/crash.json` đạt `crash_safety = 20/20` (Must-pass 3).
- Chạy ma trận benchmark `src/reports/benchmark.json` và tổng hợp số liệu cho ADR, research card và group report.

### Bằng chứng

- `python -m pytest -q -k durability` → passed.
- `crash_safety = 20/20` trong `src/reports/crash.json`.
- Báo cáo cá nhân: `report/team/2A202604033_PhamVanChieu.md`.
