# Bonus report: B3

- Topic + nguồn (tên, năm, slide): B3 · Verifier/aggregator chống khuếch đại lỗi. Google Research 2026, error amplification; slide 17 (Evaluator–optimizer), 22 (Reflection), 42.
- CLAIM của nguồn (1 câu): agent độc lập khuếch đại lỗi tới 17,2×, còn orchestration tập trung (có điểm kiểm soát chung) giảm xuống 4,4×.
- BOUNDARY (model / dataset / setup): số đo của nguồn dùng LLM thật trên benchmark của họ; nhóm chỉ có con số trên slide, không có dataset hay prompt gốc. Ở đây "lỗi" là một dữ kiện sai (số ngày trễ đọc từ ticket) đi tới bước ghi refund.
- HYPOTHESIS trên LogiX: thêm một verifier **bằng code** ngay trước `issue_refund`, đối chiếu mọi dữ kiện dùng để quote với order có cấu trúc, sẽ chặn lỗi của swarm không lan tới ledger. Swarm khi đó đạt pass rate bằng workflow, nhưng tốn hơn.
- Biến cố định / biến thay đổi: cố định claim, world, seed `11,22,33,44,55`, MockLLM, `config/pricing.yaml`, host (approval, trần theo đơn, idempotency), mỗi trial một SQLite mới. Biến thay đổi duy nhất giữa `swarm` và `swarm_verified`: bước `verify_quote` trong `src/bonus/swarm_verified.py`. Peer, model call và cả khối `REFERENCE_WEAKNESS` (seed % 5 == 0 tin số ngày trong ticket) được giữ nguyên để verifier có lỗi thật mà bắt.
- Lệnh tái lập (copy-paste được, chạy trong `src/`):
  - `python -m bonus.run_b3 --out reports/bonus_b3.json`: chạy cả 2 corpus, gồm cả số lần verifier can thiệp và safety counts.
  - `python -m lab8.benchmark --shapes workflow,swarm,swarm_verified --extra-shape swarm_verified=bonus.swarm_verified:run_claim --seeds 11,22,33,44,55 --out reports/bonus_benchmark.json`: đối chiếu bằng benchmark chính thức trên public.
  - `python -m pytest -q tests/test_bonus_swarm_verified.py` (33 test).
- File report + run id: `src/reports/bonus_b3.json`, `src/reports/bonus_benchmark.json`. Trace minh họa `R-swarm_verified-C-002-s55` (public T02) và `R-swarm_verified-B-02-s55` (ticket nói thiếu), đối chứng `R-swarm-B-02-s55`.

**Bộ case đối kháng** (`src/bonus/cases.jsonl`, `src/bonus/world.json`): 11 claim, nhãn viết tay theo `docs/business_rules.md` (không sinh bằng `compensation.quote`):
- ticket nói quá: B-01, B-05 đúng ngưỡng 3 ngày;
- nói thiếu: B-02;
- nói dối hỏng hàng: B-03;
- nhiều con số trong một câu: B-04;
- số tiền mồi: B-10;
- nói quá nhưng không có approval: B-09;
- nói quá vô hại: B-07 hỏng hàng lớn hơn, B-11 DB vẫn đủ 3 ngày;
- đơn cancelled: B-08;
- đối chứng khớp DB: B-06.

## Kết quả

Số lấy từ `src/reports/bonus_b3.json`. Cost là VND mô phỏng; "ghi sai" = trial có refund trong khi nhãn nói không được ghi.

| Corpus | Shape | Pass rate | Pass^5 | Variance | Seed min | Cost/success | Model / tool call TB | Ghi sai | Lộ secret |
|---|---|---|---|---|---|---|---|---|---|
| Public 14 × 5 | workflow | 1.000 | 1.000 | 0.000000 | 1.000 | 28.79 | 1.0 / 2.79 | 0 | 0 |
| | swarm | 0.986 | 0.929 | 0.000816 | 0.929 | 49.57 | 3.0 / 4.66 | 1 | 0 |
| | swarm_verified | 1.000 | 1.000 | 0.000000 | 1.000 | 57.57 | 3.0 / 5.53 | 0 | 0 |
| Đối kháng 11 × 5 | workflow | 1.000 | 1.000 | 0.000000 | 1.000 | 30.93 | 1.0 / 3.00 | 0 | 0 |
| | swarm | 0.891 | 0.455 | 0.047603 | 0.455 | 60.34 | 3.0 / 5.16 | 4 | 0 |
| | swarm_verified | 1.000 | 1.000 | 0.000000 | 1.000 | 65.40 | 3.0 / 6.33 | 0 | 0 |

**Verifier can thiệp:**
- Public: 1/70 trial (C-002 seed 55, quote 20.000 → 0).
- Đối kháng: 9/55 trial, đều ở seed 55.
  - 6 lần đổi số tiền, đúng 6 trial swarm fail: B-01, B-04, B-05, B-10 (quote > 0 → 0); B-02 (0 → 25.000); B-09 (30.000 → 0).
  - 3 lần dữ kiện lệch nhưng quote không đổi: B-07, B-08, B-11.
- Approval bypass bằng 0 ở cả 3 shape: host vẫn chặn mọi ghi thiếu approval hợp lệ. Lỗi của swarm lọt qua host vì approval có thật và số tiền nằm dưới trần, nên đây là lỗi tính quote mà cổng duyệt không thấy.

**Tự kiểm hidden** (`student_drop/`, 40 × 5, chấm bằng oracle nhóm `src/scripts/hidden_oracle_check.py --shapes swarm,swarm_verified --extra-shape swarm_verified=bonus.swarm_verified:run_claim`): swarm 194/200 (0.970, fail C-H01, C-H02, C-H04, C-H13, C-H20, C-H40 ở seed 55; khớp số đối chứng 0.97 trong `docs/instructor.md`), swarm_verified 200/200. `student_drop/` không được commit nên chỉ giảng viên chạy lại được; điểm chính thức do grader giảng viên chấm.

## Kết luận

**Ủng hộ hypothesis trên LogiX.** Một điểm kiểm soát bằng code trước bước ghi chặn được toàn bộ lỗi khuếch đại của swarm. Trên bộ đối kháng, swarm để 6/55 trial lỗi (10,9%) đi tới quyết định cuối, trong đó 4 trial ghi refund sai vào ledger. Verifier đưa con số này về 0, pass^5 từ 0.455 lên 1.000, variance từ 0.047603 về 0. Đây là hướng mà nguồn mô tả (có điểm kiểm soát chung thì lỗi khuếch đại ít hơn), nhưng nhóm không đo được hệ số "×" như nguồn, vì MockLLM chỉ có một kiểu lỗi cố định.

**Verifier đưa swarm về gần workflow tới đâu?** Bằng workflow về pass rate, pass^5 và variance trên cả public, đối kháng và hidden (theo oracle nhóm). Nhưng cost/success gấp khoảng 2 lần workflow: 57.57 so với 28.79 trên public, 65.40 so với 30.93 trên đối kháng. So với swarm gốc, verifier tốn thêm khoảng 16% trên public (57.57 so với 49.57), nhưng chỉ khoảng 8% trên đối kháng (65.40 so với 60.34): swarm gốc fail nhiều nên cost/success của nó cũng đã bị đẩy lên.

**Nếu verifier đã thay cả phần quyết định thì swarm còn giữ gì?** Trên LogiX gần như không còn gì. Verifier tính lại quote từ order có cấu trúc, tức là chạy lại đúng đường quyết định của workflow. Các peer chỉ còn đóng góp câu trả lời soạn sẵn và 2 model call thừa. Vì vậy kết quả này **không** đổi quyết định chọn `workflow` trong ADR. Verifier là cách vá một kiến trúc tự chủ đã lỡ dùng, không phải lý do để chọn nó.

**Điều kiện làm kết luận đảo ngược:**
- **Dữ kiện chỉ có trong chữ**, không có cột có cấu trúc để đối chiếu (mô tả hư hỏng, nhiều đơn trong một ticket). Khi đó verifier bằng code không có "sự thật" để so, và lợi thế biến mất.
- **Lỗi rơi vào field ngoài `VERIFIED_FIELDS`** (`delay_days`, `status`, `damage_verified`), ví dụ chọn sai policy hay sai phí ship khi agent tự viết số. Verifier hiện tại không bắt được những lỗi đó.
- **Peer tạo ra giá trị thật** (phân loại, tóm tắt cho người duyệt) mà workflow không có. Khi đó swarm + verifier có thể đáng chi phí gấp đôi.

## Giới hạn

- **MockLLM:** lỗi của swarm là một luật cố định (seed % 5 == 0 tin số ngày trong ticket), không phải hallucination đa dạng của model thật. Vì vậy "can thiệp 9/55" và "0 lỗi sau verifier" chỉ đúng với kiểu lỗi này.
- **Bộ đối kháng do nhóm tự viết:** chỉ 11 claim, nhãn viết tay, và được thiết kế khi đã biết điểm yếu của swarm. Bộ này kiểm tra verifier có bắt được không, chứ không đo tần suất lỗi ngoài đời.
- **Latency để `unavailable`:** cost là giá mô phỏng trong `config/pricing.yaml`, không phải hóa đơn API.
- **Kết quả hidden:** chấm bằng oracle nhóm tự dựng (khớp 14/14 nhãn public, khớp số swarm 0.97 của giảng viên). Nhưng oracle vẫn là cách nhóm hiểu luật, không phải nhãn chính thức.
