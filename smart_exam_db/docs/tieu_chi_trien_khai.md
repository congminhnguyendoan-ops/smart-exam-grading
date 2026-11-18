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

---

# Mục AV – Lệnh AV: hoàn tất T6 + T10 (17/11/2026, nhánh `trien-khai`)

Đăng ký TRƯỚC khi làm; không đổi sau khi thấy kết quả. Không gộp `main`; không sửa `cv_engine/`, `models/`, logic chấm của `service.py`.

| Mã | Tiêu chí |
|---|---|
| V1 | Build image từ `Dockerfile` thành công. Nếu `python:3.14-slim` hoặc `opencv-python-headless==5.0.0.93` không dùng được thì đổi sang phiên bản build được VÀ cho kết quả chấm giống bản phát triển (không đổi ngưỡng / mô hình). Ghi kích thước image. |
| V2 | Trong image KHÔNG có `data/`, `storage/` (dữ liệu), `.env*` (trừ `.env.production.example`), `.venv/`, `.git/` (liệt kê bằng `docker run … ls`). `models/ocr_cnn.json` SHA `a151c078…`; `/health` chế độ chi tiết báo đúng. |
| V3 | `docker compose up` với `.env` tạm tự sinh (bí mật ngẫu nhiên, không dùng lại mật khẩu thật): `/health` 200; `/docs` 404; khởi tạo DB sản xuất rỗng; tạo admin bằng `khoi_tao_db_san_xuat`; đăng nhập đúng; sai 5 lần → khoá THEO IP THẬT qua proxy (Caddy chuyển `X-Forwarded-For`, `FORWARDED_ALLOW_IPS` khớp dải compose). Nếu HTTPS cục bộ khó thì thử qua HTTP và ghi rõ HTTPS / chứng chỉ CHƯA thử. |
| V4 | Chấm thật trong container: 1 ảnh JPG BV01 + ÍT NHẤT 1 ảnh HEIC thật (từ `data/` nếu có) + 1 lô 5 ảnh; điểm bằng điểm kỳ vọng đã biết. Nếu HEIC bị kiểm nội dung từ chối thì sửa (đăng ký `pillow_heif` trước bước kiểm) và thêm test HEIC. |
| V5 | `docker stats`: RAM lúc nghỉ, lúc chấm 1 ảnh, lúc chấm lô 5 ảnh với `CHAM_DONG_THOI=1` và `=2`; thời gian khởi động tới `/health` 200. Bảng số liệu, ghi rõ máy nào; không suy ra cho Render. |
| V6 | Dọn: `docker compose down -v`, xoá `.env` tạm, xoá image / container thử, xác nhận không còn dữ liệu thật trong volume. |
| V7 | Ẩn liên kết "API (Swagger)" ở `frontend/index.html` khi `DOCS_ENABLED=0` (sửa tối thiểu, không đổi bố cục khác); cập nhật test. |
| V8 | `render.yaml` (web Docker gói Starter, 1 worker, đĩa bền gắn `STORAGE_DIR`, health check `/health`; 1 Postgres) + mục Render trong `docs/trien_khai_public.md` (biến phải đặt, cách chạy không Caddy, `--workers 1` cố định). `DATABASE_URL` dạng `postgres://` của Render phải chạy với psycopg (không thì chuẩn hoá trong cấu hình, kèm test). Ghi rõ CHƯA thử trên Render thật. |
| V9 | Mật khẩu role `smart_exam_app` cục bộ: sinh ngẫu nhiên 24 ký tự, `ALTER ROLE`, cập nhật `.env` cục bộ, KHÔNG in mật khẩu ra màn hình / log / báo cáo; tìm mọi chỗ khác đọc mật khẩu cũ và báo cáo; mật khẩu cũ bị từ chối; server cục bộ khởi động và chấm 1 phiếu. Thiếu quyền → DỪNG, đưa lệnh cho người dùng. |
| V10 | pytest toàn bộ ≥ 698 đạt + test mới; `kiem_truoc_demo` 0 KHÔNG ĐẠT (cây làm việc sạch trước khi chạy). |


---

# Mục AW – Lệnh AW phần 2: nạp dữ liệu demo cho CSDL công khai (18/11/2026, nhánh `nap-demo-cong-khai`)

Đăng ký TRƯỚC khi làm; không đổi sau khi thấy kết quả. Phần 1 (gộp `trien-khai` vào `main`) đã xong và xanh (713 đạt, `kiem_truoc_demo` 0 KHÔNG ĐẠT).
Không sửa `cv_engine/`, `models/`, `backend/service.py`, `backend/schemas.py`. Phần 2 CHƯA gộp `main` cho tới khi W1–W7 đạt và người dùng duyệt.

| Mã | Tiêu chí |
|---|---|
| W1 | `tools/nap_demo_cong_khai.py`: idempotent, chạy trên CSDL đã khởi tạo bằng `khoi_tao_db_san_xuat`. Mặc định XEM TRƯỚC (giao dịch chỉ đọc, không ghi). GHI chỉ khi có `--xac-nhan NAP_DEMO_CONG_KHAI`. Luôn in đích nạp (host + tên CSDL từ `DATABASE_URL`, KHÔNG in người dùng / mật khẩu / cổng) trước mọi thao tác. |
| W2 | Nội dung: lớp, sinh viên, môn, kỳ thi của 3 demo (`[XLA] Xử lý ảnh`, `[ML] Máy học`, `[ĐACN] Đồ án chuyên ngành`; tiêu đề trùng `nap_bo_demo.BA_MON` và `dat_lai_demo.KY_THI_BA_MON`; 40 câu, mã đề 101–104, đáp án trùng `demo_bv_dap_an.csv`). Mọi sinh viên là dữ liệu GIẢ: in ra họ tên + MSSV (= SBD) từng người; người dùng xác nhận không có tên / mã thật. Không chắc một bản ghi giả hay thật → DỪNG và hỏi. |
| W3 | Tài khoản: 1 admin + 2 giáo viên, tên do tham số (`--admin`, `--giao-vien A B`); từ chối `admin`, `gv_an`, `gv_binh`, `sv220001` (không phân biệt hoa thường) và tên trùng nhau. Mật khẩu ngẫu nhiên ≥ 16 ký tự, in MỘT lần ra màn hình, không ghi log / tệp; tài khoản đã có thì GIỮ NGUYÊN (không đổi mật khẩu, không in). Không tạo tài khoản sinh viên. |
| W4 | Không nạp ảnh bài làm, không đọc `data/`; kỳ thi 0 phiếu. |
| W5 | Thử trên CSDL tạm (compose tạm hoặc schema tạm) rồi dọn sạch: nạp xong đăng nhập được bằng tài khoản mới; tải ảnh BV01 lên kỳ thi XLA → ghép đúng SBD 220001, điểm **9,5**; chạy lần 2 không thêm bản ghi nào (đếm từng bảng trước / sau). Có test. |
| W6 | `docs/trien_khai_public.md`: bước "nạp dữ liệu demo" đúng thứ tự (db → khởi tạo → nạp demo → app) + cách đặt lại demo giữa các lần trình bày (`dat_lai_demo.py --ky-thi`), nếu không chạy được trên CSDL công khai thì nêu rõ. |
| W7 | pytest toàn bộ ≥ 713 đạt + test mới đạt (bỏ `PUBLIC_BASE_URL` trước khi chạy); `kiem_truoc_demo` 0 KHÔNG ĐẠT. |

Báo cáo phải nêu rõ những gì CHƯA thử (ví dụ: chưa nạp vào CSDL công khai thật, chưa thử trên Render).
