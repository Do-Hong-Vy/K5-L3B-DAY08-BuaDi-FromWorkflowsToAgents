# Research card

File này nằm cố định ở `report/team/research_card.md`; `python -m lab8.check_submission` đọc cột "Nhóm điền" bằng máy.

Phần này nối tiếp phần mini research ở buổi lý thuyết (slide 62–63). Chọn **một** câu R1–R4, điền 6 dòng, rồi biến nó thành **một ablation** chạy được trong lab: giữ nguyên model (MockLLM), tool, seed, corpus và giá, chỉ thay đổi một biến.

| Câu | Nguồn (thư viện tham khảo, slide 68–69) | Câu hỏi gợi ý cho lab |
| --- | --- | --- |
| R1 · Scaling | Google Research 2026, *Towards a Science of Scaling Agent Systems* | Task claims chủ yếu tuần tự hay song song được? Dự đoán thêm investigator sẽ làm pass rate và cost/success thay đổi thế nào. |
| R2 · Failure taxonomy | MAST, NeurIPS 2025, *Why Do Multi-Agent LLM Systems Fail?* | Các trial fail của swarm (seed 55) thuộc nhóm nào: lỗi giao việc, lệch mục tiêu, hay lỗi kiểm chứng? |
| R3 · Architecture choices | AgentArch, AACL 2026 | Nếu đổi topology mà giữ nguyên mọi thứ khác, biến nào phải cố định để kết luận còn đúng? |
| R4 · Evaluation confounders | EMNLP 2026, *Rethinking Evaluation of MAS Efficiency* | Làm sao chứng minh chênh lệch giữa A/B/C/D là do topology, không phải do prompt, tool hay seed? |

## Phiếu của nhóm

Điền vào cột cuối. Không xóa hai cột đầu.

| Field | Hướng dẫn | Nhóm điền |
| --- | --- | --- |
| CÂU | R1 / R2 / R3 / R4 | R2 · Failure taxonomy |
| SOURCE | Paper/blog, năm, URL, loại bằng chứng (benchmark, production report, blog kinh nghiệm) | Cemri et al., *Why Do Multi-Agent LLM Systems Fail?* (MAST), arXiv:2503.13657, 2025; bản v3 thuộc NeurIPS 2025 Datasets & Benchmarks track. https://arxiv.org/abs/2503.13657 . Loại bằng chứng: phân tích định tính có gán nhãn trên hơn 150 execution trace của các framework multi-agent (Grounded Theory, Cohen's Kappa 0.88 giữa người gán nhãn) |
| CLAIM | Một kết luận gốc của nguồn. Không viết rộng hơn phạm vi paper | Lỗi của hệ multi-agent gom được thành 14 failure mode trong 3 nhóm (thiết kế/đặc tả hệ thống, lệch pha giữa các agent, kiểm chứng tác vụ); nhiều lỗi đến từ thiết kế hệ thống chứ không chỉ từ giới hạn của LLM, nên cần sửa cấu trúc thay vì chỉ sửa prompt |
| BOUNDARY | Model / dataset / setup giới hạn kết luận đó | Trace lấy từ các framework multi-agent mã nguồn mở với LLM thật, trên các task lập trình/toán/tổng quát; không phải bài hoàn tiền có host gate. Lab này dùng MockLLM có seed, 14 claim public, và lỗi của swarm là lỗi cài sẵn (`REFERENCE_WEAKNESS`, seed % 5 == 0) chứ không phải lỗi phát sinh tự nhiên, nên chỉ dùng taxonomy để phân loại, không để ước lượng tần suất lỗi |
| HYPOTHESIS | Nếu đổi shape A→B (hoặc bật/tắt một thành phần), metric X sẽ đổi theo hướng nào, khoảng bao nhiêu | Trial fail của swarm (C-002 seed 55: tin số ngày trễ trong ticket thay vì `delay_days` của order) thuộc nhóm **kiểm chứng tác vụ** của MAST: số liệu khách tự khai không được đối chiếu với nguồn sự thật trước khi tính tiền. Nếu đổi swarm → single, trong đó `decide` chỉ đọc dữ kiện từ tool và không parse ticket, thì lỗi này biến mất: pass rate tăng từ 0.986 lên 1.000, pass^5 từ 0.929 lên 1.000, seed variance về 0; cost/success không tăng dù single gọi model nhiều hơn mỗi claim, vì swarm gửi nguyên ticket vào prompt và gọi nhiều tool hơn |
| METHOD | Biến giữ cố định: model, tools, seed, corpus, giá, evaluator. Biến duy nhất được thay đổi: … | Giữ cố định: MockLLM, bộ tool `lab8.tools`, seed 11/22/33/44/55, corpus `data/public_claims.jsonl` (14 claim), `config/pricing.yaml`, evaluator `lab8.metrics.trial_pass`, SQLite mới cho từng trial, as_of 2026-11-15 (đọc từ `controlled_variables` trong file report). Biến duy nhất được thay đổi: shape (`swarm` → `single`) |
| FAILURE / METRIC | Một lỗi dự kiến và cách đo nó: pass rate, pass^5, variance, cost/success, leak, bypass | Lỗi dự kiến: trả tiền theo số ngày trễ khách tự khai (`status resolved != denied` trên C-002). Đo bằng pass rate, pass^5, seed min–max, seed variance và cost/success trong `src/reports/ablation_r2_swarm_vs_single.json`; liệt kê run id các trial fail |

## Kết quả ablation

- Lệnh đã chạy (copy nguyên văn, trong `src/`): `python -m lab8.benchmark --shapes swarm,single --cases data/public_claims.jsonl --seeds 11,22,33,44,55 --out reports/ablation_r2_swarm_vs_single.json`
- Run id / file report: `src/reports/ablation_r2_swarm_vs_single.json`. Trial fail duy nhất: `R-swarm-C-002-s55`. Cùng claim, cùng seed ở single: `R-single-C-002-s55` → `denied`, đạt.
- Kết quả so với hypothesis: **đúng** trên bộ public.

  | Shape | pass rate | pass^5 | seed min–max | seed variance | cost/success (VND mô phỏng) | model call TB | tool call TB |
  | --- | --- | --- | --- | --- | --- | --- | --- |
  | swarm | 0.986 (69/70) | 0.929 | 0.929–1.000 | 0.000816 | 49.57 | 3.00 | 4.66 |
  | single | 1.000 (70/70) | 1.000 | 1.000–1.000 | 0 | 36.30 | 4.43 | 3.43 |

  Single gọi model nhiều hơn (4.43 so với 3.00 mỗi claim) nhưng cost/success vẫn thấp hơn, vì prompt của single không chứa ticket (ít token hơn), single gọi ít tool hơn, và swarm phải chia chi phí cho 69 thay vì 70 trial đạt.
- Giới hạn: MockLLM không phải model sản xuất, latency là `unavailable`. Lỗi của swarm do lab cài sẵn theo seed, nên kết quả chỉ cho thấy single loại được *đúng loại lỗi này*, không chứng minh single bền hơn swarm với LLM thật. Chỉ có 1 trial fail nên phân loại MAST dựa trên một trường hợp. Số liệu chạy trên commit đang làm việc của nhánh single; M4 cần chạy lại lệnh trên commit chốt để khớp file nộp.

Muốn đi xa hơn một ablation để lấy điểm cộng thì xem [docs/bonus_topics.md](../../docs/bonus_topics.md).
