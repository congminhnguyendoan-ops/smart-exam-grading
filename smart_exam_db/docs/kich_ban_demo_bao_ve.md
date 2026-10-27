# Kịch bản demo bảo vệ – bộ [DEMO-BV] (nhánh `cai-tien-b`, 27/10/2026)

Mục tiêu: trong ~10 phút cho hội đồng thấy (1) đăng nhập + phân quyền theo lớp, (2) môn + lớp trên kỳ thi / bảng điểm / Excel,
(3) chấm đủ 40 câu từ ảnh chụp, (4) máy KHÔNG tự ghi điểm khi không chắc (ô mờ, tô hai ô, tô nhạt cả tờ, SBD ngoài danh sách) và giáo viên duyệt xong thì điểm đúng.

## 1. Dữ liệu (đã nạp 27/10/2026, chỉ INSERT – `tools/nap_bo_demo.py --ap-dung`)
| | Kỳ thi | exam_id | Giáo viên | Môn | Lớp | Mã đề | Dự thi |
|---|---|---|---|---|---|---|---|
| E1 | Giữa kỳ Cơ sở dữ liệu – K22A [DEMO-BV] | 1380 | `gv_an` | IT3080 | CNTT-K22A | 101, 102 | 220001–220005 |
| E2 | Giữa kỳ Trí tuệ nhân tạo – K22B [DEMO-BV] | 1381 | `gv_binh` | IT4040 | CNTT-K22B | 103, 104 | 220006–220009 |

40 câu, thang 10, đạt 5. **220010 cố ý KHÔNG thuộc kỳ thi nào** (phiếu BV10). Nguồn: `answer_sheet/demo_bv/` (đáp án, kịch bản tô 10 phiếu, PDF in phiếu + phiếu giao việc).
Sao lưu ngay trước khi nạp: `data/_backup/smart_exam_20261027_175511_truoc_demo_bv.dump` (`pg_restore -l` đọc được).
Kiểm kịch bản: `python tools/kiem_bo_demo.py` (khớp 10/10). Nạp lại: chạy lại không tạo trùng (lần hai: INSERT 0 ở mọi bảng).

## 2. Chuẩn bị trước buổi bảo vệ
1. `git switch cai-tien-b`; `.env` có `AUTH_MODE=on`, `AUTH_SECRET`; `python -m backend.migrate --kiem` → 001, 002 "ĐÃ ÁP".
2. Mật khẩu `gv_an`, `gv_binh` (quên: `python -m backend.tai_khoan dat-lai-mat-khau gv_an` – nhập bằng getpass).
3. In `answer_sheet/demo_bv/phieu_demo_in.pdf` (Actual size / 100%), tô theo `phieu_giao_viec_demo.pdf`; viết SBD + mã đề bằng tay vào ô viết tay.
4. Diễn tập KHÔNG ghi CSDL: `python tools/thu_bo_demo.py chay` (ảnh giả hoá, ROLLBACK) – phải in "Khớp 10/10".
   **Không diễn tập bằng cách tải ảnh thật lên E1 / E2** (phiếu sẽ nằm lại; tải lại cùng SBD → `duplicate_sbd`). Muốn xoá phiếu diễn tập phải hỏi trước (quy tắc CSDL).
5. `uvicorn backend.main:app --port 8000` → `http://127.0.0.1:8000/` (Ctrl+F5 để trình duyệt tải lại `app.js` mới).
6. Dự phòng: ảnh giả hoá `data/_eval/demo_bv/gia/BV01.jpg … BV10.jpg` (`python tools/thu_bo_demo.py tao-anh`) – tải được như ảnh thật nếu điện thoại / ánh sáng có sự cố.

## 3. Trình tự demo
| # | Thao tác | Điều cần chỉ ra |
|---|---|---|
| 1 | Mở trang khi chưa đăng nhập | màn đăng nhập; API trả 401 |
| 2 | Đăng nhập `gv_an` | thanh bên: tên GV; ô **Kỳ thi** hiện đủ tên "Giữa kỳ Cơ sở dữ liệu – K22A [DEMO-BV]" + "Môn … · lớp CNTT-K22A"; KHÔNG thấy kỳ thi K22B |
| 3 | **Lớp của tôi** → CNTT-K22A | danh sách sinh viên lớp mình (có ô tìm) |
| 4 | **Tải ảnh & chấm**: BV01 → BV05 | mỗi phiếu: điểm tạm + số câu cần xem (bảng mục 4) |
| 5 | **Hàng đợi duyệt**: BV02 câu 6 (tô A+C) | lý do "nhiều ô": câu tô hai ô bị tính SAI sau khi GV xác nhận; ô mờ → GV chọn đáp án |
| 6 | **Bảng điểm** + **Xuất Excel** | cột Điểm chỉ có điểm chính thức; Excel có "Môn: IT3080 – Cơ sở dữ liệu" (A4), "Lớp: CNTT-K22A – …" (F4); BV04 5,5 đạt sát ngưỡng, BV05 4,25 không đạt |
| 7 | Đăng xuất → đăng nhập `gv_binh` | chỉ thấy E2; gõ tay `#/…` hay gọi `GET /exams/1380` → 404 như không tồn tại |
| 8 | Tải BV06, BV08, BV09 | như bước 4 |
| 9 | Tải **BV07** (tô nhạt cả tờ) | cả 40 câu "cần xem" lý do `to_nhat`, điểm tạm 0 – máy không đoán khi cả tờ nhạt. Duyệt từng câu: máy đọc đúng ô thì "Xác nhận", không thì chọn theo giấy → 7,5 (5b đã duyệt bằng "chọn theo giấy"; chưa đo riêng tỉ lệ máy đọc đúng ô ở tờ này) |
| 10 | Tải **BV10** (SBD 220010) | SBD "cần xem" (ô viết tay trống / không có trong danh sách); GV nhập 220010 vẫn **không ghi điểm** (`sbd_not_found`) – phiếu chờ tới khi thêm SV vào danh sách dự thi. Đây là chốt chặn "ghi nhầm điểm" |

## 4. Kết quả mong đợi (đo bằng `python tools/thu_bo_demo.py chay`, ảnh giả hoá, ROLLBACK – `data/_eval/demo_bv/ket_qua_thu.md`)
| Phiếu | SBD | Kỳ thi / mã đề | Điểm tạm lúc tải | Câu cần xem (lý do) | Sau khi GV duyệt đúng giấy | Mong đợi |
|---|---|---|---|---|---|---|
| BV01 | 220001 | E1/101 | 9,0 | 2: 10, 40 (`o_mo`) | chính thức 9,5 | 9,5 |
| BV02 | 220002 | E1/102 | 7,75 | 3: 6, 24, 40 (`nhieu_o`, `o_mo`) | chính thức 8,25 | 8,25 |
| BV03 | 220003 | E1/101 | 6,25 | 3: 1, 30, 33 (`nhieu_o`, `o_mo`) | chính thức 6,75 | 6,75 |
| BV04 | 220004 | E1/102 | 5,0 | 2: 10, 32 (`o_mo`) | chính thức 5,5 | 5,5 |
| BV05 | 220005 | E1/101 | 3,75 | 3: 6, 10, 12 (`nhieu_o`, `o_mo`) | chính thức 4,25 | 4,25 |
| BV06 | 220006 | E2/103 | 8,5 | 2: 10, 26 (`o_mo`) | chính thức 9,0 | 9,0 |
| BV07 | 220007 | E2/104 | 0,0 | 40 (`to_nhat`) | chính thức 7,5 | 7,5 |
| BV08 | 220008 | E2/103 | 5,5 | 2: 29, 38 (`o_mo`) | chính thức 6,0 | 6,0 |
| BV09 | 220009 | E2/104 | 2,75 | 2: 8, 29 (`o_mo`) | chính thức 3,25 | 3,25 |
| BV10 | 220010 | E2/103 | 7,25 | 2: 5, 31 (`o_mo`); SBD `o_trong_ngoai_ds` | KHÔNG ghi điểm, chờ `sbd_not_found` (tạm 7,75) | không ghi điểm |
Khớp 10/10; 0 câu chấm sai mà không gắn cần xem. Câu tô hai ô: GV xác nhận đúng giấy → câu đó SAI (đúng ⇔ tô đúng MỘT ô).

## 5. Khác biệt khi dùng ẢNH THẬT (nói trước với hội đồng nếu xảy ra)
- Ảnh giả hoá vẽ phẳng, **không có chữ viết tay**: SBD / mã đề "chắc" chỉ nhờ có trong danh sách. Với ảnh thật, CNN chữ số đọc từng ô viết tay; trên dev
  khoảng **46–54% phiếu có SBD hoặc mã đề "cần xem"** (T4, `docs/ke_hoach_tuan6.md`) – GV xác nhận 1 lần, không sai điểm. Không phải lỗi demo.
- Số câu cần xem có thể nhiều hơn bảng mục 4 (ảnh tối / nghiêng C2–C3); điểm chính thức sau duyệt vẫn phải bằng cột "Mong đợi".
- BV07 thật (bút chì HB nhẹ tay) có thể KHÔNG kích hoạt `to_nhat` nếu nét đậm hơn ngưỡng (T ≥ 0,44, `ke_hoach_cai_tien_27-10.md` 6.6) – khi đó các ô mờ được gắn `o_mo` từng câu.
- Ảnh bị từ chối (mờ, thiếu marker…) → thông báo + lời khuyên chụp lại; chụp lại rồi tải.

## 5b. Luồng CHỤP BẰNG ĐIỆN THOẠI → chấm ngay (yêu cầu 2; `docs/thiet_ke_chup_dien_thoai.md`)
**Chuẩn bị (một lần, trước buổi bảo vệ)**
1. Mở cổng 8000 cho mạng nội bộ – PowerShell **quản trị** (hệ thống không tự chạy):
   `New-NetFirewallRule -DisplayName "SmartExam-8000-LAN" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Public,Private -RemoteAddress LocalSubnet`
   (chỉ máy cùng mạng con nội bộ vào được, không mở ra Internet). **Sau buổi demo xoá**: `Remove-NetFirewallRule -DisplayName "SmartExam-8000-LAN"`.
2. Chạy server cho mạng nội bộ (thay cho `uvicorn … --port 8000`): `python tools/chay_server_lan.py` – in địa chỉ `http://<IP>:8000/m` + mã QR + hai lệnh trên.
   Lượt dọn ảnh tạm đầu tiên sẽ xoá ảnh của 3 phiếu kỳ thi `[THU] Kiểm giao diện F1-F4` (bản sao ảnh dev) – muốn giữ: `--khong-xoa-anh`.
3. Điện thoại nối **cùng Wi‑Fi**; trên máy tính bấm **📱 Kết nối điện thoại** → quét QR → đăng nhập. Hộp thoại báo vàng "chỉ nghe 127.0.0.1" = đang chạy nhầm `uvicorn` thường.

**Diễn tập trên kỳ thi TẬP, KHÔNG trên 1380 / 1381**: **1632** "Giữa kỳ Cơ sở dữ liệu – K22A [DEMO-BV-TẬP]" (gv_an) và **1633** "… K22B [DEMO-BV-TẬP]" (gv_binh) – cùng đáp án, môn,
lớp, danh sách dự thi như E1 / E2. Đã có 21 phiếu thử của công cụ giả lập (27/10): chụp lại đúng tệp ảnh đó sẽ báo "ảnh đã tải trước đó"; ảnh chụp mới từ điện thoại luôn có SHA khác.
Diễn tập không cần điện thoại: `python tools/thu_dien_thoai.py chay` (ROLLBACK, không ghi gì).

**Trình tự trong buổi bảo vệ** (chèn sau bước 3 của mục 3, thay cho "Tải ảnh & chấm" trên máy tính):
| # | Điện thoại | Máy tính (màn chiếu) |
|---|---|---|
| a | Mở `/m` bằng QR, đăng nhập `gv_an`, chọn "Giữa kỳ Cơ sở dữ liệu – K22A [DEMO-BV]" | "Danh sách phiếu" của kỳ thi đó đang mở |
| b | **📷 Chụp phiếu** (camera gốc) → "Đang chấm…" → thẻ: tên SV, **điểm TẠM**, số câu cần xem | ≤ 4 s sau phiếu tự hiện, nhãn "mới" + thông báo – KHÔNG chép file, không tải lại trang |
| c | **Chụp tiếp** BV02 … BV05 | Bấm **Duyệt** từng phiếu (màn lớn) → điểm chính thức |
| d | Đăng xuất, đăng nhập `gv_binh`; chụp BV07 → cảnh báo "tô nhạt cả tờ"; BV10 → "SBD … không có trong danh sách" | như bước 9–10 mục 3 |
Cảnh báo / thông điệp điện thoại có thể hiện: ảnh bị từ chối + lời khuyên chụp lại; "ảnh này đã tải trước đó"; "mất kết nối / quá thời gian chờ"; "phiên đăng nhập đã hết".

**Phương án dự phòng**
- QR không mở được dù đúng IP + đã mở tường lửa (Wi‑Fi trường chặn thiết bị nói chuyện với nhau) → bật **hotspot điện thoại**, máy tính nối vào, chạy lại `chay_server_lan.py` (IP mới, QR mới).
- Ảnh chụp tại chỗ bị từ chối nhiều (thiếu sáng, nghiêng) → chụp lại theo lời khuyên; vẫn không được → máy tính "Tải ảnh & chấm" với ảnh chụp sẵn `data/_eval/demo_bv/gia_12mp/BVxx_v1.jpg`
  (hoặc ảnh phẳng `gia/BVxx.jpg`).
- Điện thoại không vào được mạng → toàn bộ demo vẫn chạy trên máy tính như mục 3.
- Sau buổi demo: xoá luật tường lửa; xoá ảnh phiếu trong thư viện ảnh điện thoại (cả "Đã xoá gần đây").

**Số đo (giả lập Pixel 7, ảnh 3024×4032, loopback – chưa gồm Wi‑Fi)**: ROLLBACK p50 0,81 s / p95 0,85 s; ghi thật trên kỳ thi TẬP p50 1,13 s / p95 2,13 s.
CHƯA thử bằng điện thoại thật cùng mạng – thử trước buổi bảo vệ (đo lại thời gian thật qua Wi‑Fi).

## 6. Tái tạo
`python tools/kiem_bo_demo.py` · `python tools/nap_bo_demo.py` (xem trước) · `python tools/thu_bo_demo.py chay` · `python -m pytest tests/test_bo_demo.py`.
Kiểm quyền 5a (27/10, chỉ GET, `AUTH_MODE=on`, token dựng từ hash trong CSDL): 24/24 đạt – gv_an thấy E1, không thấy E2 (5 đường `/exams/1381…` → 404,
lớp CNTT-K22B → 404); gv_binh ngược lại; admin thấy cả hai; `/me/classes` đúng lớp; Excel A4 "Môn: …", F4 "Lớp: …". Ảnh giao diện: `data/_eval/ui_b/8_chon_ky_thi_demo_bv_*.png`.
