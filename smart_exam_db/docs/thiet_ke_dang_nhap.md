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

## 6. Bảng endpoint × quyền
(Điền ở Bước 3 sau khi tự rà mã – xem mục 7.)
