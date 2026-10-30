# Hướng dẫn quản trị – Smart Exam (lệnh H + lệnh I, 29/10/2026; lệnh V, 30/10/2026: mục 7–8)

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

## 0b. Lớp học (Quản trị → Lớp học) – lệnh I
Phần này chỉ quản lý **lớp** và **giáo viên của lớp**. Không quản lý sinh viên: số sinh viên chỉ hiển thị để xem.
1. **Tạo lớp**: nhập mã lớp, tên lớp, năm học.
   - Mã lớp 2–30 ký tự, ví dụ `CNTT-K23A`. Mã phải duy nhất và không phân biệt hoa thường: trùng mã sẽ bị từ chối.
   - Năm học có thể bỏ trống.
2. **Sửa**: chỉ sửa được tên lớp và năm học. Mã lớp không đổi được vì kỳ thi và trang bìa đang dùng nó.
3. **Vô hiệu hoá / Kích hoạt lại**:
   - Lớp bị vô hiệu hoá không chọn được cho kỳ thi mới, không gán thêm giáo viên mới được.
   - Giáo viên **đã** được gán vẫn xem được kỳ thi cũ của lớp, nên điểm và lịch sử được giữ.
4. **Xoá**: chỉ xoá được lớp **chưa gắn kỳ thi và chưa có sinh viên**. Các lớp còn lại thì vô hiệu hoá.
5. **Giáo viên** (nút trên mỗi dòng lớp):
   - Xem danh sách giáo viên của lớp.
   - Thêm giáo viên: chọn từ danh sách giáo viên đang hoạt động.
   - Bỏ giáo viên khỏi lớp: giáo viên mất quyền theo lớp **ngay ở thao tác kế tiếp**, không cần đăng xuất.
6. Quan hệ giáo viên – lớp là **nhiều – nhiều**: một giáo viên dạy nhiều lớp, một lớp có nhiều giáo viên (bảng `teacher_classes`).
7. Cột "Môn tôi dạy" ở trang "Lớp của tôi" chưa nhập được từ web, chỉ đặt bằng công cụ / SQL. Khi đổi lớp trên web, môn của lớp được giữ lại sẽ không bị mất.

## 1. Tạo tài khoản giáo viên (Quản trị → Tài khoản giáo viên)
1. Nhập tên đăng nhập (3–50 ký tự: chữ không dấu, số, `.` `_` `-`), họ tên, email (có thể bỏ trống), mật khẩu ban đầu (tối thiểu 8 ký tự).
   Có thể bấm "Sinh ngẫu nhiên" để tạo mật khẩu.
   Có thể **tick luôn các lớp** của giáo viên ngay lúc tạo. Nếu một lớp không hợp lệ thì tài khoản không được tạo.
   Sau này muốn sửa lớp của giáo viên: bấm nút **Lớp** trên dòng tài khoản, tick / bỏ tick nhiều lớp rồi Lưu.
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
   - **lớp**: chọn từ danh sách các lớp đang hoạt động, hoặc để trống;
   - **giáo viên phụ trách**.
2. Đáp án nhập mỗi dòng một mã đề, dạng `101: ABCDABCD…`, đủ số câu, mỗi câu một chữ A–D.
   Quy tắc kiểm tra giống hệt API tạo kỳ thi cũ.
3. **Ai thấy kỳ thi** — quy tắc là **HỢP** (một trong hai là đủ), không phải giao:
   - giáo viên **phụ trách** kỳ thi;
   - **hoặc** giáo viên **thuộc lớp** của kỳ thi.

   Giáo viên không thuộc trường hợp nào nhận lỗi "không tìm thấy" (404), và tên kỳ thi không bị lộ.
   Quy tắc này áp dụng cho `/app/`, trang `/m` (kể cả `/m?kythi=`), trang bìa, danh sách phiếu và bảng điểm. Admin thấy tất cả.
   - **Sửa** lớp của kỳ thi: giáo viên của lớp mới thấy kỳ thi, giáo viên của lớp cũ thôi thấy. Người phụ trách giữ nguyên.
   - Bỏ phụ trách một giáo viên vẫn thuộc lớp của kỳ thi: họ **vẫn thấy** kỳ thi qua lớp.
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
  - Lệnh I:
    - `tests/test_quan_tri_lop.py`: lớp, trùng mã, gán nhiều – nhiều, bỏ gán có hiệu lực ngay.
    - `tests/test_quan_tri_lop_ky_thi.py`: quy tắc phụ trách HỢP lớp.
- Thử bằng trình duyệt thật (chỉ ROLLBACK, không ghi CSDL):
  - `python tools/thu_lenh_h.py`, kết quả ở `data/_eval/ui_h/`;
  - `python tools/thu_lenh_i.py`, kết quả ở `data/_eval/ui_i/`.
- **Migration 004** (lệnh I, CHỈ THÊM cột `classes.is_active`, mặc định TRUE):
  - Đã áp lên CSDL thật 29/10/2026.
  - Sao lưu trước khi áp: `data/_backup/smart_exam_20261029_220658_truoc_004.dump`.
  - Đã chạy thử trong một giao dịch ROLLBACK trước khi áp.
  - Máy khác cần chạy `python -m backend.migrate`.
- Quyết định thiết kế (lệnh H):
  - **Không thêm migration**: giáo viên phụ trách dùng cột `exams.created_by` có sẵn (phân quyền đã cho người tạo thấy kỳ thi); đóng / mở dùng `exams.status` có sẵn (`closed` / `draft`).
  - (Lệnh H chỉ ghi log máy chủ; từ lệnh V có bảng nhật ký riêng – mục 7.)

## 7. Nhật ký thao tác quản trị (Quản trị → Nhật ký) – lệnh V, 30/10/2026
- Thẻ **Nhật ký** hiện **100 dòng gần nhất** (mới nhất trước): thời điểm, người thao tác, hành động, đối tượng (Kỳ thi / Tài khoản / Lớp + mã), chi tiết
  (tên, mã, giá trị cũ → mới). API: `GET /admin/audit?page=1&page_size=100` (tối đa 200 / trang). **Chỉ admin** – giáo viên / sinh viên nhận 403.
- Ghi **một dòng cho mỗi thao tác THÀNH CÔNG**: tạo / sửa / đóng / mở / xoá kỳ thi; tạo tài khoản, đặt lại mật khẩu, vô hiệu hoá, kích hoạt lại,
  gán / bỏ gán kỳ thi, đặt lớp cho giáo viên (chỉ khi danh sách lớp thật sự đổi); tạo / sửa / vô hiệu hoá / kích hoạt lại / xoá lớp; thêm / bỏ giáo viên khỏi lớp.
  Thao tác bị từ chối (409, 404, 422, 403, 401) **không** được ghi. Dòng nhật ký ghi trong cùng giao dịch với thay đổi: thay đổi bị huỷ thì nhật ký cũng không còn.
- **Không bao giờ** ghi mật khẩu, mã băm mật khẩu hay token (đặt lại mật khẩu chỉ ghi tên đăng nhập); `backend/nhat_ky.py` còn tự bỏ mọi khoá có tên nhạy cảm.
- Nhật ký chỉ đọc trên web (không sửa / xoá được). Thao tác bằng dòng lệnh (`python -m backend.tai_khoan`, `tools/*`) **không** đi qua API nên không có trong nhật ký.
- **Migration 005** (`backend/migrations/005_nhat_ky_quan_tri.sql`, CHỈ THÊM bảng `admin_audit_log`):
  - Đã áp lên CSDL thật 30/10/2026; sao lưu trước khi áp: `data/_backup/smart_exam_20261030_174500_truoc_005.dump`.
  - Đã chạy thử 2 lần trong giao dịch ROLLBACK (bảng không còn sau rollback, số dòng các bảng khác không đổi).
  - Backend cũ (trước lệnh V) vẫn chạy trên CSDL đã áp (đã chạy lại test quản trị + API của bản cũ). Máy khác: `python -m backend.migrate`.
- Kiểm chứng: `tests/test_nhat_ky_quan_tri.py` (quyền; mỗi loại thao tác đúng một dòng; thao tác bị từ chối không ghi; mật khẩu không xuất hiện; phân trang).

## 8. Ô chọn kỳ thi ẩn kỳ thi đã đóng – lệnh V
- Thanh bên `/app/` và màn "Chọn kỳ thi" của `/m` **mặc định ẩn kỳ thi đã đóng**. Tick **"Hiện cả kỳ thi đã đóng (n)"** để hiện lại (vd để duyệt / xem bảng điểm
  của kỳ thi đã đóng). Lựa chọn được nhớ trên trình duyệt đó và bị xoá khi đăng xuất. Kỳ thi đang chọn luôn còn trong ô chọn.
- Đây **chỉ là lọc hiển thị**: quyền không đổi. Trang Quản trị luôn hiện đủ mọi kỳ thi.
- Tải ảnh vào kỳ thi đã đóng: dòng / thẻ **"Bị từ chối"** kèm lý do "Kỳ thi đã đóng…", **không có nút Gửi lại** (gửi lại cũng sẽ bị từ chối).
  Nút **Gửi lại** chỉ có khi lỗi mạng / máy chủ tạm thời.
