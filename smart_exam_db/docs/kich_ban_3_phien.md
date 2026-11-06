# Kịch bản 3 phiên demo (lệnh AJ, 06/11/2026)

Ba phiên, ba góc nhìn trên CÙNG một hệ thống chấm phiếu: **Xử lý ảnh (≈ 3 phút)** · **Máy học (≈ 3 phút)** · **Đồ án chuyên ngành (≈ 6–7 phút)**.
Phiên 1 và 2 là hai trang HTML sinh sẵn (chạy offline, không cần server, không đụng CSDL). Phiên 3 chạy trên hệ thống thật (server + điện thoại + CSDL).
Lời dẫn viết theo ngôi “nhóm em”; các con số trích từ kết quả đã chạy (nguồn ghi ở cuối mỗi mục). Lệnh dùng `$py` = `C:\Users\MSI\PycharmProjects\smart_exam_db_1\.venv\Scripts\python.exe`,
thư mục làm việc `smart_exam_db\`. Chi tiết server / tài khoản: `docs/chay_server_va_tai_khoan.md`; kịch bản phiên 3 gốc, dài hơn: `docs/kich_ban_demo.md`.

## 0. Chuẩn bị chung và đặt lại

### 0.1 Quy tắc bất di bất dịch
1. **Không chạy hai phiên cùng lúc.** Phiên 1–2 chỉ đọc nên không xung đột với ai, nhưng phiên 3 ghi vào CSDL; chạy `pytest` / `kiem_truoc_demo.py` / `kiem_backend_dau_cuoi.py` song song với server hoặc với nhau từng gây `DeadlockDetected` (lỗi cách chạy, không do mã).
2. **Không để hai điện thoại gửi CÙNG MỘT phiếu.** Hai ảnh cùng SBD gửi đồng thời → một bên bị `409` và **phiếu của bên đó không được lưu** (đo ở lệnh AH: 13–17/20 lần). Mỗi tờ giấy chỉ do một điện thoại chụp; chụp lại thì chờ thẻ kết quả của lần trước hiện xong.
3. Sau MỖI phiên 3 (kể cả diễn tập): `dat_lai_demo` (mục 0.4). Không tải ảnh thật lên kỳ thi 1380 / 1381 trước buổi chính thức.
4. Không chạy lệnh tường lửa thay người dùng: lệnh mở / xoá cổng 8000 do **người trình bày** tự gõ (PowerShell quản trị).

### 0.2 Nhánh, cấu hình
```powershell
Set-Location C:\Users\MSI\PycharmProjects\smart_exam_db_1\smart_exam_db
$py = "C:\Users\MSI\PycharmProjects\smart_exam_db_1\.venv\Scripts\python.exe"
git branch --show-current          # phải là hoan-thien (bản có công cụ demo này); bản bảo vệ gốc là cai-tien-b
git status --short                 # nên sạch
```
- `.env`: `AUTH_MODE=on`, `AUTH_SECRET` có giá trị; **`PUBLIC_BASE_URL`**: để trống (QR lấy địa chỉ của trình duyệt đang mở trang) hoặc `http://<IP LAN>:8000`. Đặt **sau khi** đã nối Wi‑Fi của phòng, rồi **khởi động lại server** – IP đổi theo mạng; QR trang bìa in sẵn mang IP cũ sẽ không mở được.
  `kiem_truoc_demo.py` thường báo CẢNH BÁO về mục này khi trống: chấp nhận được nếu mở trang bìa từ `http://<IP LAN>:8000/` (không dùng `127.0.0.1`).
- Không đặt `ANH_XOA_TU_DONG=1`; không thêm `--bat-don-anh` (sẽ xoá ảnh phiếu đã chốt quá 24 giờ ở mọi kỳ thi không có “[DEMO”).

### 0.3 Dựng trang cho phiên 1–2 (làm trước, ở nhà; không cần mạng)
```powershell
# Phiên 1 – xử lý ảnh (mỗi ảnh ~ 5 giây; dùng đúng pipeline thật, không ghi CSDL)
& $py tools/demo_xu_ly_anh.py --anh data/_eval/demo_3_phien/T05_thuong.JPG        --ra data/_eval/demo_3_phien/xu_ly_anh_T05_thuong.html
& $py tools/demo_xu_ly_anh.py --anh data/_eval/demo_3_phien/T03_kho.JPG           --ra data/_eval/demo_3_phien/xu_ly_anh_T03_kho.html
& $py tools/demo_xu_ly_anh.py --anh data/_eval/demo_3_phien/T05_mo_phong_nhe.jpg  --ra data/_eval/demo_3_phien/xu_ly_anh_T05_mo_phong_nhe.html
& $py tools/demo_xu_ly_anh.py --anh data/_eval/demo_3_phien/T05_mo_phong_nang.jpg --ra data/_eval/demo_3_phien/xu_ly_anh_T05_mo_phong_nang.html
# Phiên 2 – máy học (bản thường và bản có chạy CNN thật trên 504 ô; ~ 10 giây)
& $py tools/demo_may_hoc.py                       --ra data/_eval/demo_3_phien/may_hoc.html
& $py tools/demo_may_hoc.py --truc-tiep           --ra data/_eval/demo_3_phien/may_hoc_truc_tiep.html
```
Mở bằng trình duyệt (kéo tệp `.html` vào Chrome / Edge, hoặc `Start-Process data\_eval\demo_3_phien\xu_ly_anh_T05_thuong.html`). Mở sẵn các tab theo thứ tự trình bày; **Ctrl + 0** đặt thu phóng 100%.
Ảnh demo nằm ở `data/_eval/demo_3_phien/` (đọc `DOC_TOI_DAY.txt`): `T05_thuong.JPG`, `T03_kho.JPG` là bản sao ảnh THẬT; `*_mo_phong_*.jpg` là ảnh **MÔ PHỎNG** (làm nhoè bằng Gaussian, không phải ảnh chụp mờ thật) – phải nói rõ như vậy khi chiếu.

### 0.4 Phiên 3: chạy server, kiểm trước, đặt lại
```powershell
# (1) Kiểm toàn bộ trước giờ trình bày – KHÔNG ĐẠT phải = 0 (mã thoát 0)
& $py tools/kiem_truoc_demo.py
# (2) Xem trước phần sẽ dọn (chỉ đọc). Chỉ tiếp tục nếu danh sách chỉ gồm phiếu của kỳ thi tập
& $py tools/dat_lai_demo.py
#     nếu "SẼ XOÁ" > 0:  & $py tools/dat_lai_demo.py --xac-nhan DAT_LAI    (tự sao lưu CSV + ảnh trước khi xoá)
# (3) Server cho điện thoại (giữ cửa sổ này mở; KHÔNG thêm --bat-don-anh)
& $py tools/chay_server_lan.py --khong-xoa-anh
#     dòng cuối phải có: "Dọn ảnh tạm: TẮT (mặc định)"; ghi lại địa chỉ "ĐIỆN THOẠI mở: http://<IP>:8000/m"
```
Tường lửa (người trình bày tự gõ, PowerShell **quản trị**, một lần): `New-NetFirewallRule -DisplayName "SmartExam-8000-LAN" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Public,Private -RemoteAddress LocalSubnet`;
sau buổi: `Remove-NetFirewallRule -DisplayName "SmartExam-8000-LAN"`.

**Kỳ thi dùng cho phiên 3: tập dượt trên `[DEMO-BV-TẬP]` (1632 gv_an / 1633 gv_binh), buổi chính thức mới dùng 1380 / 1381.**
Cách chọn: nếu phiên 3 chạy bằng gv_binh thì dùng **1633** (K22B, mã đề 103 / 104, dự thi 220006–220009; mặc định TRỐNG); gv_an thì **1632** (K22A, 101 / 102, 220001–220005; có sẵn phiếu nền – đừng chụp trùng SBD 220001–220005 đã có điểm).
Mật khẩu `admin`, `gv_an`, `gv_binh`: người trình bày tự nhớ; quên thì `& $py -m backend.tai_khoan dat-lai-mat-khau <tên>` (nhập bằng getpass, không ghi vào tệp).

**Đặt lại SAU MỖI phiên 3** (kể cả khi diễn tập; đây là lệnh XOÁ có phạm vi cố định 1380, 1381, 1633 về 0 phiếu và 1632 về nền – không đụng kỳ thi khác):
```powershell
& $py tools/dat_lai_demo.py                           # xem trước: chỉ phải liệt kê phiếu vừa tải của kỳ thi tập
& $py tools/dat_lai_demo.py --xac-nhan DAT_LAI        # xoá thật (sao lưu CSV + ảnh vào data\_eval\sao_luu_don_du_lieu\ trước)
& $py tools/kiem_truoc_demo.py --bo-qua-toc-do        # KHÔNG ĐẠT phải = 0
```
Đặt lại phải chạy **sau khi** tắt (Ctrl+C) hoặc dừng tải ảnh; đừng đặt lại giữa lúc điện thoại còn đang gửi.

---

## 1. PHIÊN 1 – Xử lý ảnh (≈ 3 phút)
**Mục tiêu:** cho thấy ảnh chụp tay → số liệu tin cậy qua từng bước, và quan trọng hơn: **khi nào máy từ chối / báo cờ thay vì đoán**.
**Chuẩn bị:** tab 1 `xu_ly_anh_T05_thuong.html`, tab 2 `xu_ly_anh_T03_kho.html`, tab 3 `xu_ly_anh_T05_mo_phong_nang.html` (và, nếu còn thời gian, `…_mo_phong_nhe.html`).

| Giờ | Thao tác | Lời dẫn (nhóm em) | Chỉ vào |
|---|---|---|---|
| 0:00–0:20 | Tab 1, đầu trang | “Đây là một phiếu thật chụp bằng điện thoại, chạy bằng đúng các hàm của hệ thống, không viết lại cho demo. Xử lý cả tờ khoảng 0,9 giây, trong đó nắn ảnh chiếm phần lớn; con số ‘tổng’ ở đầu trang (~1,3 giây) còn gồm cả thời gian vẽ các hình minh hoạ.” | dòng “tổng … ms”; hộp màu vàng “4/40 câu cần giáo viên xem” |
| 0:20–0:50 | Bước 1 → 2 → 3 | “Bước 1 là ảnh gốc xám, đã xoay đúng chiều theo EXIF. Bước 2 đo độ nét: ảnh này gấp hơn 25 lần ngưỡng nên đạt. Bước 3 tìm bốn ô vuông đen ở góc: vòng vàng là ứng viên, vòng xanh là bộ bốn góc được chọn sau khi kiểm hình học.” | thanh độ nét; tứ giác xanh với nhãn TL, TR, BR, BL |
| 0:50–1:20 | Bước 4 → 5 | “Từ bốn góc, nhóm em biến đổi phối cảnh về tờ A4 chuẩn 2480×3508, nên mọi ô nằm đúng toạ độ trong file layout. Giấy cong hoặc in lệch vài mi-li-mét, nên máy còn dò lại từng hàng; phiếu này lệch lớn nhất ≈ 1,2 mm.” | vòng xanh lá lệch khỏi chấm xanh dương ở bước 5 |
| 1:20–1:50 | Bước 6 | “Mỗi ô được phân ba lớp: trống, mờ, rõ. Khung đỏ là câu máy không chắc – ví dụ câu 10 tô mờ, câu 19 tô hai ô. Máy không chấm các câu này; nó chuyển cho giáo viên.” | khung đỏ câu 10, 19, 37, 39; bảng lý do bên dưới |
| 1:50–2:20 | Bước 7 → 8 | “Đây là chỗ máy học chạy: chín ô viết tay được cắt, chuẩn hoá 28×28 rồi đưa vào CNN. Nhưng nhóm em không tin CNN một mình: SBD và mã đề còn có kênh bubble. Chỉ khi hai kênh cùng chữ số thì mới tự nhận. Đây là cách tránh ghi nhầm điểm.” | khung “Đây là bước máy học nhận diện chữ số”; bảng bước 8 toàn “chắc” |
| 2:20–3:00 | Tab 2 (ảnh khó) rồi tab 3 (ảnh mờ mô phỏng) | “Ảnh thứ hai chụp trong điều kiện khó: cột SBD thứ 2 không tô bubble nên máy KHÔNG nhận mà báo ‘thiếu bubble’ dù CNN đọc ra 2. Ảnh thứ ba là ảnh **mô phỏng** – nhóm em làm nhoè một ảnh thật – bị từ chối ngay ở bước chất lượng và nói rõ lý do để chụp lại. Nắn sai mà vẫn chấm là ghi nhầm điểm, từ chối thì còn giáo viên.” | tab 2: hàng đỏ ‘thieu_bubble’, SBD “cần giáo viên xem”; tab 3: thẻ đỏ “Ảnh bị TỪ CHỐI” |

**Số liệu có thể nêu (nguồn: CLAUDE.md mục 6 / `docs/ke_hoach_tuan4.md` / `docs/ke_hoach_tuan5.md`):** nắn ảnh dev 78/78 đúng, 0 lỗi im lặng (thuật toán cũ 59/78, 19 lỗi im lặng); test 12/12 đúng.
OMR: 0 lỗi nặng trên 2 744 lượt câu + cột (OOF 7‑fold, CP95 ≤ 0,13%).
**Câu hỏi thầy có thể hỏi:**
- *Ảnh nghiêng / có bóng thì sao?* — Có 4 điều kiện chụp (C1–C4) trong dữ liệu; ảnh nghiêng quá (độ phối cảnh < 0,50) bị từ chối. Với ảnh C3 (nghiêng nhất) thuật toán cũ sai 15/17, thuật toán hiện tại đúng 17/17 trên dev.
- *Vì sao 4 ô vuông mà không dùng cạnh tờ giấy?* — Ô vuông đen có kích thước biết trước (8×8 mm, cách nhau 182 mm), dễ kiểm tra hình học và kiểm in đúng tỉ lệ; cạnh giấy dễ nhầm với nền bàn.
- *Ngưỡng độ mờ chọn thế nào?* — Ngưỡng `MO_MIN = 0,012` là ngưỡng **tạm, thận trọng**, chưa đo đầy đủ theo mức mờ; ghi trong nợ kỹ thuật Tuần 6 (nói thẳng nếu bị hỏi).
- *Ảnh mờ demo có phải ảnh thật không?* — Không: là mô phỏng bằng Gaussian blur (σ = 4 và 12 px trên ảnh 4284×5712), ghi rõ trong tên tệp và `DOC_TOI_DAY.txt`.
**Dự phòng:** trình duyệt không mở được trang → mở trang chụp màn hình `data/_eval/demo_3_phien/anh_chup/*.png` (đã sinh lúc kiểm). Trang bị trống ảnh → chạy lại mục 0.3 (5 giây / trang). Nếu máy chậm: chỉ cần tab 1 + tab 3 (2 phút).

---

## 2. PHIÊN 2 – Máy học (≈ 3 phút)
**Mục tiêu:** nói rõ máy học nằm ở đâu, dùng dữ liệu nào, có hơn các cách khác không, và **chỗ nào không đạt**.
**Chuẩn bị:** tab `may_hoc_truc_tiep.html` (đã có mục chạy CNN thật). Cuộn sẵn tới từng mục để khỏi cuộn lâu.

| Giờ | Mục trên trang | Lời dẫn (nhóm em) | Chỉ vào |
|---|---|---|---|
| 0:00–0:30 | 1. Dữ liệu | “Bài toán có hai loại dữ liệu: **ô chữ số viết tay** (3 872 ô dùng được từ 10 trang, **chỉ 5 người viết**; 504 ô trên phiếu để đo) và **ô tô** (14 000 ô từ 28 phiếu). Ngoài ra MNIST 60 000 để tiền huấn luyện. Phiếu để kiểm tra nhóm em chia theo mã phiếu, và tập test không đụng vào khi chỉnh tham số.” | bảng người viết × chữ số; bảng ô tô blank / filled / faint |
| 0:30–1:00 | 2. Hai mô hình | “Có hai mô hình. Ô tô dùng hồi quy logistic 40 tham số vì chỉ cần đo độ đậm. Chữ số dùng CNN nhỏ ~106 nghìn tham số, 0,4 MB, chạy bằng NumPy nên máy chấm không cần cài PyTorch.” | hai thẻ; dòng “40” và “105,866” |
| 1:00–1:50 | 3. So sánh | “Nhóm em so CNN với 5 thuật toán cổ điển bằng cùng quy trình: học từ 4 người, thử trên người thứ 5 chưa từng thấy, luân phiên. CNN đúng nhất, 95,4%; SVM 91,4%. Nhưng độ lệch giữa người là ±2,6 điểm, nên khác biệt nhỏ giữa các thuật toán không đáng tin; chênh CNN–SVM thì ổn định ở cả 5 người.” | cột xanh CNN; thanh sai số; “Xem dạng bảng” |
| 1:50–2:20 | 4. Chạy CNN thật | “Đây là CNN thật chạy ngay bây giờ trên 504 ô viết tay của phiếu, mô hình chưa từng huấn luyện trên chúng: 467/504 đúng, 92,7%. Dưới là 24 ô lấy ngẫu nhiên. Phần 8 ô sai bên dưới là nhóm em **chọn có chủ ý** để thấy kiểu sai: 3 với 9, 9 với 5. Tỉ lệ chung vẫn là 92,7%.” | khung xanh “467/504”; nhãn “CHỌN CÓ CHỦ Ý” |
| 2:20–2:50 | 6. Kết quả không đạt | “Nhóm em thử thêm khoảng 300 000 mẫu, gồm EMNIST và ô phiếu giả. Tiêu chí đặt trước là phải tăng ít nhất 1 điểm; thực tế chỉ tăng 0,36 điểm và số cột cần xem còn tăng nhẹ. Nhóm em không dùng. Nút thắt là chỉ có 5 người viết, không phải số lượng.” | khung vàng “KHÔNG ĐẠT”; 95,40% → 95,75% |
| 2:50–3:00 | 7. Giới hạn | “Giới hạn: 5 người viết, và ảnh quét sạch khác ảnh điện thoại. Vì vậy hệ thống không dựa vào độ đúng của CNN mà dựa vào đối chiếu hai kênh để lỗi im lặng bằng 0.” | mục “Giới hạn” |

**Nguồn số:** E2b `data/_eval/ai/ket_qua.json` (lệnh AI, 04/11/2026; tiêu chí đăng ký trước `docs/tieu_chi_so_sanh_thuat_toan.md`, commit `253a4b5`); âm tính `data/_eval/ad/ket_qua.json` / `docs/lenh_ad.md`; kiểm kê `docs/kiem_ke_du_lieu.md`.
Con số “92,7%” là kết quả chạy lại trực tiếp lúc dựng trang (`--truc-tiep` in số tương ứng); nếu máy khác phiên bản thư viện có thể lệch rất nhỏ.
**Câu hỏi thầy có thể hỏi:**
- *Sao không dùng OCR có sẵn?* — Lệnh D (28/10) đã thử thư viện OCR (PP‑OCRv6): đúng hơn CNN (98,2% so với 92,7% trên 504 chữ số phiếu dev) nhưng nặng hơn ~50 lần (~5,3 triệu tham số, +71 MB phụ thuộc, 54 ms so với 3,8 ms cho 9 chữ số), và lắp nguyên trạng làm số ảnh phải xem **tăng** (53,6% so với 46,4%) vì điểm tin cậy chưa hiệu chỉnh. Giữ CNN cho buổi bảo vệ; OCR là hướng cải tiến.
- *92,7% có đủ dùng không?* — Một mình thì không; vì thế có đối chiếu bubble. Lỗi im lặng mức trường (nhận nhầm SBD hay mã đề mà không báo) = 0 trên dev, đổi lại ≈ 46–54% ảnh phải giáo viên xem SBD / mã đề (mục tiêu 10% chưa đạt – nói thẳng).
- *Sao CNN kém trên phiếu (92,7%) hơn trên trang chữ số (95,4%)?* — Hai phép đo khác nhau (người viết, nền phiếu có viền / bubble, ảnh điện thoại); đây chính là khoảng cách giữa ảnh quét sạch và ảnh thật nói ở mục Giới hạn. Chưa có thí nghiệm tách nguyên nhân – không khẳng định.
- *Sao không dùng mô hình lớn hơn?* — Chỉ có 5 người viết; lệnh AD cho thấy thêm dữ liệu chỉ đổi kiểu lỗi (nhầm 8↔6 giảm, 1→7 tăng).
- *Test có bị rò rỉ không?* — Ranh giới dev / val / test chỉ định nghĩa ở `cv_engine/tap_du_lieu.py`; phiếu test 0035–0040 chạy MỘT lần theo đăng ký trước. Lưu ý: `omr.py` đã đổi sau commit đăng ký test cuối, nên kết quả test cuối 21/10 là của bản cũ (đã ghi trong tài liệu).
**Dự phòng:** nếu `--truc-tiep` lỗi (thiếu `data/_ocr/cat/`) → dùng `may_hoc.html` (không có mục 4, các mục còn lại không phụ thuộc dữ liệu thô) và nói “đã chạy thử trước, kết quả 467/504”. Trang trống → chạy lại mục 0.3.

---

## 3. PHIÊN 3 – Đồ án chuyên ngành: hệ thống chấm thật (≈ 6–7 phút)
**Mục tiêu:** từ quản trị → giáo viên chụp bằng điện thoại → máy chấm, **không đoán khi không chắc** → giáo viên duyệt → bảng điểm / Excel → phân quyền theo lớp.
**Chuẩn bị:** mục 0.4 đã xong; server chạy; máy tính mở `http://<IP LAN>:8000/` (Ctrl+F5); điện thoại đã nối cùng Wi‑Fi, quét QR thử, **chưa chụp**.
Dùng kỳ thi tập 1633 (gv_binh) cho diễn tập; phiếu BV06 (SBD 220006, mã đề 103, tô theo kịch bản `answer_sheet/demo_bv/`). Ảnh dự phòng: `data\_eval\demo_bv\anh_gia\BV06.jpg` (giả hoá, không có chữ viết tay).

| Giờ | Ai / ở đâu | Thao tác | Lời dẫn (nhóm em) | Kết quả mong đợi |
|---|---|---|---|---|
| 0:00–0:45 | máy tính, admin | Đăng nhập admin → Quản trị → **Quản lý kỳ thi** dòng kỳ thi (môn, lớp, giáo viên phụ trách) → **Trang bìa** (PDF) | “Admin tạo kỳ thi, gán lớp và giáo viên; giáo viên không tự tạo kỳ thi. Trang bìa có mã QR dẫn thẳng tới kỳ thi và không in đáp án.” | PDF có tên kỳ thi, QR `…/m?kythi=<id>` |
| 0:45–2:00 | điện thoại, gv_binh | Quét QR → đăng nhập gv_binh → kỳ thi đã chọn sẵn → **Chụp phiếu** BV06 | “Giáo viên chụp bằng điện thoại, ảnh đi thẳng lên máy chủ. Khoảng 2 giây có thẻ kết quả.” | thẻ kết quả: **điểm TẠM**, số câu cần xem (BV06 ảnh giả hoá: tạm 8,5; cần xem câu 10, 26) |
| 2:00–2:45 | máy tính, gv_binh | Đăng xuất → gv_binh → **Danh sách phiếu** | “Máy chỉ chấm các câu chắc chắn; câu cần xem không được chấm như câu chắc. Chưa có điểm chính thức.” | trạng thái “Cần xem”, điểm tạm |
| 2:45–4:15 | máy tính | **Duyệt** → khung “Chốt SBD / mã đề” (hai kênh cạnh nhau) → câu cần xem: ảnh câu + lý do → **Xác nhận như máy đọc** hoặc chọn ô → **Lưu** | “Đây là chỗ giáo viên quyết: ảnh từng câu cùng lý do. Ở SBD, bubble và chữ viết tay hiện cạnh nhau, giáo viên bấm chọn kênh đúng. Máy không tự chọn.” | sau câu cuối: “Đã chốt điểm chính thức”; BV06 = **9,0** nếu duyệt đúng giấy |
| 4:15–5:15 | điện thoại + máy tính | Chụp LẠI cùng tờ bằng một ảnh MỚI (không tải lại đúng tệp cũ) → **Duyệt** phiếu mới | “Phiếu trùng số báo danh không ghi đè điểm cũ mà bị giữ lại; giáo viên chọn bỏ phiếu mới hoặc dùng thay phiếu cũ, ghi nhật ký ai đã làm.” | “Trùng SBD với phiếu #…”; hai nút Bỏ / Thay → bấm **Bỏ phiếu chụp lại** |
| 5:15–6:00 | máy tính | **Bảng điểm** → **Xuất Excel** | “Bảng điểm chỉ có điểm chính thức; phiếu chưa duyệt hiện ở cột điểm tạm. Excel có môn, lớp và sheet chi tiết từng câu.” | Excel 2 sheet “Bảng điểm” + “Chi tiết” |
| 6:00–6:45 | máy tính | Đăng xuất → gv_an → ô Kỳ thi → gõ `#/sheet/<số phiếu BV06>` | “Giáo viên chỉ thấy lớp mình; phiếu của lớp khác trả về như không tồn tại, không lộ là có phiếu.” | không thấy kỳ thi K22B; phiếu → “Không có phiếu …” |

Tổng ≈ 6:45 (+ 0:15 chuyển cảnh). Nếu thiếu giờ: bỏ bước phiếu trùng (4:15–5:15) – đây là bước đầu tiên được cắt.

**Câu hỏi thầy có thể hỏi (phiên 3):**
- *Sao điểm chưa có ngay?* — Điểm chính thức chỉ có khi giáo viên xem hết hoặc máy không còn gì cần xem; đây là chủ ý: sai một câu cần xem còn tệ hơn mất 30 giây duyệt.
- *Ảnh thật có phải giáo viên xem nhiều hơn không?* — Có: trên dev khoảng 46–54% phiếu có SBD / mã đề cần xem (CNN chưa đủ chắc); giáo viên chốt một lần, điểm không sai. Đã thử 10 tờ giấy thật (13 ảnh): SBD / mã đề đạt tiêu chí H3 (0 sai âm thầm); tiêu chí C1 chính thức **KHÔNG ĐẠT** do 1 câu (T01 câu 37) – nhóm xác minh sau khi có kết quả thì người tô thực tế đã tô A, kịch bản ghi “bỏ trống” (bảng phụ `data/_eval/ag/sau_xac_minh.md`, **không thay** kết luận chính thức).
- *Nhiều giáo viên cùng chấm được không?* — Đăng nhập đồng thời, phân quyền theo lớp, mỗi (tên, IP) khoá riêng sau 5 lần sai đều ĐẠT ở lệnh AH. Rủi ro đã biết: hai ảnh **cùng SBD** gửi đồng thời → bên thua 409, phiếu không lưu (phải chụp lại); cùng tệp gửi hai lần cùng lúc → 3/10 lỗi 500; đăng xuất không thu hồi token; thông lượng ~2,7 ảnh/s. Chưa đo 40 tờ liên tục qua Wi‑Fi thật; chưa thử Android (chỉ iPhone / Safari).
- *Dữ liệu có an toàn không?* — Mật khẩu băm scrypt; cookie HttpOnly; phiên có hạn. Mật khẩu role CSDL còn nằm trong LỊCH SỬ git (commit cũ): nếu công khai repo phải đổi (ghi ở CLAUDE.md mục 8).
- *Ảnh phiếu lưu ở đâu?* — Trên đĩa (`STORAGE_DIR`), CSDL chỉ giữ đường dẫn; chính sách dọn ảnh tạm mặc định TẮT, chỉ bật khi chủ ý.
- *Thêm đề mới có phải train lại?* — Không; mô hình chỉ đọc ô / chữ số, đáp án nằm trong CSDL. Chỉ train lại khi đổi mẫu phiếu.
- *Có chạy trên Android / web thật không?* — Trang `/m` là HTML tĩnh dùng camera gốc; chưa thử Android; HTTPS + camera trực tiếp chỉ khảo sát, chưa làm.

**Dự phòng khi lỗi** (mỗi tình huống < 1 phút; chi tiết `docs/kich_ban_demo.md` mục 2):
| Tình huống | Xử lý |
|---|---|
| Wi‑Fi chặn điện thoại | Bật **hotspot điện thoại**, máy tính nối vào, Ctrl+C server, chạy lại `chay_server_lan.py --khong-xoa-anh` (IP mới) → nút **📱 Kết nối điện thoại** → quét QR trên màn hình (QR bìa in sẵn mang IP cũ). Đổi `PUBLIC_BASE_URL` nếu đã đặt. |
| Camera lỗi / ảnh đen | `/m` → **Chọn nhiều ảnh** chọn ảnh chụp sẵn; hoặc máy tính **Tải ảnh & chấm** kéo `BV06.jpg`. |
| Ảnh bị từ chối | Biến thành điểm trình bày (“máy không chấm ảnh không dùng được”), chụp lại thẳng, đủ 4 ô đen, đủ sáng. |
| Phiếu đã có điểm trong kỳ thi tập (SBD trùng) | Dùng SBD khác (BV07–BV09) hoặc chạy `dat_lai_demo` (mục 0.4) trước khi trình bày. |
| Server không lên / CSDL | `kiem_truoc_demo.py --bo-qua-toc-do` đọc dòng KHÔNG ĐẠT; `Get-Service postgresql-x64-17` → quản trị `Start-Service`; cổng bận: `Get-NetTCPConnection -LocalPort 8000 -State Listen`. |
| 429 khi đăng nhập | Chờ 15 phút, hoặc Ctrl+C rồi chạy lại server (bộ đếm nằm trong bộ nhớ). |
| Hai điện thoại cùng chụp một tờ | Một bên bị 409 và phiếu không lưu: chụp lại ở **một** điện thoại, chờ thẻ kết quả xong. |

**Sau phiên:** Ctrl+C tắt server → `dat_lai_demo` (mục 0.4) → xoá luật tường lửa → xoá ảnh phiếu trong thư viện ảnh điện thoại (cả “Đã xoá gần đây”).

---

## 4. Thứ tự và khoảng cách giữa các phiên
1. Phiên 1 → 2 chỉ đổi tab trình duyệt (không cần server). Giữ server TẮT cho tới phiên 3 nếu có thể, để không ai chạm CSDL trong lúc kiểm.
2. Giữa phiên 2 và 3: chạy mục 0.4 (kiểm → xem trước đặt lại → server) – chừa ≥ 5 phút.
3. Giữa hai lần chạy phiên 3 (diễn tập): đặt lại + kiểm lại (mục 0.4). Không chạy hai phiên 3 song song, kể cả hai kỳ thi khác nhau (cùng CSDL, cùng thư mục ảnh).
