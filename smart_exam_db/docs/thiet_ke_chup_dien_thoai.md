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
- **Tường lửa** (chốt với người dùng 27/10/2026 – Wi‑Fi của máy đang ở hồ sơ **Public**). Hệ thống CHỈ IN, người dùng tự chạy bằng PowerShell **quản trị** (Run as Administrator):
  ```powershell
  New-NetFirewallRule -DisplayName "SmartExam-8000-LAN" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Public,Private -RemoteAddress LocalSubnet
  Remove-NetFirewallRule -DisplayName "SmartExam-8000-LAN"      # xoá luật sau buổi demo
  ```
  Luật chỉ nhận kết nối vào cổng 8000 từ máy **cùng mạng con nội bộ** (`LocalSubnet` – ví dụ 192.168.1.x khi máy là 192.168.1.142); máy ngoài Internet không tới được
  (router cũng không chuyển cổng vào). Vì áp cho cả hồ sơ Public, ở mạng công cộng (quán cà phê, Wi‑Fi trường) người cùng mạng con cũng tới được trang đăng nhập →
  **xoá luật khi không dùng** (lệnh thứ hai). Mọi API vẫn cần đăng nhập.
- **Wi‑Fi trường chặn thiết bị nói chuyện với nhau** (AP / client isolation – QR mở không được dù đúng IP và đã mở tường lửa): bật **điểm phát sóng (hotspot) trên điện thoại**,
  máy tính nối vào đó, rồi chạy lại `chay_server_lan.py` để lấy IP mới (điện thoại vẫn dùng chính hotspot của nó để mở `/m`). Cách khác: Mobile hotspot của Windows (máy tính thành 192.168.137.1).

## 5. Bảo mật
- Chỉ trong mạng nội bộ; server KHÔNG mở ra Internet (không chuyển cổng router). Mọi API vẫn cần đăng nhập (cookie HttpOnly SameSite=Lax hoặc Bearer); `/m` chỉ là HTML tĩnh (như `/app/`).
- Tường lửa: `-RemoteAddress LocalSubnet` (mục 4) – chỉ cùng mạng con; xoá luật sau buổi demo.
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
- Chạy: luồng nền nhẹ lúc khởi động + mỗi giờ, CHỈ khi `ANH_XOA_TU_DONG=1` – `chay_server_lan.py --bat-don-anh` bật (từ lệnh Z 30/10/2026 mặc định TẮT; trước đó `chay_server_lan.py` bật sẵn); `uvicorn` gọi trực tiếp, pytest và công cụ
  `tools/*` (dùng TestClient trên CSDL thật) mặc định KHÔNG dọn → chạy test / đánh giá không bao giờ xoá ảnh thật. Thủ công: `python -m backend.don_anh` (xem trước) / `--ap-dung`.
  Chưa áp migration 003 → luồng dọn tự tắt, ghi cảnh báo; API ảnh vẫn chạy (đọc cột bằng `to_jsonb(...)`, không lỗi khi thiếu cột).
- **Lượt dọn đầu tiên trên CSDL hiện tại** (xem trước 27/10, `python -m backend.don_anh`, chỉ đọc): 12 phiếu – 9 phiếu seed kỳ thi 1 (tệp không có trên đĩa → chỉ đánh dấu)
  và 3 phiếu kỳ thi `[THU] Kiểm giao diện F1-F4` (exam 115, **5 tệp thật** = bản sao ảnh dev; `data/raw` không bị đụng). Muốn giữ: chạy `chay_server_lan.py --khong-xoa-anh`.

## 9. Chụp LIÊN TỤC (lệnh M, 27/10/2026) – thay luồng "chụp → chờ → Chụp tiếp" ở mục 2
- `frontend/m_hang_doi.js` (thuần logic, test Node `tests/js/hang_doi.test.js`): mỗi tờ chụp xong vào hàng, gửi nền **tối đa 2 yêu cầu song song** (cùng API
  `POST /exams/{id}/sheets`), không chặn chụp tờ kế; lỗi mạng GIỮ ảnh để "Gửi lại"; 401 tạm dừng rồi gửi tiếp sau khi đăng nhập lại; ảnh trùng không tính, không lặp dòng;
  tờ bị từ chối "Chụp lại" giữ số tờ. Ảnh đã có kết quả được giải phóng khỏi bộ nhớ điện thoại.
- Giao diện: nút "📷 Chụp tiếp · Tờ N/tổng" cố định ở đáy; ô "Tổng số tờ" (mặc định 40); khối tổng kết dính đầu (đã chụp / chấm được / cần xem / từ chối / đang chờ, lỗi, trùng) +
  đường dẫn duyệt trên máy tính; danh sách tờ theo thứ tự chụp (đang gửi % / đang chấm / cần xem N câu / bị từ chối / lỗi mạng; tên + SBD + điểm TẠM + cảnh báo);
  "Chọn nhiều ảnh" (input multiple, không capture). Danh sách vẽ TỪNG DÒNG (ô "Chụp lại" không bị thay giữa lúc camera đang mở). Rời trang khi còn tờ chờ → hỏi lại.
- Đo (`python tools/thu_dien_thoai.py chay`, ROLLBACK, giả lập Pixel 7, ảnh 3024×4032 ~2,3 MB, loopback – chưa gồm Wi‑Fi; kỳ thi gộp 4 mã đề trong giao dịch):
  | Kịch bản | Tờ | Tổng | Xử lý mỗi tờ p50 / p95 | Chụp → kết quả p50 / p95 / max | Lỗi |
  |---|---|---|---|---|---|
  | B. Camera, mỗi 2 s một tờ (không chờ) | 20 | 39,5 s (chụp xong tờ 20 sau 40,7 s) | 0,79 / 0,83 s | 0,79 / 0,83 / 0,85 s | 0 |
  | A. "Chọn nhiều ảnh" 20 tờ một lần | 20 | 10,4 s | 1,04 / 1,09 s | 5,7 / 10,4 / 10,4 s (xếp hàng) | 0 |
  Lỗi mạng (2 tờ, ngắt mạng) → Gửi lại: 2/2 chấm được ở lần gửi thứ 2. Ảnh trắng → từ chối → Chụp lại (giữ số tờ) → chấm được. Ảnh trùng: tổng "chấm được" không đổi, "trùng" +1, không thêm dòng.
  Vân tay CSDL 15 bảng giống hệt trước / sau. Ảnh: `data/_eval/ui_m/lien_tuc/` (01–11), số đo `thoi_gian.json`.
- Camera trực tiếp (getUserMedia, tự bắt khung): khảo sát `docs/khao_sat_camera_truc_tiep.md` – KHÔNG làm trước buổi bảo vệ.

## 8. Kết quả (27/10/2026)
- **Migration 003 ĐÃ ÁP** (người dùng đồng ý; sao lưu trước `data/_backup/smart_exam_20261027_184231_truoc_003.dump`, `pg_restore -l` đọc được). Chạy lại: "không có migration mới".
  Vân tay dòng cũ 15 bảng giống hệt trước khi áp; 31 phiếu cũ `image_deleted_at = NULL`.
- **Kỳ thi TẬP** (`nap_bo_demo.py --ban-tap --ap-dung`, chỉ INSERT; lần hai INSERT 0): **1632** "Giữa kỳ Cơ sở dữ liệu – K22A [DEMO-BV-TẬP]" (gv_an) và **1633** "Giữa kỳ Trí tuệ nhân tạo – K22B [DEMO-BV-TẬP]" (gv_binh).
- **Giả lập điện thoại** (`tools/thu_dien_thoai.py`, Playwright Chromium giả lập Pixel 7; ảnh giả hoá 3024×4032 JPEG ~2,3 MB có phối cảnh, nền bàn, ánh sáng không đều):
  | Chế độ | n | p50 | p95 | max |
  |---|---|---|---|---|
  | ROLLBACK (một kết nối, ảnh vào thư mục tạm) | 20 | 0,81 s | 0,85 s | 0,91 s |
  | Ghi thật trên kỳ thi TẬP 1632/1633 (mỗi yêu cầu một kết nối + commit, ảnh vào `storage/`) | 20 | 1,13 s | 2,13 s | 2,38 s |
  Thời gian = bấm tải (chọn ảnh) → thẻ kết quả hiện, qua **loopback 127.0.0.1**: KHÔNG gồm thời gian truyền ~2–4 MB qua Wi‑Fi của điện thoại thật (số đo điện thoại thật: xem ghi chú "ĐÃ thử bằng điện thoại thật ngày 27/10/2026" ở cuối mục 8).
  Ảnh màn hình: `data/_eval/ui_m/` (ROLLBACK, 01–13) và `data/_eval/ui_m/tap/` (kỳ thi TẬP). Máy tính tự hiện phiếu mới (nhãn "mới" + thông báo) không cần tải lại.
  Sau lần chạy ROLLBACK, vân tay CSDL 15 bảng giống hệt trước; kỳ thi TẬP sau lần ghi thật: 1632 có 11 phiếu (10 cần xem, 1 ảnh trắng bị từ chối), 1633 có 10 (cần xem); 1380/1381: 0 phiếu.
- **Dọn ảnh tạm**: `tests/test_dien_thoai.py::test_don_anh_dong_ho_gia` (đồng hồ giả +25 giờ, thư mục ảnh tạm, ROLLBACK): xoá đúng 12 tệp của phiếu đã chốt + phiếu bị từ chối,
  giữ phiếu chờ duyệt và kỳ thi [DEMO…]; API ảnh → 410; điểm chính thức giữ nguyên; tải lại ảnh cũ vẫn nhận ra (SHA). Không chạy dọn thật trên kỳ thi nào.
- pytest **375 đạt + 1 skip có chủ đích**; hồi quy `kiem_backend_dau_cuoi.py`: điểm chính thức 56/56, 0 câu chấm sai không cờ.
- **Ghi trung thực**: ảnh chụp bằng camera gốc KHÔNG do hệ thống kiểm soát (ánh sáng, độ nghiêng, lấy nét) – ảnh xấu bị từ chối kèm lời khuyên, nhưng số ảnh bị từ chối
  ngoài đời chưa đo. Đã thử bằng GIẢ LẬP điện thoại, **ĐÃ thử bằng điện thoại thật ngày 27/10/2026** (người dùng đo trực tiếp trên MỘT iPhone, Safari, cùng Wi‑Fi với máy chủ; có ảnh chụp màn hình điện thoại và nhật ký làm việc 27/10): chụp 1 tờ (từ chụp đến hiện kết quả **1,8 giây**, một tờ, một lần đo), chụp liên tục, rớt Wi‑Fi rồi gửi lại (**khoảng 2 giây**, ước chừng), chụp mờ bị từ chối kèm lý do, chọn nhiều ảnh, xuất Excel, phân quyền (gv_binh không xem được phiếu K22A). **Chưa thử Android; chưa đo thời gian 40 tờ liên tục qua Wi‑Fi thật.** Camera trực tiếp (`getUserMedia`, khung căn phiếu)
  cần HTTPS → hướng nâng cấp, chưa làm.
