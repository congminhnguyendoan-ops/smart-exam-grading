# Kịch bản demo (8–10 phút) – lệnh U, 30/10/2026

Bản này là kịch bản **ngày demo**, ngắn và theo thời gian. Chi tiết bộ phiếu, kết quả đo và khác biệt khi dùng ảnh thật nằm ở `docs/kich_ban_demo_bao_ve.md`.
Lệnh chạy server / tài khoản nguyên văn: `docs/chay_server_va_tai_khoan.md`. Quản trị: `docs/huong_dan_quan_tri.md`.
Trong các lệnh dưới đây, `$py` = `C:\Users\MSI\PycharmProjects\smart_exam_db_1\.venv\Scripts\python.exe` và thư mục làm việc = `smart_exam_db\`.

## 0. Dữ liệu dùng trong demo
| Kỳ thi | exam_id | Phụ trách | Lớp | Mã đề | Dự thi | Vai trò trong demo |
|---|---|---|---|---|---|---|
| Giữa kỳ Cơ sở dữ liệu – K22A [DEMO-BV] | **1380** | gv_an | CNTT-K22A | 101, 102 | 220001–220005 | kỳ thi CHẤM THẬT trong demo (phải trống lúc bắt đầu) |
| Giữa kỳ Trí tuệ nhân tạo – K22B [DEMO-BV] | **1381** | gv_binh | CNTT-K22B | 103, 104 | 220006–220009 | chứng minh phân quyền (gv_an không thấy) |
| … K22B [DEMO-BV-TẬP] | **1633** | gv_binh | CNTT-K22B | 103, 104 | 220006–220009 | dự phòng cho gv_binh (trống) |
| … K22A [DEMO-BV-TẬP] | **1632** | gv_an | CNTT-K22A | 101, 102 | 220001–220005 | diễn tập; nền 5 chính thức + #6028 cần xem |

Phiếu: in `answer_sheet/demo_bv/phieu_demo_in.pdf` (**Actual size / 100%**), tô theo `answer_sheet/demo_bv/phieu_giao_viec_demo.pdf`, viết SBD + mã đề bằng tay.
Demo dùng **BV01, BV02, BV03** (E1, SBD 220001–220003). Ảnh dự phòng (giả hoá, không có chữ viết tay): `data\_eval\demo_bv\anh_gia\BV01.jpg … BV10.jpg`.

## 1. Trình tự (≈ 9 phút)
| # | Mục tiêu | Thao tác | Tài khoản | Tệp / phiếu | Kết quả kỳ vọng trên màn hình | Thời gian |
|---|---|---|---|---|---|---|
| 1 | Admin chuẩn bị kỳ thi: lớp, giáo viên, trang bìa QR | Máy tính `http://<IP LAN>:8000/` (KHÔNG dùng 127.0.0.1 – xem mục 3) → đăng nhập → **Quản trị** → **Lớp học**: CNTT-K22A có gv_an → **Quản lý kỳ thi**: dòng #1380 (môn IT3080, lớp K22A, phụ trách gv_an, 0 phiếu). Tuỳ chọn: điền nhanh form **Tạo kỳ thi** (tên KHÔNG có `[DEMO`, dán đáp án dạng `101: ABCD…` từ `demo_bv_dap_an.csv`) rồi **Xoá** ngay – kỳ thi chưa có phiếu xoá được. Bấm **Trang bìa** của #1380 | admin | – | trang Quản trị mở thẳng sau đăng nhập; PDF trang bìa: tên kỳ thi, mã kỳ thi, **mã QR** `…/m?kythi=1380`, không có đáp án | 1:30 |
| 2 | Giáo viên chụp bằng điện thoại | Máy tính: **Đăng xuất** → đăng nhập gv_an (vào **Tải ảnh & chấm**), mở **Danh sách phiếu**. Điện thoại: quét QR trên trang bìa → đăng nhập gv_an → kỳ thi #1380 **đã chọn sẵn** → **Chụp phiếu** BV01 → **Chụp tiếp** BV02 → BV03 | gv_an | BV01, BV02, BV03 (giấy thật) | điện thoại: mỗi tờ một thẻ kết quả ~2 s (điểm TẠM, số câu cần xem); máy tính: phiếu mới tự hiện (làm mới 4 s, nhãn "mới") | 2:00 |
| 3 | Máy không đoán khi không chắc | Máy tính: **Danh sách phiếu** → nói về cột Trạng thái / Điểm | gv_an | – | cả ba phiếu "Cần xem" kèm điểm **tạm** (BV01 ~9,0; BV02 ~7,75; BV03 ~6,25 theo ảnh giả hoá – ảnh thật có thể nhiều câu cần xem hơn); **chưa có điểm chính thức** | 0:45 |
| 4 | Duyệt "cần xem": hai kênh SBD + nút chốt | **Duyệt** BV01 → khung "Chốt số báo danh / mã đề" (nếu có): hàng **Ô tô (bubble)** cạnh **Chữ viết tay** (ảnh ô + chữ máy đọc + %) → **Lấy theo ô tô** / **Lấy theo chữ viết tay** → **Lưu SBD / mã đề**. Từng câu: ảnh câu + lý do ("ô tô mờ") → **Xác nhận như máy đọc** hoặc chọn ô → **Lưu lựa chọn** | gv_an | BV01 | sau câu cuối: "Đã chốt điểm chính thức – phiếu duyệt xong", điểm **9,5** (theo giấy) | 1:30 |
| 5 | Phiếu trùng SBD bị giữ, không ghi đè | Điện thoại: chụp LẠI tờ BV01 (một ảnh MỚI – tải lại đúng tệp cũ chỉ trả phiếu cũ "ảnh đã tải trước đó") → máy tính **Bảng điểm** → **Duyệt** phiếu mới | gv_an | BV01 (chụp lần 2) | phiếu mới "Cần xem", lý do "trùng SBD với phiếu khác" (nếu SBD của ảnh mới còn "cần xem" thì lý do này chỉ hiện SAU khi chốt SBD 220001 ở khung "Chốt số báo danh / mã đề" – như phiếu #6028 của kỳ thi tập); Bảng điểm: thẻ đỏ "Còn 1 phiếu trùng chờ duyệt" + cảnh báo trên bảng; màn duyệt: "Trùng SBD với phiếu #…", hai nút **Bỏ phiếu chụp lại (giữ phiếu cũ)** / **Dùng phiếu này thay phiếu cũ** → bấm **Bỏ phiếu chụp lại** | 1:00 |
| 6 | Bảng điểm + Excel | **Bảng điểm**: cột Điểm chỉ có điểm chính thức, cột Điểm tạm cho phiếu chưa duyệt → **Xuất Excel** → mở tệp | gv_an | – | Excel 2 sheet "Bảng điểm" + "Chi tiết"; dòng Môn IT3080, Lớp CNTT-K22A; BV01 9,5 chính thức, BV02 / BV03 "Chưa duyệt xong – điểm tạm" | 0:45 |
| 7 | Phân quyền theo lớp | **Đăng xuất** → đăng nhập gv_binh → ô Kỳ thi chỉ có K22B (1381, 1633; kỳ thi đã đóng bị ẩn – tick "Hiện cả kỳ thi đã đóng" nếu cần). Gõ địa chỉ `#/sheet/<số phiếu BV01>` → lỗi; gõ `#/admin` → "Chỉ quản trị viên dùng được trang này." + nút **Về trang chính** | gv_binh | – | không thấy kỳ thi K22A; phiếu của gv_an: "Không có phiếu …" (máy chủ trả 404 như không tồn tại); trang admin bị từ chối | 0:45 |
| | | | | | **Tổng** | **≈ 8:15 + 0:45 hỏi đáp dự phòng** |

Lưu ý kỹ thuật cho người trình bày:
- Đăng xuất xoá sạch dữ liệu của người trước trên trình duyệt (lệnh J); đăng nhập xong mỗi vai trò vào trang mặc định của mình (admin → Quản trị, giáo viên → Tải ảnh).
- Điểm "tạm" chỉ tính câu máy chắc chắn; câu cần xem KHÔNG bao giờ được chấm như câu chắc (đó là thông điệp chính: tránh ghi nhầm điểm).
- Ảnh thật: khoảng một nửa phiếu có SBD hoặc mã đề "cần xem" (CNN chữ số chưa đủ chắc) – giáo viên chốt một lần, không sai điểm (`docs/kich_ban_demo_bao_ve.md` mục 5).
  Lý do hiện theo từng cột (lệnh V), vd "Cột 6: ô tô trống hoặc không đọc được …; chữ viết tay đọc là 4", "Cột 2: ô tô đọc 9, chữ viết tay đọc 4".
- (Tuỳ chọn, bước 1, lệnh V) Sau khi tạo / xoá kỳ thi thử: mở **Quản trị → Nhật ký** – hai dòng "Tạo kỳ thi", "Xoá kỳ thi" do admin, không có mật khẩu.
- Lỗi khi tải ảnh: thẻ "**lỗi mạng**" có nút **Gửi lại** (ảnh vẫn giữ trên máy); thẻ "**bị từ chối**" (vd kỳ thi đã đóng – 409) KHÔNG có Gửi lại: đổi kỳ thi hoặc nhờ admin mở lại.

## 2. Nếu hỏng thì (mỗi tình huống < 1 phút)
| Tình huống | Dấu hiệu | Xử lý |
|---|---|---|
| Wi‑Fi lớp học chặn thiết bị | điện thoại quét QR nhưng trang không mở, dù đúng IP | Bật **điểm phát sóng** trên điện thoại → máy tính nối vào → Ctrl+C server, chạy lại `& $py tools/chay_server_lan.py --khong-xoa-anh` (IP mới) → máy tính bấm **📱 Kết nối điện thoại** → quét QR **trên màn hình** (QR trên trang bìa in sẵn mang IP cũ). Luật tường lửa dùng `LocalSubnet` nên vẫn đúng với mạng mới. |
| Camera điện thoại lỗi | không mở được camera / ảnh đen | Trên `/m` bấm **Chọn nhiều ảnh** → chọn ảnh BV đã chụp sẵn trong thư viện ảnh. Hoặc máy tính: **Tải ảnh & chấm** → kéo `data\_eval\demo_bv\anh_gia\BV01.jpg` … vào. |
| Server không lên | `chay_server_lan.py` báo lỗi cổng / cấu hình | Cổng bận: `Get-NetTCPConnection -LocalPort 8000 -State Listen \| Select-Object OwningProcess` → `Stop-Process -Id <số>`. Lỗi cấu hình (.env): chạy `& $py tools/kiem_truoc_demo.py --bo-qua-toc-do` đọc dòng KHÔNG ĐẠT. Hết cách: `& $py -m uvicorn backend.main:app --port 8000` (chỉ máy tính, tải ảnh từ máy tính). |
| CSDL không kết nối | trang báo "Không nối được API" / lỗi 500 khi đăng nhập | `Get-Service postgresql-x64-17` → nếu Stopped: PowerShell **quản trị** `Start-Service postgresql-x64-17`, rồi khởi động lại server. |
| Ảnh bị từ chối | thẻ đỏ "Bị từ chối" + lý do + lời khuyên | Biến thành điểm demo: "máy không chấm ảnh không dùng được". Chụp lại: đủ 4 ô vuông đen ở góc, đủ sáng, không nghiêng quá, không rung. |
| Đăng nhập sai nhiều lần | "Thử đăng nhập sai quá nhiều lần. Hãy thử lại sau ít phút." (429) | Bộ đếm nằm trong bộ nhớ server, theo (tên đăng nhập, IP), 5 lần / 15 phút: Ctrl+C rồi chạy lại server là xoá; hoặc đăng nhập từ máy khác (IP khác). Quên mật khẩu: `& $py -m backend.tai_khoan dat-lai-mat-khau <tên>`. |

## 3. Chuẩn bị (trước ngày demo và trước khi vào phòng)
**Trước ngày demo**
- [ ] Sạc đầy laptop + điện thoại; mang sạc / pin dự phòng.
- [ ] Điểm phát Wi‑Fi dự phòng (điện thoại thứ hai hoặc chính điện thoại chụp) – đã thử máy tính nối vào được.
- [ ] Sao lưu CSDL: `& $py tools/sao_luu_demo.py` → `data\_backup\smart_exam_<ngày giờ>_demo.dump` (in "pg_restore -l đọc được … mục").
- [ ] In phiếu demo (Actual size), tô BV01–BV10 theo phiếu giao việc, viết SBD / mã đề bằng tay.
- [ ] Chụp sẵn BV01–BV10 bằng điện thoại, để trong thư viện ảnh (dự phòng camera / thời gian).
- [ ] Mật khẩu admin, gv_an, gv_binh: nhớ / ghi giấy riêng (KHÔNG ghi vào tệp trong dự án). Quên: `& $py -m backend.tai_khoan dat-lai-mat-khau <tên>`.
- [ ] Luật tường lửa `SmartExam-8000-LAN` đã có (PowerShell quản trị, `docs/chay_server_va_tai_khoan.md` mục 0).

**Trước khi vào phòng (≈ 10 phút)**
1. Nối Wi‑Fi của phòng (hoặc hotspot).
2. `& $py tools/kiem_truoc_demo.py` → không có dòng **KHÔNG ĐẠT** (mã thoát 0). Đọc các CẢNH BÁO, nhất là IP LAN và PUBLIC_BASE_URL.
3. `& $py tools/dat_lai_demo.py` (xem trước) → nếu "SẼ XOÁ" > 0 phiếu: `& $py tools/dat_lai_demo.py --xac-nhan DAT_LAI` (tự sao lưu CSV + ảnh trước khi xoá) → chạy lại `kiem_truoc_demo.py`.
4. `& $py tools/chay_server_lan.py --khong-xoa-anh` → giữ cửa sổ mở.
5. Máy tính mở `http://<IP LAN>:8000/` (IP ở dòng "ĐIỆN THOẠI mở:"), **Ctrl+F5**. In trang bìa #1380 **sau khi** đã ở mạng của phòng, hoặc đặt `PUBLIC_BASE_URL=http://<IP LAN>:8000` trong `.env` rồi khởi động lại server – QR lấy địa chỉ gốc từ đó (rỗng = địa chỉ trình duyệt đang dùng).
6. Điện thoại: quét QR thử, đăng nhập, **chưa** chụp phiếu thật vào 1380 (diễn tập dùng 1632).

## 4. Sao lưu / khôi phục
- Sao lưu: `& $py tools/sao_luu_demo.py` (pg_dump -Fc; mật khẩu lấy từ DATABASE_URL qua PGPASSWORD, không in).
- Khôi phục (GHI ĐÈ toàn bộ CSDL – chỉ khi đã quyết; dừng server trước; nhập mật khẩu khi được hỏi):
  ```powershell
  & "C:\Program Files\PostgreSQL\17\bin\pg_restore.exe" -h localhost -p 5432 -U smart_exam_app -d smart_exam --clean --if-exists --no-owner "data\_backup\smart_exam_<ngày giờ>_demo.dump"
  ```
  **Chưa thử khôi phục thật** trên máy này (chỉ kiểm `pg_restore -l` đọc được). Nếu báo lỗi quyền với `smart_exam_app`, chạy lại với `-U postgres`.
- Đặt lại chỉ phiếu demo (không đụng phần khác): `tools/dat_lai_demo.py` (mục 3 bước 3). Phạm vi là **đúng danh sách id cố định** 1380, 1381, 1633 (về 0 phiếu)
  và 1632 (về nền 3878, 3880, 4270, 4271, 4272 + #6028) – KHÔNG chọn theo chữ "[DEMO" trong tên, nên kỳ thi 6 "[DEMO] …", 178 "[DEMO-2] …", 115 / 509 "[THU] …"
  không bao giờ bị đụng (có test). **Đã diễn tập thật 30/10/2026** (lệnh V): sao lưu → tải BV01 vào 1633 qua API (phiếu #8361, 11 tệp ảnh) → xem trước
  → `--xac-nhan DAT_LAI` → CSDL + kho ảnh trùng khít trạng thái trước khi tải (mọi kỳ thi, mọi bảng, 202 tệp), 0 dòng mồ côi.
- Bản sao lưu trước migration 005: `data\_backup\smart_exam_20261030_174500_truoc_005.dump`.

## 5. Sau buổi demo
- Ctrl+C tắt server. Xoá luật tường lửa (PowerShell quản trị): `Remove-NetFirewallRule -DisplayName "SmartExam-8000-LAN"`.
- Muốn giữ kết quả demo: `& $py tools/sao_luu_demo.py`. Muốn dọn: `tools/dat_lai_demo.py` (xem trước → `--xac-nhan DAT_LAI`).
