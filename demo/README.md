# Trang demo Lab 8

Trang trình bày bài lab theo thứ tự CP1–CP5: luật nghiệp vụ, chạy thử từng claim qua shape workflow, ledger và crash, must-pass, benchmark 4 shape và quyết định kiến trúc.

Cách mở: mở file `demo/index.html` bằng trình duyệt (bấm đúp). Không cần cài gì; cần internet chỉ để tải font, không có internet thì trang dùng font hệ thống.

Số liệu nhúng trong trang lấy từ `src/reports/benchmark.json`, `src/reports/crash.json` (commit `0bc1326`) và từ lần chạy `src/lab8/shapes/workflow.py` trên từng claim public, seed 11. Nếu chạy lại benchmark hoặc sửa shape thì cần dựng lại trang để số khớp.

Thư mục này không thuộc phần được chấm: grader chỉ lấy ba file shape và `src/bonus/`.
