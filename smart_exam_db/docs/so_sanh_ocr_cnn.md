# So sánh CNN chữ số hiện tại với OCR và M0 (lệnh D, 27/10/2026) – CHỈ ĐO, không sửa hệ thống

Câu hỏi của giảng viên: CNN "to", sao không dùng OCR? Tài liệu này đo trên dữ liệu thật (chỉ DEV) và trả lời trung thực, kể cả khi số liệu không nghiêng về CNN.
Công cụ: `tools/so_sanh_ocr.py` (chỉ đọc mô hình sản xuất, không ghi CSDL). Số liệu thô: `data/_eval/so_sanh_ocr/` (`cnn_hien_tai.json`, `ket_qua.json`,
`du_doan_tung_chu_so.csv`, `m0_he_so.json`). Tái tạo: `python tools/so_sanh_ocr.py do-cnn` · `python tools/so_sanh_ocr.py so-sanh`.

**Trạng thái: M0 và CNN ĐÃ ĐO. Thư viện OCR CHƯA ĐO – chờ người dùng duyệt cài đặt (mọi ứng viên > 50 MB, mục 4).**

## 1. CNN hiện tại (Bước 1, `python tools/so_sanh_ocr.py do-cnn`)
| Mục | Giá trị |
|---|---|
| Kiến trúc | Conv 3×3·16 → pool → Conv 3×3·32 → pool → Dense 64 → 10 (một mô hình, không ensemble) |
| Số tham số | **105 866** (≈ 0,1 triệu; 95% nằm ở lớp Dense 1 568 → 64) |
| Dung lượng | trọng số float32 **0,40 MB**; tệp `models/ocr_cnn.json` **1,27 MB** (JSON văn bản, kèm siêu dữ liệu) |
| RAM | đỉnh lúc nạp ~5,9 MB (`tracemalloc`, chủ yếu do phân tích JSON); working set của tiến trình không đổi đo được (< 0,1 MB) |
| Phụ thuộc lúc chạy | **chỉ NumPy** (+ OpenCV để dò khung / cắt ô – đã có cho OMR); không torch, không GPU, không Internet. torch chỉ dùng lúc HUẤN LUYỆN |
| Thời gian | 1 chữ số **0,61 ms** (p95 0,80) · 9 chữ số một lô **3,5 ms** (p95 6,0) · cả phiếu (dò 9 khung + cắt + CNN) **16,3 ms** (p95 18,5; 56 ảnh dev) – nạp mô hình 81 ms một lần |
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
| Thư viện OCR | **chưa đo** | | | | | | | | |
Kiểm định cặp McNemar chính xác: CNN vs M0 trên P **p = 0,78** (27 chữ số chỉ CNN đúng, 24 chỉ M0 đúng) – **không khác biệt có ý nghĩa**; OOF người lạ p = 0,17.

**3b. Trang D – OOF 5-fold theo người viết (3 872 chữ số, tập lớn)**
| Ứng viên | Độ đúng [Wilson 95%] | Sai | Sai mà tự tin (p ≥ 0,5) | Cặp nhầm nhiều nhất |
|---|---|---|---|---|
| M0 | 92,8% [92,0–93,6] | 278 | 237 | 1→7 (24), 7→2 (18), 5→8, 9→3 |
| **CNN** | **95,8% [95,2–96,4]** | 161 | 132 | 7→8 (19), 3→9 (18), 1→7 (16) |
McNemar: 183 chữ số chỉ CNN đúng, 66 chỉ M0 đúng → **p < 0,001: CNN tốt hơn rõ** (giảm ~42% số lỗi) trên tập lớn, người lạ.

**3c. Tác động lên HỆ THỐNG (luật đối chiếu hai kênh của sản xuất, 56 ảnh / 112 trường SBD + mã đề của tập P)**
| Ứng viên | Lỗi thầm lặng mức trường (nhận mà sai) | Trường nhận tự động | Ảnh có SBD / mã đề "cần xem" (T4) |
|---|---|---|---|
| M0 | **0** | 76 / 112 | 51,8% (29/56) |
| **CNN** | **0** | 75 / 112 | **46,4%** (26/56) – khớp số đo độc lập Tuần 6 `eval_ocr.py` |
| M0 OOF / CNN OOF | 0 / 0 | 72 / 71 | 58,9% / 53,6% |
| Thư viện OCR | chưa đo | | |
Vì chữ số viết tay chỉ được NHẬN khi trùng với bubble, mọi lỗi đọc của mô hình chữ số biến thành "cần xem" chứ không thành điểm sai: **lỗi thầm lặng = 0 với cả hai**;
mô hình tốt hơn chỉ làm GIẢM số phiếu giáo viên phải xem.

## 4. Thư viện OCR – ứng viên (CHƯA CÀI, chờ duyệt)
Đã tải về (không cài) để đọc siêu dữ liệu wheel:
| Ứng viên | Thành phần | Mô hình | Ước tính trong venv RIÊNG `data/_eval/so_sanh_ocr/venv_ocr` | Hệ thống / Internet |
|---|---|---|---|---|
| **A. RapidOCR 3.10** (PaddleOCR → ONNX) | onnxruntime 1.31.1 (có bản Python 3.14, 43,6 MB giải nén) + opencv-python-headless, numpy, shapely, pyclipper, omegaconf, Pillow, requests… | PP-OCRv6 dò chữ 9,9 MB + nhận dạng 21,2 MB, đóng gói trong wheel | **~200 MB** | không cần quản trị / Internet / GPU; không torch |
| **A'. RapidOCR tối giản** | chỉ numpy + onnxruntime (+ flatbuffers, protobuf, packaging) + tệp mô hình NHẬN DẠNG PP-OCRv6 + từ điển ký tự lấy từ wheel; bỏ khâu dò chữ (ô đã cắt sẵn) | 21,2 MB | **~90 MB** | như trên |
| B. Tesseract 5 (pytesseract) | gói Python ~0 MB + **bộ cài Tesseract cho Windows** | eng.traineddata | ~70–100 MB, cài HỆ THỐNG | **cần quyền quản trị** |
Không xét: EasyOCR, TrOCR, PaddleOCR gốc (kéo theo torch / paddle, hàng trăm MB–GB).
Lưu ý trước khi đo: cả hai là OCR cho CHỮ IN / dòng chữ; nhận dạng một chữ số viết tay đơn lẻ trong ô 6×9 mm là ngoài miền huấn luyện chính của chúng; sẽ cấu hình
"chỉ chữ số" (Tesseract: `--psm 10 -c tessedit_char_whitelist=0123456789`; RapidOCR: lọc kết quả về 0–9) và thử cả ô gốc lẫn ô chuẩn hoá 28×28 phóng to, báo cái tốt hơn.

## 5. Kết luận (viết sẵn – PHẦN OCR sẽ bổ sung sau khi đo)
1. CNN của hệ thống **không lớn**: 105 866 tham số, 0,4 MB trọng số, chạy bằng NumPy thuần trên CPU, 0,6 ms một chữ số, ~16 ms cho 9 ô của một phiếu – không cần GPU, torch hay Internet.
2. Trên 504 chữ số viết tay của phiếu dev mà không mô hình nào được học, CNN (92,7%) và đường cơ sở cổ điển HOG + logistic (92,1%) **tương đương** (McNemar p = 0,78);
   trên 3 872 chữ số trang D đo theo kiểu "người viết lạ", CNN **đúng hơn rõ** (95,8% so với 92,8%, giảm ~42% lỗi, p < 0,001).
3. Ở mức hệ thống, cả hai đều cho **0 lỗi thầm lặng** nhờ cơ chế kiểm chéo hai kênh (chữ viết tay chỉ được nhận khi trùng bubble); mô hình chữ số tốt hơn chỉ giảm số phiếu
   phải xem (46% so với 52% ảnh).
4. [Chờ đo] So với thư viện OCR: …
5. Đề xuất hiện tại: **giữ CNN** làm kênh chữ viết tay; nếu OCR không đúng hơn có ý nghĩa thì chi phí ~90–200 MB phụ thuộc không đáng; nếu đúng hơn, chỉ cân nhắc
   như kênh phụ trong cơ chế kiểm chéo, không thay quy tắc "chỉ nhận khi hai kênh khớp".

## 6. Hạn chế
- Tập P nhỏ (504 chữ số, 252 cặp ảnh cùng phiếu → không hoàn toàn độc lập), 4 người viết; khoảng tin cậy ±2–3 điểm %.
- Chữ viết tay trong ô vuông 6×9 mm, chuẩn hoá về 28×28 kiểu MNIST – kết luận không áp cho chữ in hay cả dòng chữ.
- M0 trong bảng 3a học MNIST + toàn bộ D (giống CNN sản xuất), C = 10 chọn ở Tuần 6 trên val nội bộ MNIST; xác suất M0 không hiệu chỉnh nên cột "sai mà tự tin" của M0 không so trực tiếp được.
- Chỉ (sẽ) thử MỘT thư viện OCR; thời gian đo trên một máy (Windows, CPU laptop).

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
