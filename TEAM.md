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
|   4 | Phạm Văn Chiêu   | 2A202604033 |                         | pvchiu        | Ledger/crash + evaluation |

Gợi ý chia vai:

- Nhóm 6 người: integration; workflow; single agent; orchestrator; ledger/policy/crash; eval/report.
- Nhóm 4 người: workflow + integration; single; orchestrator + handoff; ledger + evaluation.

## Bảng đóng góp

`python -m lab8.check_submission` đọc bảng này bằng máy: giữ nguyên tiêu đề `## Bảng đóng góp` và các cột. Mỗi người một dòng: commit có nội dung và ít nhất một test đã thêm hoặc sửa.

| Người | Vai | Commit | Test đã thêm hoặc sửa |
| ----- | --- | ------ | --------------------- |
| Đỗ Hồng Vỹ | Workflow + integration | | `tests/test_workflow_extra.py` (27 test) |

## Cá nhân

Mỗi thành viên đồng thời tạo một báo cáo riêng trong `report/` theo dạng:

```text
report/team/MSSV_HoTen.md
```

Ví dụ: `report/team/20241234_NguyenVanAn.md`.

Sao chép mục dưới đây cho từng thành viên.

## MSSV_HoTen

### Phần việc phụ trách

-

### Đóng góp cụ thể

-

### Bằng chứng

-

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
