# Kế hoạch Tuần 5 – `cv_engine/omr.py` (đọc ô trả lời, SBD, mã đề)

> Trạng thái: **ĐÃ DUYỆT (07/10/2026)** với các quyết định ở mục ★ ngay dưới. HEAD lúc lập: `09157e9`.
> Chia làm **PHẦN A** (bản mốc, xong trước báo cáo thứ 3 ngày 13/10/2026) và **PHẦN B** (sau báo cáo) – mục 7.
> Chỗ nào mục ★ khác phần thân bên dưới thì **theo mục ★**.

## ★ Quyết định của người dùng khi duyệt (07/10/2026)

| # | Quyết định |
|---|---|
| Q1 | Câu **trống chắc chắn KHÔNG "cần xem"**. Câu trống mà có ô **sát ngưỡng** (không chắc là trống) → "cần xem" – đọc nhầm vết tô thành trống là **lỗi nặng**. |
| Q2 | Tiêu chí: **lỗi nặng = 0 (bắt buộc)**; **F1 mờ ≥ 0,90 mỗi điều kiện C1–C4**; **cần xem thừa ≤ 3%**; luôn báo kèm khoảng tin cậy. |
| Q3 | Giữ **0029–0034 riêng**. Phần A chỉ dùng **7-fold trên 0001–0028**, KHÔNG chạm 0029–0034 (để Phần B). Tập test 0035–0040 tuyệt đối không đọc. |
| Q4 | Cài scikit-learn (dry-run trước), **chỉ dùng trong công cụ huấn luyện**; `omr.py` lúc chạy chỉ NumPy + JSON. `requirements.txt` ghi chú "chỉ để huấn luyện". |
| Q5 | **Sinh sẵn PNG mẫu phiếu trắng từ `generate_sheets.py`**, có cách tái tạo + SHA. `eval_omr.py` đo vị trí theo cách **KHÁC** `omr.py`. |
| Q6 | Mô hình ở `smart_exam_db/models/`, **JSON vào git**, kèm siêu dữ liệu (commit, ngày, SHA dữ liệu, fold). |
| Định vị | **Dò 2 tầng**: (1) cả khối (đáp án / SBD / mã đề) ±4 mm, **một độ dịch chung**; (2) từng hàng (từng cột với bubble) cửa sổ **< nửa khoảng cách ô (±1,5 mm)** + kiểm hàng lệch bất thường so với hàng lân cận → "cần xem". Giữ phép thử **dịch đúng 1 khoảng cách ô** (ngang và dọc). |
| Bubble | Mô hình **2 lớp** + luật an toàn (giá trị lưng chừng → "cần xem"); ghi giới hạn đã biết. Cột mờ / trống, câu 3–4 ô, rõ + mờ cùng câu: **kiểm bằng pytest dữ liệu tạo ra**. |
| Cách làm | Phần A làm một lèo A1 → A4, mỗi mốc chạy pytest (cả test cũ) rồi commit (`git commit -F`, đường dẫn cụ thể). Chỉ dừng hỏi khi (a) phải đụng 0029–0034 / test, hoặc (b) lỗi nặng > 0 không sửa được trong Phần A. Lựa chọn nhỏ: tự quyết theo hướng **an toàn hơn** (gắn "cần xem" thay vì đoán), ghi vào mục "Quyết định tự đưa ra trong Phần A". |

Hệ quả cho phần thân:
- Mục 1: **val 0029–0034 không dùng trong Phần A**; mọi số Phần A là **OOF 7-fold trên 56 ảnh train**.
- Mục 4a: thay bằng định vị 2 tầng ở trên (cửa sổ tầng 2 ±1,5 mm < nửa chu kỳ nhỏ nhất 2,9 mm).
- Mục 5: dòng "0 ô có tô" → `trong`, **không** cần xem nếu cả 4 ô "trống chắc chắn"; có ô lưng chừng → cần xem
  `tin_cay_thap`. `CHINH_SACH_CAN_XEM` mặc định **không** gồm `trong` (khớp DB hiện tại).
- Mục 4c tiêu chí ĐẠT giữ nguyên số (0 lỗi nặng; F1 faint ≥ 0,90 mỗi C; cần xem thừa ≤ 3%; 3 ca thử), giờ là tiêu chí đã chốt.

Mục tiêu: từ `KetQuaTienXuLy` (chỉ khi `ok=True`) đọc **40 câu**, **SBD 6 chữ số**, **mã đề 3 chữ số** (kênh bubble), mỗi
câu / mỗi cột kèm trạng thái **chắc chắn** hoặc **cần xem** (có lý do). Giáo viên duyệt mục "cần xem" ở Tuần 9–10.

- **Mục tiêu số 1: lỗi im lặng = 0** ở mức câu / cột – đọc sai mà không gắn "cần xem".
- **Mục tiêu số 2**: ít "cần xem" nhất có thể (sau khi đã đạt mục tiêu 1).

Không thuộc Tuần 5: đọc chữ số viết tay (CNN – Tuần 6), so SBD viết tay ↔ bubble (Tuần 6/8), ghi DB (Tuần 7).

---

## 0. Dữ liệu (số đếm trên dev 0001–0034, chỉ đọc dòng phiếu ≤ 0034 – 07/10/2026)

| | Ô đáp án (34 phiếu × 160) | × 2 ảnh | Ô bubble SBD + mã đề (34 × 90) | × 2 ảnh |
|---|---|---|---|---|
| `blank` | 4 105 | 8 210 | 2 755 | 5 510 |
| `faint` | **217 (4,0%)** | **434** | **0** | 0 |
| `filled` | 1 118 | 2 236 | 305 | 610 |

- Câu (1 360 / 2 720 lượt ảnh): rõ 1 ô 896 · mờ 1 ô 217 · trống 136 · nhiều ô 111 (**chỉ có tổ hợp 2 ô rõ**; không có 3–4 ô,
  không có rõ + mờ). Cột bubble: 305 cột có tô, **1 cột không tô** (0001 sbd6 – `06238-`).
- Mã nhãn `ground_truth.csv`: chữ hoa = rõ, chữ thường = mờ, 2 chữ = 2 ô rõ, `-` = trống; `sbd_bubble` / `exam_code_bubble`
  là chữ số được TÔ (`-` = cột không tô). `cell_labels.csv`: 6 400 dòng ô đáp án + 3 600 dòng bubble (`question` = `sbd1–6`,
  `exam_code1–3`, `option` 0–9).
- Điều kiện: mỗi phiếu chụp đúng 2 điều kiện, theo cặp C1+C2 / C2+C3 / C3+C4 / C4+C1 (dev 9/9/8/8). Bút: chì 2B 12, bi xanh
  11, bi đen 11. Mỗi ảnh dev đều có ô faint (~100–115 ô faint mỗi điều kiện – số Tuần 4 Bước 5).

## 1. Quy tắc dữ liệu

| Tập | Phiếu | Dùng để |
|---|---|---|
| **train** (`PHIEU_TRAIN`) | 0001–0028 (56 ảnh; mỗi cặp điều kiện 7 phiếu) | Học mô hình, **k-fold nhóm theo phiếu** để chọn đặc trưng / mô hình / ngưỡng tin cậy |
| **val** (`PHIEU_VAL`) | 0029–0034 (12 ảnh) | **Kiểm tra giữ lại**: không dùng khi chọn; chạy ở Bước 6 trước khi chốt (dev – được xem ảnh lỗi, nhưng mọi lần chạy lại sau khi sửa phải ghi) |
| **test** (`PHIEU_TEST`) | 0035–0040 (12 ảnh) | Đánh giá cuối **một lần**, đăng ký trước (Bước 7). **Phiên lập kế hoạch và Bước 0–6 không đọc** |

- Ranh giới lấy từ `cv_engine/tap_du_lieu.py` (`PHIEU_TRAIN/VAL/TEST`, `chan_test`), **không định nghĩa lại**. Công cụ mới gọi
  `chan_test()` trước khi đọc file; lọc dòng nhãn phiếu test ngay khi đọc CSV (như `check_labels audit`).
- **k-fold trong train: 7 fold nhóm theo phiếu, phân tầng theo cặp điều kiện** – mỗi fold 4 phiếu (1 phiếu mỗi cặp) = 8 ảnh,
  mỗi điều kiện C1–C4 xuất hiện 2 lần. Hai ảnh cùng phiếu luôn cùng fold. Gán phiếu → fold bằng seed 2026, ghi vào `split.csv`.
  Dự đoán ngoài fold (OOF) trên 56 ảnh train là cơ sở chọn mọi thứ.
- **Tại sao giữ val riêng** thay vì k-fold cả 34 phiếu: ngưỡng tin cậy chọn trên OOF rồi đo lại trên chính OOF sẽ lạc quan;
  val chưa dùng để chọn cho số "giữ lại" trung thực trước khi chạm test. (Nếu người dùng muốn k-fold cả 34 phiếu: chọn ngưỡng
  bằng k-fold lồng – xem câu hỏi mở Q3.)
- **Mô hình cuối** để chạy test: huấn luyện lại trên 0001–0034 với cấu hình + ngưỡng đã chốt (chốt trước, ghi trong đăng ký).
- Ca thử dev (CLAUDE.md mục 7): **0019 câu 24 ô C** (C3/C4), **0033 câu 4 ô C** (C1/C2), **0020 câu 33 ô C** (C1/C4) – nhãn
  `faint` đúng (đã so giấy), n 0,23–0,26 sát `MARK_MIN`. Báo dự đoán OOF của chúng ở mọi bước. 8 mục rõ/mờ của test (0036 câu
  2, 10, 13; 0037 câu 1, 15, 31; 0040 câu 5, 10) **chỉ dùng ở Bước 7**.

## 2. Định nghĩa đo (dùng chung mọi bước)

**Đơn vị đếm**: lượt (ảnh, câu) và (ảnh, cột). Mỗi phiếu có 2 ảnh, đếm riêng từng ảnh (backend chấm từng ảnh).

**Trạng thái đúng của một câu** (eval tự suy từ `ground_truth.csv`, không dùng code của `omr.py`): tập ô được tô + mức
(`trong` / `ro` / `mo` / `nhieu`). **Một cột** bubble: chữ số được tô hoặc "không tô".

Mỗi lượt câu / cột được xếp vào **một** loại:

| Loại | Nghĩa | Mong muốn |
|---|---|---|
| **đúng – chắc chắn** | `omr` không gắn cần xem, tập ô + mức đúng | càng nhiều càng tốt |
| **lỗi im lặng NẶNG** | không gắn cần xem, **tập ô đọc ra khác thật** (đáp án / chữ số sai, hoặc đọc "trống" khi có tô, hoặc ngược lại) ⇒ ghi nhầm điểm / nhầm SBD | **= 0** |
| **lỗi im lặng NHẸ** | không gắn cần xem, tập ô đúng nhưng **sai mức** mà làm mất review theo chính sách (thật `mo` → đọc `ro` chắc chắn) | báo riêng, càng ít càng tốt (điểm không sai vì `faint_counts_as_answer = true`, nhưng bỏ qua bước xem) |
| **cần xem – cần thiết** | gắn cần xem, và trạng thái thật thuộc nhóm chính sách bắt xem (mờ / nhiều ô / trống – mục 5) | không tránh được |
| **cần xem – thừa** | gắn cần xem nhưng thật là câu rõ 1 ô (hoặc cột tô rõ 1 ô) | **mục tiêu 2: giảm loại này** |

Ghi chú: thật `ro` → đọc `mo` (cần xem) là "cần xem thừa", không phải lỗi. Đọc sai nhưng có gắn cần xem = an toàn (giáo viên
sửa), vẫn đếm riêng để biết mô hình sai bao nhiêu.

**Chỉ số** (mọi bảng tách **C1–C4**, kèm thêm theo **bút**):
1. Ma trận nhầm lẫn 3×3 cấp ô (OOF), riêng ô đáp án và ô bubble (bubble chỉ có 2 lớp thật).
2. **F1 lớp `faint`** theo C1–C4 + macro-F1; precision / recall `faint`.
3. Độ đúng mức câu (tập ô + mức; và chỉ tập ô); SBD đúng cả 6 chữ số; mã đề đúng cả 3; theo cột.
4. Số lỗi im lặng nặng / nhẹ (câu, cột, và **số ảnh có ≥ 1 lỗi**).
5. Tỉ lệ cần xem (cần thiết / thừa, theo lý do); số ảnh "sạch" (0 mục cần xem thừa).
6. Thời gian `doc_phieu()` mỗi ảnh (trung vị / lớn nhất, không gồm `preprocess`).

**Khoảng tin cậy**: các câu trong cùng ảnh / phiếu không độc lập ⇒ **bootstrap theo phiếu** (rút phiếu, giữ cả 2 ảnh), 1000
lần, seed 2026, CI 95%; so hai cấu hình dùng **bootstrap ghép cặp** (cùng chỉ số rút) như Tuần 4 Bước 5. Lỗi im lặng quan sát
0 → báo **cận trên 95% Clopper–Pearson** trên số lượt (2 240 lượt câu OOF train ⇒ ≈ 0,16%; 480 lượt câu val ⇒ ≈ 0,77%; 480 lượt
câu test ⇒ ≈ 0,77%) và nêu rõ đây là cận lạc quan vì lượt không độc lập. Quy tắc số 3 chỉ khi n ≥ 10 (như `report-cuoi`).
Luôn báo **cỡ mẫu** (vd faint OOF theo điều kiện chỉ ~90 ô ⇒ F1 có CI rộng).

## 3. Đánh giá độc lập (`tools/eval_omr.py`)

Như Tuần 4: phép đo không được dùng chung code quyết định với thứ được đo.

- `eval_omr.py` **không import** luật ô→câu, ngưỡng, hàm định vị hay hàm đặc trưng của `omr.py`. Nó chỉ gọi API công khai
  (`doc_phieu`) rồi so kết quả với nhãn bằng **bộ đọc nhãn riêng** (tự phân tích mã `ground_truth.csv`; đối chiếu chéo với
  `cell_labels.csv` – hai nguồn lệch nhau thì dừng).
- **Vị trí độc lập**: eval tự đo vị trí từng hàng / khối bằng cách khác `omr.py` (vd tìm tâm viền tròn in sẵn bằng khớp vòng
  tròn / Hough trên ảnh, hoặc lưới khớp của phép 2 Tuần 4) rồi so với dịch chuyển `omr.py` báo ra – lệch > 0,5 mm ⇒ ghi "vị
  trí đáng ngờ". Bắt được ca định vị khớp nhầm chu kỳ mà nhãn tình cờ vẫn đúng.
- Kết luận "lỗi im lặng" từ máy → **xem bằng mắt mọi ca** (ảnh cắt hàng câu / khối bubble + nhãn + kết quả) trước khi ghi
  vào `data/_eval/omr/<phien_ban>/truth_*.csv` (cột `nguon` = `tu_dong` / `mat`), giống `finalize` Tuần 4. Ca nghi nhãn sai →
  người dùng so giấy; **không sửa `ground_truth.csv` khi chưa xác nhận**.
- Chỉ ghi `data/_eval/omr/`, `data/_omr/` (bảng đặc trưng đệm), `models/` (mô hình). Không ghi `data/raw*`.
- Dữ liệu huấn luyện / mô hình **chỉ đọc nhãn train** của fold đang học – kiểm bằng phép thử: xáo nhãn phiếu ngoài fold → dự
  đoán của fold không đổi từng bit.

## 4. Đặc trưng và mô hình

### 4a. Định vị (bắt buộc – yêu cầu Tuần 4)
- Dò lại **từng hàng câu** và **từng khối SBD / mã đề** trong **±4 mm** quanh toạ độ `layout.json`, bằng khớp mẫu với phiếu
  trắng render 300 DPI (cách của `check_labels.register`). Lý do: ảnh nắn đúng vẫn lệch tới 2,06 mm (0035_C3), 2,31 mm
  (0030_C3); 0014_C2 giấy cong sai 2 hàng ở toạ độ cố định.
- **Chống khớp nhầm chu kỳ** (rủi ro thật): ô cách 7 mm ngang (nửa chu kỳ 3,5 mm < 4 mm), bubble chữ số 5,8 mm dọc (nửa chu kỳ
  2,9 mm < 4 mm). Cách chống: (i) khung khớp chứa phần **không lặp** (số câu in sẵn; khối SBD gồm cả ô viết tay + tiêu đề, khớp
  **cả khối** chứ không từng cột); (ii) đỉnh khớp phải duy nhất (đỉnh 2 ở xa ≥ chu kỳ phải thấp hơn rõ); (iii) dịch chuyển phải
  trơn giữa các hàng kề nhau (giấy cong là trơn) – hàng lệch bất thường hoặc khớp yếu ⇒ câu đó **cần xem, lý do `vi_tri`**,
  không đoán.
- Mẫu phiếu trắng: render `phieu_trang.pdf` một lần (PyMuPDF, đã có) và đệm trong bộ nhớ – xem câu hỏi mở Q5.

### 4b. Đặc trưng mỗi ô (tính sau định vị; **không dùng nhãn**)
| Nhóm | Đặc trưng | Vì sao |
|---|---|---|
| Tương đối quanh ô | `ld` = `local_darkness` (lõi 0,75r so vành giấy 1,15–1,45r) | gần như bất biến với bóng; Tuần 4: tách faint/blank 100% hàng |
| Tương đối trong hàng | `ld − min(hàng)`; hạng trong hàng; chênh với ô kế tiếp | ô trống in sẵn viền + chữ A–D (~0,3) – so trong hàng khử phần này |
| Tương đối trong ảnh | `(ld − min hàng) / S_anh`, `S_anh` = trung vị độ chênh của các hàng nổi bật nhất trên ảnh (**không dùng nhãn** – khác `check_labels`, nơi S lấy theo nhãn "rõ") | thang theo ảnh (bút chì nhạt vs bi đen; C2 tối) – chính là cái phân rõ/mờ |
| Tuyệt đối | `1 − lõi/255` trên `anh_chuan_hoa` (và `anh_nan` cho thí nghiệm) | Tuần 4 B5: chuẩn hoá giúp đúng ở đặc trưng này |
| Kết cấu | độ lệch chuẩn lõi, tỉ lệ điểm tối trong lõi, độ phủ (bao nhiêu % lõi tối hơn vành) | tô mờ thường loang / không phủ kín; bi xanh nhạt hơn trên ảnh xám |
| Ngữ cảnh | mức giấy vành, chất lượng khớp của hàng | để mô hình "biết" khi nào nên kém tự tin |

Bubble SBD / mã đề: cùng hàm, bán kính 26 px (ô đáp án 29,5); "trong hàng" thay bằng "trong cột 10 ô" (nền = trung vị cột).

### 4c. Mô hình – mốc đơn giản trước
- **M0 (số "trước", không học)**: ngưỡng cố định của audit `MARK_MIN 0,25 / FILLED_MIN 0,80` trên thang n, nhưng với `S_anh`
  không dùng nhãn. Chỉ để có số so sánh – cho thấy giới hạn ngưỡng cố định (3 ca thử dev).
- **M1 (mốc)**: **hồi quy logistic đa lớp** trên ~6–10 đặc trưng chuẩn hoá (z-score học trên fold train), `class_weight`
  cân bằng (faint 4%), C chọn trong {0,1; 1; 10} bằng k-fold. Hai mô hình: **ô đáp án 3 lớp** và **bubble 2 lớp** (dev không có
  bubble mờ – xem rủi ro R3). Lưu hệ số dưới dạng **JSON** (không pickle) ⇒ suy luận chỉ cần NumPy, không phụ thuộc phiên bản
  scikit-learn.
- **Chỉ khi M1 không đạt** mới thử, theo thứ tự (mỗi lần một bước): M2 = thêm đặc trưng / tương tác bậc 2 cho logistic → M3 =
  gradient boosting nhỏ hoặc SVM RBF trên cùng đặc trưng → M4 = CNN nhỏ trên ảnh cắt 32×32 (Kaggle/CPU, như kế hoạch gốc).
- **Tiêu chí ĐẠT của một mô hình (chốt trước, đo trên OOF train sau khi áp luật mục 5)**:
  1. Lỗi im lặng **nặng = 0** (câu và cột) ở mọi điều kiện.
  2. **F1 `faint` ≥ 0,90 ở mọi điều kiện C1–C4** và không thấp hơn M0 ở điều kiện nào (ghép cặp, CI).
  3. **Cần xem thừa ≤ 3%** số lượt câu rõ 1 ô (và ≤ 3% cột).
  4. Ca thử 0019:24, 0033:4, 0020:33: ô C đọc **có tô** (faint hoặc filled) ở cả 2 ảnh, hoặc cần xem – không được "trống chắc
     chắn".
- **Chọn giữa các mô hình cùng đạt**: maximin F1 `faint` theo điều kiện, rồi tỉ lệ cần xem thừa; chênh nằm trong CI ghép cặp
  = **hoà → chọn mô hình đơn giản hơn**. Không mô hình nào đạt → báo trung thực, người dùng quyết (không tự nới tiêu chí).
- Con số 0,90 và 3% là **đề xuất** – người dùng chốt ở lúc duyệt (câu hỏi mở Q2). Lưu ý trần: rõ/mờ vốn mơ hồ với chính người
  gán (Tuần 4: audit nhóm B 45 mục dev; 8/8 mục test người giữ nhãn dù ngưỡng đọc khác).

### 4d. `anh_nan` hay `anh_chuan_hoa` (yêu cầu Tuần 4)
Cùng M1, cùng fold, chỉ đổi nguồn ảnh tính đặc trưng ⇒ so **F1 `faint` theo C1–C4** (bootstrap ghép cặp). Quy tắc: chọn
`anh_chuan_hoa` nếu maximin F1 faint cao hơn ngoài CI và không điều kiện nào thấp hơn ngoài CI; **hoà → `anh_nan`** (ít phụ
thuộc hơn: không qua `normalize`). Xem riêng 0032_C4 câu 21–30 (mép bóng sắc, Tuần 4 B5). Đặc trưng `ld` gần như như nhau trên
hai ảnh; khác biệt chủ yếu ở đặc trưng tuyệt đối.

## 5. Luật ô → câu / cột và "cần xem"

Mỗi ô có xác suất `p(blank), p(faint), p(filled)`. Ô **quyết được** khi `max p ≥ τ_o`; ô "có tô" = faint hoặc filled.
Ngưỡng `τ_o` (và `τ` cột) chọn trên OOF train: **giá trị nhỏ nhất cho 0 lỗi im lặng nặng, cộng biên an toàn** (vd lấy ngưỡng
của fold tệ nhất), rồi kiểm trên val.

**Câu** (xét theo thứ tự, lý do có thể cộng dồn):

| Điều kiện | `trang_thai` | `dap_an` | Cần xem? | Lý do |
|---|---|---|---|---|
| định vị hàng không tin cậy | theo ô | theo ô | **có** | `vi_tri` |
| có ô không quyết được | theo dự đoán tốt nhất | theo dự đoán tốt nhất | **có** | `tin_cay_thap` |
| 0 ô có tô | `trong` | `''` | theo chính sách (mặc định **có**) | `khong_o_nao` |
| đúng 1 ô, filled | `ro` | ô đó | **không** | – |
| đúng 1 ô, faint | `mo` | ô đó | **có** | `o_mo` |
| ≥ 2 ô có tô (rõ hay mờ) | `nhieu` | các ô, vd `AC` | **có** | `nhieu_o` |

- `do_tin_cay` câu = **min** trên 4 ô của `max p` (ô yếu nhất quyết định); `xac_suat` lưu đủ cho DB (`option_probs`).
- Ánh xạ DB `bubble_state`: `trong→blank`, `ro→filled`, `mo→faint`, `nhieu→multiple`; `selected_options = dap_an`. Phù hợp
  `fn_process_sheet` hiện tại (faint ⇒ `low_omr_confidence`, nhiều ô ⇒ `multiple_marks`).
- **Chính sách cho `trong`**: yêu cầu của người dùng liệt kê "không ô nào" là cần xem; DB hiện **không** đưa câu trống vào review.
  Đề xuất để thành **tham số** `CHINH_SACH_CAN_XEM` (mặc định gồm `trong`) và báo tỉ lệ cần xem cả hai cách – Q1.

**Cột SBD / mã đề** (10 ô):
| Điều kiện | `chu_so` | Cần xem? | Lý do |
|---|---|---|---|
| định vị khối không tin cậy | dự đoán tốt nhất | **có** | `vi_tri` |
| có ô không quyết được | dự đoán tốt nhất | **có** | `tin_cay_thap` |
| đúng 1 ô có tô | chữ số đó | không | – |
| 0 ô | `?` | **có** | `khong_o_nao` |
| ≥ 2 ô | `?` | **có** | `nhieu_o` |

`sbd` = chuỗi 6 ký tự (`?` ở cột cần xem chưa quyết), `sbd_can_xem` = có cột nào cần xem. **Ô mờ ở bubble**: dev không có
mẫu ⇒ mô hình bubble 2 lớp; ô có `p(có tô)` lưng chừng sẽ rơi vào `tin_cay_thap` (an toàn). Đối chiếu với SBD viết tay là việc
Tuần 6/8.

**Phiếu**: `can_xem` = có ≥ 1 câu / cột cần xem. Kèm thống kê theo lý do để backend chọn `review_reason`.

## 6. API đề xuất (`cv_engine/omr.py`, ổn định cho Tuần 7+)

```python
from cv_engine.preprocessing import preprocess, nap_layout
from cv_engine.omr import doc_phieu, nap_mo_hinh, MA_LY_DO_OMR

layout = nap_layout("phieu")
mo_hinh = nap_mo_hinh()                       # models/omr_<phien_ban>.json – nạp 1 lần khi khởi động backend
kq = preprocess("data/raw/0001_C1.jpg", layout)
if kq.ok:
    omr = doc_phieu(kq, layout, mo_hinh)       # ValueError nếu kq.ok = False (không chấm ảnh bị từ chối)
    omr.cau[0].dap_an, omr.cau[0].trang_thai, omr.cau[0].can_xem, omr.cau[0].ly_do
    omr.sbd, omr.sbd_can_xem, omr.ma_de, omr.ma_de_can_xem
```

```python
@dataclass(frozen=True)
class KetQuaCau:
    cau: int                              # 1..40
    trang_thai: str                       # 'trong' | 'ro' | 'mo' | 'nhieu'
    dap_an: str                           # '' | 'A' | 'AC' (theo thứ tự A–D) = selected_options
    xac_suat: dict[str, dict[str, float]] # {'A': {'blank': .97, 'faint': .02, 'filled': .01}, ...}
    do_tin_cay: float                     # 0..1
    can_xem: bool
    ly_do: tuple[str, ...]                # mã trong MA_LY_DO_OMR, () khi chắc chắn

@dataclass(frozen=True)
class KetQuaCot:
    truong: str                           # 'sbd' | 'ma_de'
    vi_tri: int                           # 1..6 / 1..3
    chu_so: str                           # '0'..'9' hoặc '?'
    xac_suat_to: tuple[float, ...]        # 10 giá trị p(có tô) cho ô 0..9
    do_tin_cay: float
    can_xem: bool
    ly_do: tuple[str, ...]

@dataclass(frozen=True)
class KetQuaOMR:
    cau: tuple[KetQuaCau, ...]            # 40
    sbd: str                              # 6 ký tự, '?' ở cột chưa quyết
    sbd_cot: tuple[KetQuaCot, ...]
    ma_de: str                            # 3 ký tự
    ma_de_cot: tuple[KetQuaCot, ...]
    can_xem: bool                         # có ≥ 1 câu / cột cần xem
    sbd_can_xem: bool
    ma_de_can_xem: bool
    dich_chuyen_mm: dict[str, tuple[float, float]]   # 'q1'..'q40', 'sbd', 'ma_de' -> (dx, dy) – để gỡ lỗi / xem lại
    nguon_anh: str                        # 'anh_nan' | 'anh_chuan_hoa'
    phien_ban_mo_hinh: str                # vd 'omr_m1_20261010' -> ml_models
    thoi_gian_ms: float

MA_LY_DO_OMR = {'o_mo': ..., 'nhieu_o': ..., 'khong_o_nao': ..., 'tin_cay_thap': ..., 'vi_tri': ...}  # mã -> câu cho giáo viên
```
- Hàm phụ công khai (cho công cụ / test): `dinh_vi(anh, layout) -> dich_chuyen`, `dac_trung_o(anh, layout, dich_chuyen)`,
  `ap_luat_cau(xac_suat)`. Lỗi lập trình **vẫn ném ra** (như `preprocess`).
- Không ghi file, không đọc nhãn, không phụ thuộc scikit-learn khi suy luận.

## 7★. PHẦN A / PHẦN B (chốt khi duyệt 07/10/2026 – thay thứ tự Bước 0–7 bên dưới)

**PHẦN A – bản mốc, trước báo cáo thứ 3 (13/10/2026)**. Chỉ dùng 56 ảnh train 0001–0028, 7-fold theo phiếu. Làm một lèo,
mỗi mốc: pytest (cả test cũ) → commit.

| Mốc | Việc | Xong khi | Commit |
|---|---|---|---|
| A0 | Ghi quyết định vào kế hoạch này, chia Phần A/B, mục Nợ kỹ thuật | tài liệu có | COMMIT 1 (chỉ tài liệu) |
| A1 | PNG mẫu phiếu trắng (`generate_sheets.py`, SHA); `dinh_vi()` 2 tầng (Bước 2 bên dưới) + cờ `vi_tri`; `split.csv` (Bước 0); phép thử dịch đúng 1 khoảng cách ô ngang 7 mm / dọc 11 mm / bubble 5,8 mm (+ 2 / 3,5 / 4 mm) trên ảnh train; **0014_C2 (giấy cong) định vị đúng** | mọi ca dịch giả: đúng hoặc gắn `vi_tri`, 0 khớp nhầm không cờ; 0014_C2 đúng mọi hàng; pytest đạt | COMMIT 2 |
| A2 | Đặc trưng (Bước 3) + M0 (ngưỡng cố định, số "trước") + M1 (logistic, sklearn) trên 7-fold; so `anh_nan` vs `anh_chuan_hoa` ở mức đơn giản (F1 faint theo C1–C4, CI ghép cặp), chọn một, ghi lý do | bảng so sánh + lựa chọn ghi ở đây | COMMIT 3 |
| A3 | Luật ô → câu / cột + "cần xem" (mục 5 + ★Q1); API `doc_phieu(kq, layout, mo_hinh) -> KetQuaOMR` (mục 6); mô hình JSON vào `models/` (+ siêu dữ liệu); pytest cho ca luật hiếm (cột mờ / trống, 3–4 ô, rõ + mờ, ô lưng chừng) | pytest đạt | COMMIT 4 |
| A4 | `tools/eval_omr.py` độc lập (mục 3): bảng M0 vs M1 theo C1–C4 (ma trận 3 lớp, F1 faint + CI, độ đúng câu / SBD / mã đề, lỗi nặng / nhẹ, cần xem cần thiết / thừa, thời gian / phiếu); 3 ca thử; HTML ca lỗi / cần xem (ảnh cắt + nhãn) để người dùng xem bằng mắt SAU; hồi quy Tuần 4 không đổi; CLAUDE.md (API omr, tiến độ) | số liệu tái tạo bằng một lệnh | COMMIT 5 |

**PHẦN B – sau báo cáo 13/10**:
- B1: người dùng xem HTML Phần A bằng mắt; ca nghi nhãn sai → so giấy (không tự sửa `ground_truth.csv`).
- B2: nếu M1 không đạt tiêu chí ★Q2 → M2 → M3 → M4 (mục 4c), mỗi bước một dừng; chọn `anh_nan` / `anh_chuan_hoa` kỹ (đủ
  bootstrap, xem 0032_C4 mép bóng, theo bút); trả các khoản Nợ kỹ thuật (mục 9).
- B3: **kiểm tra cuối trên val 0029–0034** (lần "giữ lại", Bước 6 bên dưới).
- B4: **đăng ký trước + đánh giá test 0035–0040 một lần + xem mù** (Bước 7 bên dưới), 8 mục rõ/mờ của test.

## 7. Các bước (thiết kế chi tiết – thứ tự thực hiện theo 7★)

Quy ước như Tuần 4: số liệu ghi vào mục "Kết quả"; mỗi số tái tạo được bằng một lệnh. Phần A: không dừng giữa các mốc (★);
Phần B: mỗi bước có dừng chờ người dùng.

### Bước 0 – Chuẩn bị + `split.csv`
- **Việc**: kế hoạch này; cài `scikit-learn` (chỉ để huấn luyện – `pip install --dry-run` 07/10: scikit-learn 1.9.1, scipy
  1.18.1, joblib, threadpoolctl, narwhals, cloudpickle; có bánh xe cho Python 3.14) – **hỏi người dùng trước khi cài**; thêm vào
  `requirements.txt` (ghi "chỉ để huấn luyện"). `tools/tao_split.py` → `data/split.csv` (`anh, phieu, dieu_kien, but, tap,
  fold`) từ `tap_du_lieu` + `ground_truth.csv` (chỉ cột `conditions`, `pen` của phiếu dev); hàng test chỉ ghi tên, `fold` trống.
- **Cách đo**: không phiếu nào ở 2 tập / 2 fold; 2 ảnh cùng phiếu cùng fold; mỗi fold 4 phiếu, mỗi điều kiện 2 ảnh; tạo lại
  với seed 2026 → file giống từng byte; pytest cho các ràng buộc này.
- **Xong khi**: người dùng duyệt kế hoạch + `split.csv`. **Dừng.**

### Bước 1 – Công cụ đánh giá + số "trước" (M0)
- **Việc**: `tools/eval_omr.py` (`run`, `finalize`, `report`; `--split train_oof|val|test`, test cần `--xac-nhan-test` và
  bị chặn tới Bước 7) với bộ đọc nhãn độc lập; HTML xem bằng mắt các ca lỗi. Khung `omr.py` tối thiểu + **M0** (định vị tạm
  bằng toạ độ cố định *và* bằng dò lại, để thấy tác dụng của dò lại).
- **Cách đo**: bảng mục 2 cho M0 trên 56 ảnh train (M0 không học nên không cần fold). Tự kiểm của eval: đưa vào kết quả giả
  (= nhãn) → 0 lỗi; đổi 1 đáp án → đúng 1 lỗi im lặng nặng; đổi rõ→mờ có gắn cần xem → 0 lỗi; bộ đọc nhãn khớp `cell_labels.csv`
  100%.
- **Xong khi**: số M0 tái tạo bằng một lệnh; 3 ca thử dev được báo; tự kiểm đạt. **Dừng.**

### Bước 2 – Định vị `dinh_vi()`
- **Việc**: dò lại hàng câu / khối bubble ±4 mm + 3 lớp chống khớp nhầm (mục 4a) + cờ `vi_tri`.
- **Cách đo**: (a) so với vị trí đo độc lập của eval trên 68 ảnh dev (train + val – định vị không học từ nhãn, nên dùng cả hai
  được): |Δ| ≤ 0,5 mm hoặc bị cờ; (b) ảnh dịch giả từ ảnh dev đúng: 0,5 / 2 / 3,5 / 4 mm, đúng 7 mm ngang, 5,8 mm dọc, 11 mm dọc,
  vùng cong cục bộ – mọi ca hoặc khớp đúng hoặc gắn `vi_tri`, **0 ca khớp nhầm mà không cờ**; (c) tách theo nhãn bằng `ld`:
  100% hàng như Tuần 4; (d) 0014_C2, 0030_C3, ảnh C3; (e) thời gian.
- **Xong khi**: (a)(b) đạt, số hàng gắn `vi_tri` trên ảnh thật dev được báo (mong đợi ≈ 0). **Dừng.**

### Bước 3 – Đặc trưng + bảng đệm
- **Việc**: `dac_trung_o()` (mục 4b) cho cả `anh_nan` và `anh_chuan_hoa`; `S_anh` không dùng nhãn. Bảng đặc trưng 68 ảnh dev →
  `data/_omr/dac_trung_<nguon>.csv` (đệm để huấn luyện nhanh; có SHA ảnh + phiên bản code để biết khi phải tính lại).
- **Cách đo**: phép thử không dùng nhãn (xáo nhãn → bảng giống từng byte); phân bố từng đặc trưng theo lớp × C1–C4 (bảng p1/p50/p99,
  AUC đơn biến faint/blank, faint/filled); so `S_anh` với S theo nhãn của audit (tương quan, lệch lớn nhất).
- **Xong khi**: bảng đủ 68 ảnh × 250 ô; báo đặc trưng nào tách tốt faint/filled. **Dừng.**

### Bước 4 – Mốc M1 + chọn nguồn ảnh
- **Việc**: logistic 3 lớp (ô đáp án) + 2 lớp (bubble), 7 fold OOF trên train, cho cả hai nguồn ảnh.
- **Cách đo**: ma trận nhầm lẫn 3×3 + F1 faint theo C1–C4 (CI ghép cặp) cho `anh_nan` vs `anh_chuan_hoa`; hệ số mô hình (đặc
  trưng nào quan trọng); 3 ca thử dev.
- **Xong khi**: người dùng chọn nguồn ảnh theo quy tắc mục 4d. **Dừng.**

### Bước 5 – Luật câu/cột + ngưỡng tin cậy; (nếu cần) mô hình phức tạp hơn
- **Việc**: `ap_luat_cau` / luật cột (mục 5); chọn `τ_o`, `τ` cột trên OOF (ngưỡng nhỏ nhất cho 0 lỗi nặng + biên); đo đủ bảng
  mục 2. Đối chiếu tiêu chí ĐẠT (mục 4c). Không đạt → M2, M3, M4 lần lượt, mỗi lần một dừng.
- **Cách đo**: bảng mục 2 (OOF train); đường cong "tỉ lệ cần xem thừa ↔ τ_o"; xem bằng mắt mọi lượt sai (kể cả sai có cần xem).
- **Xong khi**: một mô hình đạt cả 4 tiêu chí (hoặc báo trung thực không mô hình nào đạt); người dùng duyệt. **Dừng.**

### Bước 6 – API, kiểm tra giữ lại trên val, kiểm thử
- **Việc**: hoàn thiện API mục 6, docstring tiếng Việt, `MA_LY_DO_OMR`; huấn luyện trên **train** → chạy **val 0029–0034** (lần
  "giữ lại"); pytest (luật câu/cột trên xác suất giả – mọi hàng của bảng mục 5; định vị trên ảnh dịch giả; 3 ca thử dev; API
  ném lỗi khi `ok=False`; không đọc test); đo thời gian; (tuỳ người dùng) công cụ xem kết quả OMR dạng HTML cho 1 ảnh.
- **Cách đo**: bảng mục 2 trên val (12 ảnh, 480 lượt câu); so với OOF train.
- **Xong khi**: val 0 lỗi im lặng nặng (nếu có: phân tích, sửa, **ghi lại cả lần trượt**); pytest đạt; CLAUDE.md cập nhật. **Dừng.**

### Bước 7 – Đăng ký trước + đánh giá cuối trên test (một lần)
- **Đăng ký trước** (commit riêng, trước khi chạy): commit code cố định, SHA mô hình JSON (huấn luyện lại trên 0001–0034, cấu
  hình + ngưỡng của Bước 5–6), tiêu chí ĐẠT = **0 lỗi im lặng nặng ở mức câu và cột trên 12 ảnh test**; báo kèm lỗi nhẹ, tỉ lệ
  cần xem, F1 faint theo điều kiện, CP cận trên; cách xem bằng mắt mọi ca máy kết luận lỗi.
- **Việc**: `eval_omr.py run --split test --xac-nhan-test` **một lần** (tự chặn chạy lại), `finalize`, `report`; báo riêng
  **8 mục rõ/mờ** của test (dự đoán so với nhãn người – minh hoạ giới hạn của ngưỡng cố định so với classifier).
- **Nếu có lỗi**: ghi nguyên trạng, phân tích, sửa ở phiên bản sau và chỉ đánh giá lại trên dev. Không chạy lại test.
- **Xong khi**: số liệu tái tạo bằng một lệnh, đưa vào báo cáo; TUẦN 5 XONG.

## 8. Rủi ro / câu hỏi mở

**Rủi ro**
- **R1 – Mất cân bằng + cỡ mẫu nhỏ**: faint 4% (434 lượt ô dev; OOF train 366 lượt, ~90 mỗi điều kiện) ⇒ F1 faint theo điều kiện
  có CI rộng (vài ô sai = vài điểm %). Xử lý: `class_weight`, báo CI + cỡ mẫu, không kết luận khác biệt nhỏ.
- **R2 – Rõ/mờ mơ hồ với chính người gán**: 45 mục nhóm B dev chưa đối chiếu; 8/8 mục test người giữ nhãn dù ngưỡng đọc ngược ⇒
  trần F1 faint < 1 và nhãn có nhiễu. Vì vậy tách lỗi "nhẹ" khỏi "nặng"; nhầm faint↔filled không làm sai điểm.
- **R3 – Bubble không có mẫu mờ, chỉ 2 lượt cột không tô** (0001 sbd6 × 2 ảnh) ⇒ không đo được trực tiếp "cột mờ" / "cột trống";
  chỉ đo gián tiếp qua 5 510 lượt ô bubble trống. Tô mờ bubble trong thực tế sẽ dựa vào cờ `tin_cay_thap` – cần nêu trong báo cáo.
- **R4 – Tổ hợp chưa thấy**: không có 3–4 ô, không có rõ + mờ cùng câu ⇒ luật xử lý được (≥ 2 ô → `nhieu`) nhưng không đo được
  trên ảnh thật; kiểm bằng pytest trên xác suất giả.
- **R5 – Khớp nhầm chu kỳ khi dò ±4 mm** (mục 4a): nửa chu kỳ ngang 3,5 mm và bubble dọc 2,9 mm đều < 4 mm. Đây là đường dẫn
  thẳng tới lỗi im lặng nặng (cả hàng lệch một ô) ⇒ Bước 2 có phép thử dịch đúng 1 chu kỳ.
- **R6 – Ngưỡng tin cậy chọn trên OOF bị lạc quan** ⇒ biên an toàn + val giữ lại; lỗi im lặng 0/2 240 vẫn chỉ cho cận trên ~0,16%
  (thực tế rộng hơn vì lượt không độc lập).
- **R7 – Tải review rất cao theo chính sách**: trên dev, câu mờ + nhiều ô + trống = 34% số câu (bộ dữ liệu cố tình nhiều ca hiếm);
  gần như **mọi phiếu** sẽ có ≥ 1 câu cần xem. Phiếu thật ít ca này hơn, nhưng `fn_process_sheet` gửi cả phiếu vào review khi có 1
  câu faint ⇒ cần bàn cách review theo câu ở Tuần 9–10.
- **R8 – Bút**: bi xanh trên ảnh xám nhạt hơn ⇒ báo thêm theo bút; nếu một bút kém hẳn thì thêm đặc trưng, không thêm mô hình.
- **R9 – Ngoài phạm vi dữ liệu**: tẩy xoá, gạch chéo, tô ra ngoài ô, phiếu bẩn – không có mẫu; nêu là giới hạn.
- **R10 – Phụ thuộc**: scikit-learn chỉ để huấn luyện; mô hình JSON ⇒ backend chỉ cần NumPy/OpenCV.

**Câu hỏi mở (ĐÃ QUYẾT 07/10/2026 – xem mục ★; giữ nguyên văn để đối chiếu)**
- **Q1**: Câu **trống** có tính "cần xem" không? (Yêu cầu liệt kê "không ô nào"; DB hiện không review câu trống.) Đề xuất: tham
  số, mặc định CÓ cho Tuần 5, báo tỉ lệ cả hai cách.
- **Q2**: Duyệt tiêu chí ĐẠT: F1 faint ≥ 0,90 mỗi điều kiện, cần xem thừa ≤ 3%, và định nghĩa lỗi im lặng nặng / nhẹ (mục 2).
- **Q3**: Giữ val 0029–0034 làm kiểm tra giữ lại (đề xuất), hay k-fold cả 34 phiếu với chọn ngưỡng lồng?
- **Q4**: Cho phép cài scikit-learn vào `.venv` gốc?
- **Q5**: Mẫu phiếu trắng cho định vị: render `phieu_trang.pdf` lúc nạp (cần PyMuPDF ở backend), hay sinh sẵn một PNG
  `answer_sheet/output/phieu_trang_300dpi.png` từ `generate_sheets.py` (đổi layout = sinh lại cùng các file khác)? Đề xuất: PNG
  sinh từ `generate_sheets.py` – giữ nguyên tắc "mọi thứ sinh từ `sheet_layout.py`".
- **Q6**: Thư mục mô hình: `smart_exam_db/models/` (theo `HUONG_DAN.md` Phần C, chưa tạo) – có đưa file JSON mô hình vào git
  không (nhỏ, vài KB; không chứa ảnh)?

## 9. NỢ KỸ THUẬT (chỗ làm tạm ở Phần A – trả ở Phần B hoặc ghi là giới hạn)

Cập nhật dần trong khi làm Phần A; mỗi khoản: chỗ làm tạm → vì sao → trả thế nào.

1. **Ngưỡng tin cậy chọn và đo trên cùng OOF** → số lỗi nặng / cần xem thừa của Phần A lạc quan → Phần B: kiểm trên val
   0029–0034 (giữ lại), rồi test.
2. **Siêu tham số logistic cố định** (không dò C bằng k-fold lồng) → tránh chọn trên OOF rồi báo trên chính OOF → Phần B: dò lồng
   nếu M1 không đạt.
3. **So `anh_nan` / `anh_chuan_hoa` mức đơn giản** (một mô hình M1, bootstrap theo phiếu trên 28 phiếu) → Phần B: so kỹ (theo bút,
   0032_C4 mép bóng, nhiều cấu hình).
4. **Bubble 2 lớp không có mẫu mờ thật, chỉ 2 lượt cột không tô** → luật an toàn + pytest dữ liệu tạo ra; không có số đo thật cho
   cột mờ / trống → giới hạn đã biết trong báo cáo.
5. **Câu 3–4 ô, rõ + mờ cùng câu**: chỉ có pytest dữ liệu tạo ra (xác suất giả), không có ảnh thật.
6. **Ngưỡng định vị** (điểm khớp, độ duy nhất đỉnh, hàng lệch so với lân cận) chọn trên 56 ảnh train + ảnh dịch giả → Phần B
   kiểm trên val.
7. **Mô hình cuối cho Phần A huấn luyện trên 0001–0028** (chưa gộp 0029–0034) → Phần B quyết huấn luyện lại trên 0001–0034
   trước test (đăng ký trước).
8. **Phiếu gần như bỏ trống** (thang `S_anh` theo ảnh không dùng nhãn có sàn) – không có ảnh thật → pytest dữ liệu tạo ra; Phần B
   xem lại.

## 10. KẾT QUẢ PHẦN A

### A1 – định vị 2 tầng (07/10/2026)
- **PNG mẫu**: `answer_sheet/generate_sheets.py --chi-mau-png` → `answer_sheet/output/phieu_trang_300dpi.png` (+ `.json`: SHA-256
  điểm ảnh `a8ac9f44…0d42`, PyMuPDF 1.28.2). Render từ `phieu_trang.pdf` hiện có (không ghi lại PDF); chạy 2 lần → cùng SHA;
  giống từng điểm ảnh `check_layout.render_pdf_page` (cắt 2481 → 2480 px). `.gitignore` thêm ngoại lệ cho đúng file PNG này.
  `omr.nap_mau()` kiểm SHA mỗi lần nạp.
- **`data/split.csv`** (`tools/tao_split.py`, `--kiem` so từng byte): train 56 ảnh (7 fold × 4 phiếu × 2 ảnh, mỗi fold mỗi điều
  kiện 2 ảnh), val 12, test 12 (chỉ tên file; cột `but` trống – không đọc nhãn test).
- **`omr.dinh_vi()`**: tầng 1 khối ±4 mm ở 75 DPI + kiểm đỉnh duy nhất trên ±14 mm; tầng 2 hàng / cột ±1,5 mm ở 300 DPI,
  **bám theo lân cận** (xem Quyết định tự đưa ra #1); cờ: khối khớp yếu / đỉnh không duy nhất / chạm biên; hàng khớp yếu / chạm
  biên / lệch đường thẳng lân cận > 0,8 mm.
- **56 ảnh train thật** (`tools/kiem_dinh_vi.py thong-ke` → `data/_eval/omr/dinh_vi/`): **0 cờ** (2 240 lượt hàng câu, 504 lượt
  cột chữ số). Điểm khối nhỏ nhất 0,224 (0014_C2), biên duy nhất nhỏ nhất 0,056 (0025_C2 mã đề); điểm hàng nhỏ nhất 0,315;
  lệch lân cận lớn nhất 0,44 mm (0014_C2 q20); |dịch| lớn nhất 3,37 mm (0014_C2 hàng câu), 2,27 mm (cột chữ số). Thời gian
  `dinh_vi` trung vị 75–106 ms.
- **0014_C2 (giấy cong)**: mọi hàng định vị, không cờ; khớp với tìm rộng ±5 mm từng hàng sai ≤ 0,1 mm (q10 ≈ (−2,65; 3,37) mm).
  Bản đầu (cửa sổ tầng 2 đặt quanh độ dịch khối) gắn cờ 0014_C2 q3–q10, q18–q20 (chạm biên, khớp yếu tới 0,03) → sửa bằng bám
  theo lân cận.
- **Ảnh dịch giả** (`kiem_dinh_vi.py dich-gia`, 56 ảnh × 20 độ dịch = 54 880 lượt phần tử): **KHỚP NHẦM KHÔNG CỜ = 0**. Dịch đúng
  1 khoảng cách ô (±7 mm ngang, ±11 mm dọc, +5,8 mm dọc): 100% gắn cờ; −5,8 mm: 2 171 đúng + 573 cờ; 2 / 3,5 / 4 mm: đúng, trừ
  vài ca chạm biên (cờ). Điểm khối của ảnh dịch 1 ô tới 0,56 (chồng lên ảnh thật 0,22–0,78) – chặn được nhờ biên duy nhất
  (≤ −0,016) và chạm biên, không nhờ điểm.
- pytest: 63 đạt (51 cũ + 12 mới `tests/test_omr_dinh_vi.py`).

## 11. Quyết định tự đưa ra trong Phần A (theo ★ "lựa chọn nhỏ – hướng an toàn hơn")

1. **Tầng 2 bám theo lân cận** thay vì cửa sổ ±1,5 mm quanh độ dịch khối: 0014_C2 lệch trong khối tới ~4,5 mm, cửa sổ quanh
   khối không với tới (cờ cả cột). Cửa sổ vẫn ±1,5 mm (< nửa khoảng cách ô) nhưng quanh độ dịch **ngoại suy từ 1–2 hàng vừa
   định vị**, bắt đầu từ hàng khớp tốt nhất. Không mở rộng cửa sổ – giữ đúng tinh thần "< nửa khoảng cách ô".
2. **Ngưỡng điểm khối hạ 0,30 → 0,15** (0014_C2 = 0,224): điểm không phân biệt được dịch 1 ô (tới 0,56); bảo vệ chống dịch 1 ô là
   biên duy nhất ≥ 0,03 và chạm biên. Lệch lân cận so với **đường thẳng** khớp các hàng ±3 (không phải trung vị) – giấy cong đổi
   đều ~0,4 mm / hàng, trung vị sẽ báo nhầm ở hàng đầu / cuối cột.
3. **PNG mẫu vào git** bằng ngoại lệ `.gitignore` (520 KB) – `omr.py` cần lúc chạy; SHA điểm ảnh (không phải SHA file) để không phụ
   thuộc bộ nén PNG.
4. **Đệm ảnh đã nắn** `data/_omr/anh/` (PNG không mất mát) cho công cụ huấn luyện; mỗi lần đọc kiểm `anh_nan` = vân tay v4 từng
   byte. `tools/omr_du_lieu.py` chặn val (Phần A) và test trước khi đọc file.

### A2 – đặc trưng + M0 + M1, chọn nguồn ảnh (07/10/2026)
- **Đặc trưng** (`omr.dac_trung_o`, 9 cột `TEN_DAC_TRUNG`: `ld, ld_hang, ld_anh, tuyet_doi, phu_nhe, phu_dam, do_lech, hang, giay`),
  định vị luôn trên `anh_nan`. `S_anh` (không dùng nhãn) trên 56 ảnh train: 0,400 (0022_C2) – 0,804 (0015_C4) ⇒ sàn
  `S_SAN = 0,20` (≈ 0,5 × nhỏ nhất); phiếu trắng (mẫu PNG) → S = sàn, mọi ô `ld_anh` < 0,25 (pytest).
  `tools/huan_luyen_omr.py dac-trung` → `data/_omr/dac_trung_{nan,chuan}.csv` (14 000 dòng mỗi nguồn).
- **M0** = ngưỡng audit 0,25 / 0,80 trên `ld_anh`; **M1** = `StandardScaler` + `LogisticRegression(C=1, class_weight='balanced')`,
  3 lớp (ô đáp án) / 2 lớp (bubble). `huan_luyen_omr.py cv` → `data/_omr/a2_so_sanh.md`, `chon_nguon.json`, OOF `oof_*.npy`.
- **F1 lớp faint cấp ô (OOF 7-fold, argmax), [CI 95% bootstrap theo phiếu, 1000 lần, seed 2026], (n faint)**:

  | Mô hình | Nguồn | C1 | C2 | C3 | C4 | maximin |
  |---|---|---|---|---|---|---|
  | M0 | anh_nan | 0,971 [0,940; 0,995] (89) | **0,844** [0,772; 0,907] (95) | 0,926 [0,833; 0,983] (94) | 0,971 [0,937; 0,995] (88) | 0,844 |
  | M1 | anh_nan | 0,989 [0,972; 1,000] | 0,935 [0,888; 0,972] | 0,968 [0,934; 0,994] | 0,945 [0,880; 0,984] | **0,935** |
  | M0 | anh_chuan_hoa | 0,971 | 0,844 | 0,926 | 0,966 | 0,844 |
  | M1 | anh_chuan_hoa | 0,989 | 0,922 | 0,953 | 0,956 | 0,922 |

  M1 `anh_nan`: **0 ô nhầm trống ↔ có tô** (8 210 → 6 720 ô trống OOF đều đúng; mọi ô có tô đúng là có tô); nhầm chỉ giữa faint /
  filled: faint→filled 6 ô, filled→faint 25 ô (C2 12). Bubble (2 lớp) M0 và M1: 0 nhầm (4 538 trống, 502 tô).
- **Chọn `anh_nan`** (quy tắc 4d): hiệu F1 faint M1 (chuẩn hoá − nan) C1 +0,000 · C2 −0,014 [−0,030; 0] · C3 −0,016 [−0,032; 0] ·
  C4 +0,011 [0; +0,029]; maximin −0,014 [−0,030; +0,026] – CI chứa 0 ⇒ hoà → `anh_nan` (ít phụ thuộc hơn). Ở mức đơn giản này
  chuẩn hoá không giúp vì đặc trưng chính (`ld`) đã so với giấy ngay quanh ô (Tuần 4 B5 dừng A dự báo đúng điều này).
- **Biên xác suất M1 (OOF)**: ô trống: p(có tô) lớn nhất 0,057 (0014_C3 q30 B); ô có tô: p(có tô) nhỏ nhất 0,559 (0019_C3 q30 D
  mờ), kế đến 0,574 (**0019_C3 q24 C – ca thử**). Bubble: trống ≤ 0,003, tô ≥ 0,832.
- **Ca thử**: 0019 câu 24 ô C: C3 p = (trống 0,426 / mờ 0,574 / rõ 0), C4 (0,079 / 0,921 / 0) – đọc `faint` cả 2 ảnh (M0 bỏ sót C3:
  n 0,235 < 0,25); 0020 câu 33 ô C: C1 0,994 mờ, C4 0,995 mờ (M0 bỏ sót C1). **0033 câu 4 thuộc val 0029–0034 – Phần A không
  chạm, để Phần B.**
- Tiêu chí ★Q2 "F1 faint ≥ 0,90 mỗi điều kiện" (cấp ô, argmax): **M1 `anh_nan` đạt** ở cả 4 điều kiện (thấp nhất C2 0,935), nhưng
  **cận dưới CI của C2 (0,888) và C4 (0,880) < 0,90** – cỡ mẫu ~90 ô faint / điều kiện. M0 không đạt (C2 0,844).
- pytest 65 đạt (2 mới `tests/test_omr_dac_trung.py`).
