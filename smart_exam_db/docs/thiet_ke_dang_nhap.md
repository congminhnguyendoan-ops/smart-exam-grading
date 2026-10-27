# Thiết kế: tên môn / lớp + đăng nhập giáo viên + phân quyền theo lớp (nhánh `cai-tien-b`, 29/10/2026)

Yêu cầu 1 và 7 của `docs/ke_hoach_cai_tien_27-10.md`. **Chỉ làm trên nhánh `cai-tien-b`** (từ `d3d0426`); test đợt 2 chạy từ tag `dang-ky-dot2` (mã khoá `ma-dot2-dong-bang-v3`), nên `backend/` ở `main` không đổi.

## 1. Hiện trạng
Không xác thực (`DEMO_USER` trong `.env` hoặc header `X-User`). `users` có `password_hash` / `role` (admin | teacher | student) / `is_active` / `last_login_at`, nhưng hash trong `04_seed.sql` là CHUỖI GIẢ
(chưa đăng nhập được). `classes`, `subjects`, `students.class_id` đã có; `exams.subject_id` có nhưng **chưa có `class_id`**; chưa có quan hệ giáo viên–lớp.

## 2. Quyết định (kèm lý do)
| Hạng mục | Chọn | Lý do |
|---|---|---|
| Băm mật khẩu | `hashlib.scrypt` (stdlib), n = 2^14, r = 8, p = 1, muối 16 byte; định dạng `scrypt$n$r$p$muối$hash` (base64); so sánh `hmac.compare_digest` | argon2-cffi / bcrypt chưa cài, mỗi gói thêm là thêm phụ thuộc cho máy đồ án; scrypt là KDF nhớ-cứng chuẩn, tham số nằm trong chuỗi nên nâng cấp sau được. Hash lạ (chuỗi giả của seed) → xác minh trả False, không ném lỗi |
| Phiên | token tự ký `v1.<payload>.<chữ ký>` HMAC-SHA256 (stdlib), payload `{u: user_id, e: hết hạn, f: dấu vân tay mật khẩu}`; hạn mặc định 8 giờ (`SESSION_HOURS`) | không thêm thư viện; `f` làm đổi mật khẩu vô hiệu mọi token cũ; mỗi yêu cầu vẫn tra `users` (khoá tài khoản có hiệu lực ngay) |
| Nơi giữ token | cookie `se_session` **HttpOnly + SameSite=Lax** (`Secure` bật bằng `COOKIE_SECURE=1`, vì chạy nội bộ bằng http); chấp nhận thêm `Authorization: Bearer` cho công cụ / test | JS không đọc được token (không dùng localStorage); SameSite=Lax chặn gửi cookie ở POST chéo trang (CSRF) |
| Khoá ký | biến môi trường `AUTH_SECRET` (≥ 32 ký tự); **không có giá trị mặc định trong code**; thiếu khi `AUTH_MODE=on` → `LoiCauHinh` rõ ràng, API không khởi động | tránh khoá yếu / lộ trong git |
| Chế độ | `AUTH_MODE=on` (mặc định, an toàn) \| `demo` (giữ hành vi cũ DEMO_USER / X-User, KHÔNG kiểm quyền; chỉ dev + test cũ) | test cũ (275) và công cụ `tools/eval_*` chạy tiến trình trong chế độ demo; `conftest.py` đặt `AUTH_MODE=demo` |
| Chống dò | mọi lỗi đăng nhập (sai tên, sai mật khẩu, tài khoản bị khoá) trả CÙNG một thông báo + 401; luôn chạy một phép scrypt giả khi không có tài khoản (cân bằng thời gian); giới hạn 5 lần sai / 15 phút cho mỗi (username, IP) → 429; bộ nhớ trong tiến trình | gọn; mất khi khởi động lại (chấp nhận: máy nội bộ một tiến trình). Hạn chế: nhiều worker thì mỗi worker đếm riêng |
| Quan hệ giáo viên–lớp | bảng `teacher_classes(user_id, class_id, subject_id NULL)`, khoá chính `(user_id, class_id)` | một GV nhiều lớp, một lớp nhiều GV; môn là TUỲ CHỌN. Mỗi cặp một dòng (môn GV dạy ở lớp đó) cho gọn; nếu sau này một GV dạy 2 môn cùng lớp thì đổi khoá chính sang 3 cột |
| Kỳ thi ↔ lớp | `exams.class_id` NULL được; kỳ thi cũ (không lớp) vẫn hiện cho người tạo (`created_by`) | không mất dữ liệu cũ |
| Không tự tạo lớp | `POST /exams` có `class_code` / `class_id` mà lớp không tồn tại → 422 | lớp là dữ liệu danh mục do admin quản, tránh rác do gõ nhầm |
| Phân quyền | admin = mọi thứ; teacher = lớp trong `teacher_classes` + kỳ thi mình tạo hoặc thuộc lớp mình; student = 403 ở mọi API chấm | khớp yêu cầu |
| IDOR | MỌI endpoint theo id kiểm quyền; ngoài quyền → **404** (không lộ tồn tại, cùng thông báo "Không có …" như khi không tồn tại), chưa đăng nhập → 401, sai vai trò → 403 | |
| Excel | thêm "Môn: …" ở ô A4 và "Lớp: …" ở ô F4 (hàng 4 đang trống) | KHÔNG chèn dòng: `test_bang_diem` đọc dữ liệu từ hàng 6; hàng 5 là tiêu đề cột |

## 3. Thay đổi dữ liệu – migration `backend/migrations/002_lop_giao_vien.sql`
Chỉ THÊM, chạy lại an toàn (`IF NOT EXISTS`), cùng phong cách 001: `exams.class_id BIGINT NULL REFERENCES classes(class_id) ON DELETE SET NULL` + chỉ mục;
bảng `teacher_classes` (`ON DELETE CASCADE` theo user và class; môn `ON DELETE SET NULL`) + chỉ mục theo lớp. Không sửa / xoá dữ liệu cũ; backend ở tag cũ bỏ qua cột / bảng mới.

## 4. API
Mới: `POST /auth/login`, `POST /auth/logout`, `GET /me`, `PATCH /me` (họ tên, email), `POST /me/password` (cần mật khẩu cũ, tối thiểu 8 ký tự, khác mật khẩu cũ),
`GET /me/classes` (lớp mình phụ trách + môn + số sinh viên; admin: mọi lớp), `GET /classes/{id}/students` (mã, họ tên, ngày sinh, giới tính, email; tìm `q` theo tên / mã; phân trang `page`, `page_size`).
Sửa: `POST /exams` nhận `class_code` hoặc `class_id` (tuỳ chọn; phải thuộc lớp của người tạo, trừ admin); `GET /exams`, `GET /exams/{id}`, `GET /exams/{id}/results` và Excel trả đủ
`subject_code`, `subject_name`, `class_id`, `class_code`, `class_name`.
Công cụ: `python -m backend.tai_khoan` (tạo / đặt lại mật khẩu / khoá; mật khẩu nhập bằng `getpass`, KHÔNG qua tham số; `--mau` tạo `gv_an`, `gv_binh`, `admin` với mật khẩu NGẪU NHIÊN, in một lần);
`tools/nap_giao_vien_demo.py` (xem trước, ghi khi `--ap-dung`).

## 5. Giao diện (`frontend/`, JS thuần)
Màn đăng nhập (khi `GET /me` trả 401 hoặc API trả 401 → quay về); thanh đầu: tên giáo viên + đăng xuất; "Hồ sơ" (xem / sửa họ tên, email; đổi mật khẩu); "Lớp của tôi" (danh sách lớp → bảng sinh viên có ô tìm);
chọn kỳ thi hiện "Môn – Lớp – tên kỳ thi"; đầu bảng điểm hiện Môn và Lớp. Không dùng localStorage cho token.

## 6. Bảng endpoint × quyền (sinh từ danh sách route thật; kiểm tự động bởi `tests/test_xac_thuc_khong_csdl.py`)
Chưa đăng nhập (AUTH_MODE=on) → **401** ở mọi endpoint không công khai. Header `X-User` bị BỎ QUA khi `on`. "Kiểm quyền" = `phan_quyen.kiem_*`; ngoài quyền → **404** cùng thông báo như id không tồn tại.
| Endpoint | admin | teacher | student | Ghi chú |
|---|---|---|---|---|
| `GET /health`, `GET /meta/reject-reasons` | ✓ | ✓ | ✓ | công khai (không dữ liệu người dùng) |
| `GET /` → `/app/…` | ✓ | ✓ | ✓ | trang tĩnh HTML/JS/CSS công khai |
| `POST /auth/login` | ✓ | ✓ | ✓ | công khai; 401 một thông báo; 429 sau 5 lần sai / 15 phút; đặt cookie HttpOnly |
| `POST /auth/logout` | ✓ | ✓ | ✓ | xoá cookie; không cần đăng nhập |
| `GET /me`, `PATCH /me`, `POST /me/password` | ✓ | ✓ | ✓ | chỉ chính mình; PATCH chỉ đổi họ tên / email (không đổi vai trò) |
| `GET /me/classes` | mọi lớp | lớp trong `teacher_classes` | 403 | |
| `GET /classes/{id}/students` | ✓ mọi lớp | lớp của mình (kiểm quyền `kiem_lop`) | 403 | tìm `q`, phân trang |
| `POST /exams` | ✓ lớp bất kỳ | ✓ lớp mình phụ trách (hoặc không lớp) | 403 | `class_id` / `class_code` không tồn tại hoặc không phụ trách → 422 cùng một thông báo; không tự tạo lớp |
| `GET /exams` | tất cả | kỳ thi mình tạo + kỳ thi thuộc lớp mình dạy | 403 | lọc bằng SQL tham số |
| `GET /exams/{id}`, `…/sheets`, `…/results`, `…/export.xlsx`, `…/review-questions` | ✓ | kiểm quyền kỳ thi | 403 | |
| `POST /exams/{id}/sheets`, `…/sheets/batch` | ✓ | kiểm quyền kỳ thi | 403 | tải ảnh + chấm |
| `GET /sheets/{id}`, `…/image`, `…/questions/{n}/image`, `…/digits/{f}/{p}/image`, `…/review-questions` | ✓ | kiểm quyền phiếu (qua kỳ thi) | 403 | |
| `POST /sheets/{id}/questions/{n}/review`, `PUT /sheets/{id}/identity` | ✓ | kiểm quyền phiếu | 403 | ghi `reviewed_by` = người đăng nhập (không còn DEMO_USER) |
Quyền kỳ thi của giáo viên = `created_by = mình` HOẶC `exams.class_id ∈ lớp mình dạy`. Quyền phiếu = quyền của kỳ thi chứa phiếu.

## 7. Tự rà trước khi áp dụng (29/10/2026) – kết quả
- **Endpoint thiếu xác thực / phân quyền**: không còn. 3 test không cần CSDL kiểm toán TOÀN BỘ route: (1) mọi route trừ công khai phụ thuộc `get_nguoi_dung`; (2) mọi route trừ `/me*` phụ thuộc `giao_vien` (chặn sinh viên);
  (3) mọi route có `{exam_id}` / `{sheet_id}` / `{class_id}` gọi `phan_quyen.kiem_*` trong thân hàm; `GET /exams` lọc theo quyền, `POST /exams` kiểm lớp. Route mới thêm sau này mà quên → test đỏ.
- **Nối chuỗi SQL**: chỉ hai chỗ có f-string, đều ghép HẰNG nội bộ (mệnh đề `dk` cố định trong `sinh_vien_lop`; `dieu_kien_ky_thi` sinh ở `phan_quyen`); mọi dữ liệu người dùng đi qua tham số `%s`. Tìm kiếm `q` thoát `% _ \` trước khi ghép vào mẫu LIKE (tham số).
- **Log mật khẩu / token**: không có `log` / `print` nào chứa mật khẩu, token, khoá (test quét mã); chỉ `backend.tai_khoan --mau` in mật khẩu ngẫu nhiên MỘT lần cho người vận hành.
- **Cookie**: `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` theo `COOKIE_SECURE`, `max-age` = hạn phiên; JS không đọc được token (test: JS không dùng `document.cookie`, `Authorization`, localStorage cho token).
- **So sánh mật khẩu**: `hmac.compare_digest` trên đầu ra scrypt; chữ ký token cũng `compare_digest`.
- **Lộ tồn tại username**: một thông báo duy nhất (kể cả tài khoản bị khoá / hash giả); tên không tồn tại vẫn tốn một phép scrypt; 429 áp cho cả tên không tồn tại. Đã sửa thêm: thông báo lớp "không tồn tại" và "không phụ trách" trùng nhau (không dò được mã lớp), kiểm quyền lớp trước khi so `class_id` với `class_code`.
- **Hạn chế còn lại**: giới hạn thử sai ở bộ nhớ tiến trình (nhiều worker / khởi động lại thì đếm lại); không có CSRF token riêng (dựa SameSite=Lax; API không nhận form chéo trang); trang tĩnh `/app/` công khai (chỉ mã giao diện);
  `/health` công khai lộ phiên bản mô hình (có từ trước); sau `AUTH_MODE=demo` mọi người thành "demo user" không kiểm quyền – KHÔNG dùng ngoài dev.

## 8. Sự cố đã biết
**Migration 002 bị áp lên CSDL thật ngoài ý muốn (27/10/2026, 14:11:25 theo đồng hồ máy), trước khi người dùng đồng ý ghi CSDL.**
- Nguyên nhân: fixture `csdl_san_sang` trong `tests/conftest.py` tự gọi `migrate.ap_dung()`; tôi chạy `tests/test_frontend.py` (có test dùng fixture `client`) khi 002 đã nằm trong `backend/migrations/` → 002 được áp.
- Phạm vi: chỉ THÊM cột `exams.class_id`, bảng `teacher_classes` (lúc đó 0 dòng), 3 chỉ mục, 2 comment, 1 dòng `schema_migrations`. Không sửa / xoá dữ liệu cũ (kiểm: 0 kỳ thi có `class_id`, 0 dòng `teacher_classes` ngay sau sự cố).
- Quyết định của người dùng (29/10): GIỮ NGUYÊN, không gỡ. Sau đó người dùng đồng ý ghi CSDL; đã `pg_dump` trước các thao tác ghi còn lại (`data/_backup/`).
- Phòng ngừa: `csdl_san_sang` KHÔNG tự áp migration nữa – chỉ kiểm đã áp, chưa áp thì SKIP có thông báo rõ; muốn áp trong test phải đặt `SMART_EXAM_TEST_MIGRATE=1`. Áp bình thường: `python -m backend.migrate`.

## 9. Vận hành
- **Đặt lại mật khẩu khi quên** (nhập bằng getpass, không qua tham số): `python -m backend.tai_khoan dat-lai-mat-khau gv_an` · khoá / mở khoá: `khoa <username>` / `mo-khoa <username>` · tạo mới: `tao <username> --email … --ho-ten "…" [--vai-tro teacher|admin|student]` ·
  tạo lại cả 3 tài khoản mẫu với mật khẩu ngẫu nhiên (in một lần): `python -m backend.tai_khoan --mau`. Tài khoản mẫu: `admin`, `gv_an` (CNTT-K22A, IT3080), `gv_binh` (CNTT-K22B, IT4040).
- **`.env`** (không commit): `AUTH_SECRET` (đã sinh bằng `secrets.token_hex(32)`), `AUTH_MODE=on`. Công cụ `tools/*` tự đặt `AUTH_MODE=demo` trong tiến trình; `tests/conftest.py` cũng vậy.
- **Quy trình chạy test đợt 2 AN TOÀN** (nhánh `cai-tien-b` KHÔNG dùng để chạy đợt 2; tag `dang-ky-dot2`, mã khoá `ma-dot2-dong-bang-v3`):
  1. cây làm việc sạch (`git status` rỗng, commit mọi thứ trên `cai-tien-b`);
  2. `git switch --detach dang-ky-dot2` NGAY trong thư mục hiện tại – KHÔNG `git worktree`, KHÔNG clone mới (`core.autocrlf=true` đổi xuống dòng của vài file đã đăng ký bằng LF → SHA lệch; chuyển nhánh tại chỗ giữ nguyên file không đổi);
  3. `python -c "import sys; sys.path.insert(0,'tools'); import eval_dot2 as E; E.kiem_dang_ky()"` (hoặc để `run` tự kiểm);
  4. chạy: `python tools/eval_dot2.py run --xac-nhan-dot2 --xem` (CSDL đã có migration 001 + 002; backend ở tag bỏ qua cột / bảng mới nên vẫn chạy);
  5. `git switch cai-tien-b`.
  Nếu `kiem_dang_ky` từ chối vì xuống dòng (SHA lệch ở file chỉ khác CRLF/LF): **DỪNG và báo người dùng**, không sửa file, không sửa SHA / đăng ký.

