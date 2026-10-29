# Hướng dẫn quản trị – Smart Exam (lệnh H, 29/10/2026)

Áp dụng cho nhánh `cai-tien-b`. Mọi thao tác dưới đây làm trên web, ở mục **Quản trị** (`/app/#/admin`).
Mục này chỉ hiện với tài khoản vai trò **admin**. Máy chủ cũng tự kiểm tra: giáo viên gọi `/admin/...` sẽ nhận lỗi 403.

## 0. Trước khi dùng
- Tài khoản admin đầu tiên vẫn tạo bằng dòng lệnh (chạy từ `smart_exam_db\`):
  ```powershell
  python -m backend.tai_khoan --mau    # in MỘT lần mật khẩu ngẫu nhiên của admin, gv_an, gv_binh
  ```
- **Đổi mật khẩu mặc định ngay** ở trang **Hồ sơ**. Không dùng lại mật khẩu đã in ra màn hình hay đã dán vào chat.
- Chỉ dùng **dữ liệu giả**: SBD ngẫu nhiên, tên mẫu. Không nhập họ tên hay mã số sinh viên thật khi chạy thử hoặc demo.
- Chạy cho điện thoại trong mạng LAN: đặt `PUBLIC_BASE_URL=http://<IP-LAN>:8000` trong `.env`. Khi deploy lên web thì đặt địa chỉ https thật.
  Nếu để trống, mã QR trên trang bìa lấy địa chỉ từ trình duyệt đang mở trang. Mở bằng `localhost` thì điện thoại không vào được, và trang bìa sẽ in cảnh báo màu đỏ.

## 1. Tạo tài khoản giáo viên (Quản trị → Tài khoản giáo viên)
1. Nhập tên đăng nhập (3–50 ký tự: chữ không dấu, số, `.` `_` `-`), họ tên, email (có thể bỏ trống), mật khẩu ban đầu (tối thiểu 8 ký tự).
   Có thể bấm "Sinh ngẫu nhiên" để tạo mật khẩu.
2. Đưa mật khẩu ban đầu cho giáo viên qua kênh riêng. Giáo viên tự đổi ở trang Hồ sơ.
   Hệ thống chỉ lưu bản băm scrypt: không lưu mật khẩu gốc, không hiện lại, không ghi vào nhật ký.
3. Trên mỗi dòng tài khoản có các nút:
   - **Đặt lại mật khẩu**: mọi phiên đang mở của giáo viên đó bị đăng xuất.
   - **Vô hiệu hoá**: giáo viên không đăng nhập được nữa; phiên đang mở bị từ chối ngay ở lần thao tác kế tiếp. Bấm **Kích hoạt lại** để mở lại.
   - **Kỳ thi**: gán hoặc bỏ gán kỳ thi cho giáo viên (xem mục 2).
4. Web chỉ quản lý tài khoản **giáo viên**. Tài khoản admin quản lý bằng `python -m backend.tai_khoan`.
   Đăng nhập sai 5 lần trong 15 phút thì tài khoản bị tạm khoá đăng nhập.

## 2. Tạo kỳ thi (Quản trị → Quản lý kỳ thi)
1. Điền các thông tin sau:
   - tên kỳ thi, mã môn, tên môn (môn chưa có sẽ được tạo), ngày thi, số câu (tối đa 40);
   - mã lớp: lớp phải có sẵn, hệ thống không tự tạo lớp;
   - **giáo viên phụ trách**.
2. Đáp án nhập mỗi dòng một mã đề, dạng `101: ABCDABCD…`, đủ số câu, mỗi câu một chữ A–D.
   Quy tắc kiểm tra giống hệt API tạo kỳ thi cũ.
3. Giáo viên phụ trách thấy kỳ thi này ở `/app/` và `/m`. Giáo viên dạy lớp của kỳ thi cũng thấy. Giáo viên khác nhận lỗi "không tìm thấy" (404).
   Mỗi kỳ thi có **một** người phụ trách: gán cho người mới thì người cũ thôi phụ trách. Bỏ gán thì quyền phụ trách chuyển về admin đang thao tác.
4. Các thao tác khác:
   - **Sửa**: đổi tên và ngày thi. Đáp án không sửa ở đây: sửa đáp án khi đã có phiếu cần chấm lại, đây là việc còn nợ.
   - **Đóng**: kỳ thi không nhận ảnh mới (tải ảnh bị từ chối với thông báo rõ). Duyệt phiếu, bảng điểm và xuất Excel vẫn dùng bình thường. Bấm **Mở lại** để nhận ảnh tiếp.
   - **Xoá**: chỉ xoá được kỳ thi chưa có phiếu, chưa có danh sách dự thi và không phải kỳ thi `[DEMO…]`. Các trường hợp còn lại thì **đóng** kỳ thi.
5. Giáo viên **không** tự tạo kỳ thi được (API `POST /exams` trả 403 khi đăng nhập là giáo viên).

## 3. In trang bìa kỳ thi
- Có hai chỗ mở trang bìa: nút **"In trang bìa kỳ thi"** ở thanh bên của `/app/` (cho kỳ thi đang chọn), hoặc nút **Trang bìa** trong bảng Quản lý kỳ thi.
- Trang bìa là PDF A4 gồm: tên kỳ thi, **mã kỳ thi**, môn, lớp, ngày thi, giáo viên phụ trách, các mã đề, và **mã QR** trỏ tới `<địa chỉ gốc>/m?kythi=<mã>`.
  Trang bìa **không có đáp án**.
- In với tỉ lệ 100% rồi kẹp lên trên xấp phiếu của kỳ thi đó. Mẫu phiếu trả lời không đổi.

## 4. Giáo viên chụp phiếu theo kỳ thi
1. Dùng điện thoại quét mã QR trên trang bìa để mở trang chụp phiếu `/m?kythi=<mã>`.
2. Đăng nhập. Kỳ thi trên trang bìa được **chọn sẵn**; đầu trang hiện "Kỳ thi mã … · môn · lớp" và tên kỳ thi.
   **Đối chiếu tên này với trang bìa** trước khi chụp.
   - Giáo viên không phụ trách kỳ thi đó sẽ thấy "Không tìm thấy kỳ thi (hoặc bạn không phụ trách lớp này)". Tên kỳ thi không bị lộ.
   - Kỳ thi đã đóng thì trang báo "ĐÃ ĐÓNG" và máy chủ không nhận ảnh.
3. Chụp lần lượt từng tờ. Ảnh luôn gắn vào **kỳ thi đang chọn**: hệ thống không tự đoán kỳ thi từ nội dung phiếu.
   Đổi sang xấp khác thì quét trang bìa của xấp đó, hoặc bấm "Đổi kỳ thi".
4. Duyệt các câu cần xem trên máy tính (`/app/` → Hàng đợi duyệt), như trước.

## 5. Lưu ý bảo mật
- Đổi mật khẩu mặc định (mục 0). Mỗi giáo viên dùng tài khoản riêng, không dùng chung.
- Giáo viên nghỉ hoặc chuyển công tác: **vô hiệu hoá** tài khoản, không xoá. Lịch sử duyệt và điểm vẫn giữ người thực hiện.
- `AUTH_SECRET` trong `.env` phải bí mật. Khi chạy sau https, đặt `COOKIE_SECURE=1`.
- Chỉ mở cổng 8000 cho mạng nội bộ (`docs/chay_server_va_tai_khoan.md`) và xoá luật tường lửa sau buổi dùng.
- Mã QR không phải mật khẩu: ai quét cũng chỉ mở được trang chụp, vẫn phải đăng nhập và có quyền với kỳ thi.

## 6. Kiểm chứng
- Kiểm thử tự động:
  - `tests/test_quan_tri_ky_thi.py`: quyền, tạo / sửa / đóng / xoá kỳ thi.
  - `tests/test_quan_tri_tai_khoan.py`: tài khoản, mật khẩu không lộ, vô hiệu hoá, gán kỳ thi.
  - `tests/test_trang_bia.py`: QR được giải mã lại từ PDF; `PUBLIC_BASE_URL`; `kythi` ngoài quyền.
  - `tests/js/m_kythi.test.js`.
- Thử bằng trình duyệt thật (chỉ ROLLBACK, không ghi CSDL): `python tools/thu_lenh_h.py`, kết quả ở `data/_eval/ui_h/`.
- Quyết định thiết kế (lệnh H):
  - **Không thêm migration**: giáo viên phụ trách dùng cột `exams.created_by` có sẵn (phân quyền đã cho người tạo thấy kỳ thi); đóng / mở dùng `exams.status` có sẵn (`closed` / `draft`).
  - Chưa có bảng nhật ký thao tác quản trị riêng: chỉ ghi log máy chủ (ai làm gì, không có mật khẩu).
