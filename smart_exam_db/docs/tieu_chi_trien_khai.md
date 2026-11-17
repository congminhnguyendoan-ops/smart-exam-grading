# Tiêu chí – Lệnh AU: chuẩn bị mã cho bản công khai (17/11/2026)

Đăng ký TRƯỚC khi viết mã; không đổi sau khi thấy kết quả. Nhánh `trien-khai` tách từ `main` (`f812cb2`). Nguồn: báo cáo Lệnh AT.
Khung đóng băng (KHÔNG sửa): `cv_engine/`, `models/`, `backend/service.py` (logic chấm), `backend/schemas.py`, `layout.json` / mẫu PNG.
Nếu một sửa buộc phải đụng vào đó thì DỪNG và hỏi. Mặc định (không đặt biến mới) hành vi LAN hiện tại không đổi.

| Mã | Tiêu chí |
|---|---|
| T1 | `DOCS_ENABLED` (mặc định 0): 0 → `/docs`, `/redoc`, `/openapi.json` trả 404; 1 → như cũ. `HEALTH_CHI_TIET` (mặc định 0): 0 → `/health` chỉ trả trạng thái (không phiên bản, không SHA mô hình); 1 → như cũ. |
| T2 | Sau proxy: `proxy_headers` của uvicorn + `FORWARDED_ALLOW_IPS` (biến). Test: `X-Forwarded-For` từ IP được tin → khoá đăng nhập tính theo IP thật; từ IP không được tin → bỏ qua header. |
| T3 | Giới hạn tải lên ở tầng ứng dụng, TRƯỚC khi đọc cả tệp vào RAM: từ chối sớm theo `Content-Length` và dừng đọc khi vượt `MAX_UPLOAD_MB` (413); `MAX_ANH_MOI_LO` (mặc định 30) cho `/sheets/batch`; số điểm ảnh đọc từ tiêu đề (không giải mã), vượt `MAX_DIEM_ANH` (mặc định 60 triệu) → 413/422 thông báo tiếng Việt, đặt `Image.MAX_IMAGE_PIXELS` tương ứng; kiểm nội dung thật là JPEG/PNG/HEIC (không chỉ đuôi). Test từng ca: tệp quá lớn, lô quá nhiều ảnh, ảnh quá nhiều điểm ảnh, đuôi `.jpg` nhưng không phải ảnh. Ảnh hợp lệ cũ vẫn qua, điểm không đổi (bộ test chấm hiện có đạt như cũ). |
| T4 | `.env.production.example`. `MOI_TRUONG=production` → backend từ chối khởi động nếu `AUTH_MODE != on`, `COOKIE_SECURE != 1`, hoặc `AUTH_SECRET` < 32 ký tự. Mặc định (không đặt) không đổi hành vi. |
| T4b | `MOI_TRUONG=production` → chạy 1 worker; tài liệu ghi lý do (bộ đếm khoá đăng nhập + giới hạn chấm theo từng tiến trình). |
| T5 | `tools/khoi_tao_db_san_xuat.py`: chạy `01` + `02` + `03` + `python -m backend.migrate` (001–006); KHÔNG chạy `04_seed` / `05_demo_workflow`; KHÔNG tạo tài khoản mặc định; bước tạo admin đầu tiên bằng `backend.tai_khoan` (tên người dùng chọn, mật khẩu ngẫu nhiên in một lần). Thử trên schema tạm rồi ROLLBACK; có bằng chứng. |
| T6 | `Dockerfile`, `.dockerignore` (loại `data/`, `storage/`, `.env*`, `.venv/`, `.git/`, test nặng), `docker-compose.yml` mẫu (app + postgres:17 + volume storage và DB), cấu hình Caddy (TLS + giới hạn thân yêu cầu). Lệnh: `uvicorn backend.main:app --host 0.0.0.0 --port 8000 --proxy-headers --workers 1`. Có Docker trên máy → build thử + gọi `/health`; không có → ghi rõ CHƯA BUILD THỬ (không tuyên bố đạt). |
| T7 | Mô hình có sẵn trong image (`models/ocr_cnn.json` SHA `a151c078…`, mô hình OMR); `/health` ở chế độ chi tiết vẫn báo đúng SHA. |
| T8 | `docs/trien_khai_public.md`: từng bước từ máy trắng; danh sách biến; sao lưu + khôi phục DB và storage; đổi mật khẩu DB; RAM tối thiểu 1 GB; danh sách việc đã biết chưa làm (pool kết nối, rate limit toàn cục, batch cùng tệp, ép đổi mật khẩu, dọn `revoked_tokens`). |
| T9 | pytest toàn bộ ≥ 626 đạt + mọi test mới đạt (bỏ `PUBLIC_BASE_URL` trước khi chạy); `kiem_truoc_demo` 0 KHÔNG ĐẠT; `chay_demo` chế độ LAN cũ vẫn chạy, hành vi mặc định không đổi. |

Không làm trong lệnh này: pool kết nối, rate limit toàn cục, ép đổi mật khẩu, khoá batch cùng tệp, dọn `revoked_tokens`.
Báo cáo kết quả phải nêu rõ những gì CHƯA thử thật (ví dụ: không có proxy thật, không có Docker, không thử HTTPS thật).
