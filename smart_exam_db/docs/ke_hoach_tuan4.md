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
tra của `preprocessing.py` (`verify()`, Bước 4) **không được** dùng lại chúng (cũng không import code của chúng): nếu
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
- **Phát hiện: nội dung lệch xuống có hệ thống ~+0,3 mm** (`align_cu`/dev, 58 ảnh không sai, bỏ 0014_C2;
  ô lưới tin cậy, dưới pixel). dy trung bình theo hàng lưới (y = 36 → 261 mm): 0,13 / 0,23 / 0,32 / **0,49** /
  0,31 / 0,27 / 0,39 / 0,33; cùng hình dạng ở C1, C2, C4 và cả trang chữ số D (nội dung khác hẳn);
  58/58 ảnh có dy tb > 0; dx ≈ −0,1 mm. Ba giả thuyết và cách kiểm tra (giới hạn thời gian: làm A, B rồi
  chuyển tiếp, không đào sâu):
  | Giả thuyết | Kiểm tra | Kết quả 03/10/2026 |
  |---|---|---|
  | A. Do phép đo (phép 2) | `tu-kiem`: trang mẫu render, không dịch → phải ra 0; dịch 0,5 mm → 0,5 | **Loại cho thuật toán**: 0,000 / 0,494–0,503 mm, sai số ≤ 0,03 mm (cả phiếu và trang chữ số). *Chưa loại* phần sai lệch chỉ có trên ảnh chụp (nhoè, mực, ánh sáng) – trang render không có |
  | B. Tâm marker do `align()` lệch | `tam-marker`: tâm dưới pixel của 4 ô đen trên ảnh nắn so với `layout.json` | **Loại**: dy marker tb −0,013 mm (đối chứng trang render −0,04 do quy ước tâm pixel), mọi góc, mọi điều kiện |±0,05| mm; tương quan dy marker ↔ dy nội dung giữa các ảnh r = −0,22. Marker nằm đúng chỗ mà nội dung vẫn lệch |
  | C. Máy in kéo giấy không đều (méo phi tuyến theo chiều dọc, chung mọi tờ) | Scan phẳng 1 tờ phiếu trắng, chạy phép 2 trên ảnh scan (không có phối cảnh/ống kính) | *Tuỳ chọn – chờ người dùng có máy scan.* Phù hợp với dữ liệu: hình dạng theo hàng giống nhau ở mọi điều kiện và mọi loại trang |
  **Kết luận** (người dùng chốt, không đào sâu thêm): không do `align()`. Lệch ~+0,3 mm theo hàng: nguyên
  nhân khả dĩ nhất là **máy in (C), chưa kiểm chứng trực tiếp**; lệch đo riêng trên ảnh chụp khó xảy ra vì
  như nhau ở C1/C2/C4/D. Ảnh hưởng:
  ~0,3 mm nằm sẵn trong mọi `lech_*` (cả trước và sau) – nhỏ so với dung sai ~1 mm, không đổi phân loại
  đúng/sai; khi so trước/sau ở Bước 7 phải nhớ đây là sàn chung, preprocessing không sửa được.
- **Ngưỡng đã chốt (03/10/2026)**: `data/_eval/nguong.json` (giá trị + căn cứ từng con số; script chỉ đọc
  file này). Lưu ý: ngưỡng được chọn **chủ yếu trên C1/C2/C4** – `align_cu` chỉ nắn đúng **2 ảnh C3**
  (0002_C3, 0003_C3, là 2 ảnh C3 nghiêng ít nhất). Nếu preprocessing mới bị từ chối / kết luận sai nhiều ảnh
  C3 với `lech_*` ở **1,0–1,5 mm**, thì xem lại các ảnh đó **bằng mắt trên dev** rồi mới quyết; **không nới
  ngưỡng theo tập test**.
- **Xong khi**: `align_cu/truth_dev.csv` có đủ 78 dòng dev; ngưỡng phép 2, 3 chốt (≤ dung sai OMR) và ghi
  lại kèm ảnh làm căn cứ; bảng "trước" theo C1–C4 tái tạo được từ file đó bằng một lệnh.

### Quy ước chung cho Bước 2–7 (chốt 03/10/2026)
- **Mỗi bước = một phương pháp mới trong eval** (`v2_load`, `v3_hinh_hoc`, `v4_verify`, `v5_chuan_hoa`, …),
  đăng ký trong `PHUONG_PHAP` của `eval_preprocessing.py`, có thư mục `data/_eval/<ten>/` và `truth_dev.csv`
  riêng: `run` → xem bằng mắt mọi ảnh `sai`/`xem` → `finalize` → `report`. Ngưỡng giữ nguyên `nguong.json`.
  **`finalize` ép quy tắc này** (sửa 03/10/2026, trước Bước 3): chỉ ảnh máy kết luận `dung` được lấy tự động
  (`nguon = tu_dong`); còn ảnh `sai` hoặc `xem` nào chưa có `ket_luan_mat` (và không thừa kế hợp lệ qua
  `--ke-thua`) thì dừng, không ghi `truth_dev.csv`. Trước đây máy kết luận `sai` được ghi thẳng – số "lỗi im
  lặng" có thể dựa hoàn toàn vào máy. Kiểm tra: finalize lại `align_cu` và `v2_load --ke-thua align_cu` → chạy
  được (19 ảnh sai đều đã có kết luận bằng mắt), `truth_dev.csv` **giống hệt từng byte** bản trước khi sửa;
  phép thử chặn trên bản sao trong scratchpad: xoá `ket_luan_mat` của 1 ảnh `sai` (0006_C2), hoặc đổi 1 ảnh
  `dung` chưa xem thành `xem` → đều dừng, không ghi file; bản không sửa → ghi bình thường.
- **`preprocess(path)` trả một dataclass kết quả** (chốt từ Bước 2, điền dần):
  `anh_nan` (xám, đã nắn, chưa chuẩn hoá) · `anh_chuan_hoa` (Bước 5) · `ok` · `ly_do` (mã: `thieu_marker`,
  `marker_khong_dat`, `nhieu_phieu`, `marker_mo_ho`, `marker_cham_mep`, `anh_mo`, `khong_khop_bo_cuc`,
  `khong_ro_chieu` – chốt ở Bước 4; không có mã "sai hướng": xoay sai thì tự xoay lại) · `marker` (toạ độ 4 tâm trên ảnh gốc,
  dưới pixel) · `huong_xoay` (0/90/180/270) · `blur_score`. Hàm bọc cho eval: `ok` → `anh_nan`, không thì
  `(None, ly_do)`.
- Tuần 5 chọn `anh_nan` hay `anh_chuan_hoa` để train OMR **bằng thí nghiệm** (so F1 lớp `faint` theo C1–C4),
  không chọn theo cảm tính.
- `preprocessing.py` không import phép 2/3 của `eval_preprocessing.py` (Định nghĩa đo).

### Bước 2 – Khung module + `load_image()`
- **Việc**: tạo `cv_engine/preprocessing.py` với dataclass kết quả và `load_image(path)`: đường dẫn Unicode,
  HEIC/JPG (pillow-heif), áp EXIF Orientation, trả ảnh xám. Thêm `pillow`, `psycopg[binary]`, `playwright` vào
  `answer_sheet/requirements.txt` (`pillow-heif` đã có sẵn; CLAUDE.md mục 8, mâu thuẫn 4). Venv: `.venv` ở gốc.
- **Lưu ý**: mọi ảnh `data/raw/` đã có Orientation = 1 (xoay đã áp vào điểm ảnh khi chuyển HEIC→JPG), và EXIF
  gốc của 0006 **sai** (3 thay vì 6) ⇒ `load_image()` không sửa được 0006; chiều phiếu quyết định bằng nội
  dung ở Bước 4. Phần EXIF chỉ kiểm được bằng ảnh thử tự tạo.
- **Cách đo**: ảnh thử có EXIF 1/3/6/8 (tạo trong `data/_eval/_exif/`, không ghi `data/raw/`) → ra đúng chiều
  điểm ảnh; 78 ảnh dev đọc ra giống hệt `cv2.imdecode` (so từng điểm ảnh).
- **Xong khi**: cả hai phép trên đạt; `pip install -r requirements.txt` chạy được trên venv đang dùng.
  Kèm: eval `v2_load` (= `load_image()` + `align()` cũ) cho số đo trùng khớp `align_cu` thì mới được thừa kế
  kết luận bằng mắt (`finalize --ke-thua align_cu`); `report --so-voi align_cu` = 0 ảnh đổi phân loại.
- **Kết quả (xong 03/10/2026)**: (a) `tools/kiem_load_image.py exif` → 8/8 ca đạt: EXIF 1/3/6/8 ra đúng chiều
  (MAD 0,04–0,49 mức xám; mọi chiều sai ≥ 31), HEIC thật `IMG_4214.HEIC` không xoay 2 lần (MAD 1,08), đường dẫn
  có dấu, file không tồn tại / hỏng → `LoiDocAnh`. (b) `kiem_load_image.py so-pixel` → **78/78** ảnh dev giống
  từng điểm ảnh `cv2.imdecode`. (c) `v2_load`: `finalize --ke-thua align_cu` đạt, bảng giống hệt `align_cu`
  (59 đúng / 19 lỗi im lặng / 0 từ chối), 0 ảnh đổi phân loại; `pip install --dry-run -r` không cần cài thêm gì.
  Phép thử chặn của `--ke-thua` (bản sao trong scratchpad): làm lệch 1 số đo ở `diem_dev.csv` hoặc
  `o_luoi_dev.csv`, hoặc 1 ảnh khác điểm ảnh → đều bị từ chối, không ghi `truth_dev.csv`; nếu máy kết luận
  `xem` thì `finalize` thường dừng đòi kết luận bằng mắt. Bước 6 đưa phép thử này vào kiểm thử tự động.

### Bước 3 – Lọc ứng viên + chọn 4 marker theo hình học (nguyên nhân 1, 2, 3) – `v3_hinh_hoc`
- **Việc**: lọc ứng viên (nới w/h ≈ 0,5–2,0; xem lại độ đặc / số đỉnh cho marker méo; giữ *nhiều* ứng viên);
  chọn bộ 4 tạo tứ giác lồi, tỉ lệ ~182:269 mm (cho phép phối cảnh; trang chữ số dùng chung tỉ lệ), 4 marker
  cùng cỡ – thay "gần góc ảnh nhất"; **tâm marker dưới pixel** (moment / khớp góc thay vì contour thô).
- **Cách đo**: phụ – tỉ lệ ảnh dev có đủ 4 marker thật trong danh sách ứng viên (marker thật = điểm mà ảnh nắn
  đúng chiếu ngược ra), số ứng viên trung bình/ảnh (tách lỗi "không tìm thấy" với "chọn sai"). Chính – eval
  `v3_hinh_hoc` trên dev.
- **Xong khi**: phụ 100% (hoặc ảnh thiếu được giải thích từng cái); số ảnh đúng tăng rõ so với `align_cu`
  (nhất là C3, 2/17); lỗi im lặng không tăng; `lech_max` của ảnh đúng giảm so với 1,4–1,6 mm (mục tiêu độ chính
  xác, xem Bước 7).
- **Chia nhỏ, dừng chờ người dùng sau mỗi phần** (duyệt 03/10/2026): 3a marker thật + số "trước" của khâu tìm;
  3b bộ lọc ứng viên, báo **hạng lớn nhất của marker thật** trên toàn dev – số ứng viên đưa vào 3c phải lớn hơn
  hạng đó có biên; 3c chọn bộ 4 theo hình học (H từ 4 tâm dự đoán cỡ/hướng từng marker), **≥ 2 bộ 4 cùng đạt →
  từ chối `nhieu_phieu`**, không chọn bừa; tâm dưới pixel = giao hai đường chéo; homography từ **4 tâm**, 16 đỉnh
  chỉ khi `lech_max` không giảm. Báo thời gian mỗi ảnh (trung vị, lớn nhất).
- **3a – xong 03/10/2026** (`tools/marker_that.py`, chỉ ghi `data/_eval/marker_that/`):
  - Marker thật `marker_that_dev.csv` (78 ảnh): 59 ảnh `align_cu` nắn đúng → 4 điểm của `find_markers()` cũ
    (`nguon = align_cu_dung`); 19 ảnh nắn sai → người dùng xác nhận bằng mắt trên `xac_nhan.html` (`nguon = mat`;
    19/19 đồng ý 4 ứng viên máy đoán, kể cả 0013_C2/0018_C2/0021_C2 có tờ khác lọt khung, 0006 nằm ngang).
    **Sửa 06/10/2026 (phát hiện ở 3b): 0007_C3 nhãn sai** – máy đoán ô số 4 (2989, 1747) = ô đen của **tờ khác** ở mép
    phải khung hình (bị khung cắt), marker TR thật là ô số 5 (2330, 858), ngay trên dòng "Mã phiếu: 0007". Người dùng
    xem `khao_sat/0007_C3_so_nhan.jpg` (tứ giác đỏ = nhãn cũ, xanh = đề xuất) + 2 ảnh phóng to rồi xác nhận;
    `xac_nhan.csv` → `chon = 1 2 3 5`, chạy lại `chot`: chỉ dòng 0007_C3 đổi, 77 dòng còn lại giống từng byte. Bản cũ:
    `data/_eval/marker_that/backup/*_truoc_sua_0007_20261006.csv`. 18 ảnh `mat` còn lại xem lại bằng tứ giác: đúng.
  - **Bài học**: kiểm marker bằng mắt phải xem **tứ giác 4 ô có khớp 4 góc tờ phiếu chính** không, không chỉ xem từng
    ô (từng ô đều "là ô vuông đen" – ô của tờ khác cũng vậy). HTML xem bằng mắt của 3c (và mọi bước sau) **phải vẽ
    tứ giác** 4 điểm được chọn lên ảnh.
    Ứng viên để gán nhãn tìm bằng bộ lọc rất lỏng (chia nền giấy cục bộ, mực < 50% nền, độ vuông ≥ 0,70, độ đặc
    ≥ 0,85) – không phải bộ lọc của v3. Cách đoán kiểm tra trước trên 59 ảnh đã biết: trúng **59/59**.
  - Khảo sát (dùng cho 3b/3c): 236 marker thật ở 59 ảnh đúng có độ vuông (diện tích / `minAreaRect`) 0,83–1,01,
    độ đặc 0,96–1,01; ứng viên khác lọt bộ lọc tối đa 0,885 (p95 0,81). Marker phía xa ở C3 chỉ ~3 600 px²
    (~2,9e-4 ảnh, ngang ô tròn gần máy), cạnh ngắn/dài ~0,6 ⇒ **không lọc theo cỡ tuyệt đối**. 0034_C3: marker
    dưới phải chỉ đứng hạng 5 theo độ vuông (sau ô mẫu "Đúng ●"). 0031_C3 có ô đen của tờ khác ở góc trên trái.
  - **Số "trước" của khâu tìm** (`python tools/marker_that.py ung-vien --bo-loc cu`; bộ lọc của `find_markers()`
    cũ, bản sao được kiểm tra khớp 4 điểm cũ trên mọi ảnh; khớp ≤ 10 px, thực tế xa nhất 0,61 px):
    | Điều kiện | Ảnh | Đủ 4 marker thật trong ứng viên | Ứng viên/ảnh TB (min–max) | Đủ 4 mà vẫn nắn sai |
    |---|---|---|---|---|
    | C1 | 17 | 17 (100%) | 454 (389–490) | 0 |
    | C2 | 18 | 18 (100%) | 462 (398–486) | 4 |
    | C3 | 17 | **3 (17,6%)** | 301 (263–387) | 1 |
    | C4 | 16 | 16 (100%) | 464 (396–484) | 0 |
    | D | 10 | 10 (100%) | 142 (76–240) | 0 |
    | **Tổng** | **78** | **64 (82,1%)** | **384** | **5** |
  - ⇒ 19 ảnh `align_cu` sai = **14 "không tìm thấy"** (toàn C3, thiếu 1–2 marker: nguyên nhân 1, w/h quá chặt)
    + **5 "chọn sai"** dù có đủ 4 (0013_C2, 0018_C2, 0021_C2: tờ khác lọt khung – nguyên nhân 2/3; 0006_C2,
    0006_C3: chiều phiếu – nguyên nhân 4, để Bước 4). ~384 ứng viên/ảnh (lẽ ra 4) là gốc của nguyên nhân 2.
  - **Đính chính (3b)**: "độ vuông 0,83–1,01" chỉ đúng trên 59 ảnh `align_cu` đúng. Trên đủ 78 ảnh, với mặt nạ của
    bộ lọc lỏng 3a, marker thật thấp nhất **0,789** (0034_C3, marker gần máy bị thủng lõi – xem 3b) ⇒ độ vuông
    không dùng làm ngưỡng.
- **3b – xong 06/10/2026, người dùng đã duyệt** (`cv_engine/preprocessing.py`: `do_vet_muc()`, `tim_ung_vien_marker()`;
  đo bằng `python tools/marker_that.py khao-sat` và `ung-vien --bo-loc moi`, chỉ dev, ghi `data/_eval/marker_that/`):
  - **Mặt nạ mực**: xám / nền giấy < 0,5; nền = max cục bộ cửa sổ max(H, W)/12 (340 px) rồi làm mượt, tính trên ảnh
    thu 1/4. Cửa sổ / cạnh hộp bao marker lớn nhất (145 px, 0031_C3) = **2,34** (bộ lọc 3a: 51 px → 0,35). Cửa sổ nhỏ
    hơn marker làm lõi marker sáng không "thấy" giấy → **thủng lõi** (0034_C3 marker gần máy, mực xám `den_trong`
    0,34 – cao nhất 312 marker, khả dĩ do loá: 3a vuông 0,789 / đặc 0,905 → mới 0,868 / 0,993; tâm chỉ lệch 0,2 px
    vì lỗ nằm giữa). Ảnh `khao_sat/0034_C3_marker_gan_cu_moi.jpg`.
  - **Đặc trưng mới `tu_giac`** = diện tích contour / tứ giác bao `cv2.approxPolyN(hull, 4)` (OpenCV 5.0.0). Thử trên
    hình vẽ (vẽ ×8, thu nhỏ, làm mờ, ngưỡng): hình vuông độ phối cảnh 1,0 / 0,6 / 0,45, xoay 0 / 0,4 rad, cạnh 110 /
    60 / 35 px → **0,944–1,000** (độ vuông `minAreaRect` chỉ 0,71–1,00); tròn Ø25–60 px, elip → **0,68–0,78**; tứ
    giác luôn bao NGOÀI contour (khoảng cách có dấu nhỏ nhất của điểm contour = 0) ⇒ `tu_giac` ≤ 1.
  - **Ngưỡng** (312 marker thật / 78 ảnh; "loại riêng" = ứng viên khác chỉ bị loại bởi ngưỡng đó khi đã áp các ngưỡng
    còn lại): `dac` ≥ 0,80 – xấu nhất 0,969 (0014_C2), biên 0,169, loại riêng 99,5%; `canh` ≥ 0,30 – xấu nhất
    **0,568 (0015_C3)**, biên 0,268, loại riêng 28,6% (10/35) – biên lớn hơn căn cứ dữ liệu **cố ý**, chừa cho marker
    bị khung hình cắt (dẹt hơn) vẫn lọt tới 3c để 3c quyết định; `tu_giac` ≥ 0,83 – xấu nhất 0,938 (0014_C2), biên
    0,108, loại riêng 99,1%; diện tích 1e-4–5e-3 ảnh – marker 2,33e-4–1,38e-3 (biên ×2,3 / ×3,6); ngưỡng mực 0,5 –
    `den_trong` xấu nhất 0,338, biên 0,162. Không marker thật nào trong 0,05 trên ngưỡng. `muc_vien` ≤ 0,17 thử nhưng
    **không áp** (chỉ loại 6/25; marker cạnh ngón tay / bóng sẽ mất) – chỉ dùng xếp hạng. `muc_vien` xấu nhất 0,070
    (0014_C2 góc TR): nhiễu hạt của ảnh C2 tối lọt ngưỡng mực quanh marker, không phải vết in.
  - **Xếp hạng** `diem = tu_giac × (1 − muc_vien)` (không trọng số khớp dữ liệu). Hạng lớn nhất như nhau với `vuong`,
    `tu_giac`, `diem`, `diem × (1 − den_trong)` (đều 5) – ứng viên đã gần như chỉ còn marker.
    | Điều kiện | Ảnh | Đủ 4 marker thật | Ứng viên/ảnh TB (min–max) | Hạng lớn nhất |
    |---|---|---|---|---|
    | C1 | 17 | 17 (100%) | 4,2 (4–6) | 4 |
    | C2 | 18 | 18 (100%) | 4,3 (4–6) | 5 |
    | C3 | 17 | 17 (100%) | 4,6 (4–6) | 5 |
    | C4 | 16 | 16 (100%) | 4,0 (4–4) | 4 |
    | D | 10 | 10 (100%) | 4,6 (4–6) | 4 |
    | **Tổng** | **78** | **78 (100%)** | **4,3** (bộ lọc cũ 384) | **5** (0021_C2, 0030_C3) |
    Khớp ≤ 10 px, thực tế xa nhất 1,75 px. Thời gian lọc (không tính đọc ảnh): trung vị **140 ms**, max 178 ms.
  - **Chạy lại sau khi sửa nhãn 0007_C3** (06/10/2026) – số đổi so với lần trước: `canh` xấu nhất 0,475 (0007_C3) →
    0,568 (0015_C3), biên 0,175 → 0,268; diện tích nhỏ nhất 2,07e-4 → 2,33e-4 (biên ×2,1 → ×2,3); hạng lớn nhất của
    0007_C3 4 → 5 (C3 vẫn 5, tổng vẫn 5); hạng theo `vuong` (chỉ báo cáo) C3 4 → 5; thời gian 141/174 → 140/178 ms (dao
    động đo). `ung_vien_moi_dev.csv`: chỉ dòng 0007_C3 đổi (bỏ cột thời gian). Bảng trên, ngưỡng, `dac`, `tu_giac`,
    `muc_vien`, `den_trong` không đổi.
  - Ca riêng: 0034_C3, 0031_C3, 0018_C2, 0006_C2 – 4 marker hạng 1–4; 0031_C3 ô đen tờ khác ở TL hạng 5
    (`tu_giac` 0,870); 0013_C2 thêm 2 vết lớn ở góc dưới trái (15 559 / 24 189 px², `muc_vien` 0,24 / 0,31) hạng 5–6;
    **0021_C2 marker TR hạng 5** sau một vết 33 801 px² chạm mép (52, 3874) hạng 2 – cỡ gấp ~3 marker cùng ảnh;
    0006_C3 thêm 2 vết hạng 5–6; **0007_C3 marker TR thật hạng 5**, sau **ô đen tờ khác bị khung cắt** (2990, 1748;
    2 522 px², `tu_giac` 0,957, `cham_mep`) – ô này **vẫn lọt bộ lọc mới, hạng 4**.
  - **0007_C3 không có marker nào của tờ chính bị cắt** (đính chính: lần trình bày đầu của 3b gọi nhầm ô tờ khác là
    "marker TR / marker dưới bị cắt", ước lượng mất 32–40%, tâm lệch 13–17 px ≈ 1,7–2,2 mm – các số đó là của ô tờ khác,
    bỏ). Ảnh này thuộc nhóm **tờ khác lọt khung** như 0013_C2, 0018_C2, 0021_C2. Trên dev hiện **không có** marker thật
    nào chạm mép ảnh.
  - **Lưu ý cho 3c**: marker của tờ khác có mặt trong ứng viên khi nó lọt khung trọn vẹn, **và cả khi bị khung cắt**
    (0007_C3) – `nhieu_phieu` / `marker_cham_mep` của 3c phải xử lý cả hai.
- **3c – quy ước (chốt khi duyệt 3b)**:
  - K (số ứng viên đưa vào chọn bộ 4) chọn **trên dev** theo hạng lớn nhất của 3b: K = max(2 × hạng, hạng + 4) = **10**
    (dev hiện có tối đa 6 ứng viên/ảnh). Nếu không bộ 4 nào trong top-K đạt kiểm tra hình học → **từ chối có lý do**
    (`thieu_marker` / `marker_khong_dat`), **không nới chuẩn** để cố tìm.
  - **"4 marker cùng cỡ" so SAU khi tính phối cảnh**: dùng H từ 4 tâm để dự đoán hình (cỡ, hướng) của marker 8 mm ở
    từng góc trên ảnh, rồi so với contour thật – **không** so diện tích px trực tiếp (ở C3 marker gần máy to gấp ~4–5
    lần marker xa: tỉ lệ diện tích lớn nhất/nhỏ nhất của 4 marker cùng ảnh lên tới 5,4 – 0015_C3, mặt nạ 3a, nhãn đã sửa). Ca kiểm tra: **0021_C2** – vết
    33 801 px² phải bị loại; **mọi ảnh C3 dev** không được bị loại nhầm vì điều kiện này.
  - **Ca thử cho `nhieu_phieu` / `marker_cham_mep`**: 0007_C3 (ô tờ khác bị khung cắt, hạng 4, trên marker thật), 0013_C2,
    0018_C2, 0021_C2 (tờ khác lọt khung), 0031_C3 (ô đen tờ khác ở góc TL, hạng 5).
  - HTML xem bằng mắt **vẽ tứ giác** của bộ 4 được chọn (bài học 3a).
- **3c – dừng A xong 06/10/2026, người dùng đã duyệt** (`preprocessing.py`: `tim_ung_vien_marker()` thêm đỉnh/tâm dưới
  pixel, `do_bo_4()`, `chon_cach_gan()`, `find_markers()`; đo bằng `marker_that.py khao-sat-bo-4`, `tu-kiem-tam`,
  `chon-bo-4`; chỉ dev; ghi `data/_eval/marker_that/` và `data/_eval/_gia/`):
  - **Không kiểm tỉ lệ 182:269 từ 4 tâm**: mọi tứ giác lồi đều là ảnh chiếu của một hình chữ nhật bất kỳ; ước lượng tỉ lệ
    kiểu Zhang–He (điểm chính = giữa ảnh) trên bộ thật cho 0,56–2,00 (đúng 1,478), 30/78 ảnh không giải được tiêu cự.
    Tỉ lệ được ép gián tiếp bằng **K4** (hình dạng 4 marker sau H).
  - **Mỗi bộ 4 thử cả 4 cách gán góc xoay vòng**, giữ cách có K4 nhỏ nhất; nhiều cách gán của cùng bộ vẫn là 1 bộ khi
    đếm `nhieu_phieu`/`marker_mo_ho`. Layout đối xứng qua 180° ⇒ cách gán r và r+2 cho K4 **giống hệt** (chênh 0,000 mm
    trên 78 bộ thật): **3c chỉ quyết dọc/ngang** theo hình dạng marker (lấy r = 0 hoặc 1); **0° hay 180° là việc của
    Bước 4 (bằng nội dung)**. 0006_C2/C3 (cách gán 1 = ngang) nắn ra 0° **là do tình cờ** (hướng xoay của hai ảnh
    này trùng quy tắc r ∈ {0, 1}); ảnh giả `xoay270_ngang` ra 180°.
  - **Ngưỡng** (78 bộ thật vs 142 bộ khác trong top-10 ứng viên; "loại một mình" = trên 94 bộ khác lồi):
    | Tiêu chí | Bộ thật xấu nhất | Biên | Loại riêng | Loại một mình |
    |---|---|---|---|---|
    | K1 lồi | 78/78 lồi | – | – | 48/142 không lồi |
    | K2 độ phối cảnh ≥ 0,50 | 0,597 (0015_C3) | 0,097 | 0 | 67/94 |
    | K3 cỡ (diện tích / ô 8 mm dự đoán) 0,61–1,40 | 0,767 (0014_C2) / 1,117 (0033_C1) | ×1,26 / ×1,25 | 0 | 93/94 |
    | K4 đỉnh ≤ 2,0 mm | 1,28 (0014_C2, giấy cong) | 0,72 mm | 1 | 94/94 |
    Quy tắc "loại riêng < 5% thì bỏ" áp cho **bộ lọc ứng viên 3b**. Ở 3c, K2/K3 **giữ lại** làm lớp phòng thủ thứ hai
    cho K4 (K4 phụ thuộc khâu tìm đỉnh): chỉ với K4, bộ khác tốt nhất lệch 2,44 mm (0030_C3) – sát ngưỡng 0,44 mm; trong
    các bộ khác **đã qua K1–K3** trên toàn dev, K4 nhỏ nhất **7,58 mm (0013_C2)** – biên thật của tổ hợp. **K4 vượt
    ngưỡng → từ chối, không chọn sai**; giấy cong mạnh hơn 0014_C2 sẽ bị từ chối – chấp nhận. Cách gán dọc/ngang sai
    của bộ thật có K4 ≥ 2,43 mm (0031_C3) ⇒ tự bị loại; khoảng cách K4 vuông góc − tốt nhất ≥ 1,64 mm (D001), trung vị
    2,16 mm (từng ảnh trong `bo_4_dev.csv`).
  - **Khâu chọn** (`chon-bo-4`): **78/78 chọn đúng** (C1 17, C2 18, C3 17, C4 16, D 10), 0 chọn sai, 0 từ chối; mọi
    ảnh đúng 1 bộ đạt (kể cả 0007_C3, 0013_C2, 0018_C2, 0021_C2, 0031_C3). `find_markers` (gồm lọc 3b) trung vị 143 ms,
    max 198 ms. Ảnh ghép tứ giác 78 ảnh: `khao_sat/bo_4_ghep_1.jpg`, `_2.jpg` (đã xem: khớp 4 góc tờ chính).
  - **Ảnh giả** (`tu-kiem-tam`, `data/_eval/_gia/`, H biết trước): thẳng, C1, C3 độ phối cảnh 0,6, xoay 15°, xoay 90°
    ngang (thẳng và C3), xoay 180°, xoay 270° ngang → dọc/ngang đúng cả 8 ca (180° / 270° ra 180° như thiết kế); hai tờ
    → `nhieu_phieu`.
  - **Tâm dưới pixel** = `tam_phoi_canh()`: khử phối cảnh bằng 4 đỉnh (fitLine từng cạnh), lấy trọng tâm có trọng số
    Jacobi trên mọi điểm ảnh của marker. Sai số max trên ảnh giả (so với tâm đo trên trang render): centroid 0,15–1,10 px
    (kém ở phối cảnh mạnh: c3 1,10), giao đường chéo 0,17–0,69, **phối cảnh 0,19–0,72**. **Tiêu chí ≤ 1 px** (≈ 0,1 mm
    trên mặt phiếu – nhỏ hơn nhiều sàn ~0,3 mm do máy in và dung sai OMR 1,75 mm) → **đạt**. Kiểm tra nhanh (dx, dy) có
    dấu: ca thẳng hai cách cho sai số giống hệt (dy −0,3…−0,55, dx −0,44 bên trái / +0,09 bên phải) – khả năng do quy
    ước tâm/biên pixel khi tạo ảnh giả, cùng loại với −0,45 px của tâm marker trang render so với `layout.json`; ca c1
    cách phối cảnh lệch tới 0,71 px theo nhiều hướng (nhiễu tìm đỉnh, centroid chỉ 0,15). Dừng điều tra (giới hạn 15 phút).
- **3c – dừng B (06/10/2026)**: eval `v3_hinh_hoc` (`eval_preprocessing.py run --phuong-phap v3_hinh_hoc`): trả ảnh
  78/78, máy kết luận 71 `dung`, 0 `sai`, 7 `xem` – **cả 7 là C3** (0006, 0011, 0026, 0027, 0030, 0031, 0034), trượt vì
  `lech_toan_trang`/`lech_trungvi` 1,0–1,5 mm, 45 ô lưới tin cậy, tỉ lệ hàng dương 1,00. Giao diện eval: phương pháp
  được trả thêm phần tử thứ 3 (chi tiết marker) → HTML vẽ tứ giác lên ảnh gốc; hồi quy `run v2_load` + `finalize
  --ke-thua align_cu` → `truth_dev.csv` **giống từng byte** (`diem_dev.csv` chỉ khác cột `giay`).
  - **Mục tiêu độ chính xác Bước 3 KHÔNG đạt** (người dùng chấp nhận): `lech_max` trên 58 ảnh `align_cu` cũng đúng (bỏ
    0014_C2) TB 0,900 → 0,908 mm, max 1,55 → 1,57 mm. `tam-marker`: tâm marker trên ảnh nắn đúng **±0,06 mm (TB)** ở mọi
    góc/điều kiện (max 0,10 mm C1/C2/C4/D, 0,19 mm C3; `align_cu` TB 0,019 vs v3 0,024 mm) – phần lệch nằm **ở giữa
    trang, không do tâm marker** (tương quan dy marker ↔ dy nội dung r = 0,03). **Không làm homography 16 đỉnh** (16 đỉnh
    vẫn ở 4 góc).
  - **Nội dung C3 lệch xuống TB +0,84 mm** (theo ảnh 0,37–1,30; C1/C2/C4/D ~+0,3 = sàn máy in). Kiểm tra nguồn gốc
    (20 phút): phép 2 trên ảnh giả `_gia/` nắn bằng `find_markers` v3 – thang / c1 / **c3_pc06**: `lech_toan_trang` 0,11
    / 0,10 / 0,10 mm, `lech_trungvi` 0,11 / 0,12 / 0,10, dy TB theo 8 hàng lưới ≤ +0,14 mm ở cả 3 ⇒ phép 2 **không** đo sai
    ở vùng bị thu nhỏ mạnh; lệch C3 là **lệch thật** của ảnh (giấy không phẳng / méo ống kính khi chụp nghiêng – ảnh giả
    là mặt phẳng hoàn hảo, không có hai thứ đó; homography 4 điểm không sửa được). ⇒ **Tuần 5: OMR bắt buộc dò lại từng
    hàng cho ảnh nghiêng mạnh** (CLAUDE.md mục 7).
- **3c – xong 06/10/2026 ⇒ BƯỚC 3 XONG.** Người dùng xem bằng mắt 7 ảnh `xem` (C3): **cả 7 `dung`** (0006_C3: ảnh nắn
  đứng thẳng, tiêu đề ở trên; ảnh gốc chụp ngang). Ghi chú **`lech_c3`** trong `truth_dev.csv` cho ảnh `dung` có
  `lech_trungvi` > 1,0 mm: 0026_C3 (1,17), 0027_C3 (1,03), 0030_C3 (1,19), 0031_C3 (1,06), 0034_C3 (1,03) – để Tuần 5
  biết. `finalize v3_hinh_hoc` → nguồn 71 `tu_dong` + 7 `mat`; `report --so-voi align_cu`:
  | Điều kiện | Ảnh | Đúng | Lỗi im lặng | Bị từ chối | `align_cu` đúng / lỗi im lặng |
  |---|---|---|---|---|---|
  | C1 | 17 | 17 | 0 | 0 | 17 / 0 |
  | C2 | 18 | 18 | 0 | 0 | 14 / 4 |
  | C3 | 17 | **17** | 0 | 0 | **2 / 15** |
  | C4 | 16 | 16 | 0 | 0 | 16 / 0 |
  | D | 10 | 10 | 0 | 0 | 10 / 0 |
  | **Tổng** | **78** | **78** | **0** | **0** | 59 / 19 |
  19 ảnh đổi phân loại, đều `loi_im_lang → dung`; không ảnh nào đổi từ đúng sang sai. Đối chiếu "Xong khi" của Bước 3:
  phụ 100% (78/78 đủ 4 marker, 3b) – đạt; số ảnh đúng tăng rõ (59 → 78, C3 2 → 17) – đạt; lỗi im lặng không tăng (19 →
  0) – đạt; `lech_max` của ảnh đúng giảm – **không đạt** (người dùng chấp nhận, xem dừng B).
  **Lưu ý cho Bước 4**: 0006_C2/C3 đúng chiều là **tình cờ** (quy tắc r ∈ {0, 1}); ảnh chụp ngang theo hướng ngược lại
  sẽ ra 180° (ảnh giả `xoay270_ngang`) ⇒ Bước 4 vẫn phải quyết 0°/180° bằng nội dung, và ảnh giả xoay 180° / 270° phải
  được đưa vào eval Bước 4 (dev thật không có ca này).
- **Câu hỏi mở cho 3c / Bước 4 – ĐÃ ĐÓNG 06/10/2026: TỪ CHỐI `marker_cham_mep`** (xem Bước 4). Nội dung câu hỏi cũ: marker **chạm mép ảnh** (`cham_mep`) thì **ước lượng tâm** (từ cạnh còn
  lại / hình học 3 marker kia) hay **từ chối** (lý do `marker_cham_mep`, yêu cầu chụp lại)? Trên dev không có marker thật
  nào chạm mép (4 ảnh như vậy – 0014_C3, 0028_C4, 0032_C4, D007 – đã chụp lại trước Tuần 4); ca thật hiện có chỉ là ô
  tờ khác bị cắt (0007_C3) – loại nó là đúng dù chọn cách nào. Có thể cần ảnh giả (che/cắt 1 marker) ở Bước 4.

### Bước 4 – Warp + chiều phiếu bằng nội dung + `verify()` từ chối có lý do (nguyên nhân 4) – `v4_verify`
- **Việc**: warp; thử 4 cách gán TL/TR/BR/BL (0/90/180/270°), chọn chiều bằng **dấu hiệu nội dung riêng của
  preprocessing** (ví dụ vị trí khối ô đáp án / dòng tiêu đề so với marker), không tin EXIF, không dùng phép so
  phiếu trắng của eval. `verify()` tự kiểm tra: độ đen marker, hình học 4 marker, dấu hiệu bố cục riêng, độ nét
  (Laplacian → `blur_score`, từ chối `anh_mo` nếu quá mờ) → `ok = False` kèm mã lý do thay vì trả ảnh sai.
- **Kiểm tra chiều phải dựa trên NỘI DUNG, không dựa marker**: 4 marker giống hệt nhau, ảnh xoay 90°/180°
  vẫn có marker thật ở cả 4 góc ⇒ độ đen marker về bản chất không bắt được lỗi chiều. 0006_C2/0006_C3
  (`align_cu`) chỉ hụt nhẹ (đen 0,85 / 0,90) vì trang dọc bị ép vào tứ giác ngang (méo ~1,48 : 0,68) – tình
  cờ, không dựa vào được; `tu-kiem` xoay 180°: độ đen 1,00 ở cả 7 ảnh.
- **Cách đo**: eval `v4_verify` trên dev; ảnh giả có lỗi cố ý (che 1 marker, tờ khác lọt khung, xoay 90/180°,
  làm mờ) – tạo trong `data/_eval/`.
- **Xong khi**: 0006_C2, 0006_C3 đúng; **lỗi im lặng = 0 trên dev** và trên ảnh giả; mỗi ảnh bị từ chối có
  lý do đúng; không ảnh nào đổi từ đúng sang sai so với Bước 3.
- **Kế hoạch chi tiết (người dùng duyệt 06/10/2026)**:
  - **Chiều 0°/180°**: 4 tâm marker layout đối xứng qua tâm trang ⇒ ảnh nắn theo cách gán r + 2 = `np.rot90(anh_nan, 2)`
    (không warp lại). Điểm bố cục **S(θ)** = trung vị trên mọi phần tử in sẵn của layout (phiếu: 250 ô tròn – vành tròn
    so với vòng giấy ngoài, ô trống lẫn ô tô đều dương; trang D: 400 ô viết – cạnh dọc + ngang **cùng một độ dịch**)
    của tương phản cục bộ, dò lệch ±2 mm (C3 còn lệch thật tới 1,30 mm). Chọn θ có S lớn hơn. Bỏ vùng 20×20 mm quanh
    marker; không EXIF; không render PDF/không so bản đồ cạnh (phép 2); không nhãn (phép 3). Tính bất đối xứng (đo trên
    hai file layout, `doi_xung.py` scratchpad): phiếu – 16/250 ô tròn sau xoay 180° rơi trong 15 px một ô tròn khác
    (32 trong 30 px), trung vị cách 82,6 px ≈ 7 mm (khối đáp án ở y 1795–2965, xoay sẽ rơi vào vùng tiêu đề/SBD); trang D
    – 0/400 ô viết trùng, lưới dời (142, 246) px vì lề trái/phải 378/236, trên/dưới 567/321 px: cạnh dọc lệch ~4 mm
    (> cửa sổ dò) nhưng cạnh ngang chỉ ~1,35 mm ⇒ phải ép chung độ dịch cho cả ô. Dọc/ngang vẫn do K4 (3c) quyết;
    sai dọc/ngang thì nội dung lệch hoàn toàn → `khong_khop_bo_cuc`. Tự kiểm: 78 ảnh nắn dev đưa vào ở **cả hai chiều**.
  - **`huong_xoay`** = góc phiếu bị xoay trong ảnh gốc (chiều kim đồng hồ, bội 90°) từ vectơ TL→TR cuối cùng; `marker`
    sắp theo TL/TR/BR/BL thật của trang. Chiều đúng của dev lấy từ `v3_hinh_hoc` (78/78 đúng qua phép 2 – bắt được xoay
    180° – và mắt), **không** từ `marker_that_dev.csv` (thứ tự góc 0006 ghi "không quan trọng").
  - **Bộ mã** (kết luận theo thứ tự): `khong_doc_duoc` · `thieu_marker` / `marker_khong_dat` / `nhieu_phieu` /
    `marker_mo_ho` (3c, `find_markers()` **không sửa** để v3 tái tạo từng byte) · `marker_khong_dat` thêm phép lõi 6×6 mm
    4 marker trên `anh_nan` (tự viết, không import `marker_fill`) · `marker_cham_mep`: (1) marker của bộ được chọn chạm
    mép ảnh → từ chối; (2) `find_markers` thất bại mà có ứng viên chạm mép → đổi mã thành `marker_cham_mep` · `anh_mo`:
    `blur_score` < ngưỡng · `khong_khop_bo_cuc`: S(θ\*) < ngưỡng tuyệt đối · `khong_ro_chieu`: biên tương đối
    (S(θ\*) − S(θ khác)) / S(θ\*) < ngưỡng.
  - **Marker chạm mép → TỪ CHỐI** (chốt 06/10/2026): marker bị cắt có trọng tâm lệch tới nửa cạnh (~4 mm); dev không có
    ca thật để kiểm chứng một cách ước lượng tâm; chụp lại rẻ (4 ảnh như vậy đã chụp lại trước Tuần 4); "thà từ chối còn
    hơn lỗi im lặng". Quy tắc (1) không đổi 0007_C3 (ô bị cắt ở đó thuộc tờ khác, không nằm trong bộ được chọn).
  - **`blur_score`**: chính – phương sai Laplacian trên `anh_nan` thu 150 DPI, trong dải quanh phần tử in theo layout,
    chia bình phương tương phản (giấy − mực); đối chứng – Laplacian toàn vùng trong 4 marker. **Ngưỡng gắn với hậu quả**:
    với mỗi mức mờ của ảnh giả (Gauss σ, chuyển động), đo trên ảnh nắn hiệu nhỏ nhất (filled − blank) và (faint − blank)
    theo nhãn như phép 3 / `dung-sai` – **chỉ để CHỌN ngưỡng, `verify()` không gọi phép 3**; báo σ nhỏ nhất làm
    faint/blank không còn tách. Ngưỡng đặt giữa ảnh dev thật xấu nhất và mức đó, có biên; tập "chấp nhận được" của nhóm
    mờ chốt theo số liệu này (ngoại lệ duy nhất của quy tắc "ảnh giả chỉ để kiểm").
  - **Độ độc lập giữa `verify()` và eval** (ghi rõ để báo cáo không nói quá): phép lõi marker của `verify()` **gần giống
    phép 1 của eval** (vốn chỉ là phép phụ, không độc lập với `align()`); điểm bố cục S và **phép 3** của eval **cùng dựa
    `layout.json`** (sai `layout.json` thì cả hai cùng sai). **Giám khảo độc lập thật của eval là phép 2** (so nét với PDF
    render) – cùng với xem bằng mắt.
  - **Ảnh giả** (`tools/kiem_verify.py tao-gia`, chỉ từ ảnh dev, ghi `data/_eval/_gia_v4/` + `danh_sach.csv` có H biến
    đổi và kết quả mong đợi chốt TRƯỚC khi chạy verify; nhóm `khong_du_marker` = {`thieu_marker`, `marker_khong_dat`}):
    xoay 90/180/270 (gồm **0006_C2 xoay 180°**), che 1 marker, khung cắt qua marker (2 px – hết), đối chứng cắt lề, hai
    tờ, tờ khác lọt khung, mờ Gauss / chuyển động, nhầm loại trang, tối + nhiễu, **quá nghiêng** (độ phối cảnh ~0,40 /
    ~0,45 → `khong_du_marker`), **không có phiếu** (mặt bàn / giấy trắng cắt từ nền ảnh dev → `thieu_marker` /
    `khong_du_marker`). Chấm tự động: ca ok – 4 tâm khớp H · tâm v3 của ảnh nguồn ≤ 3 px và `huong_xoay` đúng; ca từ chối
    – mã thuộc tập mong đợi.
  - **Ngưỡng chọn trên dev thật**; ảnh giả chỉ để kiểm (trừ ngưỡng `anh_mo` như trên). Ảnh giả trượt → báo người dùng,
    không lặng lẽ chỉnh ngưỡng. Ảnh giả lấy từ ảnh dev **chỉ kiểm logic** (mỗi lỗi cố ý ra đúng mã); khả năng tổng quát
    hoá chỉ đo ở Bước 7 (tập test).
  - **Dừng A xong 06/10/2026, người dùng duyệt**: 100 ảnh giả (`kiem_verify.py tao-gia`; 28 phải ok, 19 ok-hoặc-đúng-mã,
    53 phải từ chối; 30 ca nhóm mờ "tạm", chốt ở dừng B), ảnh ghép `_gia_v4/ghep_1..3.jpg`. Nguồn 0001_C1, 0005_C2,
    0015_C3, **0008_C4** (không có 0010_C4), D003, 0006_C2 (vốn ở hướng 90° ⇒ `xoay180_0006_C2` = 270°). Cắt qua marker:
    xoay nguồn 5° + thu 0,88 trước khi cắt (tờ gần thẳng trục, cắt thẳng sẽ sượt marker cùng cạnh); script tự kiểm 3
    marker còn lại nguyên vẹn. **`_gia_v4/` tái tạo được bằng `tao-gia`, không cần sao lưu**: mọi ngẫu nhiên có seed cố
    định, chạy lại ra 104 file (100 ảnh + 3 ảnh ghép + `danh_sach.csv`) **giống từng byte** (SHA-256, 06/10/2026).
  - **Dừng B (06/10/2026) – khảo sát, ngưỡng ĐỀ XUẤT, chờ duyệt** (`python tools/kiem_verify.py khao-sat` →
    `data/_eval/v4_verify/khao_sat_dev.csv` 78 ảnh dev thật, `khao_sat_mo.csv` 8 ảnh phiếu + D003 × 25 mức mờ; nắn bằng
    4 tâm `find_markers` = v3, script tự kiểm khớp v3 ≤ 0,01 px). Số đo hàm trong `preprocessing.py`: `warp`,
    `diem_bo_cuc`, `blur_score`, `den_loi_marker` (chưa có `verify`).
    | Ngưỡng đề xuất | Dev thật xấu nhất | Phía "sai" tốt nhất | Biên |
    |---|---|---|---|
    | `khong_ro_chieu`: biên (S_tốt − S_kia)/S_tốt < 0,20 | phiếu 0,805 (0018_C2); D 0,429 (D006) | – | ×4,0 / ×2,1 |
    | `khong_khop_bo_cuc` phiếu: S_tốt < 0,23 | 0,365 (0010_C2) | trang D chấm theo layout phiếu 0,144 (D006) | ×1,59 / ×1,60 |
    | `khong_khop_bo_cuc` D: S_tốt < 0,18 | 0,451 (D001) | phiếu chấm theo layout D 0,072 (0026_C2) | ×2,5 / ×2,5 |
    | `anh_mo`: `mo_huong` < 0,012 | phiếu 0,221 (0034_C3), D 0,416 (D002) | mờ gãy đầu tiên (chuyển động 80 px) ≤ 0,00063 | ×18,7 / ×18,7 |
    | `marker_khong_dat` (lõi marker): lõi/vành > 0,60 | 0,357 (0034_C3, marker loá); D 0,246 | – (chưa có mẫu sai; đo ở dừng C) | 0,24 |
    - **Chiều**: 0006_C2 biên 0,808, 0006_C3 0,835 (quyết bằng nội dung, rõ ràng). Phiếu: S0 0,365–0,474, S180 0,059–0,089
      (≈ mức "ngẫu nhiên": layout D chấm trên phiếu 0,048–0,072). Bỏ 32 ô trùng sau xoay: biên min 0,805 → 0,825 (S180 max
      0,089 → 0,076); S180 của ô đáp án (rơi vào vùng tiêu đề/SBD có chữ in) max 0,094 vs bubble SBD/mã đề (rơi vào khối đáp
      án) 0,072 ⇒ chữ in vùng tiêu đề kéo S_nguoc lên nhiều hơn 32 ô trùng, cả hai nhỏ. Đề xuất giữ đủ 250 ô. Trang D: ép
      chung độ dịch biên min 0,429 vs dò riêng từng hướng 0,385; S180 cạnh ngang 0,32–0,37 > cạnh dọc 0,22–0,26 (đúng dự
      đoán: lưới D lật 180° chỉ lệch ~1,35 mm theo dọc).
    - **Hậu quả mờ (mục 3, chỉ để chọn ngưỡng)**: 8 ảnh phiếu (mỗi C: ảnh nguồn ảnh giả + ảnh nhiều ô faint nhất), 78 ô
      faint; dò lại ±4 mm như OMR Tuần 5. **Faint/blank tách ở mọi hàng tới Gauss σ = 32 px** (hiệu min +0,216 → +0,014) và
      chuyển động 80 px; **gãy đầu tiên: chuyển động 80 px – filled/blank 0,91** (ô tô rõ lem sang ô trống cạnh), Gauss
      σ = 32 filled 0,88; faint gãy ở chuyển động 120 px (0,67). ⇒ OMR (đo độ tối trung bình ô Ø5 mm) chịu mờ rất tốt; giới
      hạn thật sẽ là đọc chữ số viết tay (Tuần 6) – chưa đo được ở đây.
    - **Đổi cách đo blur so với kế hoạch**: (1) **không chia bình phương tương phản mực** – mờ làm nét mảnh nhạt đi, chia
      cho tương phản sẽ triệt tiêu chính tín hiệu mờ; chỉ chia nền giấy (khử chiếu sáng). (2) Laplacian đẳng hướng
      (`phan_tu`) **hỏng với mờ chuyển động trên trang D**: cạnh ngang lưới ô vẫn sắc ⇒ điểm ≥ 0,31 kể cả ở 120 px (dev D
      min 1,09) – trang D mờ chuyển động chỉ bị chặn muộn bởi S/biên. ⇒ đề xuất **`phan_tu_huong`** = min(var ∂²/∂x²,
      var ∂²/∂y²) trong vùng phần tử: D003 chuyển động 20 px đã 0,011 < 0,012. `toan_trang` (đối chứng) phụ thuộc mật độ
      nội dung (dev D min 0,72 vs phiếu 0,16) và chiếu sáng (C2 thấp) – loại.
    - **Kiểm chéo**: mọi ảnh mờ qua được `anh_mo` (Gauss ≤ 3, chuyển động ≤ 15) có S ≥ 0,265 (phiếu) / 0,276 (D) và biên
      ≥ 0,788 / 0,362 ⇒ không bị từ chối nhầm sang `khong_khop_bo_cuc` / `khong_ro_chieu`.
    - **Tập "chấp nhận được" nhóm mờ (đề xuất theo số liệu trên)**: σ 1–2 → ok; σ 3 → ok hoặc `anh_mo`; σ 5–8 → `anh_mo` /
      `khong_du_marker`; chuyển động 15 → ok hoặc `anh_mo`; 30 → `anh_mo` (kể cả D003).
    - Thời gian đo (S hai chiều + 3 cách blur + lõi + S nhầm loại, chỉ để khảo sát): ~370 ms/ảnh phiếu, ~300 ms/trang D.
      Chạy lại khảo sát cho cùng số (so bảng tóm tắt dev của lần chạy 1 và 3).
  - **Người dùng duyệt dừng B (06/10/2026)**: ngưỡng như bảng trên – `khong_khop_bo_cuc` **hai ngưỡng riêng** (phiếu 0,23,
    trang D 0,18: hai phép đo khác nhau); `anh_mo` dùng **`mo_huong`**, không chia tương phản mực. **`anh_mo` < 0,012 là
    NGƯỠNG TẠM, THẬN TRỌNG**: OMR chịu mờ tới Gauss σ ≈ 32 px / chuyển động 80 px, ngưỡng đặt chặt hơn nhiều vì CNN chữ số
    viết tay (Tuần 6) chưa đo – Tuần 6 đo CNN theo mức mờ trên `_gia_v4` rồi chỉnh lại theo hậu quả (CLAUDE.md mục 7).
    **Đơn vị**: σ / độ dài chuyển động tính bằng **px của ẢNH GỐC** (4032×3024; ở C1 ~13,7 px/mm mặt phiếu ⇒ σ 32 px ≈
    2,3 mm, 80 px ≈ 5,8 mm; C3 phía xa thưa hơn); `blur_score` đo trên **`anh_nan` thu về 150 DPI**.
  - **Ý cho báo cáo – "OMR chịu mờ tốt"**: đặc trưng OMR (độ tối trung bình lõi ô Ø5 mm so với vành giấy quanh ô, dò lại
    hàng ±4 mm) vẫn tách `faint` khỏi `blank` ở **mọi hàng** tới Gauss σ = 32 px (hiệu nhỏ nhất +0,216 → +0,014) và chuyển
    động 80 px; lớp gãy trước tiên lại là `filled`/`blank` (chuyển động 80 px: 0,91 số hàng; Gauss σ 32: 0,88) vì ô tô đậm
    lem sang ô trống bên cạnh (khoảng cách tâm 7 mm). Lý do: ô Ø5 mm lớn gấp nhiều lần độ nhoè; mờ chỉ làm trơn biên ô,
    không đổi độ tối trung bình. Hệ quả thiết kế: ô to, thưa (CLAUDE.md mục 4) đổi được lấy sức chịu mờ; giới hạn độ nét
    thật của hệ thống nằm ở khâu đọc chữ số viết tay. (Mờ là mờ tổng hợp trên ảnh dev, chưa phải mờ quang học thật.)
  - **Dừng C (06/10/2026) – chờ người dùng xem bằng mắt**. `preprocessing.py`: `verify()` (thứ tự `anh_mo` →
    `khong_khop_bo_cuc` → `khong_ro_chieu` → lõi marker), `preprocess(path, layout)` (điền mọi trường trừ `anh_chuan_hoa`;
    `marker_cham_mep` theo 2 quy tắc; trang lộn ngược → gán lại góc r + 2 và nắn lại). Eval: phương pháp `v4_verify`
    (cột thêm `huong_xoay`, `huong_dung` (từ marker v3), S0, S180, `bien_chieu`, `blur_score`, `loi_marker` – CSV phương
    pháp cũ giữ nguyên cột), `can_xem.html`, lệnh `run-gia`, `report` ghi rõ từ chối trên dev = từ chối nhầm + thời gian.
    `tao-gia`: chốt tập mờ (σ ≤ 2 → ok), thêm mờ chéo 45° (15 / 30 px × 0001_C1, 0015_C3, D003) và mờ σ 5 + tối ×0,4 +
    nhiễu σ 8 (× 0001_C1, 0008_C4) ⇒ 108 ảnh; **100 ảnh cũ giống từng byte** (SHA-256); chạy lại `tao-gia` lần nữa ra
    112 file (108 ảnh + 3 ảnh ghép + `danh_sach.csv`) giống từng byte.
    - **Dev `v4_verify`**: trả ảnh 78/78, **0 từ chối**, máy kết luận 71 `dung` / 0 `sai` / 7 `xem` (đúng 7 ảnh C3 đã
      xem bằng mắt ở 3c). Mọi số đo phép 2/3 và `o_luoi_dev.csv` **trùng v3 từng giá trị** ⇒ ảnh nắn giống v3. Chiều:
      76 ảnh 0°, 0006_C2/C3 = 90° = chiều đúng (biên chiều 0,808 / 0,835) – **quyết bằng nội dung**; 0 ảnh lệch chiều.
      Xấu nhất: biên chiều 0,429 (D006), blur 0,221 (0034_C3), lõi marker 0,357 (0034_C3), S 0,365 (0010_C2) – đúng như
      khảo sát. Thời gian `preprocess` (gồm đọc file): trung vị 532 ms, max 608 ms.
    - **Ảnh giả `run-gia` (108)**: 44 `dung` + 59 `tu_choi_dung`, **0 lỗi im lặng**, 0 từ chối nhầm; **5 không đạt**:
      (1) `cat_2px_tr_0015_C3` trả ok, tâm lệch 0,33 px: cắt 2 px qua ĐỈNH của marker xoay 5° chỉ gọt mũi nhọn, vết mực
      không chạm mép ⇒ ảnh thật sự còn nguyên marker – lỗi thiết kế ca thử; (2) `mo_cheo30_0001_C1`, `mo_cheo15_0015_C3`
      → `khong_khop_bo_cuc` thay vì `anh_mo`: `mo_huong` chỉ xét ∂²/∂x², ∂²/∂y² – mờ chéo 45° không làm nhoè hẳn hướng
      nào trong hai (blur 0,028 / 0,020 > 0,012; mờ ngang cùng độ dài 0,004); (3) `mo_toi_nhieu_0001_C1`, `_0008_C4` →
      `khong_khop_bo_cuc`: nhiễu đẩy blur từ 0,003 (σ 5 không nhiễu) lên 0,060 – **nhiễu làm ảnh mờ lọt qua `anh_mo`**,
      lớp sau (S < 0,23) chặn lại. Cả 4 ca (2)(3) vẫn bị từ chối (không lỗi im lặng) nhưng sai mã. Thời gian trung vị
      467 ms, max 578 ms.
    - **Hồi quy**: `run v2_load` + `finalize --ke-thua align_cu`, `run v3_hinh_hoc` + `finalize` ⇒ `truth_dev.csv` của
      `align_cu`, `v2_load`, `v3_hinh_hoc` **giống từng byte**; `o_luoi_dev.csv` giống từng byte; `diem_dev.csv` chỉ khác
      cột `giay`.
  - **Người dùng duyệt dừng C (06/10/2026) ⇒ BƯỚC 4 XONG**:
    - **7 ảnh C3 `xem`**: `anh_nan` v4 so với v3 **từng điểm ảnh**: 0006_C3, 0011_C3, 0026_C3, 0027_C3, 0030_C3,
      0031_C3, 0034_C3 đều **0 điểm khác** ⇒ `ket_luan_mat = dung`, ghi chú "ảnh nắn giống từng điểm ảnh v3_hinh_hoc, đã
      xem bằng mắt 06/10" (người dùng đã xem bằng mắt ở 3c).
    - **Sửa ca thử `cat_2px` – sửa ca thử THIẾT KẾ SAI, có bằng chứng, KHÔNG phải nới mong đợi để cho qua**. Mức "2 px"
      cắt 2 px qua đỉnh ô 8 mm *dự đoán từ H*, không đo trên mực. Đo mặt nạ mực (cùng ngưỡng mực của preprocessing:
      xám/nền < 0,5) của marker trên ảnh đã cắt: `cat_2px_br_0001_C1` **0 px** (chạm mép), `cat_2px_tr_0015_C3` **1 px**
      (không chạm – chỉ gọt mũi nhọn của marker xoay 5°), `cat_2px_bl_D003` **0 px**. ⇒ chỉ đổi mong đợi của **ca có
      bằng chứng** (`tr_0015_C3`: "ok hoặc `marker_cham_mep`"; nay trả ok, tâm lệch 0,33 px); 2 ca chạm mép giữ nghiêm
      `marker_cham_mep` (người dùng duyệt điều kiện cho cả 3 – thực tế chỉ 1/3 đạt nên áp hẹp hơn). Quy tắc nằm trong
      `tao-gia` (đo mực ≥ 1 px ⇒ ok_hoac), không dựa kết quả verify. **Thêm 3 ca `cat_muc_2px`** (0001_C1 BR, 0015_C3 TR,
      D003 BL): cắt sao cho mép ảnh đi vào **mực** marker đúng 2 px (đo trên mặt nạ của ảnh đã xoay; `tao-gia` kiểm lại
      trên ảnh đã cắt: mực chạm mép 0 px, không đạt thì dừng) → mong đợi `marker_cham_mep` → **3/3 đạt**.
    - **Giới hạn đã biết (để Tuần 6)**: `mo_huong` chỉ xét trục x/y; **mờ chéo 45° và mờ có nhiễu lọt qua `anh_mo`**, hiện
      bị chặn bởi `khong_khop_bo_cuc` (sai mã, vẫn an toàn). 4 ca `mo_cheo30_0001_C1`, `mo_cheo15_0015_C3`,
      `mo_toi_nhieu_0001_C1`, `mo_toi_nhieu_0008_C4` ghi `sai_ma_da_biet` (`SAI_MA_DA_BIET` trong `eval_preprocessing.py`;
      chỉ áp khi ca đó vẫn bị từ chối đúng mã `khong_khop_bo_cuc`), không tính là từ chối nhầm. Tuần 6: blur 4 hướng + trừ
      nhiễu, chọn lại ngưỡng `anh_mo` cùng lúc với đo CNN theo mức mờ.
    - **Bảng cuối – dev** (`report --phuong-phap v4_verify --so-voi v3_hinh_hoc`; nguồn 71 `tu_dong` + 7 `mat`):
      | Điều kiện | Ảnh | Đúng | Lỗi im lặng | Bị từ chối (= từ chối nhầm) |
      |---|---|---|---|---|
      | C1 | 17 | 17 | 0 | 0 |
      | C2 | 18 | 18 | 0 | 0 |
      | C3 | 17 | 17 | 0 | 0 |
      | C4 | 16 | 16 | 0 | 0 |
      | D | 10 | 10 | 0 | 0 |
      | **Tổng** | **78** | **78** | **0** | **0** |
      So với `v3_hinh_hoc`: **0 ảnh đổi phân loại**. Chiều: 76 ảnh 0°, 0006_C2/C3 90° = chiều đúng. `preprocess` (gồm đọc
      file): trung vị 523 ms, max 561 ms.
    - **Bảng cuối – ảnh giả** (`run-gia`, 111 ảnh, `data/_eval/v4_verify/gia.csv`, `gia.html`): **45 `dung` + 62
      `tu_choi_dung` + 4 `sai_ma_da_biet`; 0 lỗi im lặng, 0 lọt qua, 0 sai mã chưa biết, 0 từ chối nhầm**. Theo nhóm: xoay
      18/18 đúng chiều (gồm `xoay180_0006_C2` → 270°); che marker 10, cắt qua marker 17 + 1 ok, hai tờ 3, quá nghiêng 4,
      không có phiếu 4, nhầm loại trang 2 – đúng mã; cắt lề 3, tối + nhiễu 2 – ok; lọt khung 1 ok + 3 `marker_mo_ho`; mờ 20
      ok + 19 đúng mã + 4 đã biết. Thời gian trung vị 462 ms, max 1 288 ms (cat_le_0001_C1; ảnh chậm thứ hai 683 ms).
    - **Hồi quy lần cuối** (sau mọi thay đổi): `truth_dev.csv` + `o_luoi_dev.csv` của `align_cu`, `v2_load`, `v3_hinh_hoc`
      **giống từng byte** bản trước Bước 4; `diem_dev.csv` v2/v3 chỉ khác cột `giay`. `tao-gia`: 108 ảnh của dừng C giống
      từng byte; bộ cuối 116 file (111 ảnh + 4 ảnh ghép + `danh_sach.csv`) chạy lại giống từng byte.
    - **Đối chiếu "Xong khi"**: 0006_C2, 0006_C3 đúng – **đạt, nhờ nội dung** (biên chiều 0,808 / 0,835; ảnh giả
      `xoay180_0006_C2` ra 270° đúng) · lỗi im lặng = 0 trên dev và ảnh giả – **đạt** · mỗi ảnh bị từ chối có lý do đúng –
      **đạt trừ 4 ca đã biết** (sai mã nhưng vẫn từ chối) · không ảnh nào đổi từ đúng sang sai so với Bước 3 – **đạt** (0
      ảnh đổi) · từ chối nhầm trên dev = 0 – **đạt**.
  - **Hệ quả cho người dùng cuối**: K2 (độ phối cảnh 4 tâm marker) ≥ 0,50 ⇒ ảnh chụp nghiêng hơn mức này bị từ chối
    (ảnh dev nghiêng nhất 0,597 – 0015_C3). Đưa vào **"Hướng dẫn chụp cho giáo viên"** (Bước 7 / báo cáo), kèm ảnh minh
    hoạ mức nghiêng chấp nhận được.
  - **Dừng**: A – ảnh giả + bảng mong đợi + ảnh ghép (người dùng xem ảnh ghép + bảng); B – khảo sát + ngưỡng, báo
    **riêng phiếu và trang D** (phân bố S_dung, S_nguoc, biên tương đối, ảnh xấu nhất; phiếu: S_nguoc có bị kéo lên bởi
    32 ô trùng sau xoay hay chữ in vùng tiêu đề – thử bỏ 32 ô, so biên; D: biên khi ép chung độ dịch), hai cách
    `blur_score`, ngưỡng `anh_mo` theo hậu quả, lõi marker; C – `verify`/`preprocess` + eval `v4_verify` (dev + `run-gia`),
    xem bằng mắt, `finalize`, `report --so-voi v3_hinh_hoc`, hồi quy `v2_load`/`v3_hinh_hoc` giống từng byte; D – tài
    liệu + commit.

### Bước 5 – `normalize()` khử bóng / cân bằng sáng – `v5_chuan_hoa`
- **Việc**: điền `anh_chuan_hoa` (giữ nguyên `anh_nan`). Khử nền/bóng (vd chia cho nền ước lượng), cân bằng
  sáng giữa C1–C4.
- **Rủi ro**: khử bóng mạnh có thể xoá nét tô mờ – đúng lớp hiếm nhất (`faint` 4%).
- **Cách đo** (eval chỉ đo vị trí nên cần phép riêng, ghi vào `data/_eval/v5_chuan_hoa/`): độ đồng đều nền
  giấy theo C1–C4; độ tách `filled`/`blank` và **`faint`/`blank`** theo nhãn `cell_labels.csv`, so `anh_nan`
  với `anh_chuan_hoa`; chú ý C2 (tối), C4 (đèn vàng), 0032_C4 (vệt bóng). Eval vị trí chạy lại để chắc
  không đổi.
- **Xong khi**: nền đồng đều hơn ở mọi điều kiện; độ tách `faint`/`blank` **không giảm** ở điều kiện nào;
  kết quả eval giống hệt Bước 4.

### Bước 6 – API + thay `align()` trong các công cụ
- **Việc**: API gọn `preprocess(path) -> kết quả`, docstring tiếng Việt; thay `align()` trong `check_photos.py`
  (sinh lại `_aligned/`), `check_labels.py`, `prepare_photos.py`; kiểm thử tự động cho các ảnh khó (pytest hoặc
  script: 0006, 0013_C2, 0014_C2, 0018_C2, 0021_C2, ảnh C3, ảnh giả Bước 4).
- **Audit nhãn CHỈ trên 0001–0034** (quét lại 0006, 0018). **0035–0040 audit SAU Bước 7** – audit mở ảnh và nhãn
  phiếu test, làm trước sẽ mất tính khách quan của đánh giá cuối.
- **Cách đo**: eval không đổi so với Bước 5; audit quét được 34/34 phiếu dev.
- **Xong khi**: CLAUDE.md mục 7/8 cập nhật (gỡ cảnh báo `check_photos.py`, `align()`).

### Bước 7 – Đánh giá cuối (một lần)
- **Việc**: chốt code (commit), rồi chạy `eval_preprocessing.py run --split test --xac-nhan-test` trên
  0035–0040 đúng một lần; chạy thêm toàn bộ 80 ảnh và 10 trang chữ số để báo cáo; ghi số "trước/sau" theo C1–C4.
  Sau đó mới audit nhãn 0035–0040 (Bước 6).
- **Xem bằng mắt TOÀN BỘ ảnh máy kết luận `sai`** (và mọi ảnh `xem`) ở lần đánh giá cuối, cả dev lẫn test,
  trước khi ghi `truth_*.csv` – không để số "lỗi im lặng" của báo cáo dựa hoàn toàn vào máy.
- **Cách đo**: bảng trước (`align_cu`, Bước 1) / sau cho dev và test. Đo lại độ chính xác của ảnh nắn đúng
  (`lech_trungvi_mm`, `lech_max_mm` trên ô lưới tin cậy).
- **Mục tiêu độ chính xác** (từ Bước 1, `align_cu`/dev): ảnh nắn đúng vẫn có `lech_max` 1,4–1,6 mm (0023_C4 1,56;
  D006 1,45; 0017_C1 1,44), không tính 0014_C2 (giấy cong, 4,2 mm) – sát dung sai đo được của OMR đọc toạ độ cố
  định (1,75 mm với bubble SBD/mã đề). Phép 2 đo dưới pixel nên so trước/sau được ở mức vài phần mười mm; nhớ
  sàn chung ~0,3 mm (máy in, Bước 1).
- **Xong khi**: số liệu tái tạo được bằng một lệnh, đưa vào báo cáo; lỗi im lặng trên test được nêu trung thực
  dù bằng bao nhiêu.
