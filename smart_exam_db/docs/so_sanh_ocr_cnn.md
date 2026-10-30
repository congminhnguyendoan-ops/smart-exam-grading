# So sánh CNN chữ số hiện tại với OCR và M0 (lệnh D, 27/10/2026) – CHỈ ĐO, không sửa hệ thống

Câu hỏi của giảng viên: CNN "to", sao không dùng OCR? Tài liệu này đo trên dữ liệu thật (chỉ DEV) và trả lời trung thực, kể cả khi số liệu không nghiêng về CNN.
Công cụ: `tools/so_sanh_ocr.py` (venv chính, chỉ đọc mô hình sản xuất, không ghi CSDL) + `tools/so_sanh_ocr_rapid.py` (CHỈ chạy trong venv RIÊNG
`data/_eval/so_sanh_ocr/venv_ocr`: numpy + onnxruntime, không cv2 / cv_engine). Số liệu thô: `data/_eval/so_sanh_ocr/` (`cnn_hien_tai.json`, `ket_qua.json`,
`du_doan_tung_chu_so.csv`, `m0_he_so.json`, `o_chu_so.npz`, `du_doan_ocr_*.csv`, `q_ocr_*.npz`, `ocr_chi_phi.json`). Tái tạo (từ `smart_exam_db\`):
```powershell
python tools/so_sanh_ocr.py do-cnn
python tools/so_sanh_ocr.py xuat-o                                                     # ô chữ số dev -> o_chu_so.npz (kiểm 28×28 trùng bộ đệm từng byte)
data\_eval\so_sanh_ocr\venv_ocr\Scripts\python.exe -I tools/so_sanh_ocr_rapid.py       # OCR A' (môi trường riêng)
python tools/so_sanh_ocr.py so-sanh                                                    # M0 + CNN + OCR, cùng tập, cùng thước đo
```

**Trạng thái (28/10/2026): ĐÃ ĐO cả 3 ứng viên – M0, CNN, OCR A' (RapidOCR tối giản: PP-OCRv6 nhận dạng + onnxruntime). Chỉ dữ liệu dev.**

## 1. CNN hiện tại (Bước 1, `python tools/so_sanh_ocr.py do-cnn`)
| Mục | Giá trị |
|---|---|
| Kiến trúc | Conv 3×3·16 → pool → Conv 3×3·32 → pool → Dense 64 → 10 (một mô hình, không ensemble) |
| Số tham số | **105 866** (≈ 0,1 triệu; 95% nằm ở lớp Dense 1 568 → 64) |
| Dung lượng | trọng số float32 **0,40 MB**; tệp `models/ocr_cnn.json` **1,27 MB** (JSON văn bản, kèm siêu dữ liệu) |
| RAM | đỉnh lúc nạp ~5,9 MB (`tracemalloc`, chủ yếu do phân tích JSON); working set tiến trình tăng **+3,1 MB** khi nạp (đo lại 28/10 – bản 27/10 ghi "< 0,1 MB" là SAI PHÉP ĐO: lời gọi Windows thất bại, luôn trả 0; đã sửa `bo_nho_tien_trinh_mb`) |
| Phụ thuộc lúc chạy | **chỉ NumPy** (+ OpenCV để dò khung / cắt ô – đã có cho OMR); không torch, không GPU, không Internet. torch chỉ dùng lúc HUẤN LUYỆN |
| Thời gian (đo lại 28/10) | 1 chữ số **0,70 ms** (p95 0,94) · 9 chữ số một lô **3,8 ms** (p95 4,8) · cả phiếu (dò 9 khung + cắt + CNN) **17,0 ms** (p95 20,2; 56 ảnh dev) – nạp 89 ms một lần (27/10: 0,61 · 3,5 · 16,3 ms – dao động của máy) |
"CNN to" theo nghĩa nào? So với mô hình ảnh thông dụng (ResNet-18 ~11 triệu tham số, ~45 MB) CNN này nhỏ hơn ~100 lần; so với M0 (3 250 hệ số, 65 KB) thì lớn hơn ~30 lần.

## 2. Tập so sánh (Bước 2) – chỉ dữ liệu DEV
Định nghĩa có sẵn `tools/huan_luyen_ocr.py tap_do` (phiếu lọc theo `cv_engine.tap_du_lieu.PHIEU_TRAIN` ngay khi đọc; bộ đệm ô cắt có phiếu val 0029–0034 → bị loại, không tính gì;
không đọc test 0035–0040, đợt 2 0101–0110).
| Tập | Nội dung | Ai đã học? | Dùng thế nào |
|---|---|---|---|
| **P** | **504 chữ số viết tay trên phiếu dev 0001–0028** (56 ảnh × 9) | **không mô hình nào** | **tập so sánh CHÍNH** |
| D | 3 872 chữ số trang D001–D010 (bỏ 128 ô không dò được khung) | **CNN sản xuất đã học toàn bộ D** | CNN sản xuất trên D chỉ báo riêng (97,9% – "đã học", KHÔNG so); so công bằng bằng **OOF 5-fold theo người viết** (mô hình học 4 người, đọc người thứ 5) cho cả CNN (bộ đệm `oof_g0_goc_2026` – đúng cấu hình sản xuất) và M0 |
Trùng lặp cần nêu: (1) người viết 1–4 của tập P cũng viết trang D → M0 và CNN sản xuất đã thấy NÉT của họ (không phải các chữ số này); số "người lạ" thật lấy từ dòng OOF.
(2) Tập P từng được dùng ở Tuần 6 Phần C để SO các cấu hình CNN (chọn cấu hình đơn giản nhất vì khác biệt không có ý nghĩa) → hơi lạc quan cho CNN.
(3) Kênh bubble (OMR) của 56 ảnh dev do mô hình OMR đã học các phiếu này → cột "hệ thống" mục 3 hơi lạc quan cho mọi ứng viên như nhau.

## 3. Kết quả (Bước 3, `python tools/so_sanh_ocr.py so-sanh`)
Độ đúng kèm khoảng tin cậy Wilson 95%. "Sai mà tự tin" = đọc sai nhưng vượt ngưỡng: với CNN là **p ≥ τ_khop 0,5** (ngưỡng thật dùng trong luật đối chiếu hai kênh) và
`cnn_chac` (p ≥ 0,9995 & lề ≥ 0,99 – chỉ báo cáo); với M0 dùng cùng mức p (xác suất M0 KHÔNG được hiệu chỉnh nhiệt độ).

**3a. Tập P – 504 chữ số chưa mô hình nào học**
| Ứng viên | Độ đúng [Wilson 95%] | Sai | Sai mà tự tin (p ≥ 0,5) | Sai + p ≥ 0,9995 | Cặp nhầm nhiều nhất | Tham số | Dung lượng | ms / chữ số · / 9 | Phụ thuộc |
|---|---|---|---|---|---|---|---|---|---|
| M0 HOG + logistic (MNIST + D) | 92,1% [89,4–94,1] | 40 | 33 (82% số sai) | 0 | 3→8 (4), 3→7, 4→0, 5→8 | 3 250 | 65 KB (JSON) | 0,18 · 0,59 | NumPy (sklearn chỉ để học) |
| **CNN sản xuất** (MNIST + D) | **92,7% [90,0–94,6]** | 37 | 20 (54% số sai) | 0 | 3→9 (5), 2→9 (5), 1→2, 0→6 | 105 866 | 0,40 MB (1,27 MB JSON) | 0,61 · 3,5 | NumPy |
| CNN, OOF người lạ | 91,9% [89,2–94,0] | 41 | 31 | 0 | 2→9 (6), 3→9 (5) | – | – | – | – |
| M0, OOF người lạ | 89,5% [86,5–91,9] | 53 | 46 | 0 | 7→2 (5), 3→7, 5→8 | – | – | – | – |
| **OCR A' – PP-OCRv6 rec, ô 28×28, ép chữ số** (biến thể chính, chọn theo D) | **98,2% [96,6–99,1]** | **9** | **6** (67% số sai) | 0 | 7→2 (3), 9→5 (2), 6→2 (2) | ~5,3 triệu | 20,3 MB ONNX + ~51 MB onnxruntime | 6,5 · 54 | onnxruntime + NumPy |
| OCR A', ô gốc ~97×62 px, ép chữ số | 97,2% [95,4–98,3] | 14 | 9 | 0 | 7→2 (4), 1→4 (3) | – | – | – | – |
| OCR A', ô 28×28, giải mã tự do rồi lọc 0–9 | 93,3% [90,7–95,1] | 34 (28 ∅) | 6 | 0 | 9→∅ (8), 1→∅ (8), 0→∅ (6) | – | – | – | – |
| OCR A', ô gốc, giải mã tự do rồi lọc 0–9 | 91,3% [88,5–93,4] | 44 (34 ∅) | 9 | 0 | 1→∅ (13), 5→∅ (8) | – | – | – | – |
Kiểm định cặp McNemar chính xác: CNN vs M0 trên P **p = 0,78** (27 chữ số chỉ CNN đúng, 24 chỉ M0 đúng) – **không khác biệt có ý nghĩa**; OOF người lạ p = 0,17.
**OCR (chính) vs CNN trên P: 33 chữ số chỉ OCR đúng, 5 chỉ CNN đúng → p < 0,001 – OCR ĐÚNG HƠN RÕ** (lỗi 37 → 9, giảm ~76%); OCR vs M0: 38 / 7, p < 0,001.
∅ = "không đọc được" (giải mã tự do ra 0 hoặc ≥ 2 chữ số – "1" thành "I"/"l", "9" thành "g", "0" thành "O"…) – tính là SAI. "Ép chữ số" = chỉ xét 10 lớp 0–9 của đầu ra
CTC (điểm = xác suất lớn nhất theo khung thời gian), tương đương cấu hình "chỉ chữ số" của OCR. Biến thể chính chọn theo **D** (OCR không học gì của D), không theo P.

**3b. Trang D – OOF 5-fold theo người viết (3 872 chữ số, tập lớn)**
| Ứng viên | Độ đúng [Wilson 95%] | Sai | Sai mà tự tin (p ≥ 0,5) | Cặp nhầm nhiều nhất |
|---|---|---|---|---|
| M0 | 92,8% [92,0–93,6] | 278 | 237 | 1→7 (24), 7→2 (18), 5→8, 9→3 |
| **CNN** | **95,8% [95,2–96,4]** | 161 | 132 | 7→8 (19), 3→9 (18), 1→7 (16) |
| **OCR A' (28×28, ép chữ số)** – không huấn luyện, D hoàn toàn "lạ" | **96,9% [96,3–97,4]** | 121 | 67 | 9→5 (25), 7→8 (20), 1→4 (15), 7→2 (13) |
| OCR A' (ô gốc, ép chữ số) | 96,7% [96,1–97,2] | 128 | 69 | 7→8 (22), 1→4 (21), 9→5 (21) |
| OCR A' (28×28 / ô gốc, lọc 0–9) | 91,6% / 90,7% | 327 / 359 (248 / 271 ∅) | 66 / 68 | 9→∅ (106 / 116) |
McNemar: 183 chữ số chỉ CNN đúng, 66 chỉ M0 đúng → **p < 0,001: CNN tốt hơn rõ** (giảm ~42% số lỗi) trên tập lớn, người lạ.
**OCR vs CNN OOF trên D: 109 chỉ OCR đúng, 69 chỉ CNN đúng → p = 0,003: OCR đúng hơn, nhưng chênh nhỏ hơn nhiều so với P** (lỗi 161 → 121, ~25%); OCR vs M0 OOF p < 0,001.
"Sai mà tự tin" cùng mức p ≥ 0,5: OCR 67 (1,7%) so với CNN 132 (3,4%); ở p ≥ 0,9995: cả hai 0.

**3c. Tác động lên HỆ THỐNG (luật đối chiếu hai kênh của sản xuất, 56 ảnh / 112 trường SBD + mã đề của tập P)**
| Ứng viên | Lỗi thầm lặng mức trường (nhận mà sai) | Trường nhận tự động | Ảnh có SBD / mã đề "cần xem" (T4) |
|---|---|---|---|
| M0 | **0** | 76 / 112 | 51,8% (29/56) |
| **CNN** | **0** | 75 / 112 | **46,4%** (26/56) – khớp số đo độc lập Tuần 6 `eval_ocr.py` |
| M0 OOF / CNN OOF | 0 / 0 | 72 / 71 | 58,9% / 53,6% |
| OCR A' (28×28, ép chữ số) – **cùng luật, τ_khop 0,5** | **0** | 77 / 112 | **53,6%** (30/56) – TỆ HƠN CNN dù đọc đúng hơn |
| OCR A' (ô gốc) | 0 | 74 / 112 | 57,1% (32/56) |
Vì chữ số viết tay chỉ được NHẬN khi trùng với bubble, mọi lỗi đọc của mô hình chữ số biến thành "cần xem" chứ không thành điểm sai: **lỗi thầm lặng = 0 với cả ba**;
mô hình tốt hơn chỉ làm GIẢM số phiếu giáo viên phải xem.

**Vì sao OCR đọc đúng hơn mà T4 lại tệ hơn? – điểm tin cậy KHÔNG hiệu chỉnh.** τ_khop 0,5 là cổng chọn cho xác suất CNN đã hiệu chỉnh nhiệt độ (T = 1,75). Điểm OCR là
xác suất thô của mô hình CTC 18 710 ký tự (một phần xác suất rơi vào ký tự giống số như "I", "l", "O", "g"), nên nhiều chữ số đọc ĐÚNG có p < 0,5:
**P: 28 chữ số đúng của OCR có p < 0,5 (CNN: 5); D: 238 (CNN OOF: 27)** → luật coi là "tin cậy thấp" → cần xem.
Chẩn đoán (KHÔNG phải đề xuất, không chọn ngưỡng theo P) – bỏ cổng tin cậy (τ_khop = 0: nhận khi chữ viết tay trùng bubble) cho CẢ BA ứng viên:
| τ_khop = 0 | Lỗi thầm lặng | Trường nhận | T4 |
|---|---|---|---|
| M0 | 0 | 77 / 112 | 50,0% |
| CNN | 0 | 79 / 112 | 42,9% |
| **OCR A'** | 0 | **103 / 112** | **16,1%** (9/56) |
Tức là T4 của CNN chủ yếu do CNN đọc SAI (không trùng bubble), còn của OCR chủ yếu do thang điểm. Nhưng cổng τ_khop có để chặn ca "thí sinh tô SAI bubble mà chữ số đọc trùng
ngẫu nhiên" – rủi ro này KHÔNG đo được trên 56 ảnh dev; mô phỏng Tuần 6 cho thấy hạ τ làm rủi ro nhận nhầm tăng ~5× (`ke_hoach_tuan6.md`, "luật mềm"). Dùng OCR đúng cách
cần: hiệu chỉnh điểm OCR trên D, chọn lại τ_khop trên D, mô phỏng tô sai bubble, rồi đánh giá trên val theo đăng ký mới – CHƯA làm.

## 4. Thư viện OCR – A' đã cài và đo (28/10/2026)
**Người dùng chọn A': RapidOCR tối giản** – chỉ tệp mô hình NHẬN DẠNG `PP-OCRv6_rec_small.onnx` lấy từ wheel `rapidocr-3.10.0` (SHA-256 `6f327246…c14884`; từ điển
18 710 ký tự nằm sẵn trong siêu dữ liệu ONNX) + `onnxruntime 1.31.1`; bỏ khâu dò chữ (ô đã cắt bằng `ocr.cat_anh` của hệ thống). Tiền xử lý viết lại bằng NumPy theo
`resize_norm_img` của PaddleOCR (chữ tối nền trắng, cao 48, giữ tỉ lệ, chuẩn hoá ±1, đệm phải tới rộng 320). Cài OFFLINE từ wheel vào venv riêng; không đụng `.venv`;
không vào git (`data/` bị `.gitignore`). Không torch, không CUDA, không cần quyền quản trị, không Internet lúc chạy.
| Mục | Giá trị |
|---|---|
| Gói cài (venv riêng) | onnxruntime 1.31.1 (47,4 MB), numpy 2.5.4 (54,5 MB – venv chính ĐÃ có), protobuf 7.36 (2,9 MB), flatbuffers + packaging (~1,4 MB), pip (12,8 MB) |
| Dung lượng | venv **121 MB** + mô hình **20,3 MB** = **~141 MB** tổng (< 150 MB ngưỡng dừng); phần THÊM so với hệ thống hiện tại (đã có numpy) ≈ **71 MB** |
| Mô hình | ~5,3 triệu tham số (ước tính tệp / 4 byte) – gấp ~50 lần CNN (105 866) |
| RAM | working set +54 MB khi nạp (54 → 108 MB). Chạy lô 64 ô khi đo hàng loạt làm bộ cấp phát onnxruntime giữ tới ~1 GB; một phiếu 9 ô không đo riêng |
| Thời gian | 1 chữ số **6,5 ms** (p95 7,2) · 9 chữ số một lô **54 ms** (p95 57) – gồm tiền xử lý NumPy + suy luận + giải mã; nạp 111 ms. onnxruntime dùng nhiều luồng nội bộ; đo trên ô gốc (ô 28×28 cùng cỡ tensor 3×48×320) |
| Phụ thuộc hệ thống | không; chỉ wheel Python (Windows x64, có bản chính thức cho Python 3.14) |

Bảng ứng viên ban đầu (27/10, để tham chiếu):
| Ứng viên | Thành phần | Mô hình | Ước tính trong venv RIÊNG `data/_eval/so_sanh_ocr/venv_ocr` | Hệ thống / Internet |
|---|---|---|---|---|
| **A. RapidOCR 3.10** (PaddleOCR → ONNX) | onnxruntime 1.31.1 (có bản Python 3.14, 43,6 MB giải nén) + opencv-python-headless, numpy, shapely, pyclipper, omegaconf, Pillow, requests… | PP-OCRv6 dò chữ 9,9 MB + nhận dạng 21,2 MB, đóng gói trong wheel | **~200 MB** | không cần quản trị / Internet / GPU; không torch |
| **A'. RapidOCR tối giản** | chỉ numpy + onnxruntime (+ flatbuffers, protobuf, packaging) + tệp mô hình NHẬN DẠNG PP-OCRv6 + từ điển ký tự lấy từ wheel; bỏ khâu dò chữ (ô đã cắt sẵn) | 21,2 MB | **~90 MB** | như trên |
| B. Tesseract 5 (pytesseract) | gói Python ~0 MB + **bộ cài Tesseract cho Windows** | eng.traineddata | ~70–100 MB, cài HỆ THỐNG | **cần quyền quản trị** |
Không xét: EasyOCR, TrOCR, PaddleOCR gốc (kéo theo torch / paddle, hàng trăm MB–GB).
Đã làm đúng như dự tính: cấu hình "chỉ chữ số" (ép 10 lớp 0–9, và lọc 0–9 sau giải mã tự do), thử cả ô gốc lẫn ô 28×28 phóng to; Tesseract không đo (cần cài hệ thống).

## 5. Kết luận (cập nhật 28/10 sau khi đo OCR)
1. CNN của hệ thống **không lớn**: 105 866 tham số, 0,4 MB trọng số, chạy bằng NumPy thuần trên CPU, 0,7 ms một chữ số, ~17 ms cho 9 ô của một phiếu – không cần GPU, torch hay Internet.
2. Trên 504 chữ số viết tay của phiếu dev, CNN (92,7%) và HOG + logistic (92,1%) **tương đương** (p = 0,78); trên 3 872 chữ số người viết lạ, CNN **đúng hơn rõ** M0 (95,8% / 92,8%, p < 0,001).
3. **Thư viện OCR (PP-OCRv6 nhận dạng, không huấn luyện thêm) ĐỌC ĐÚNG HƠN CNN**: P 98,2% so với 92,7% (p < 0,001); D 96,9% so với 95,8% (p = 0,003). Kết quả
   **không nghiêng về CNN** và được ghi nguyên trạng; chênh lớn trên P, nhỏ (~1 điểm %) trên tập lớn D.
4. Đổi lại OCR **nặng hơn rõ**: ~5,3 triệu tham số (×50), +71 MB phụ thuộc, +54 MB RAM, chậm hơn ~14 lần (54 ms so với 3,8 ms cho 9 chữ số) – vẫn nhỏ so với ~0,6 s nắn ảnh / phiếu.
5. Ở mức hệ thống, cả ba ứng viên đều **0 lỗi thầm lặng** nhờ kiểm chéo hai kênh. Thay CNN bằng OCR NGUYÊN TRẠNG (cùng luật τ_khop 0,5) lại **tăng** ảnh cần xem
   (53,6% so với 46,4%) vì điểm tin cậy OCR không hiệu chỉnh; tiềm năng (16% khi bỏ cổng tin cậy) chỉ được dùng sau khi hiệu chỉnh + chọn lại ngưỡng + mô phỏng rủi ro.
6. Đề xuất: **giữ CNN cho bản bảo vệ** (đã kiểm đầu-cuối, đã đăng ký đánh giá, không thêm phụ thuộc). Ghi OCR là **hướng cải tiến có số liệu**: thay kênh chữ viết tay bằng
   PP-OCRv6 *sau khi* hiệu chỉnh trên D, chọn lại τ_khop, mô phỏng tô sai bubble và đánh giá lại trên val theo đăng ký mới – giữ quy tắc "chỉ nhận khi hai kênh khớp".

## 5b. Trả lời giảng viên ("CNN to, sao không dùng OCR?")
1. CNN của em không to: khoảng 106 nghìn tham số, 0,4 MB, chạy bằng NumPy trên CPU, 0,7 ms một chữ số.
2. Em đã đo một thư viện OCR thật (PP-OCRv6 qua onnxruntime) trên cùng 504 chữ số viết tay của phiếu và 3 872 chữ số của người viết lạ, cùng thước đo với CNN.
3. Kết quả trung thực: OCR đọc đúng hơn – 98,2% so với 92,7% trên phiếu, 96,9% so với 95,8% trên người viết lạ, cả hai chênh lệch có ý nghĩa thống kê.
4. Nhưng OCR mới là mô hình "to": khoảng 5 triệu tham số, thêm ~71 MB thư viện, chậm hơn ~14 lần (54 ms so với 3,8 ms cho 9 chữ số của một phiếu).
5. Trong hệ thống, chữ viết tay chỉ được nhận khi trùng với bubble, nên cả CNN lẫn OCR đều 0 lần ghi nhầm SBD / mã đề; mô hình tốt hơn chỉ giảm số phiếu giáo viên phải xem.
6. Lắp OCR vào ngay lại làm tăng phiếu cần xem (54% so với 46%) vì độ tin cậy của OCR chưa được hiệu chỉnh; hiệu chỉnh tốt thì con số này có thể giảm mạnh (chẩn đoán ~16%).
7. Vì vậy bản bảo vệ giữ CNN đã kiểm định đầu-cuối; OCR là hướng cải tiến tiếp theo, có số liệu: hiệu chỉnh, chọn lại ngưỡng, kiểm rủi ro rồi đánh giá lại.

## 6. Hạn chế
- Tập P nhỏ (504 chữ số, 252 cặp ảnh cùng phiếu → không hoàn toàn độc lập), 4 người viết; khoảng tin cậy ±1–3 điểm %.
- Chữ viết tay trong ô vuông 6×9 mm, chuẩn hoá về 28×28 kiểu MNIST – kết luận không áp cho chữ in hay cả dòng chữ.
- M0 trong bảng 3a học MNIST + toàn bộ D (giống CNN sản xuất), C = 10 chọn ở Tuần 6 trên val nội bộ MNIST; xác suất M0 và điểm OCR không hiệu chỉnh nên cột "sai mà tự tin" không so trực tiếp được với CNN.
- OCR: 4 biến thể (2 đầu vào × 2 cách giải mã), chọn theo D; ô cắt dùng bộ cắt của hệ thống (lỗi cắt ô ảnh hưởng mọi ứng viên như nhau). P từng dùng ở Tuần 6 để so cấu hình CNN → nếu lệch thì có lợi cho CNN.
- Chỉ đo MỘT thư viện OCR (A'); không đo Tesseract. Thời gian đo trên một máy (Windows, CPU laptop); onnxruntime nhiều luồng, CNN NumPy.
- Chưa đo trên val / test / đợt 2 (đúng yêu cầu); "OCR đúng hơn" mới là kết luận mức dev.

## 7. Việc phụ: hai phiếu cùng SBD trong cùng kỳ thi (`tests/test_trung_sbd.py`, CSDL thật trong giao dịch ROLLBACK – 3 test đạt)
**Hành vi hiện tại**
- **Không bao giờ có hai điểm chính thức cho một thí sinh.** Phiếu A chốt trước; phiếu B (cùng SBD) dù giáo viên duyệt hết câu và xác nhận lại SBD vẫn ở `needs_review`
  với lý do `duplicate_sbd` (`service.danh_gia_phieu`). CSDL chặn thêm bằng chỉ mục duy nhất `uq_results_exam_student` – kể cả khi hai giáo viên chốt cùng lúc
  (lần chèn thứ hai lỗi `UniqueViolation` → API trả 409).
- **Bảng điểm / Excel lấy phiếu có điểm chính thức** (A); cùng loại thì phiếu mới hơn. API `GET /exams/{id}/results` có trường `sheets = 2` nhưng **màn Bảng điểm và
  tệp Excel KHÔNG hiện / không cảnh báo** có phiếu thứ hai đang chờ; phiếu B không nằm ở mục "chưa ghép được" (vì đã ghép đúng thí sinh) – chỉ thấy ở Hàng đợi duyệt.
**Rủi ro**
- Xuất Excel khi Hàng đợi còn phiếu B → bảng điểm trông "xong" nhưng còn một phiếu cùng thí sinh chưa xử lý. Nếu B mới là bài đúng (A là ảnh chụp nhầm / thí sinh khác ghi
  nhầm SBD của A) thì điểm của A được dùng mà không ai được nhắc.
- Không có thao tác "chọn phiếu này làm chính thức" – phiếu B chỉ thoát hàng đợi khi giáo viên SỬA SBD sang thí sinh khác; nếu đúng là cùng thí sinh (chụp lại) thì B kẹt mãi.
**Đề xuất (chưa làm)**
1. Bảng điểm + Excel: cột / ghi chú "có N phiếu – 1 phiếu trùng SBD đang chờ" (dùng trường `sheets` có sẵn) và cảnh báo khi xuất Excel lúc còn `duplicate_sbd`.
2. Màn duyệt phiếu B: hiện phiếu A cạnh nhau + 2 thao tác có ghi `score_audit_logs`: "B là ảnh chụp lại của A – bỏ B" (đặt B `void` / đóng mục hàng đợi) và
   "dùng B thay A" (đặt kết quả A `void`, chốt B) – không bao giờ tự động.
3. Giữ nguyên chỉ mục `uq_results_exam_student` (lớp bảo vệ cuối).
