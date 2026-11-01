# Hướng dẫn thử GIẤY THẬT (lệnh AG)

Mục tiêu: tô phiếu thật theo kịch bản, chụp bằng điện thoại, chấm so với đáp án đúng để đo (1) tỉ lệ "cần xem" khi dùng bình thường, (2) sai âm thầm
trên giấy thật (kể cả ô tẩy), (3) kết luận H3. Tiêu chí đã chốt TRƯỚC: `docs/tieu_chi_thu_giay_that.md` – không đổi sau khi thấy kết quả.

**Thời gian ước lượng: 45–60 phút** (in 5 phút · tô 6–8 phút / tờ, 5 người song song ≈ 20 phút · chụp 13 ảnh ≈ 10 phút · chép ảnh + chấm ≈ 5 phút).

## Bước 1 – Tạo tệp (đã có sẵn nếu chạy rồi)
```powershell
python tools/ag_tao_kich_ban.py          # kịch bản + 2 PDF + tự kiểm khổ in (phải in "ĐẠT")
```
Tạo `data/_eval/ag/kich_ban.json`, `phieu_trang_in_10.pdf` (10 phiếu trống), `phieu_giao_viec_ag.pdf` (bìa + 10 trang). Không sửa tay `kich_ban.json`.

## Bước 2 – In
- In **cả hai** tệp PDF, khổ **A4**, **tỉ lệ 100% / Actual size**. **KHÔNG** chọn "Fit to page", "Vừa trang", "Shrink oversized pages".
  Phần mềm in hay tự chọn lại "Fit" – kiểm lại mỗi lần mở hộp thoại in.
- Phiếu trống: 1 mặt, trắng đen. Kiểm nhanh bằng thước: tâm 2 ô vuông đen phía trên cách nhau **182 mm**.
- Phiếu giao việc: in thường (đen trắng được).

## Bước 3 – Phân công và tô
- Khuyến khích **5 người khác nhau, mỗi người 2 tờ** (ghi trên trang bìa phiếu giao việc). Tốt nhất có người KHÁC 5 người đã viết trang chữ số D001–D010.
- Mỗi phiếu trống: ghi số tờ (ví dụ **T03**) vào ô "Họ và tên" – **không ghi tên thật**, không ghi thông tin cá nhân.
- Dùng đúng bút của tờ (T01–T04 bi xanh, T05–T08 bi đen, T09–T10 **chì 2B** – chỉ hai tờ này có câu "tẩy").
- SBD / mã đề: viết chữ số tay vào 6 + 3 ô **và** tô ô tròn tương ứng. **T03, T06, T10** có một cột "chỉ viết, KHÔNG tô ô tròn" – làm đúng như trang của tờ đó.
- 40 câu: làm đúng bảng. Câu nền xám là câu đặc biệt:
  - *tô nhẹ*: tô nhạt, không kín, như tô vội;
  - *tô 2 ô*: tô đậm cả hai ô;
  - *tẩy* (chỉ chì): tô ô đầu, tẩy bằng tẩy bút chì như thí sinh đổi ý, rồi tô ô sau;
  - *để trống*: không đụng bút;
  - *chấm*: một chấm nhỏ đầu bút vào ô ghi trong hướng dẫn (trước hoặc sau khi tô ô chính) – KHÔNG tô.
- Lỡ làm khác kịch bản: **ghi lại** ở cuối trang của tờ đó (câu nào, đã tô gì). Không tô thêm để "sửa". Báo lại khi chấm – nhãn chỉ sửa theo giấy, và phải ghi rõ.

## Bước 4 – Chụp
- Đặt phiếu **phẳng** trên mặt bàn tối màu hơn giấy, đủ sáng, **thấy đủ 4 ô vuông đen ở 4 góc** (không bị khung hình cắt), không có tờ khác lọt vào.
- Chụp thẳng từ trên xuống, không dùng đèn flash nếu gây loá.
- Đặt tên: **T01.jpg … T10.jpg** (mỗi tờ 1 ảnh, điều kiện thường).
- Thêm **3 ảnh điều kiện khó** (chụp LẦN 2 của 3 tờ khác nhau, ví dụ T01, T05, T09): một ảnh có **bóng đổ** (tay / điện thoại che một phần), một ảnh **nghiêng nhẹ ~10°**,
  một ảnh dưới **đèn vàng**. Tên: **T01_kho.jpg**, **T05_kho.jpg**, **T09_kho.jpg** (đúng số tờ đã chụp lại). Ghi điều kiện vào ô "Đèn" của phiếu giao việc.
- HEIC của iPhone được (pipeline đọc được), PNG / JPG được. **Không gửi ảnh qua Zalo / Messenger** (bị nén) – chép bằng cáp hoặc Google Drive.

## Bước 5 – Chấm
```powershell
# chép ảnh vào smart_exam_db\data\anh_that_ag\  (thư mục này nằm trong data/ – KHÔNG vào git)
python tools/ag_cham_that.py cham
```
Kết quả: `data/_eval/ag/ket_qua.md` (+ `ket_qua.json`): kết luận **C1** (sai âm thầm = 0), **H3**, bảng C2 / C3, danh sách từng sai âm thầm, ảnh bị từ chối kèm lý do.
Ảnh bị từ chối (thiếu ô vuông, mờ…) KHÔNG phải lỗi của bài – nhưng tờ không còn ảnh nào đọc được sẽ ghi "chưa kiểm được"; có thể chụp lại **trước khi** chạy chấm lần đầu.
**Chỉ chạy chấm MỘT lần trên bộ ảnh cuối cùng** và ghi lại; không chụp lại / chạy lại để "có kết quả đẹp hơn".

Công cụ chạy offline: không ghi cơ sở dữ liệu, không cần bật server. Tự kiểm công cụ (ảnh giả lập, không dùng kết luận): `python tools/ag_cham_that.py tu-kiem`.

## Bảo mật
Không chụp thông tin cá nhân thật (tên, MSSV, mặt người). Ô "Họ và tên" chỉ ghi số tờ hoặc tên giả. Ảnh chỉ để trong `data/anh_that_ag/` (ngoài git).
