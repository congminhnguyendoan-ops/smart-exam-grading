# Kế hoạch demo báo cáo 13/10/2026 – khối BACKEND

Nguyên tắc (người dùng, 07/10/2026): **"mỏng ở bên trong, không mỏng ở chỗ nối"** – code đặt đúng chỗ, dùng lâu dài; chỗ làm
tạm ghi vào mục NỢ KỸ THUẬT (cuối file). Câu OMR "cần xem" **không bao giờ** được chấm như câu chắc chắn. Demo và test chỉ dùng
ảnh 0001–0028 (không đụng 0029–0040).

| Mốc | Việc | Trạng thái |
|---|---|---|
| B0 | Xuất lại mô hình OMR từ commit sạch | xong |
| B1 | Cấu hình CSDL qua `.env` + migration bổ sung | |
| B2 | Lớp dịch vụ chấm phiếu | |
| B3 | API FastAPI | |
| B4 | Kiểm chứng (pytest + đầu-cuối so với điểm tính độc lập) | |
| B5 | CLAUDE.md | |

## B0 – xuất lại mô hình OMR từ commit sạch (07/10/2026)
- `python tools/huan_luyen_omr.py xuat` chạy khi cây làm việc sạch, HEAD `3bcf190` → `models/omr_m{0,1}.json`:
  `git_head` `d0c9574` → `3bcf190`, `git_chua_commit` `[omr.py, huan_luyen_omr.py]` → `[]`.
- Phần mô hình (hệ số, chuẩn hoá, ngưỡng luật) **giống hệt** bản cũ (so JSON từng trường, trừ `sieu_du_lieu`).
- **Dự đoán trên 56 ảnh train giống hệt**: `omr.doc_phieu` với bản cũ và bản mới trên 56 ảnh (ảnh nắn đệm `data/_omr/anh`),
  so toàn bộ `KetQuaOMR` (trừ `thoi_gian_ms`): 56 ảnh, **0 ảnh khác**.

## B1 – cấu hình CSDL qua `.env` + migration (07/10/2026)
- `backend/config.py` đọc `smart_exam_db/.env` (`python-dotenv`, biến môi trường thật thắng); **không có mật khẩu mặc định trong
  code** – thiếu `DATABASE_URL` thì `LoiCauHinh` báo rõ. `.env` đã nằm trong `.gitignore` (kiểm: `git check-ignore`);
  `.env.example` có mẫu (mật khẩu giả). `tools/db_check.py` nay đọc cấu hình từ `backend.config` (bỏ chuỗi kết nối có mật khẩu
  khỏi code). `storage/` (ảnh phiếu backend lưu) thêm vào `.gitignore`.
- `backend/migrate.py` + `backend/migrations/001_backend_bo_sung.sql`: **chỉ thêm cột / chỉ mục**, `IF NOT EXISTS`, ghi bảng
  `schema_migrations`. Đã áp lên CSDL `smart_exam` (người dùng cho phép thay đổi bổ sung): `sheet_answers.{needs_review,
  review_reasons, omr_state, omr_selected_options, reviewed_by, reviewed_at}`, `answer_sheets.{reject_code, omr_detail,
  original_filename}`. Chạy lại 2 lần liên tiếp OK; áp lại trực tiếp file SQL 2 lần (rollback) OK. **Không xoá / reset gì**;
  số dòng các bảng không đổi (exams 1, answer_sheets 9, sheet_answers 90, results 8, review_queue 5).
- Chưa động tới: mật khẩu trong `00_create_database.sql`, `run_all.bat/.sh`, `HUONG_DAN.md` (script tạo CSDL cần nó) – nợ.
