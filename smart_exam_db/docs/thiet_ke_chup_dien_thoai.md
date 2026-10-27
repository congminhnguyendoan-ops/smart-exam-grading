# Thiết kế: chụp bằng điện thoại → chấm ngay (yêu cầu 2, nhánh `cai-tien-b`, 27/10/2026)

Mục tiêu: giáo viên cầm điện thoại, mở trang `/m` (cùng Wi‑Fi với máy tính chạy server), chụp phiếu bằng **camera gốc** → ảnh tự tải lên và chấm →
kết quả hiện ngay trên điện thoại; máy tính (giao diện giáo viên) tự hiện phiếu mới. Không chép file, không lưu ảnh trung gian; ảnh trên server chỉ giữ tạm.

## 1. Luồng
```
Điện thoại (/m, HTML tĩnh)              Server (FastAPI, --host 0.0.0.0)              Máy tính (/app/)
 đăng nhập  ── POST /auth/login ─────▶  cookie HttpOnly
 chọn kỳ thi ─ GET /exams ───────────▶  (lọc theo quyền lớp)
 [Chụp phiếu] → camera gốc (input file capture=environment, ảnh gốc, không nén)
 ── POST /exams/{id}/sheets (FormData) ▶ preprocess → OMR → CNN → chấm → CSDL
 ◀─ {sheet_id, status, …}; GET /sheets/{id} (SV, SBD/mã đề, lý do)                   thăm dò 4 s: GET /exams/{id}/sheets
 thẻ kết quả + [Chụp tiếp]                                                           → phiếu mới nổi bật → giáo viên DUYỆT
```
- Dùng lại API có sẵn (`POST /exams/{id}/sheets`, `GET /sheets/{id}`); điện thoại KHÔNG duyệt câu (màn nhỏ dễ chọn nhầm) – chỉ hiện "Phiếu #N → duyệt trên máy tính".
- Không cần HTTPS: `<input type="file" accept="image/*" capture="environment">` mở ứng dụng camera của hệ điều hành ở mọi trình duyệt, giữ độ phân giải gốc.
  Camera trực tiếp trong trang (`getUserMedia`, khung căn phiếu, tự chụp khi thấy 4 marker) CẦN HTTPS (ngữ cảnh an toàn) → **hướng nâng cấp, chưa làm**.

## 2. Màn hình điện thoại (mobile‑first: chữ ≥ 17 px, nút cao ≥ 56 px, nút chính ở nửa dưới – thao tác một tay)
1. **Đăng nhập** (tài khoản giáo viên của lệnh B). 401 ở bất kỳ bước nào → quay về màn này, giữ kỳ thi đang chọn.
2. **Chọn kỳ thi**: mỗi dòng "Môn · Lớp" + tên kỳ thi (xuống dòng, không cắt).
3. **Chụp**: nút lớn "📷 Chụp phiếu"; dưới là bộ đếm phiên "Đã chụp n · x chấm được · y bị từ chối" + 5 phiếu gần nhất.
4. **Đang chấm…** (hiện tiến trình tải lên % + "đang chấm"), khoá nút để không gửi hai lần; hết giờ 120 s → báo lỗi, cho chụp lại.
5. **Kết quả** + nút "Chụp tiếp" (mở camera ngay):
   - (a) **bị từ chối**: thông báo (`MA_LY_DO`) + lời khuyên chụp lại (`/meta/reject-reasons`, `backend/loi_khuyen.py`) + nút "Chụp lại".
   - (b) **chấm được**: tên + SBD sinh viên (nếu ghép được), **điểm TẠM** (ghi rõ "tạm – chưa phải điểm chính thức") hoặc điểm chính thức nếu máy tự chốt,
     số câu cần xem, cảnh báo định danh (SBD / mã đề cần xem; "SBD không có trong danh sách kỳ thi"; "mã đề không thuộc kỳ thi"), cảnh báo **tờ nhạt** (`to_nhat`).
   - (c) **ảnh trùng** (`da_ton_tai`): "Ảnh này đã tải trước đó – hiển thị phiếu #N cũ, không chấm lại".
   - (d) **lỗi**: mất mạng / hết giờ / ảnh quá lớn (kiểm trước khi gửi theo `MAX_UPLOAD_MB`; server cũng chặn) / không có quyền / lỗi máy chủ – thông báo dễ hiểu, không mất bộ đếm.
   - "Mở trên máy tính": hiện mã phiếu + đường dẫn `…/app/#/review/N` (không tự mở – giáo viên duyệt trên màn hình lớn).
- Bộ đếm + danh sách gần đây chỉ ở bộ nhớ trang (mất khi tải lại – chấp nhận; nguồn thật là danh sách phiếu trên máy tính). Không localStorage cho token.

## 3. Máy tính
- Nút **"Kết nối điện thoại"** (thanh bên): hộp thoại có mã QR → `http://<IP LAN>:<cổng>/m`, địa chỉ dạng chữ, các IP ứng viên khác, và 3 dòng hướng dẫn
  (cùng Wi‑Fi → quét QR → đăng nhập, chọn kỳ thi, chụp). Dữ liệu từ `GET /meta/ket-noi` (CHỈ người đã đăng nhập; không lộ thông tin mạng cho người lạ).
  Nếu server đang nghe 127.0.0.1 → cảnh báo "điện thoại không vào được, khởi động bằng `tools/chay_server_lan.py`".
- **Tự làm mới** danh sách phiếu / hàng đợi mỗi 4 s, chỉ khi tab đang hiện (`visibilitychange`), phiếu mới tô nổi bật + thông báo "n phiếu mới".

## 4. Mạng
- Cổng 8000. `tools/chay_server_lan.py`: tìm IP → in URL + QR ra terminal + lệnh tường lửa → chạy `uvicorn backend.main:app --host 0.0.0.0 --port 8000`.
  Lệnh thường `uvicorn backend.main:app --port 8000` vẫn chỉ nghe 127.0.0.1 (mặc định không đổi).
- **Chọn IP** (`backend/mang.py`, liệt kê card bằng `ifaddr`): bỏ 127.x (loopback), 169.254.x (tự cấp, không có DHCP), IPv6; chỉ nhận dải riêng 10.x / 172.16–31.x / 192.168.x;
  card ảo theo tên (WSL / vEthernet / Hyper‑V / Docker / VirtualBox / VMware / VPN / TAP / Tailscale / ZeroTier / Bluetooth) xếp CUỐI và gắn nhãn "card ảo"; ưu tiên IP của tuyến mặc định
  (mở UDP tới 8.8.8.8 – không gửi gói nào). Liệt kê MỌI ứng viên (máy có thể nhiều mạng). "Microsoft Wi‑Fi Direct Virtual Adapter" KHÔNG bị loại: đó là card của điểm phát sóng Windows (192.168.137.1).
- **Tường lửa** (chỉ IN, người dùng tự chạy bằng PowerShell quản trị; chỉ hồ sơ mạng Private):
  `New-NetFirewallRule -DisplayName "Smart Exam 8000 (LAN)" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private`
  Wi‑Fi đang là "Public" thì đổi sang Private (Cài đặt → Mạng → Wi‑Fi → Loại hồ sơ mạng: Riêng tư) thay vì mở cổng cho Public. Gỡ: `Remove-NetFirewallRule -DisplayName "Smart Exam 8000 (LAN)"`.
- **Wi‑Fi trường chặn thiết bị nói chuyện với nhau** (AP isolation – QR mở không được dù đúng IP): (1) bật điểm phát sóng trên điện thoại, máy tính nối vào đó; hoặc
  (2) bật Mobile hotspot trên Windows (máy tính thành 192.168.137.1), điện thoại nối vào. Chạy lại `chay_server_lan.py` để lấy IP mới.

## 5. Bảo mật
- Chỉ trong mạng nội bộ; server KHÔNG mở ra Internet (không chuyển cổng router). Mọi API vẫn cần đăng nhập (cookie HttpOnly SameSite=Lax hoặc Bearer); `/m` chỉ là HTML tĩnh (như `/app/`).
- `COOKIE_SECURE` vẫn tắt vì chạy http (bật thì trình duyệt không gửi cookie qua http). Hệ quả: người cùng Wi‑Fi có thể nghe lén cookie / mật khẩu (http không mã hoá) – chấp nhận cho
  phòng thi / demo; giảm rủi ro: dùng hotspot riêng, đổi mật khẩu sau buổi demo, phiên hết hạn sau `SESSION_HOURS`. HTTPS nội bộ = hướng nâng cấp (đi cùng `getUserMedia`).
- Ai cùng Wi‑Fi cũng thấy trang đăng nhập: đã có giới hạn 5 lần sai / 15 phút / (tên, IP), một thông báo lỗi chung, phân quyền theo lớp như giao diện máy tính.
- `GET /meta/ket-noi` chỉ cho giáo viên / admin đã đăng nhập.

## 6. Ảnh tạm (chi tiết + migration: Bước 3, mục 7 dưới)
Ảnh gốc, ảnh nắn, ảnh cắt ô viết tay nằm trong `STORAGE_DIR`; CSDL chỉ giữ đường dẫn. Sau khi phiếu được CHỐT thì ảnh bị xoá sau `ANH_GIU_GIO` giờ; điểm, đáp án, lý do, SHA‑256 giữ nguyên.
**Ảnh gốc vẫn nằm trong thư viện ảnh (Photos / Gallery) của điện thoại** – hệ thống không xoá được: sau buổi chấm, giáo viên vào Ảnh → chọn các ảnh phiếu → Xoá, rồi xoá cả
trong "Đã xoá gần đây" (iPhone) / "Thùng rác" (Android). (Trên vài máy Android, ảnh chụp qua ô chọn tệp không vào thư viện.)

## 7. Chính sách ảnh tạm (Bước 3)
- Migration `003_xoa_anh_tam.sql` (chỉ thêm, chạy lại an toàn): `answer_sheets.image_deleted_at TIMESTAMPTZ NULL` + chỉ mục một phần cho việc quét.
- Được xoá: phiếu `graded` (điểm chính thức) hoặc `rejected`, chưa xoá, mốc = lần thay đổi cuối của phiếu / kết quả ≤ bây giờ − `ANH_GIU_GIO` (mặc định 24).
  KHÔNG xoá phiếu `needs_review` (giáo viên còn cần ảnh). Mặc định KHÔNG xoá ảnh của kỳ thi có "[DEMO" trong tên (`ANH_GIU_DEMO=1`) – demo / báo cáo cần ảnh.
- Xoá ảnh gốc + ảnh nắn + 9 ảnh ô viết tay; chỉ tệp nằm TRONG `STORAGE_DIR` (kiểm sau `resolve()`); thiếu tệp không lỗi; xoá xong ghi `image_deleted_at = now()`.
- API ảnh của phiếu đã xoá trả **410** "Ảnh đã được xoá sau khi chốt phiếu (chính sách giữ ảnh tạm)", không 500; giao diện hiện chữ thay ảnh.
- Chạy: luồng nền nhẹ lúc khởi động + mỗi giờ, CHỈ khi `ANH_XOA_TU_DONG=1` – `chay_server_lan.py` bật sẵn (máy chủ thật); `uvicorn` gọi trực tiếp, pytest và công cụ
  `tools/*` (dùng TestClient trên CSDL thật) mặc định KHÔNG dọn → chạy test / đánh giá không bao giờ xoá ảnh thật. Thủ công: `python -m backend.don_anh` (xem trước) / `--ap-dung`.
  Chưa áp migration 003 → luồng dọn tự tắt, ghi cảnh báo; API ảnh vẫn chạy (đọc cột bằng `to_jsonb(...)`, không lỗi khi thiếu cột).
