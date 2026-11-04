# Kiểm kê dữ liệu chữ số và ô tô (lệnh AI, 04/11/2026)

Chỉ có số liệu, không có dữ liệu. Tái tạo: `python tools/ai_so_sanh_thuat_toan.py kiem-ke` → `data/_eval/ai/kiem_ke.json` (ngoài git).
Mọi tệp dữ liệu nằm trong `data/` (không vào git); MNIST / EMNIST không được commit.

## 1. Ô chữ số viết tay thật – trang D001–D010

Nguồn: 10 ảnh chụp trang chữ số `data/raw_digits/D001.jpg … D010.jpg`, mỗi trang 400 ô (10 chữ số × 40 ô), 5 người viết × 2 trang.
Cắt bằng `cv_engine.ocr` (`tools/ocr_du_lieu.py cat`) → `data/_ocr/cat/anh_nan.npz|csv`. Ô "dùng được" = dò được khung in sẵn (`ok_vien = 1`); ô còn lại bị loại khỏi
huấn luyện / đo (giống mọi số liệu Tuần 6, lệnh D, lệnh AD).

| Người viết | Trang | Ô cắt | Ô dùng được | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | D001, D002 | 800 | 761 | 79 | 80 | 80 | 80 | 72 | 58 | 72 | 80 | 80 | 80 |
| 2 | D003, D004 | 800 | 793 | 80 | 79 | 80 | 80 | 79 | 79 | 78 | 80 | 79 | 79 |
| 3 | D005, D006 | 800 | 728 | 78 | 78 | 70 | 75 | 74 | 70 | 78 | 52 | 76 | 77 |
| 4 | D007, D008 | 800 | 798 | 80 | 79 | 80 | 80 | 80 | 80 | 80 | 80 | 79 | 80 |
| 5 | D009, D010 | 800 | 792 | 79 | 80 | 79 | 79 | 78 | 78 | 80 | 79 | 80 | 80 |
| **Tổng** | 10 trang | **4 000** | **3 872** | 396 | 396 | 389 | 394 | 383 | 365 | 388 | 371 | 394 | 396 |

(128 ô không dò được khung: chủ yếu người 1 chữ số 5 (22 ô) và người 3 chữ số 7 (28 ô).)

**Ô chữ số trên phiếu (SBD + mã đề)**, phiếu dev 0001–0028 × 2 ảnh × 9 ô = **504 ô** (người 1: 144, người 2: 144, người 3: 144, người 4: 72; người 5 không có
phiếu dev). Theo chữ số: 0: 90 · 1: 102 · 2: 48 · 3: 48 · 4: 48 · 5: 32 · 6: 34 · 7: 34 · 8: 34 · 9: 34. Bộ đệm còn có ô của phiếu val 0029–0034 (tổng bộ đệm 408 ô SBD +
204 ô mã đề = 0001–0034); ô val **bị lọc bỏ** ngay khi đọc (`huan_luyen_ocr.tap_do`). Phiếu test 0035–0040 không có trong bộ đệm. Ô phiếu **chỉ dùng để đo**, không huấn luyện.

## 2. MNIST

Nguồn: 4 tệp `.gz` (bản sao PyTorch của MNIST, SHA-256 ở `data/_ocr/nguon/SHA.txt`). Train gốc 60 000 → **55 000 huấn luyện** + **5 000 kiểm định nội bộ**
(hoán vị seed 2026, `ocr_cai_tien.du_lieu_truoc("mnist")`; đúng tập tiền huấn luyện của CNN triển khai). **Test 10 000** (980 / 1 135 / 1 032 / 1 010 / 982 / 892 / 958 /
1 028 / 974 / 1 009 theo chữ số 0–9). Mô hình triển khai: tiền huấn luyện trên 55 000, KHÔNG dùng test MNIST để chọn gì.

## 3. EMNIST

Tệp `data/nguon_ngoai/emnist/emnist_archive.zip` (1,33 GB) chứa 6 bộ (balanced, byclass, bymerge, digits, letters, mnist), mỗi bộ ở hai dạng:
`emnist-<bộ>-train.csv` / `-test.csv` / `-mapping.txt`, và `emnist_source_files/emnist-<bộ>-{train,test}-{images-idx3,labels-idx1}-ubyte`.

| Tệp đã dùng (lệnh AD, `tools/ad_nap_emnist.py`) | Số mẫu | Dùng ở đâu |
|---|---|---|
| `emnist_source_files/emnist-digits-train-images-idx3-ubyte` + `-labels-idx1-ubyte` | **240 000** (24 000 / chữ số) | lệnh AD: tiền huấn luyện ứng viên `ad1` (KHÔNG đạt, không triển khai). Lệnh AI: **không dùng** |
| `emnist_source_files/emnist-digits-test-images-idx3-ubyte` + `-labels-idx1-ubyte` | **40 000** (4 000 / chữ số) | lệnh AD: chỉ trích ra, **không dùng để đo**. Lệnh AI: tập đo E1 |

Các bộ khác (letters, balanced, byclass, bymerge, mnist) và tệp `.csv` **không dùng**. Đọc thẳng từ zip, không giải nén; lưu gọn `data/nguon_ngoai/emnist_digits.npz`
(chuyển vị về đúng chiều MNIST; trùng từng byte với bản Hugging Face dùng ở Tuần 6 Phần C). Chuẩn hoá: EMNIST gốc căn theo bbox và phóng chữ số tới ~24 px, khác MNIST
(bbox 20×20 + trọng tâm). Bản `x_*_chuan` = cho từng ảnh qua `cv_engine.ocr.ve_mnist` (bbox mực → **20×20** giữ tỉ lệ, trọng tâm đặt ở (14, 14) của 28×28) – cùng cách
chuẩn hoá ô thật. Tuần 6 Phần C (`c1_emnist`) từng dùng EMNIST train **thô** (chỉ chuyển vị).

## 4. Ô phiếu giả (lệnh AD, `tools/ad_sinh_o_gia.py`)

**60 000 ô**: 30 000 vẽ từ chữ số MNIST (55 000 huấn luyện) + 30 000 từ EMNIST Digits train; seed 2026. Mỗi chữ số được vẽ thành ô 300 DPI có viền in sẵn, ô bên cạnh,
nền giấy + vân, bóng, sáng / gamma, nhoè Gauss / chuyển động, nhiễu, JPEG, xoay / nghiêng, dịch, lấn viền, nét đứt / mảnh / dày, rồi cho qua **đúng** `ocr.cat_o` +
`ocr._hop_ly_o` như ô thật. Theo chữ số: 6 063 / 6 143 / 6 021 / 6 091 / 5 888 / 5 695 / 5 873 / 6 124 / 5 948 / 6 154. Tham số chỉnh chỉ theo trang D (so thống kê 400 ô giả
với 390 ô thật: nền, lượng mực, cao / rộng, độ đậm, bề rộng nét). Chỉ dùng ở ứng viên `ad1` (không đạt). Lệnh AI không dùng.

## 5. Ô tô cho OMR (hồi quy logistic M1, `models/omr_m1.json`)

Bảng đặc trưng `data/_omr/dac_trung_nan.csv` (huấn luyện M1, `tools/huan_luyen_omr.py`): **14 000 ô** từ **56 ảnh** = **28 phiếu** train 0001–0028 × 2 ảnh
(mỗi điều kiện chụp C1–C4: 14 ảnh, 3 500 ô).

| Loại ô | Số ô | blank | filled | faint |
|---|---|---|---|---|
| Ô đáp án (40 câu × 4 ô × 56 ảnh) | 8 960 | 6 766 | 1 828 | 366 |
| Bubble SBD / mã đề (90 ô × 56 ảnh) | 5 040 | 4 538 | 502 | 0 |
| **Tổng** | **14 000** | 11 304 | 2 330 | 366 |

Chia: **theo phiếu** (2 ảnh cùng phiếu chung fold) – train 0001–0028 thành **7 fold** × 2 000 ô (4 phiếu / fold) để chọn mô hình và đo OOF; val 0029–0034 và test 0035–0040
riêng (`data/split.csv`, ranh giới ở `cv_engine/tap_du_lieu.py`). Mô hình xuất học cả 7 fold (C = 1, `class_weight = "balanced"`). Nhãn gốc ở `data/cell_labels.csv`
(40 phiếu: 6 400 ô đáp án + 3 600 ô bubble).
