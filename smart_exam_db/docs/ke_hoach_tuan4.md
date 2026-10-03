# Kế hoạch Tuần 4 – `cv_engine/preprocessing.py`

Mục tiêu: nắn phẳng ảnh phiếu chụp bằng điện thoại về đúng toạ độ `layout.json` (300 DPI),
và **không bao giờ trả về ảnh nắn sai mà báo OK**. Ảnh không nắn được phải bị *từ chối có lý do*
(sau này hệ thống đưa vào review / yêu cầu chụp lại).

Điểm xuất phát: `align()` / `find_markers()` trong `answer_sheet/check_layout.py`, nắn sai nhiều ảnh
mà không báo lỗi (CLAUDE.md mục 8 – 4 nguyên nhân). Con số "23/90" trong ghi chú cũ **không dùng**:
liệt kê ra là 24 ảnh và còn thiếu 0013_C2, 0018_C2. Số liệu "trước" lấy từ `data/_eval/align_cu/truth_dev.csv`
(Bước 1).

## Quy tắc dữ liệu (chống "học thuộc" tập kiểm tra)

| Tập | Phiếu | Số ảnh | Dùng để |
|---|---|---|---|
| Phát triển (dev) | 0001–0034 + trang chữ số D001–D010 | 68 + 10 (C1 17, C2 18, C3 17, C4 16) | Thử ý tưởng, chỉnh **mọi** tham số/ngưỡng, xem ảnh lỗi |
| Đánh giá cuối (test) | 0035–0040 | 12 (C1 3, C2 2, C3 3, C4 4) | Chạy **một lần duy nhất** ở bước 7, sau khi đã chốt code |

- Không mở ảnh nắn của 0035–0040, không chỉnh tham số theo kết quả của chúng. Nếu lỡ dùng → ghi rõ
  vào báo cáo rằng số liệu test không còn khách quan.
- Ranh giới 0034/0035 trùng với ranh giới val/test của OMR (CLAUDE.md mục 4), nên test của Tuần 4
  cũng là test của Tuần 5 – không rò rỉ giữa hai tuần.
- Trang chữ số `D001–D010` thuộc **dev** của preprocessing. Không rò rỉ: Tuần 6 dùng chúng để fine-tune
  CNN, còn tập test chữ số là 360 chữ số viết tay trên phiếu (CLAUDE.md mục 4).
- Marker trang chữ số **trùng vị trí** với phiếu (đã kiểm tra 03/10/2026): cả hai `layout.json` và
  `digit_sheet_layout.json` sinh từ cùng `MARKER_CENTERS_MM` (tâm 165,4 / 2315,0 / 3342,5 px, cạnh 94,5 px,
  trang 2480×3508), và `generate_sheets.py` vẽ cả hai trang bằng cùng `draw_markers()`. ⇒ Bước 3 dùng
  chung tỉ lệ 182:269 mm, không cần tỉ lệ riêng. Khác nhau chỉ ở nội dung bên trong (phép so phiếu trắng
  phải dùng đúng trang mẫu).

## Định nghĩa đo (dùng chung cho mọi bước)

Công cụ: `tools/eval_preprocessing.py` (bước 1). Phương pháp được chấm có giao diện
`f(duong_dan) -> (anh_nan | None, ly_do)`: **phương pháp tự đọc file** (để bước đọc ảnh/EXIF cũng được
chấm – ca 0006 nằm ngang nằm ở đây). `align()` cũ được bọc thành `imread + align`. Từ chối = `anh_nan`
là `None` hoặc phương pháp ném lỗi; lý do ghi vào CSV. Mỗi ảnh được xếp vào **một** trong 3 loại:

| Loại | Nghĩa | Mong muốn |
|---|---|---|
| **đúng** | hàm trả ảnh nắn, và phép kiểm tra độc lập xác nhận nắn đúng | càng nhiều càng tốt |
| **lỗi im lặng** | hàm trả ảnh nắn (coi như OK) nhưng thực ra nắn sai | **= 0** (lỗi nguy hiểm nhất: ghi nhầm điểm) |
| **bị từ chối** | hàm báo lỗi / không trả ảnh | chấp nhận được, nhưng càng ít càng tốt |

Kết luận đúng/sai **gắn với từng phương pháp**: `data/_eval/<ten_phuong_phap>/truth_dev.csv` (cột
`phuong_phap, anh, ket_luan, nguon, ghi_chu`; `nguon` = `tu_dong` / `mat`). Mỗi phiên bản preprocessing
sau này có thư mục riêng và phải được chấm lại. Kết luận lập bằng 3 phép kiểm tra độc lập với phương pháp
được đo (không dùng `check_align()` cũ) cộng xem bằng mắt các ca không rõ:
1. **Marker**: tâm 6×6 mm của cả 4 marker trên ảnh nắn đen ≥ 0,95 (marker thật ~1,0; ảnh nắn sai lọt
   ngưỡng 0,5 cũ có 0,68 và 0,83). Phép này *không* độc lập với `align()` (align ép 4 điểm nó chọn về
   đúng chỗ marker) – chỉ là tín hiệu phụ.
2. **So phiếu trắng bằng nét**: so bản đồ cạnh (gradient/Canny) của ảnh nắn với bản đồ cạnh của
   **trang mẫu tương ứng** (phiếu NNNN của `phieu_danh_so.pdf`; trang DNNN của `trang_chu_so.pdf`), render
   300 DPI. **Bỏ vùng quanh 4 marker** (để độc lập với `align()`), không so độ sáng thô (ảnh C2 tối, C4 đèn
   vàng). Chia trang thành nhiều ô lưới, mỗi ô tìm độ lệch tốt nhất → điểm khớp + độ lệch lớn nhất (mm).
   Bắt được ảnh nắn lệch/xoay/lật dù 4 góc vẫn rơi vào vùng đen.
   **Rủi ro khớp nhầm chu kỳ**: ô tròn lặp đều 7 mm ngang / 11 mm dọc (bubble chữ số 5,8 mm dọc) – ảnh
   lệch đúng 1 chu kỳ vẫn "khớp" trong vùng ô tròn. Chống lại bằng: (i) độ lệch toàn trang tìm trước trên
   các ô có tiêu đề/chữ in (không lặp), cửa sổ lớn hơn chu kỳ dài nhất; (ii) bỏ/giảm trọng số ô lưới có
   đỉnh khớp không duy nhất (đỉnh thứ hai ở xa gần bằng đỉnh nhất); (iii) độ lệch các ô lưới phải nhất quán
   với nhau và với độ lệch toàn trang. Tự kiểm chứng bằng ca dịch đúng 7 mm ngang, 11 mm dọc.
   Ngưỡng `lech_max_mm` **không được vượt dung sai của OMR** (không chỉ dựa vào khoảng trống giữa nhóm
   đúng/sai bằng mắt); dung sai đo bằng thí nghiệm dịch ảnh ở Bước 1.
   **Giấy cong** (vd 0014_C2, lệch cục bộ ~3 mm dù 4 marker đúng) – hướng, *chốt sau khi có số liệu
   dung-sai*: đúng/sai của preprocessing xét theo `lech_toan_trang_mm` và `lech_trungvi_mm` (chọn đúng
   marker, đúng chiều, nắn đúng); `lech_max_mm` cục bộ vẫn ghi lại kèm cờ `giay_cong` và chuyển thành
   **yêu cầu cho Tuần 5**: OMR phải dò lại vị trí từng hàng.
3. **Đối chiếu nhãn** (chỉ phiếu, không có cho trang chữ số): trong mỗi hàng câu, ô `filled` theo
   `cell_labels.csv` phải tối hơn rõ rệt các ô `blank` cùng hàng (đo tại toạ độ layout, không dò lại vị trí).

Ngưỡng của phép 2 và 3 chọn từ các ảnh **đã kiểm tra bằng mắt**, không đoán. Ảnh mà 3 phép không thống
nhất hoặc sát ngưỡng → xuất HTML cho người dùng xem → kết luận bằng mắt.

**Phép so phiếu trắng (2) và đối chiếu nhãn (3) CHỈ dùng trong `tools/eval_preprocessing.py`.** Tự kiểm
tra của `preprocessing.py` ở Bước 5 **không được** dùng lại chúng (cũng không import code của chúng): nếu
dùng chung, lỗi của phép đo sẽ trùng lỗi của hàm được đo và lỗi im lặng bị che mất. Lúc chạy thật cũng
không có nhãn hay mã phiếu để chọn trang mẫu.

`data/_eval/align_cu/truth_dev.csv` là số liệu "trước". Từ Bước 2, mỗi phương pháp mới được chấm lại bằng
đúng 3 phép kiểm tra và ngưỡng đã chốt ở Bước 1 (`data/_eval/nguong.json`, không chỉnh theo phương pháp
mới); ca không rõ lại xem bằng mắt, ghi vào `truth_dev.csv` của phương pháp đó.

Báo cáo luôn tách theo điều kiện chụp **C1–C4**.

## 8 bước

### Bước 0 – Chuẩn bị
- **Việc**: tạo `smart_exam_db/cv_engine/`; ghi quy tắc dev/test; viết kế hoạch này.
- **Cách đo**: không có.
- **Xong khi**: thư mục + tài liệu có, CLAUDE.md ghi quyết định; người dùng duyệt.

### Bước 1 – Công cụ đánh giá + số liệu "trước"
- **Việc**: `tools/eval_preprocessing.py` nhận một hàm nắn ảnh bất kỳ, `--split dev|test` (mặc định
  dev = 0001–0034 + D001–D010; **Bước 1 không chạy test**), phân loại đúng / lỗi im lặng / bị từ chối,
  xuất bảng theo C1–C4 (+ dòng trang chữ số) và HTML các ca cần xem bằng mắt. Chạy với `align()` cũ
  (không sửa `check_layout.py`). Chỉ ghi vào `data/_eval/`, không đụng `data/raw/`, `data/raw_digits/`.
- **Cách đo**: script chấm tự động bằng 3 phép kiểm tra → ca không thống nhất / sát ngưỡng ra HTML →
  người dùng xem bằng mắt → kết luận cuối ghi `data/_eval/align_cu/truth_dev.csv`. **Không** suy số
  "trước" từ ghi chú CLAUDE.md mục 8 (danh sách đó tự mâu thuẫn; chỉ dùng để đối chiếu, lệch thì giải thích).
  Tự kiểm chứng phép 2 bằng ảnh đúng (đã xem bằng mắt) bị làm hỏng cố ý: dịch 2 mm, dịch 7 mm ngang,
  11 mm dọc, 5,8 mm dọc (bước bubble SBD/mã đề – lần chạy đầu đã có 4 ô lưới khớp nhầm đúng bước này), xoay 1°, xoay 180°, nhầm loại trang (mẫu trang chữ số cho ảnh phiếu và ngược lại) – phải
  bắt được hết. (Không kiểm "nhầm phiếu NNNN": 40 trang `phieu_danh_so.pdf` chỉ khác chữ số cuối của
  "Mã phiếu" – vùng ~184–188 × 25–27,5 mm, kiểm tra pixel 03/10/2026; 10 trang `trang_chu_so.pdf` cũng
  vậy – nên phép 2 dùng 1 mẫu cho mỗi loại trang, che vùng mã. Sai tên ảnh do `prepare_photos.py
  verify-ids` lo.) Thí nghiệm dung sai OMR: dịch ảnh
  đúng 0–4 mm, đo khi nào ô `filled` không còn tách khỏi ô `blank`.
- **Xong khi**: `align_cu/truth_dev.csv` có đủ 78 dòng dev; ngưỡng phép 2, 3 chốt (≤ dung sai OMR) và ghi
  lại kèm ảnh làm căn cứ; bảng "trước" theo C1–C4 tái tạo được từ file đó bằng một lệnh.

### Bước 2 – Tìm ứng viên marker (nguyên nhân 1, 3)
- **Việc**: nới tỉ lệ w/h (≈ 0,5–2,0), xem lại ngưỡng độ đặc / số đỉnh cho marker méo; giữ
  *nhiều* ứng viên – việc chọn để bước 3.
- **Cách đo**: tỉ lệ ảnh dev có đủ 4 marker thật trong danh sách ứng viên (marker thật = điểm mà ảnh
  nắn đúng chiếu ngược ra); số ứng viên trung bình/ảnh.
- **Xong khi**: 100% ảnh dev có đủ 4 marker thật trong ứng viên (hoặc ảnh thiếu được giải thích từng cái).

### Bước 3 – Chọn 4 marker theo hình học (nguyên nhân 2, 3)
- **Việc**: thay "gần góc ảnh nhất" bằng tìm bộ 4 ứng viên tạo tứ giác lồi, tỉ lệ cạnh ~182:269 mm
  (cho phép phối cảnh), 4 marker cùng cỡ; ưu tiên bộ có điểm kiểm tra cao nhất.
- **Cách đo**: `eval_preprocessing.py` trên dev.
- **Xong khi**: số ảnh "đúng" tăng rõ so với bước 1, đặc biệt C3; không tăng lỗi im lặng.

### Bước 4 – Xác định chiều phiếu (nguyên nhân 4)
- **Việc**: thử 4 cách gán TL/TR/BR/BL (xoay 0/90/180/270°), chọn chiều bằng nội dung (không tin EXIF),
  bằng một dấu hiệu **riêng của preprocessing** (ví dụ vị trí khối ô đáp án / dòng tiêu đề so với marker),
  không dùng phép so phiếu trắng của `eval_preprocessing.py`.
- **Kiểm tra chiều phải dựa trên NỘI DUNG, không dựa marker**: 4 marker giống hệt nhau, ảnh xoay 90°/180°
  vẫn có marker thật ở cả 4 góc ⇒ độ đen marker (phép 1, và mọi tự kiểm tra kiểu đó ở Bước 5) về bản chất
  không bắt được lỗi chiều. 0006_C2/0006_C3 (`align_cu`, 03/10/2026) chỉ hụt nhẹ (đen 0,85 / 0,90) vì
  trang dọc bị ép vào tứ giác ngang (méo ~1,48 : 0,68) làm ô kiểm tra 6×6 mm lấn ra ngoài marker – tình
  cờ, không dựa vào được (ảnh xoay 180° sẽ đen 1,00).
- **Cách đo**: `eval_preprocessing.py` trên dev, riêng 0006_C2, 0006_C3 phải "đúng".
- **Xong khi**: 0006 nắn đúng; không ảnh nào khác đổi từ đúng sang sai.

### Bước 5 – Tự kiểm tra sau khi nắn + từ chối có lý do
- **Việc**: `preprocessing.py` tự kiểm tra kết quả (độ đen marker, hình học 4 marker, dấu hiệu bố cục riêng –
  **không** dùng lại phép 2/3 của `eval_preprocessing.py`) và **raise lỗi có
  mã lý do** (`thieu_marker`, `marker_khong_dat`, `khong_khop_mau`…) thay vì trả ảnh sai. Đo thêm độ nét
  (Laplacian) cho `answer_sheets.blur_score`.
- **Cách đo**: `eval_preprocessing.py` trên dev + ảnh giả có lỗi cố ý (che 1 marker, tờ khác lọt khung).
- **Xong khi**: **lỗi im lặng = 0** trên dev và trên ảnh giả; mỗi ảnh bị từ chối có lý do đúng.

### Bước 6 – Hoàn thiện module, nối vào công cụ cũ
- **Việc**: API gọn (`preprocess(path) -> kết quả`), docstring tiếng Việt; `check_photos.py` dùng module
  mới (sinh lại `_aligned/`); chạy lại `check_labels.py audit` để quét 0006, 0018; kiểm thử
  tự động cho các ảnh khó (pytest hoặc script).
- **Cách đo**: `eval_preprocessing.py` (không đổi kết quả so với bước 5); audit quét được 40/40 phiếu dev+test
  *chỉ đếm số phiếu quét được*, không xem nhãn 0035–0040 ở bước này.
- **Xong khi**: CLAUDE.md mục 7/8 cập nhật (gỡ cảnh báo `check_photos.py`).

### Bước 7 – Đánh giá cuối (một lần)
- **Việc**: chốt code (commit), rồi chạy `eval_preprocessing.py --split test` trên 0035–0040 đúng một lần;
  chạy thêm toàn bộ 80 ảnh và 10 trang chữ số để báo cáo; ghi số "trước/sau" theo C1–C4.
- **Cách đo**: bảng trước (bước 1) / sau (bước 7) cho dev và test. Đo lại cả độ chính xác của ảnh nắn
  đúng (`lech_trungvi_mm`, `lech_max_mm` trên ô lưới tin cậy) – xem mục tiêu dưới.
- **Mục tiêu độ chính xác** (từ Bước 1, `align_cu`/dev 03/10/2026): ảnh nắn đúng vẫn có `lech_max` 1,4–1,6 mm
  (0023_C4 1,56; D006 1,45; 0017_C1 1,44), không tính 0014_C2 (giấy cong, 4,2 mm) – sát dung sai ~1 mm của
  OMR đọc toạ độ cố định. ⇒ preprocessing mới cần **tâm marker chính xác hơn** (tâm theo moment/khớp góc
  thay vì contour thô, dưới pixel). Lưu ý: phép 2 hiện đo theo bước nguyên pixel 150 DPI (0,17 mm) – cần
  tinh chỉnh dưới pixel trước khi so số trước/sau ở mức vài phần mười mm.
- **Xong khi**: số liệu tái tạo được bằng một lệnh, đưa vào báo cáo; lỗi im lặng trên test được nêu
  trung thực dù bằng bao nhiêu.
