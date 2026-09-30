# HƯỚNG DẪN LÀM PHIẾU TRẢ LỜI & THU DỮ LIỆU

Mục tiêu của bước này: trong khoảng **5–7 ngày** có được bộ dữ liệu thật **đã có nhãn sẵn** gồm:

| Dữ liệu | Số lượng | Dùng cho |
|---|---|---|
| Ảnh phiếu trả lời đã tô | 40 phiếu × 2 lần chụp = **80 ảnh** | Test pipeline OpenCV (Tuần 4), test cuối (Tuần 11) |
| Ô tròn đã cắt, có nhãn | ~6.400 ô/lượt chụp → **~12.800 ảnh ô** | Train OMR classifier (Tuần 5) |
| Chữ số viết tay trên phiếu | 360 chữ số (× 2 ảnh) | Đo domain gap của CNN (Tuần 6) |
| Chữ số trên trang thu chữ số | 1.000–2.000 chữ số | Fine-tune CNN (Tuần 6) |

---

## 1. Ý tưởng chính: "kịch bản trước – tô sau" (không phải gán nhãn tay)

Cách làm thường gặp là cho bạn bè tô tuỳ ý, rồi ngồi xem từng ảnh và ghi nhãn. Cách đó
rất tốn thời gian và dễ sai.

Bộ công cụ này làm ngược lại:

1. Máy **sinh trước** kịch bản cho từng phiếu, ví dụ phiếu `0001`: SBD `062384`, mã đề `101`,
   câu 1 tô mờ D, câu 13 tô cả A và C, câu 7 bỏ trống...
2. Kịch bản được lưu trong `ground_truth.csv`, đồng thời in thành **phiếu giao việc**.
3. Người tô chỉ việc **làm theo phiếu giao việc**.
4. Mỗi phiếu có **Mã phiếu** in sẵn ở góc, nên ảnh chụp luôn nối được với đúng dòng
   trong `ground_truth.csv`, tức là nhãn đã có sẵn.

Đây cũng là điểm nên trình bày trong báo cáo: *thu thập dữ liệu có kiểm soát (controlled
data collection)*. Các lớp hiếm (tô mờ, tô 2 ô) được cố ý tạo nhiều hơn thực tế để chống
mất cân bằng dữ liệu.

---

## 2. Thiết kế phiếu – vì sao lại như vậy

![Phiếu trả lời](output/preview_phieu.png)

| Thành phần | Thiết kế | Lý do |
|---|---|---|
| 4 ô vuông đen ở góc | 8×8 mm, tâm cách mép 14 mm | OpenCV tìm 4 ô này để **nắn phẳng ảnh** (perspective transform). Ô vuông đặc, to, ở góc là thứ dễ tìm nhất và khó nhầm nhất |
| Ô viết tay SBD / mã đề | 6×9 mm, mỗi ô 1 chữ số | Cắt từng ô ra rồi đưa vào **CNN nhận diện chữ số**. Mỗi ô đúng 1 chữ số nên không phải tách chữ |
| Bubble SBD / mã đề (0–9) | Dưới mỗi ô viết tay | **Kênh thứ hai** để đọc SBD. Khi CNN đọc chữ viết và OMR đọc ô tô cho cùng kết quả thì tăng confidence; lệch nhau thì đưa vào review. Đây là một điểm cộng cho bài toán *ghi nhầm điểm* |
| 40 câu × 4 ô (A–D) | Ô Ø 5 mm, cách nhau 7 mm ngang, 11 mm dọc | Ô to và thưa thì classifier dễ học, ảnh điện thoại hơi mờ vẫn đọc được |
| Chữ A/B/C/D mờ trong ô | Màu xám 55% | Người tô dễ nhìn, còn máy vẫn phân biệt được ô trống với ô tô |
| Mã phiếu (0001…) | Góc trên phải | Nối ảnh với nhãn. Phiếu dùng cho kỳ thi thật (`phieu_trang.pdf`) không có dòng này |

**Mọi toạ độ nằm trong `sheet_layout.py`.** Chạy `generate_sheets.py` sẽ vẽ PDF, xuất
`layout.json` (toạ độ pixel ở 300 DPI) và tạo `update_template.sql` để ghi layout vào bảng
`sheet_templates` trong database. Nhờ vậy PDF, file toạ độ và database luôn khớp nhau.
Muốn đổi bố cục thì chỉ sửa `sheet_layout.py` rồi chạy lại.

---

## 3. Các bước thực hiện

### Bước 1 – Sinh file (10 phút)
```bat
cd answer_sheet
pip install reportlab opencv-python numpy pymupdf
python generate_sheets.py            REM 40 phiếu đánh số + 10 trang chữ số + layout.json
python make_dataset_plan.py          REM ground_truth.csv + cell_labels.csv + phieu_giao_viec.pdf
python check_layout.py               REM phải in ra "KẾT QUẢ LAYOUT: KHỚP"
psql -U smart_exam_app -h localhost -d smart_exam -f output/update_template.sql
```
`check_layout.py` sẽ tô giả phiếu 0001, làm nghiêng, làm mờ, rồi đọc lại. Nếu thấy
**KHỚP** thì toạ độ đúng và có thể in. Dòng "[Tham khảo] rule-based" sẽ cho thấy cách đặt
ngưỡng cố định đọc sai ô tô mờ. Đó là bằng chứng đưa vào báo cáo cho lý do cần classifier.

### Bước 2 – In (≈ 70 trang A4)
| File | Số trang | Ghi chú |
|---|---|---|
| `phieu_danh_so.pdf` | 40 | In 1 mặt, giấy A4 trắng 70–80 gsm |
| `phieu_giao_viec.pdf` | 20 | 2 phiếu giao việc/trang, cắt đôi |
| `trang_chu_so.pdf` | 10 | |

- Khi in, chọn **Actual size / 100%**, **không** chọn "Fit to page".
- In xong, lấy thước đo khoảng cách **tâm 2 ô vuông trên cùng**: phải là **182 mm (±1 mm)**.
- **Không in trên máy in hết mực.** Marker bị sọc thì OpenCV sẽ không tìm được.

### Bước 3 – Tô phiếu theo kịch bản (2–3 buổi)
Nhờ 5–10 người, mỗi người 4–8 phiếu. Mỗi phiếu đi kèm **đúng phiếu giao việc cùng mã**.

1. Viết SBD và mã đề vào ô vuông theo phiếu giao việc, rồi tô bubble tương ứng.
2. Tô 40 câu theo ký hiệu:
   - `B` (chữ hoa, đậm): **tô kín** ô B.
   - `b` (chữ thường, xám, có chữ "mờ"): **tô nhẹ tay**, chỉ phủ khoảng 50–70% ô, giống
     thí sinh tô vội hoặc bút chì nhạt.
   - `AC`: tô kín **cả hai** ô A và C.
   - `–`: bỏ trống.
3. Dùng **đúng loại bút** ghi trên phiếu giao việc (chì 2B / bi xanh / bi đen). Mục đích là
   để dữ liệu đa dạng.
4. Tô xong thì đánh dấu ☐ "Tô xong", rồi kẹp phiếu giao việc với phiếu trả lời.

**Nếu người tô làm sai** (tô nhầm ô, tô rõ thay vì tô mờ...): **không vứt phiếu**. Ghi lại
câu bị sai vào phiếu giao việc, sau đó **sửa lại đúng dòng đó trong `ground_truth.csv`** cho
khớp với thực tế, rồi chạy `python make_dataset_plan.py --from-csv` để sinh lại
`cell_labels.csv`. Nhãn phải phản ánh cái có trên giấy, không phải cái dự định.

**Người viết thật, dữ liệu giả:** SBD trong kịch bản là số ngẫu nhiên, không dùng MSSV hay
họ tên thật. Ô "Họ và tên" để trống, nhờ vậy dữ liệu có thể đưa lên Kaggle/GitHub mà
không lộ thông tin cá nhân.

### Bước 4 – Trang thu chữ số (song song với Bước 3)
Mỗi người viết **1 trang**, ghi tên viết tắt vào dòng "Người viết". Ở mỗi hàng, viết lặp
lại đúng chữ số in đậm ở đầu hàng, viết tự nhiên như khi ghi SBD (không cần viết đẹp).
Không cần viết kín cả trang: mỗi chữ số 10–20 ô là đủ, ô trống sẽ tự bị bỏ qua khi cắt.

Tại sao cần trang này: 40 phiếu chỉ có 360 chữ số, và phân bố lệch (mã đề 101–104 làm số 0
và 1 xuất hiện nhiều). Trang thu chữ số cho **1.000–2.000 chữ số cân bằng 0–9**, **cùng
kích thước ô** với phiếu thật. Đây chính là dữ liệu cho bước fine-tune ở Tuần 6.

### Bước 5 – Chụp ảnh (1 buổi)
Mỗi phiếu chụp **2 lần**, theo 2 điều kiện ghi trên phiếu giao việc:

| Mã | Điều kiện | Cách làm |
|---|---|---|
| C1 | Đủ sáng, thẳng | Ban ngày gần cửa sổ, điện thoại song song mặt phiếu |
| C2 | Thiếu sáng | Phòng tối hoặc buổi tối, **không bật flash** |
| C3 | Nghiêng | Nghiêng điện thoại 15–25°, phiếu đặt trên bàn |
| C4 | Đèn vàng / có bóng | Dưới đèn vàng, để bóng tay hoặc bóng điện thoại đổ lên một phần phiếu |

**Quy tắc bắt buộc:**
- **Đủ cả 4 ô vuông đen trong khung hình**, chừa một chút viền bàn xung quanh.
- Phiếu nằm phẳng, không gập, không cầm trên tay.
- Độ phân giải gốc của điện thoại (≥ 8MP). **Không gửi qua Zalo/Messenger**, vì ứng dụng sẽ
  nén ảnh. Hãy chép bằng cáp hoặc Google Drive.
- Trang thu chữ số chỉ cần chụp 1 lần ở điều kiện C1.

**Đặt tên file ngay khi chép vào máy:**
```
data/raw/0001_C1.jpg     data/raw/0001_C2.jpg     data/raw/0002_C2.jpg ...
data/raw_digits/D001.jpg data/raw_digits/D002.jpg ...
```

### Bước 6 – Kiểm tra ảnh ngay sau buổi chụp
```bat
python check_photos.py --dir ..\data\raw
python check_photos.py --dir ..\data\raw_digits
```
Script báo ảnh nào **sai tên, mờ (blur < 100), thiếu độ phân giải hoặc không tìm đủ 4
marker**, và lưu ảnh đã nắn phẳng vào `_aligned/`. **Chụp lại ngay các ảnh LỖI** khi phiếu
vẫn còn trong tay. Mở vài ảnh trong `_aligned/` để tự kiểm tra xem ảnh đã thẳng chưa.

### Bước 7 – Sao lưu & cấu trúc dữ liệu
```
data/
├── raw/                 80 ảnh phiếu gốc (không bao giờ sửa file gốc)
├── raw_digits/          10 ảnh trang chữ số
├── ground_truth.csv     copy từ answer_sheet/output (đã sửa theo thực tế nếu có)
├── cell_labels.csv
└── split.csv            (Tuần 5) chia train/val/test theo MÃ PHIẾU
```
Sao lưu thư mục `data/` lên Google Drive. Thư mục này **không push lên GitHub** (thêm
`data/` vào `.gitignore`); có thể đưa lên Kaggle Datasets ở chế độ private để train.

---

## 4. Lưu ý quan trọng về học máy (nên đưa vào báo cáo)

**a. Chia train/val/test theo *phiếu*, không theo *ảnh*.**
Hai ảnh C1 và C2 của cùng một phiếu có cùng nét tô và nét chữ. Nếu một ảnh rơi vào train
còn ảnh kia rơi vào test, độ chính xác đo được sẽ cao ảo (data leakage). Đề xuất chia như sau:
- Phiếu `0001–0028`: train (70%)
- Phiếu `0029–0034`: validation (15%)
- Phiếu `0035–0040`: test (15%). **Không** dùng để fine-tune hay chỉnh ngưỡng.

**b. 4 trạng thái nên xử lý ở hai cấp.**
Trạng thái "tô nhiều đáp án" là thuộc tính của **cả câu**, không phải của một ô. Vì vậy nên:
- Train classifier **cấp ô** với 3 lớp: `blank` / `filled` / `faint` (nhãn lấy từ `cell_labels.csv`).
- Dùng luật **cấp câu**: có ≥ 2 ô `filled` thì là `multiple`; có 1 ô là đáp án; không có ô
  nào thì là `blank`.

Kết quả cuối vẫn là đúng 4 trạng thái như kế hoạch, và cột `question_state` trong
`cell_labels.csv` dùng để đánh giá ở cấp câu. Nên ghi rõ điều chỉnh này trong báo cáo
Tuần 5.

**c. Mất cân bằng lớp.** Kể cả khi đã cố ý tăng, `faint` vẫn chỉ khoảng 4% số ô (≈ 260 ô ×
2 ảnh). Ở Tuần 5 hãy dùng augmentation (xoay nhẹ, đổi độ sáng, nhiễu) và `class_weight`,
đồng thời báo cáo **F1 theo từng lớp** thay vì chỉ accuracy.

---

## 5. Lịch gợi ý & checklist

| Ngày | Việc | Xong |
|---|---|---|
| 1 | Chạy Bước 1, in thử 1 phiếu, đo 182 mm, in hết | ☐ |
| 2–4 | Phát phiếu + phiếu giao việc + trang chữ số, thu về | ☐ |
| 5 | Chụp 80 ảnh + 10 trang chữ số | ☐ |
| 5 | `check_photos.py`, chụp lại ảnh lỗi | ☐ |
| 6 | Sửa `ground_truth.csv` theo lỗi người tô, sao lưu `data/` | ☐ |

Xong bước này là có đủ dữ liệu cho **Tuần 4**: viết `preprocessing.py`. Hàm `align()` trong
`check_layout.py` chính là phiên bản đầu tiên của module đó.
