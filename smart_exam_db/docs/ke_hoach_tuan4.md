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
- **`--ke-thua` luôn trỏ tới phương pháp GỐC có kết luận bằng mắt** (chốt 07/10/2026, Bước 6), không trỏ tới phương pháp
  chỉ thừa kế lại – phương pháp thừa kế có `xem_bang_mat.csv` trống, `finalize` sẽ (đúng) từ chối. Hiện nguồn gốc là
  **`v4_verify`** cho 7 ảnh C3 (0006/0011/0026/0027/0030/0031/0034_C3). Ví dụ: `v6_api --ke-thua v5_chuan_hoa` bị từ chối
  ("còn 7 ảnh 'xem' chưa có kết luận bằng mắt") vì v5 chỉ thừa kế từ v4 ⇒ đúng là `finalize --phuong-phap v6_api --ke-thua
  v4_verify` (`kiem_ke_thua` so số đo của v6 với chính file của v4). `report --so-voi` vẫn so với phương pháp liền trước.
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
- **Kế hoạch chi tiết (người dùng duyệt 07/10/2026)**:
  - **Ranh giới normalize / eval**: `normalize(anh_nan, layout, cach=...)` chỉ dùng `anh_nan` + `layout` (M2 dùng vị trí
    marker từ layout – chấp nhận). Mặt nạ giấy trắng (PDF render), nhãn `cell_labels.csv`, dò lệch ±4 mm **chỉ trong eval**
    (`tools/kiem_chuan_hoa.py`). `preprocess` điền `anh_chuan_hoa` chỉ khi `ok`, sau `verify`; `anh_nan`/`ok`/`ly_do` không đổi.
  - **Cách thử** (giữ cả cách thua trong `cach=` để số khảo sát tái tạo được, như `blur_score`): `khong` (đối chứng) ·
    M1 `chia_nen` (`uoc_luong_nen` cửa sổ 8/12/20, × 240) · M2 `chia_nen_keo` (M1 + điểm đen = lõi 4 marker, trung vị / min)
    · M3 `clahe` (clip 1,5/2/3 × lưới 8/16). Độ phức tạp: `khong` < M1 < M2 < M3.
  - **Đo**: a – nền giấy (bóng = (p95 − p5) trung vị ô lưới 10×14 / p50 – **quyết định**; dàn; std/p50; nhiễu hạt; mức giấy
    + mực marker giữa các ảnh); b – độ tách theo nhãn, độ dịch ±4 mm dò **một lần trên `anh_nan`** rồi dùng lại; hai đặc trưng:
    `local_darkness` (OMR hiện tại, gần như bất biến với bóng) và **tuyệt đối 1 − lõi/255** (nơi chuẩn hoá phải có lợi);
    theo hàng (hiệu thô + **tương đối** = hiệu / (trung vị filled − trung vị blank của ảnh), không phụ thuộc phép kéo dãn
    tuyến tính) và gộp theo điều kiện (AUC, p1 − p99) kèm **CI 95% bootstrap theo ảnh, 1000 lần, seed 2026**; báo **cỡ mẫu**;
    c – trang D: tương phản nét, nét/nhiễu, mức nét giữa trang; d – thời gian.
  - **Cổng (chặt)**: (1) faint/blank và filled/blank: số hàng tách theo `local_darkness` không giảm ở C1–C4 – một hàng lật là
    trượt. Hàng lật mà hiệu đổi cỡ làm tròn uint8 vẫn ghi **trượt**, đánh dấu **"ca biên"** kèm hiệu trước/sau, người dùng
    quyết (không tự nới); (2) bóng giảm ở mọi C1–C4 và D; (3) gộp tuyệt đối faint/blank không giảm ở điều kiện nào.
    **Xếp hạng**: maximin theo điều kiện của AUC tuyệt đối faint/blank; chênh nhỏ hơn CI = **hoà** → chọn cách đơn giản hơn /
    ít khuếch đại nhiễu C2 hơn, rồi nhanh hơn. Không cách nào qua cổng → báo trung thực, người dùng quyết.
  - **Không đổi `anh_nan`**: vân tay SHA-256 `anh_nan` v4 ghi **trước** khi sửa `preprocessing.py`; `so_pixel_dev.csv` của
    v5 so với vân tay đó → `finalize --ke-thua v4_verify`.
  - **Dừng**: A – vân tay, mặt nạ giấy (xem bằng mắt), tự kiểm, số "trước" của `anh_nan`; B – khảo sát 11 cấu hình, người
    dùng chọn; C – vào `preprocess`, eval `v5_chuan_hoa`, `run-gia`, hồi quy từng byte; D – tài liệu + commit.
- **Dừng A (07/10/2026) – chờ người dùng xem mặt nạ**:
  - **Vân tay** `data/_eval/v4_verify/anh_nan_sha256.csv`: 78 ảnh dev, ok 78/78, HEAD `7fb691c`, `preprocessing.py` sạch
    (lệnh tự chặn nếu đã sửa / đã có file). Chạy lại 5 ảnh (0001_C1, 0006_C2, 0015_C3, 0032_C4, D006) → SHA trùng (tất định).
  - **Mặt nạ giấy** (`kiem_chuan_hoa.py mat-na` → `data/_eval/v5_chuan_hoa/xem_mat_na.html`): phiếu 18,0% trang, trang D 9,3%.
    Trang mẫu render ra 2481 px rộng (PyMuPDF làm tròn) → cắt về `page_px` 2480. Trang D: khe giữa các ô viết chỉ 2 mm nên
    giấy đo được chỉ ở lề + dải tiêu đề → bóng trang D đo trên **44** ô lưới (phiếu 103) – bóng giữa lưới ô viết không đo được.
  - **Tự kiểm** (`tu-kiem`) ĐẠT: (1) đo hai lần cùng ảnh → Δ = 0 tuyệt đối; (2) gradient 0,6→1,0 chéo. **Lần đầu chỉ một hướng
    (TL→BR) và KHÔNG ĐẠT**: ảnh C1 vốn có bóng 0,23–0,26 (ô lưới 158–224) ngược chiều nên gradient bù trừ (0,258 → 0,252) –
    lỗi thiết kế ca thử, không phải phép đo. Sửa: thử 4 hướng chéo. Hướng cùng chiều bóng sẵn có: bóng ×1,85–2,08; bản thử chia
    nền đưa mọi hướng về ×0,93–1,07 của (gốc + chia nền); `local_darkness` |Δ| ≤ 0,0065, 0 hàng lật. **Sàn làm tròn**: chỉ
    nhân gradient + làm tròn uint8 đã đổi hiệu tương đối theo hàng tới **±0,012** – tham chiếu cho "ca biên".
  - **Số "trước" (`anh_nan`, `khao-sat --cach khong`, `tom_tat_khong.md`)**: xem bảng trong báo cáo dừng A. Tóm tắt: bóng trung
    vị C1 0,241 / C2 **0,573** (max 0,824 – 0010_C2) / C3 0,143 / C4 0,281 / D 0,184. Mức giấy giữa các ảnh 168–221, mực marker
    8–62. Cỡ mẫu faint: C1 107 / C2 114 / C3 110 / C4 103 ô (mọi ảnh dev đều có faint). `local_darkness`: 100% hàng tách, AUC
    1,000 mọi điều kiện; **tuyệt đối**: AUC 0,994–0,998, p1(faint) − p99(blank) **âm** mọi điều kiện (C2 −0,103) ⇒ đặc trưng
    tuyệt đối là nơi chuẩn hoá có thể có lợi. Hàng faint khó nhất: 0019_C3 câu 30 (tương đối 0,196). Filled/blank tuyệt đối
    yếu nhất: 0028_C4 sbd6 (tương đối 0,084). Trang D: mức nét 24–103 giữa trang (khác bút: chì/bi – chuẩn hoá không nên ép
    về một mức).
  - **Người dùng duyệt dừng A (07/10/2026)**: đã xem bằng mắt mặt nạ 5 ảnh (0001_C1, 0005_C2, 0015_C3, 0032_C4, D003) – vùng
    xanh tránh chữ in, ô, chữ viết tay, viền, marker: **ổn**. Ghi nhận:
    - **Giới hạn đã biết**: trang D chỉ đo được bóng ở lề (9,3% trang, 44 ô lưới); bóng giữa vùng ô viết không đo được.
    - **Ngưỡng "ca biên" của cổng 1 = |thay đổi hiệu tương đối| ≤ 0,012** (dao động do làm tròn uint8 đo ở tự kiểm).
    - **Ca thử gradient**: sửa ca thử THIẾT KẾ SAI, có bằng chứng (bóng sẵn có của ảnh C1 ngược chiều gradient TL→BR,
      0,258 → 0,252), không phải nới tiêu chí.
    - **Kết luận dừng A**: `local_darkness` đã tách faint ở 100% hàng mọi điều kiện ⇒ chuẩn hoá chỉ có thể có ích cho đặc
      trưng tuyệt đối. Nếu ở dừng B không cấu hình nào qua cổng, hoặc lợi ích nằm trong khoảng tin cậy, kết luận hợp lệ là
      **chọn cấu hình đơn giản nhất không hại (kể cả `khong`)** – không cố tìm thêm cách.
- **Dừng B (07/10/2026) – chờ người dùng chọn**. `preprocessing.py`: `normalize(anh_nan, layout, cach)` + `CACH_CHUAN_HOA`
  (12 cấu hình gồm `khong`), **chưa được `preprocess` gọi** (anh_nan không đổi). Lệnh: `kiem_chuan_hoa.py khao-sat` (224 s, 78
  ảnh × 12) → `so-sanh` (`so_sanh.md` / `.json`) → `xem-b` (`xem_b.html`). Bootstrap **ghép cặp**: cùng chỉ số ảnh rút cho mọi
  cấu hình (seed 2026, 1000 lần) ⇒ CI là của **hiệu** giữa hai cấu hình. Đối chứng: `tom_tat_khong.md` trùng dừng A trừ dòng
  thời gian (`khong` giờ trả bản sao, 1,4 ms).
  | Cấu hình | Cổng 1 | Cổng 2 bóng | Cổng 3 | Maximin AUC faint tuyệt đối | Nhiễu C2 | ms TV |
  |---|---|---|---|---|---|---|
  | `khong` | đạt | đối chứng | đạt | 0,9938 (C2) | ×1,00 | 1 |
  | `chia_nen_8` / `_12` | đạt | đạt | **trượt** (C4: AUC −0,0005 / khoảng −0,020 – trong CI) | 0,9973 / 0,9982 | ×1,09 / ×1,11 | 76 / 68 |
  | **`chia_nen_20`** | đạt | đạt | **đạt** | **0,9992** (C4) | ×1,11 | 66 |
  | `chia_nen_keo_tv` / `_min` | đạt | đạt | trượt (C4 khoảng −0,009 – trong CI) | 0,9990 / 0,9987 | ×1,34 / ×1,14 | 87 / 86 |
  | `clahe_*` (6) | đạt | **trượt** (C3 bóng tăng; 13–35 ảnh bóng tăng) | đạt | 0,9989–0,9998 | **×2,2–3,9** | 6–7 |
  - Cổng 1: **0 hàng lật ở cả 12 cấu hình** (không có ca biên). Giảm lớn nhất hiệu tương đối theo hàng (kể cả trong sai số):
    `chia_nen_20` faint −0,044 (0032_C4 câu 30), filled −0,037 (0032_C4 câu 28), 37 hàng filled + 3 faint giảm quá 0,012 – đều
    ở **mép bóng sắc** của 0032_C4 (cửa sổ nền nhỏ bám mép bóng chưa hết, xem ảnh: còn dải mảnh dọc mép bóng). CLAHE: filled
    giảm tới −0,47, 826–1 079 hàng giảm quá biên (bão hoà ô tô đậm).
  - **Đề xuất theo luật đã chốt: `chia_nen_20`** – qua cả 3 cổng, maximin tốt nhất trong nhóm qua cổng; hơn `khong` có ý nghĩa
    (CI ghép cặp của Δ maximin [+0,002; +0,012] không chứa 0). Bóng trung vị C1 0,241→0,044 · C2 0,573→0,100 · C3 0,143→0,061 ·
    C4 0,280→0,049 · D 0,184→0,073 (0032_C4 0,347→0,132; 0 ảnh bóng tăng); khoảng p1(faint) − p99(blank) tuyệt đối từ âm sang
    **dương ở mọi điều kiện** (C2 −0,103→+0,059; C4 CI của Δ [−0,006; +0,108] chạm 0). Giá: nhiễu C2 ×1,11, 66 ms/ảnh.
    Trang D: tương phản nét không đổi (0,626), nét/nhiễu 50,1→48,1, std mức nét giữa trang 29,7→32,9.
  - **Lưu ý**: cửa sổ 20 (≈ 15 mm) nằm ở **biên lưới tham số** (8/12/20) – theo kết luận dừng A, không thử thêm cửa sổ nhỏ hơn.
- **Người dùng duyệt dừng B (07/10/2026): chọn `chia_nen_20`** (đã xem `xem_b.html` bằng mắt: ô faint vẫn rõ, bóng giảm, không
  có quầng / viền lạ đáng kể). Giới hạn đã biết (ghi cả trong docstring `CACH_MAC_DINH`):
  - **Mép bóng sắc** (0032_C4 câu 21–30) còn dải mảnh; hiệu theo hàng giảm tới −0,044 (faint) / −0,037 (filled), **không hàng
    nào lật**. `anh_nan` vẫn giữ; **Tuần 5 chọn `anh_nan` / `anh_chuan_hoa` bằng thí nghiệm F1 lớp faint**.
  - **Cửa sổ 20 (≈ 15 mm) ở biên lưới đã thử**; không thử nhỏ hơn vì gần cỡ ô Ø5 mm – nguy cơ ước lượng nền "ăn" vào ô tô,
    xoá mất faint (kết luận dừng A: không cố tối ưu thêm).
  - **Lợi ích p1(faint) − p99(blank) ở C4 có CI chạm 0** ([−0,006; +0,108]) – chưa chắc chắn ở điều kiện đèn vàng.
  - **Trang D**: nét/nhiễu 50,1 → 48,1, chênh mức nét giữa trang 29,7 → 32,9 ⇒ **Tuần 6 thử CNN trên cả `anh_nan` và
    `anh_chuan_hoa`** (CLAUDE.md mục 7).
- **Dừng C (07/10/2026)**: `CACH_MAC_DINH = "chia_nen_20"`; `preprocess` điền `anh_chuan_hoa = normalize(anh_nan, layout)`
  **chỉ khi ok, sau verify**. Eval: phương pháp `v5_chuan_hoa` (hàm bọc kiểm ok ⇔ có `anh_chuan_hoa` uint8 cùng cỡ; `run-gia`
  nhận `--phuong-phap v5_chuan_hoa`, mặc định). Kết quả:
  - `kiem_chuan_hoa.py so-anh-nan`: **78/78 `anh_nan` giống vân tay v4 từng byte** (kèm `ok`, `ly_do`) → `so_pixel_dev.csv`.
  - `run v5_chuan_hoa` → `finalize --ke-thua v4_verify` **đạt** (78 ảnh giống từng điểm ảnh, mọi số đo phép 2/3 trùng khớp;
    nguồn 71 `tu_dong` + 7 `mat_v4_verify`) → `report --so-voi v4_verify`: **78/78 đúng, 0 lỗi im lặng, 0 từ chối, 0 ảnh đổi
    phân loại**. `diem_dev.csv` (trừ `giay`, `phuong_phap`), `o_luoi_dev.csv` (từng byte), `truth_dev.csv` (trừ `phuong_phap`,
    `nguon`) giống v4.
  - `run-gia --phuong-phap v5_chuan_hoa` (111 ảnh): 45 `dung` + 62 `tu_choi_dung` + 4 `sai_ma_da_biet`, 0 lỗi im lặng – `gia.csv`
    **giống v4 từng giá trị trừ cột `giay`**.
  - **Hồi quy** (chạy lại `run` + `finalize` cho `v2_load --ke-thua align_cu`, `v3_hinh_hoc`, `v4_verify`; so với bản sao lưu
    trước dừng C): `truth_dev.csv`, `o_luoi_dev.csv`, `xem_bang_mat.csv` của `align_cu`/`v2_load`/`v3_hinh_hoc`/`v4_verify` **giống
    từng byte**; `diem_dev.csv` v2/v3/v4 chỉ khác cột `giay`.
  - **Thời gian** `preprocess` (gồm đọc file, `diem_dev.csv`): v4 (Bước 4) trung vị 523 ms / max 561 ms → v5 **578 / 644 ms**;
    riêng `normalize` (khảo sát) 66 / 75 ms.
  - **Đối chiếu "Xong khi"**: nền đồng đều hơn ở mọi điều kiện – **đạt** (bóng C1–C4, D đều giảm; 0 ảnh tăng; trang D chỉ đo
    được ở lề) · độ tách faint/blank không giảm ở điều kiện nào – **đạt theo cổng đã chốt** (0 hàng lật; gộp tuyệt đối không
    giảm; giảm theo hàng nhỏ nhất −0,044 ở mép bóng 0032_C4, ghi trung thực) · eval giống hệt Bước 4 – **đạt** (từng byte).
  ⇒ **BƯỚC 5 XONG.**

### Bước 6 – API + thay `align()` trong các công cụ
- **Việc**: API gọn `preprocess(path) -> kết quả`, docstring tiếng Việt; thay `align()` trong `check_photos.py`
  (sinh lại `_aligned/`), `check_labels.py`, `prepare_photos.py`; kiểm thử tự động cho các ảnh khó (pytest hoặc
  script: 0006, 0013_C2, 0014_C2, 0018_C2, 0021_C2, ảnh C3, ảnh giả Bước 4).
- **Audit nhãn CHỈ trên 0001–0034** (quét lại 0006, 0018). **0035–0040 audit SAU Bước 7** – audit mở ảnh và nhãn
  phiếu test, làm trước sẽ mất tính khách quan của đánh giá cuối.
- **Cách đo**: eval không đổi so với Bước 5; audit quét được 34/34 phiếu dev.
- **Xong khi**: CLAUDE.md mục 7/8 cập nhật (gỡ cảnh báo `check_photos.py`, `align()`).
- **Kế hoạch chi tiết (người dùng duyệt 07/10/2026)**:
  - **Chỗ gọi `align()` cũ** (grep): `answer_sheet/check_photos.py` (nắn + lưu), `tools/prepare_photos.py` (`check_align()` /
    `best_rotation()` trong `preview`, `measure`), `tools/check_labels.py` (`check_align` – kiểm từng câu + `audit`),
    `answer_sheet/check_layout.py` (tự kiểm ảnh tô giả) ⇒ **thay bằng `preprocess()`** (check_layout: giữ `align()`, thêm
    lượt `preprocess`). **Giữ nguyên** (tái tạo số "trước"): `eval_preprocessing.py` `align_cu`/`v2_load`, `marker_that.py`;
    `prepare_photos.marker_centers()` (`verify-ids`, `measure`) – cố ý độc lập với preprocess. Ảnh bị từ chối: in
    `tên: TỪ CHỐI – <ly_do> (<MA_LY_DO>)` + ghi CSV/HTML + tổng theo mã; lỗi lập trình vẫn ném ra.
  - **API**: `preprocess(path, layout)` = `doc_anh` + `preprocess_anh(gray, layout, exif_orientation=1)` (backend nhận byte);
    `MA_LY_DO` (mã -> thông báo cho giáo viên), `nap_layout()`, docstring `KetQuaTienXuLy`. **Không đổi hành vi**: SHA
    `anh_nan` = vân tay v4, SHA `anh_chuan_hoa` = v5 (`kiem_chuan_hoa.py so-anh-nan --phuong-phap v6_api`), eval `v6_api`
    `--ke-thua v5_chuan_hoa`, `run-gia` như v5.
  - **`cv_engine/tap_du_lieu.py` = NGUỒN DUY NHẤT cho ranh giới dev/test** (`PHIEU_DEV/TEST/TRAIN/VAL`, `la_test`, `chan_test`
    ném `ChamTapTest` TRƯỚC khi đọc file nếu thiếu `--xac-nhan-test`). `eval_preprocessing.SPLITS` dùng lại module này.
    **Tuần 5 (`split.csv` OMR: train 0001–0028 / val 0029–0034 / test 0035–0040) phải dùng lại đúng module này, không định
    nghĩa lại.**
  - **Thư mục ghi**: `data/_aligned/raw/`, `data/_aligned/raw_digits/` (anh_nan, **JPEG q95, chỉ để xem**; Tuần 5 gọi
    `preprocess()` trực tiếp, có lưu đệm hay không quyết ở Tuần 5), `data/_aligned/photo_report_*.csv`,
    `data/_prepare/label_audit_dev/`, `data/_prepare/preview_dev.html`, `data/_eval/v6_api/`, `data/_eval/tham_chieu_kiem_thu/`.
    **Không ghi** `data/raw*` (trước đây `check_photos.py` ghi `<dir>/_aligned` + `photo_report.csv` VÀO `data/raw` – sửa;
    hiện không có thư mục `_aligned` nào, không có gì để sao lưu), `label_audit.*`/`preview.html`/`mapping.csv`/`measure/` cũ,
    `ground_truth.csv`.
  - **Kiểm thử** `smart_exam_db/tests/` (pytest ≥ 8, chỉ để kiểm thử): EXIF/Unicode/file lỗi (không cần `data/`); 7 ảnh dev
    đại diện so tham chiếu; ảnh giả `_gia_v4` từ chối đúng mã (mong đợi đọc từ `danh_sach.csv`); ranh giới dev/test. Thiếu
    `data/` -> SKIP. **Vân tay phụ thuộc phiên bản OpenCV/nền tảng**: tham chiếu ghi kèm `cv2`/`numpy`; cùng phiên bản -> so
    từng byte; khác phiên bản -> |Δ| ≤ 2 mức xám ở ≥ 99,9% điểm ảnh + cảnh báo, không fail.
  - **`min_blur_score` trong DB** (100, thang Laplacian thô) ≠ `blur_score`/`MO_MIN` (0,012) – chỉ ghi vào CLAUDE.md việc
    Tuần 7 (đổi sang thang `mo_huong`); không sửa DB bây giờ.
  - **Dừng**: A – API, chốt chặn, kiểm thử, eval `v6_api`; B – thay 3 công cụ + `check_layout`, trước/sau, sinh `_aligned/`,
    `preview_dev.html`; C – audit 34 phiếu dev (nhóm A mới -> người dùng so giấy, không sửa `ground_truth.csv`); D – tài liệu
    + commit.
- **Ghi nhận trung thực về tập test (cho báo cáo Bước 7)**: lần `check_labels.py audit` ngày **03/10/2026** (trước khi có
  quy tắc dev/test của Tuần 4) đã **mở ảnh và nhãn của cả 40 phiếu, gồm 0035–0040**, bằng `align()` cũ; nhãn **mã đề bubble
  của phiếu 0035** (`---`, người tô không tô ô nào) được sửa dựa trên ảnh + giấy thật (CLAUDE.md mục 6). Phân biệt:
  **sửa nhãn cho khớp tờ giấy thật ≠ rò rỉ tham số** – không có tham số / ngưỡng nào của preprocessing được chọn theo ảnh
  test; ngưỡng audit (`MARK_MIN`, `FILLED_MIN`) chọn trên 56 ảnh lúc đó có lẫn ảnh test nhưng chỉ dùng để *tìm nhãn sai*,
  không phải mô hình được đánh giá. **`preprocess()` (v3–v6) chưa từng chạy trên ảnh 0035–0040.** Bước 7 báo cáo mục này.
  Kiểm 07/10/2026: `data/_eval/` không có file `*test*`, 0 ảnh đầu ra tên 0035–0040, 0 CSV nhắc tới 0035_Ck–0040_Ck.
- **Dừng A (07/10/2026) – chờ người dùng duyệt**:
  - **pytest**: `pip install --dry-run` (Python 3.14.7) -> pytest **9.1.1** + colorama, iniconfig, packaging, pluggy, pygments;
    cài vào `.venv` gốc; `requirements.txt` thêm `pytest>=8` (ghi chú "chỉ để kiểm thử"). Môi trường: cv2 5.0.0, numpy 2.5.3.
  - **Tham chiếu kiểm thử** (`tools/tao_tham_chieu.py`, chạy TRƯỚC khi sửa `preprocessing.py`, tự chặn nếu file đã sửa):
    7 ảnh (0001_C1, 0005_C2, 0015_C3, 0032_C4, 0006_C2, 0014_C2, D003) – SHA `anh_nan` = vân tay v4, `anh_chuan_hoa` = v5,
    lưu PNG (đọc lại giống từng byte) + `tham_chieu.json` (phiên bản python/cv2/numpy/nền tảng) -> `data/_eval/tham_chieu_kiem_thu/`
    (64 MB); `v4_verify/anh_nan_sha256_moi_truong.json` (ghi bổ sung phiên bản cho vân tay v4).
  - **API**: `preprocess(path, layout)` = `doc_anh` + `preprocess_anh(gray, layout, exif_orientation=1)`; `MA_LY_DO` (9 mã ->
    thông báo cho giáo viên), `nap_layout()`, docstring `KetQuaTienXuLy` (kiểu, cỡ, toạ độ, trường nào có khi `ok=False`).
    `cv_engine/tap_du_lieu.py`; `eval_preprocessing.SPLITS` dùng lại.
  - **Không đổi hành vi**: `so-anh-nan --phuong-phap v6_api` **78/78** (`anh_nan` = vân tay v4 và `anh_chuan_hoa` = v5, từng
    byte); `finalize --phuong-phap v6_api --ke-thua v4_verify` đạt -> `report --so-voi v5_chuan_hoa` **78/78 đúng, 0 đổi**;
    `diem_dev` (trừ `giay`, `phuong_phap`), `o_luoi_dev` (từng byte), `truth_dev` (trừ `phuong_phap`), `gia.csv` (trừ `giay`:
    45 + 62 + 4 đã biết, 0 lỗi im lặng) giống v5. truth/o_luoi của align_cu/v2/v3/v4 không đổi. `preprocess` trung vị 579 ms.
    **Lệch kế hoạch (chốt chặn hoạt động đúng)**: `--ke-thua v5_chuan_hoa` bị `finalize` TỪ CHỐI ("còn 7 ảnh 'xem' chưa có kết
    luận bằng mắt") – v5 không có kết luận bằng mắt của riêng nó (7 ảnh C3 thừa kế từ v4, `xem_bang_mat.csv` của v5 trống) ⇒
    thừa kế từ **nguồn gốc `v4_verify`** (`kiem_ke_thua` so số đo v6 với chính file của v4).
  - **pytest** (`python -m pytest tests`, từ `smart_exam_db/`): **35 đạt, 8,3 s** – `test_load_image` (EXIF 1/3/6/8, Unicode,
    file thiếu/hỏng), `test_preprocess_dev` (7 ảnh + `preprocess_anh` ≡ `preprocess` + API), `test_tu_choi` (9 ảnh giả:
    `marker_khong_dat`, `marker_cham_mep`, `nhieu_phieu`, `marker_mo_ho`, `anh_mo`, `khong_khop_bo_cuc`, `thieu_marker`,
    quá nghiêng, xoay 180° 0006_C2 -> 270°), `test_tap_du_lieu`. **Phép thử chặn** (scratchpad): cùng phiên bản + lệch 1 điểm
    ảnh 1 mức -> BỊ CHẶN; khác phiên bản: lệch ≤ 2 mức -> đạt + cảnh báo, 0,2% điểm ảnh lệch 3 mức -> BỊ CHẶN; `load_image`
    bỏ qua EXIF -> EXIF 3/6/8 BỊ CHẶN. (Lần thử đầu giả lập "bỏ qua EXIF" bằng `cv2.imdecode` thường – **không** chặn được vì
    OpenCV mặc định TỰ ÁP EXIF; giả lập đúng phải thêm `IMREAD_IGNORE_ORIENTATION`.)
  - **Người dùng duyệt dừng A; commit `fc4946b`** (pytest sau commit: 35 đạt).
- **Dừng B (07/10/2026) – thay `align()` trong 4 công cụ, chờ người dùng duyệt**. Số "trước" chạy trên code `fc4946b`
  TRƯỚC khi sửa, chỉ ghi scratchpad (`check_photos` cũ chạy trên thư mục hardlink tới 78 ảnh dev – không chép, không ghi
  `data/raw`). Bảng trước / sau:
  | Công cụ | Trước (`align()` cũ) | Sau (`preprocess()`) |
  |---|---|---|
  | `check_photos.py` (78 ảnh dev) | 78/78 "OK", 0 lỗi – trong đó **19 ảnh nắn sai** (`align_cu/truth_dev.csv`) vẫn báo OK và lưu ảnh nắn sai; ghi `<dir>/_aligned` + `photo_report.csv` VÀO thư mục ảnh gốc | 78/78 OK, **SHA `anh_nan` trùng vân tay v4 78/78**; ghi `data/_aligned/raw/` (68), `raw_digits/` (10) JPEG q95 + `data/_aligned/photo_report_<thư mục>.csv` (cột `ly_do`, `thong_bao`, `huong_xoay`, `blur_score`, `sha256_anh_nan`); 0 file mới trong `data/raw*`; 12 ảnh test **BỎ QUA, không đọc**; từ chối -> `TỪ CHỐI – mã (thông báo)` + tổng theo mã; chặn `--out` nằm trong thư mục gốc |
  | `prepare_photos.py preview` (78 dòng dev của `mapping.csv`) | `check_align()` báo không tin cậy **17**; lọt 2 ảnh nắn sai (0013_C2, 0018_C2) | **0 bị từ chối** -> `data/_prepare/preview_dev.html`; `preview.html` cũ không đổi (hash); `--split tat_ca` cần `--xac-nhan-test` (cả `plan`) |
  | `prepare_photos.py measure` (IMG_4381 = 0014_C3, IMG_4357 = 0028_C4; `--work` scratchpad) | lỗi `FileNotFoundError` (không tự tạo `<work>/jpg` – lỗi có sẵn); tạo tay thư mục: IMG_4381 "align() chọn nhầm marker", IMG_4357 OK | cả hai **OK**; vùng mã cắt từ `anh_nan` đọc được "Mã phiếu: 0014"; tự tạo `jpg/`; `--ref` chỉ ảnh dev |
  | `prepare_photos.py verify-ids` | đọc cả 80 ảnh | mặc định chỉ dev (không chạy lại ở bước này – không gọi align) |
  | `check_labels.py` 0032:33, 0008:18, 0021:5,6, 0015:3 | 0021_C2 (2 câu), 0015_C3 BỎ QUA ("chọn nhầm marker") | đo được cả 3; ảnh vốn nắn đúng cho số **giống** (lệch ≤ 0,01 ở hiệu 0021_C1 câu 6); ô đúng nhãn nổi bật ở mọi ảnh; phiếu test cần `--xac-nhan-test` |
  | `check_layout.py` (ảnh tô giả) | 40/40, SBD 062384, mã đề 101, KHỚP; rule-based 36/40 | lượt `align()` y hệt; thêm lượt `preprocess_anh` 40/40, 062384, 101 -> **"KẾT QUẢ LAYOUT: KHỚP"** (giữ câu kết luận cũ) |
  - **Lỗi cũ của `prepare_photos.py measure` – ĐÃ SỬA ở dừng B**: bản cũ không tạo `<work>/jpg/` nên `measure --work <thư
    mục mới>` ném `FileNotFoundError` khi chuyển ảnh (chỉ chạy được với `--work data/_prepare` vì thư mục đó có sẵn `jpg/`).
    Bản mới `cmd_measure` tạo `<work>/jpg/` trước khi chuyển; đã kiểm bằng `measure ... --work <scratchpad mới>` chạy thông.
  - `check_labels audit`: `--split dev` (mặc định, lọc nhãn phiếu test ngay khi đọc `ground_truth.csv`) / `tat_ca` (cần
    `--xac-nhan-test`, `chan_test` trước khi đọc ảnh); ghi `data/_prepare/label_audit_<split>/` (bản 03/10 giữ nguyên). Chạy
    audit ở dừng C. `check_align()`/`best_rotation()` bị xoá khỏi `prepare_photos.py` (không còn ai gọi); `marker_fill`,
    `load_templates`, `marker_centers` giữ (eval phép 1, verify-ids).
  - **pytest**: thêm `test_chot_chan_cong_cu.py` (6 test: audit `tat_ca` không cờ -> `ChamTapTest`; audit dev bắt đầu từ
    0001; `check_labels 0035:1` -> dừng; `preview tat_ca` không cờ -> dừng; `check_photos` bỏ qua `0035_C1` không đọc; chặn
    `--out` trong thư mục gốc) – mọi hàm đọc/nắn ảnh bị thay bằng hàm ném lỗi. **Thử chặn**: gỡ từng chốt chặn -> 4/4 test
    TRƯỢT. Tổng **41 đạt**.
  - **Eval không đổi**: chạy lại `run v6_api` sau khi sửa công cụ -> `diem_dev` (trừ `giay`) giống, `o_luoi_dev` giống từng
    byte; `report --so-voi v5_chuan_hoa` 0 đổi. Import `kiem_verify`, `kiem_chuan_hoa`, `marker_that`, `tao_tham_chieu` OK.
  - **Người dùng duyệt dừng B; commit `8cf334c`** (pytest sau commit: 41 đạt).
- **Dừng C (07/10/2026) – audit nhãn 34 phiếu dev, chờ người dùng so giấy** (`python tools/check_labels.py audit` ->
  `data/_prepare/label_audit_dev/`; bản 03/10 `data/_prepare/label_audit.*` giữ nguyên, so chỉ trên phiếu 0001–0034):
  - **Quét được 34/34 phiếu, cả 68 ảnh** (mọi phiếu đối chiếu 2 ảnh; 0 ảnh bị từ chối, 0 ảnh đáng ngờ ở kiểm tra phụ, thang S
    0,42–0,83). Audit cũ: 38/40 phiếu, 18 phiếu chỉ 1 ảnh, **không quét được 0006, 0018**. Nay: **0006 (C2+C3) – 0 mục**;
    **0018 (C2+C3) – 1 mục nhóm B** (câu 4, nhãn `b` mờ, C2 đọc `b`, C3 đọc `B`).
  - Phân bố n theo nhãn (68 ảnh): blank 8 210 ô p99 0,06 · faint 434 ô p1 0,26 / p95 0,81 · filled 2 236 ô p5 0,90 – ngưỡng
    `MARK_MIN` 0,25 / `FILLED_MIN` 0,80 không đổi.
  - **Nhóm A: 3 mục** (cũ trên dev: 2) – đều "thiếu ô", 1/2 ảnh, ô C nhãn mờ có n 0,23–0,26 SÁT NGƯỠNG 0,25:
    | Phiếu:câu | Nhãn | Ảnh 1 (n A/B/C/D) | Ảnh 2 (n A/B/C/D) | Ghi chú |
    |---|---|---|---|---|
    | **0019:24 (MỚI)** | `c` (C mờ) | C3 đọc `-`: 0,00 / 0,03 / **0,23** / 0,02 | C4 đọc `c`: 0,00 / 0,04 / **0,26** / 0,02 | audit cũ chỉ có ảnh C4 (C3 bị `align()` nắn sai). Ảnh cắt: C có tô mờ ở cả 2 ảnh; chấm nhỏ ngoài vòng ô B |
    | 0033:4 (cũ) | `c` | C1 đọc `c`: 0,00 / 0,01 / 0,26 / 0,00 | C2 đọc `-`: 0,00 / 0,00 / 0,24 / 0,02 | người dùng đã quyết giữ (03/10) |
    | 0020:33 (cũ) | `c` | C1 đọc `-`: 0,00 / 0,02 / 0,25⁻ / 0,01 | C4 đọc `c`: 0,00 / 0,03 / 0,26 / 0,02 | người dùng đã quyết giữ (03/10) |
    Ảnh cắt: `data/_prepare/label_audit_dev/label_audit/0019_q24_C3.png`, `_C4.png` (tương tự 0033_q04, 0020_q33).
  - **Nhóm B: 45 mục** (cũ trên dev: 35; 35 chung, 0 mất, **10 mới**). 9/10 mục mới đến từ ảnh mà audit cũ không dùng được
    (0013_C2 câu 2, 3; 0014_C3 câu 4; 0018 câu 4; 0021_C2 câu 31, 34; 0023_C3 câu 3, 38, 39). Ngoại lệ **0025:2** (nhãn `D` rõ,
    C2 n 0,80 -> đọc mờ; C1 0,95): audit cũ cũng đọc C1+C2 – sát ngưỡng `FILLED_MIN` 0,80, khác biệt nắn dưới pixel đủ đổi bên.
  - **Không sửa `ground_truth.csv`.** Chờ người dùng so giấy 0019 câu 24 (và quyết nhóm B như lần trước).
  - **Người dùng so giấy thật (07/10/2026)**: 0019 câu 24 – ô C có vết tô mờ ⇒ nhãn `c` **ĐÚNG, giữ nguyên**. Không xem thêm
    nhóm B. `ground_truth.csv` không đổi.
  - **Kết luận nhóm A**: cả 3 mục (0019:24, 0033:4, 0020:33) **nhãn đúng**; đều là ô `faint` có độ tối tương đối n 0,23–0,26
    SÁT NGƯỠNG cố định `MARK_MIN` 0,25 ⇒ **giới hạn của ngưỡng cố định, không phải lỗi nhãn**. Ghi làm **ca thử cho
    classifier 3 lớp Tuần 5** (CLAUDE.md mục 7).
- **Đối chiếu "Xong khi" Bước 6**:
  - Eval không đổi so với Bước 5 – **đạt**: `v6_api` 78/78 đúng, 0 đổi so với `v5_chuan_hoa`; `anh_nan` (vân tay v4) và
    `anh_chuan_hoa` (v5) giống từng byte 78/78; ảnh giả như v5; chạy lại sau khi sửa công cụ vẫn giống.
  - Audit quét được 34/34 phiếu dev – **đạt** (68/68 ảnh, gồm 0006, 0018); 0035–0040 chưa audit (để sau Bước 7).
  - CLAUDE.md mục 7/8 cập nhật (gỡ cảnh báo `check_photos.py`, `align()`) – **đạt** (dừng D).
  - Kèm theo: API `preprocess` / `preprocess_anh` / `MA_LY_DO` / `nap_layout`; `cv_engine/tap_du_lieu.py` + chốt chặn tập
    test ở mọi công cụ; 4 công cụ dùng `preprocess()`, không ghi vào `data/raw*`; pytest **41/41** (~8 s).
  ⇒ **BƯỚC 6 XONG (07/10/2026).**

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
- **Dừng A (07/10/2026) – B7.0, sửa I/O, commit X = `d9e56d5`** (người dùng đã duyệt kế hoạch B7.0–B7.6): `run --split
  test` ghi `xem_bang_mat_test.{html,csv}` ở chế độ MÙ, từ chối chạy lại nếu `diem_test.csv` đã có; `finalize`/`report
  --split`, `finalize --split test` cấm `--ke-thua` và bắt buộc kết luận bằng mắt cho mọi ảnh trả về; `report-cuoi`;
  `check_labels audit --split test`. Kiểm: pytest 51/51 (10 test mới, thử chặn HTML mù đạt); hồi quy dev `align_cu` +
  `v6_api` (`diem_dev` trừ `giay`, `o_luoi_dev`, `truth_dev`, `xem_bang_mat.csv`) giống trước, không sinh file `*_test*`.
  `report-cuoi` trên dev: so công bằng trên CÙNG 58 ảnh mà cả hai nắn đúng, `lech_trungvi` TB 0,38 (align_cu) / 0,40
  (v6_api) mm, `lech_max` lớn nhất 1,55 / 1,57 mm (0023_C4) – độ chính xác gần như nhau; v6_api thêm 19 ảnh (C3, 0006_C2,
  0013_C2, 0018_C2, 0021_C2), `lech_max` lớn nhất trên 77 ảnh là 2,31 mm (0030_C3, lệch thật của ảnh C3 – Tuần 5 dò lại
  từng hàng).

#### ĐĂNG KÝ TRƯỚC (chốt 07/10/2026, TRƯỚC khi chạy bất cứ gì trên 0035–0040; commit Y = commit chứa đoạn này)
- **Sao lưu `data/`**: người dùng xác nhận đã xong (`data_20261007.zip`, trên máy + Google Drive).
- **Code cố định**: commit X **`d9e56d5`**. Khi chạy: working tree sạch và `git diff d9e56d5 HEAD -- '*.py'` RỖNG
  (commit Y chỉ sửa tài liệu). Không sửa code / ngưỡng / phương pháp sau khi thấy kết quả.
- **Ngưỡng eval**: `data/_eval/nguong.json`, SHA-256
  **`DF9908623638B392B31488C5F1AF00963541B1EADA0324B7B7A592E3AEA91780`** (kiểm 07/10 trước khi ghi). Kiểm lại ngay trước
  khi chạy; khác thì DỪNG.
- **Phương pháp**: CHỈ `align_cu` (số "trước") và `v6_api` (số "sau"). Không thêm phương pháp nào khác.
- **Tập test**: phiếu 0035–0040 (`cv_engine/tap_du_lieu.PHIEU_TEST`), **12 ảnh: C1 3, C2 2, C3 3, C4 4** (không có trang
  chữ số). Trước Bước 7 chỉ liệt kê TÊN file, chưa mở ảnh bằng preprocess / eval.
- **Quy trình (mỗi lệnh chạy MỘT lần, log lưu lại)**:
  1. Kiểm HEAD, `git diff` mã nguồn, SHA `nguong.json`.
  2. `run --phuong-phap align_cu --split test --xac-nhan-test`, rồi `run --phuong-phap v6_api --split test --xac-nhan-test`.
  3. **Xem bằng mắt MÙ**: người dùng mở `data/_eval/<pp>/xem_bang_mat_test.html` (chỉ ảnh gốc + tứ giác marker + ảnh nắn
     chồng nét mẫu; KHÔNG kết luận máy, KHÔNG số đo, KHÔNG thời gian, sắp theo tên) và **kết luận CẢ 12 ảnh của MỖI phương
     pháp** (24 lần xem) vào `xem_bang_mat_test.csv` (`ket_luan_mat` = `dung` / `sai`, lý do ở `ghi_chu`) **TRƯỚC khi
     thấy kết luận máy**. Không mở `diem_test.csv` / `o_luoi_test.csv` trước khi ghi xong. Claude không báo kết luận máy
     hay số đo cho tới khi người dùng ghi xong. Ảnh bị từ chối không có ảnh nắn: không cần kết luận (tự xếp `bi_tu_choi`).
  4. `finalize --phuong-phap <pp> --split test` (cấm `--ke-thua`; dừng nếu thiếu kết luận bằng mắt) cho cả hai – lúc này
     mới hiện chỗ máy và mắt khác nhau (ghi lại, giữ kết luận của mắt).
  5. `report --phuong-phap v6_api --split test --so-voi align_cu`, rồi `report-cuoi`.
- **Tiêu chí (đã chốt từ Bước 0)**: **ĐẠT ⇔ lỗi im lặng của `v6_api` trên test = 0.** Ảnh test thật đều hợp lệ ⇒ **mọi ảnh
  bị từ chối = từ chối NHẦM** (báo riêng, không phải lỗi im lặng). Ảnh bị từ chối có độ phối cảnh K2 < 0,50 (đo độc lập
  bằng `prepare_photos.measure_one`/`marker_centers`) ghi thêm "ngoài phạm vi hướng dẫn chụp" nhưng VẪN tính từ chối nhầm.
- **Nếu có lỗi im lặng hoặc từ chối nhầm**: ghi nhận NGUYÊN TRẠNG vào bảng kết quả, phân tích nguyên nhân (ảnh, khâu), sửa
  ở phiên bản sau và chỉ đánh giá lại trên **dev**. **KHÔNG chạy lại test** để lấy số đẹp hơn (`run --split test` tự chặn
  khi `diem_test.csv` đã có; không xoá file để chạy lại).
- **Cỡ mẫu nhỏ**: báo n theo từng điều kiện; tỉ lệ lỗi im lặng kèm **cận trên 95% Clopper–Pearson** (hai phía) và, khi
  quan sát 0 lỗi, **quy tắc số 3 (≈ 3/n)** – với 12 ảnh: CP 26%, quy tắc số 3 25%; theo điều kiện (n = 2–4) cận trên rất
  rộng (n = 2: CP 84%). Kết luận chỉ ở mức "không thấy lỗi im lặng trên 12 ảnh", không suy rộng. **Bảng gộp dev + test ghi
  rõ: dev là tập đã dùng để chỉnh tham số** (số gộp lạc quan; số khách quan là bảng test).
- **Báo kèm**: độ chính xác ảnh nắn đúng (`lech_trungvi_mm`, `lech_max_mm`; trên cùng tập ảnh đúng ở cả hai phương pháp),
  thời gian mỗi ảnh, **độ phối cảnh K2 nhỏ nhất của ảnh test** (từ 4 tâm marker v6_api) cho "Hướng dẫn chụp cho giáo viên"
  (dev nhỏ nhất 0,597 – 0015_C3; ngưỡng từ chối 0,50).
- **Sau eval**: `check_labels.py audit --split test --xac-nhan-test` (-> `data/_prepare/label_audit_test/`); mục nhóm A đưa
  người dùng so giấy; không sửa `ground_truth.csv` khi chưa xác nhận.
- **Ghi trung thực**: tập test đã bị mở MỘT lần ở audit 03/10/2026 (bằng `align()` cũ, trước khi có quy tắc dev/test): mở
  ảnh + nhãn cả 40 phiếu, nhãn mã đề bubble của 0035 sửa theo ảnh + giấy thật – **sửa nhãn cho khớp giấy thật, không phải
  rò rỉ tham số**. **`preprocess()` (v3–v6) chưa từng chạy trên 0035–0040 cho tới Bước 7** (kiểm 07/10: `data/_eval/` không
  có file / ảnh / CSV nào của 0035–0040). Ngưỡng eval (`nguong.json`) chọn chủ yếu trên C1/C2/C4 của dev (Bước 1).
- **Commit Y = `d4aa953`** (đăng ký trước). Người dùng nói "chạy" ⇒ dừng C, D.

#### KẾT QUẢ (07/10/2026) – chạy MỘT lần theo đăng ký trước
- **Kiểm trước khi chạy: ĐẠT** – HEAD `d4aa953`, `git diff d9e56d5 HEAD -- '*.py'` rỗng, working tree sạch, SHA
  `nguong.json` = giá trị đăng ký. `run --split test --xac-nhan-test` mỗi phương pháp một lần (log
  `data/_eval/buoc7_run_test.log`): cả hai trả ảnh 12/12, 0 từ chối. HTML mù kiểm tự động: không chứa kết luận máy / số đo.
- **Xem mù**: người dùng kết luận 24 ảnh trước khi thấy kết luận máy. Lần gửi đầu ghi nhầm `0035_C1`/`0035_C2` (gõ từ
  mẫu – không thuộc tập test) ⇒ Claude KHÔNG tự gán, hỏi lại; người dùng xem lại `align_cu` 0035_C3 = `sai` (lệch vùng đáp
  án), 0035_C4 = `dung`. `finalize --split test` (không `--ke-thua`): nguồn 12/12 `mat` cho cả hai phương pháp (log
  `data/_eval/buoc7_finalize_test.log`).
- **Bảng test** (`report --split test`, `report-cuoi` -> `data/_eval/bao_cao_cuoi_tuan4.md`):
  | Điều kiện | n | `align_cu` đúng / lỗi im lặng / từ chối | `v6_api` đúng / lỗi im lặng / từ chối | Cận trên 95% lỗi im lặng `v6_api` (Clopper–Pearson) |
  |---|---|---|---|---|
  | C1 | 3 | 3 / 0 / 0 | 3 / 0 / 0 | 71% |
  | C2 | 2 | 2 / 0 / 0 | 2 / 0 / 0 | 84% |
  | C3 | 3 | **0 / 3 / 0** (0035_C3, 0038_C3, 0039_C3) | **3 / 0 / 0** | 71% |
  | C4 | 4 | 4 / 0 / 0 | 4 / 0 / 0 | 60% |
  | **Tổng** | **12** | **9 / 3 / 0** | **12 / 0 / 0** | **26%** (quy tắc số 3: 25%) |
  ⇒ **`v6_api` ĐẠT tiêu chí đăng ký trước (0 lỗi im lặng, 0 từ chối nhầm trên test).** Cỡ mẫu nhỏ: chỉ kết luận "không thấy
  lỗi im lặng trên 12 ảnh test"; theo điều kiện (n = 2–4) cận trên 60–84%.
  **Quy tắc số 3 chỉ dùng khi n đủ lớn; với từng điều kiện (n = 2–4) chỉ báo Clopper–Pearson; các số > 100% (vd n = 2:
  "150%") trong log `report-cuoi` là LỖI HIỂN THỊ ĐÃ BIẾT** – không sửa code sau khi thấy kết quả (cam kết đăng ký trước);
  việc treo: sửa hiển thị trong commit riêng SAU Bước 7 (không đổi số liệu nào).
- **Máy so với mắt**: `align_cu` 12/12 trùng (3 ảnh C3 máy `sai` = mắt `sai`). `v6_api` 11/12 trùng; **0035_C3: máy `xem`
  (trượt `lech_trungvi_mm` = 1,08) → mắt `dung`** – máy chưa quyết, không phải mâu thuẫn. 0 ảnh máy/mắt ngược nhau.
- **Gộp dev + test** (90 ảnh: 80 phiếu + 10 trang chữ số; **dev là tập đã dùng để chỉnh tham số / ngưỡng ⇒ số gộp lạc
  quan, số khách quan là bảng test**): `align_cu` 68 đúng / 22 lỗi im lặng / 0 từ chối (C3 2/20 đúng); `v6_api` **90 / 0 /
  0** (cận trên 95% CP 4%).
- **Độ chính xác ảnh nắn đúng** (phép 2, ô lưới tin cậy; bỏ cờ giấy cong): trên CÙNG 9 ảnh test đúng ở cả hai –
  `lech_trungvi` TB 0,33 (align_cu) / 0,35 (v6_api) mm, `lech_max` lớn nhất 1,00 / 1,05 mm (0037_C1) ⇒ như nhau. Trên cả 12
  ảnh test `v6_api`: `lech_max` lớn nhất **2,06 mm (0035_C3)** – vượt dung sai 2,0 mm của OMR đọc toạ độ cố định ô đáp án
  (Bước 1) ⇒ xác nhận yêu cầu Tuần 5: **OMR dò lại từng hàng**. (Dev: 2,31 mm – 0030_C3.)
- **Thời gian** (gồm đọc file): `v6_api` test trung vị 594 ms, lớn nhất 635 ms (dev 574 / 650); `align_cu` 90 / 99 ms.
- **Độ phối cảnh K2** (4 tâm marker `v6_api`): test nhỏ nhất **0,618 (0039_C3)**, trung vị C3 0,620; dev nhỏ nhất 0,597
  (0015_C3); ngưỡng từ chối 0,50 ⇒ **Hướng dẫn chụp cho giáo viên**: mọi ảnh chụp nghiêng như C3 của bộ dữ liệu (độ phối
  cảnh ≥ ~0,6) đều nắn đúng; nghiêng hơn 0,50 bị từ chối (yêu cầu chụp lại) – kèm ảnh minh hoạ 0015_C3 / 0039_C3.
- **Đối chiếu "Xong khi"**: số liệu tái tạo được bằng một lệnh (`report-cuoi`) – **đạt**; lỗi im lặng trên test nêu trung
  thực (0 cho `v6_api`, 3 cho `align_cu`) – **đạt**. Còn: audit nhãn 0035–0040 (dừng E).
- **Commit kết quả: `2774def`.**
- **Dừng E (07/10/2026) – audit nhãn tập test** (`python tools/check_labels.py audit --split test --xac-nhan-test` ->
  `data/_prepare/label_audit_test/`, log `data/_eval/buoc7_audit_test.log`; bản 03/10 giữ nguyên, so trên phiếu 0035–0040):
  | | Audit cũ 03/10 (`align()`) | Audit mới (`preprocess()`) |
  |---|---|---|
  | Phiếu / ảnh quét được | 6/6 phiếu; 3 ảnh C3 nắn sai -> không dùng | **6/6 phiếu, 12/12 ảnh** (mọi phiếu đối chiếu 2 ảnh), 0 đáng ngờ |
  | Nhóm A | 0 | **0** |
  | Nhóm B | 17 | 17 (16 chung; mới 0038:16 – nhờ đọc được ảnh 0038_C3; hết 0037:14) |
  - Phân bố n (12 ảnh): blank 1 454 ô p99 0,06 · faint 84 ô p1 0,34 · filled 382 ô p1 **0,50** (dev 0,78) – vài ô nhãn rõ
    bị ảnh C2 tối của 0037 đọc mờ; ngưỡng 0,25 / 0,80 vẫn tách trống khỏi có tô.
  - **Nhóm B 17 mục**: 11 ở phiếu 0037 (6 mục C2 đọc mờ nhãn rõ: câu 6, 7, 8, 9, 10, 19; 2 mục chỉ C2 đọc rõ nhãn mờ: 22,
    33; 3 mục 2/2 – xem dưới); 0038:16 (C3 đọc mờ nhãn rõ). **8 mục CẢ 2 ảnh cùng lệch nhãn** (dễ là nhãn rõ/mờ sai thật):
    nhãn mờ – 2 ảnh đọc rõ: **0036 câu 2, 10, 13; 0037 câu 1, 15, 31; 0040 câu 5**; nhãn rõ – 2 ảnh đọc mờ: **0040 câu 10**.
  - **8 mục chờ người dùng so giấy thật** – trang `data/_prepare/label_audit_test/so_giay_8_muc.html` (mỗi mục: ảnh cắt
    hàng câu từ 2 ảnh + nhãn hiện tại, KHÔNG số đo máy; tạo bằng `data/_prepare/label_audit_test/tao_so_giay_8_muc.py`).
    **Quy tắc**: chỉ theo giấy thật; cùng tiêu chí rõ/mờ như lúc gán nhãn; **phân vân thì giữ nguyên**; mọi thay đổi ghi lại
    (phiếu, câu, cũ -> mới, lý do). Vì là nhãn tập TEST: sửa nhãn cho khớp giấy là hợp lệ nhưng phải nêu trong báo cáo, và làm
    **TRƯỚC khi chấm OMR trên test (Tuần 5)**. Bước 7 (nắn ảnh) không dùng nhãn rõ/mờ ⇒ kết quả Bước 7 không đổi dù sửa.
  - `ground_truth.csv` không đổi.
  - **Người dùng so giấy thật 07/10/2026: 8/8 GIỮ NGUYÊN – nhãn đúng.** Cả 2 ảnh cùng đọc lệch mức rõ/mờ so với người nhìn
    giấy ⇒ **ranh giới rõ/mờ của ngưỡng cố định 0,80 (`FILLED_MIN`) không khớp cách người phân biệt** – giới hạn của ngưỡng
    cố định, không phải lỗi nhãn. Không sửa `ground_truth.csv` / `cell_labels.csv`. 8 mục thành ca thử lớp faint/filled cho
    classifier 3 lớp (CLAUDE.md mục 7, yêu cầu Tuần 5).
  - **Sửa hiển thị `report-cuoi` (việc treo sau Bước 7)**: "quy tắc số 3" chỉ in khi n ≥ 10 (`QUY_TAC_3_N_MIN`), n nhỏ hơn
    in "–". Chạy lại -> `data/_eval/buoc7_report_cuoi_sau_sua_hien_thi.log`: so với `buoc7_report_cuoi.log`, 93/93 dòng giống
    sau khi bỏ phần quy tắc số 3; đúng 7 dòng đổi (các dòng test n = 2–4: "100%/150%/75%" -> "–"), cận trên Clopper–Pearson
    và mọi số khác không đổi. pytest 51/51. **Số liệu Bước 7 không đổi.**

### TUẦN 4 XONG (07/10/2026) – Bước 0–7
Kết quả chính: `preprocess()` (v6_api) nắn đúng **78/78 ảnh dev và 12/12 ảnh test, 0 lỗi im lặng, 0 từ chối nhầm** (trước:
`align_cu` 59/78 dev, 9/12 test); ảnh giả 111: 0 lỗi im lặng. API ổn định (CLAUDE.md mục 4b), 4 công cụ dùng `preprocess()`,
pytest 51/51. Việc treo đã xong 07/10: sửa hiển thị "quy tắc số 3" của `report-cuoi` (commit riêng, không đổi số liệu); so giấy
8 mục rõ/mờ tập test (8/8 giữ nguyên). Yêu cầu chuyển sang Tuần 5/6/7: CLAUDE.md mục 7.
