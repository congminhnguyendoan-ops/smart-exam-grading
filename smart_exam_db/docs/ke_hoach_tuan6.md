# Kế hoạch Tuần 6 – `cv_engine/ocr.py` (CNN đọc chữ số viết tay: SBD, mã đề)

> Trạng thái: **ĐÃ DUYỆT (10/10/2026)** – lập cùng ngày, HEAD lúc lập `606a799`. Các quyết định duyệt ở mục ★ ngay dưới;
> chỗ nào mục ★ khác phần thân thì **theo mục ★**. **Mốc báo cáo: thứ Bảy 17/10/2026** (không phải 13/10).

## ★ Quyết định của người dùng khi duyệt (10/10/2026)

| # | Quyết định |
|---|---|
| Q1 | D001–D010 do **5 người viết, mỗi người 2 trang**: người 1 = D001–D002, người 2 = D003–D004, người 3 = D005–D006, người 4 = D007–D008, người 5 = D009–D010. **5-fold THEO NGƯỜI VIẾT** (mỗi fold = 2 trang của 1 người) để đo khả năng đọc nét người chưa gặp; báo kết quả **theo từng người viết** (chỉ ghi "người 1–5", không tên thật). |
| Q2 | Duyệt T1–T5. Bắt buộc **lỗi im lặng = 0** ở mức chữ số và mức trường SBD / mã đề. T4 ≤ 10% phiếu cần xem thừa chấp nhận cho bản đầu. Luôn báo khoảng tin cậy. |
| Q3 | Bubble đọc được, ô viết tay trống → chấp nhận bubble **CHỈ KHI bubble chắc chắn VÀ SBD có trong danh sách thí sinh của kỳ thi**; thiếu một điều kiện → cần xem. |
| Q4 | Cài **PyTorch bản CPU** vào `.venv` gốc (dry-run trước, báo dung lượng); `requirements.txt` ghi "chỉ để huấn luyện"; backend chạy NumPy + JSON. **Không dùng Kaggle.** |
| Q5 | Được sửa `cv_engine/tap_du_lieu.py` thêm ranh giới trang chữ số (theo người viết); **thêm test chứng minh các tập phiếu dev / test cũ không đổi**. |
| MNIST | Ghi nguồn, xác minh giấy phép khi tải, lưu SHA-256. |
| Quy tắc | Không đụng phiếu 0035–0040 (test) trong mọi bước; chữ số phiếu 0001–0034 chỉ để đo, không huấn luyện; pytest cũ vẫn đạt; hồi quy Tuần 4–5 không đổi. Làm Bước 0–5 một lèo, commit mỗi mốc; chỉ dừng khi cần mắt người dùng, phải đụng tập test, hoặc lỗi im lặng > 0 không sửa được. |
> Khi khác `HUONG_DAN.md` / `KeHoach_DoAn_3Thang.docx` thì theo CLAUDE.md (kế hoạch gốc xếp CNN ở Tuần 7 và xuất `.h5/.keras`;
> CLAUDE.md xếp Tuần 6 – và mục 5 dưới đây đổi cách xuất mô hình vì Python 3.14).

Mục tiêu: từ ảnh đã nắn đọc **chữ số viết tay** ở ô SBD (6) và mã đề (3), kèm xác suất; **đối chiếu với kênh bubble** của OMR
(hai kênh độc lập: khớp → tin cậy, lệch → "cần xem").
- **Mục tiêu số 1: lỗi im lặng = 0** – SBD / mã đề sai mà vẫn được nhận tự động (ghi nhầm điểm cho sinh viên khác).
- **Mục tiêu số 2**: ít "cần xem" thừa nhất có thể (sau khi đạt mục tiêu 1).

---

## 0. Dữ liệu hiện có (đã kiểm 10/10)

| Nguồn | Nội dung | Vai trò |
|---|---|---|
| `data/raw_digits/D001–D010` | 10 trang × 400 ô (`digit_sheet_layout.json`: nhãn = `row // 2`, 20 cột; ô 6×9 mm) = **4 000 chữ số, ~400/lớp**, nhãn theo VỊ TRÍ (không gán tay) | huấn luyện tinh chỉnh |
| Phiếu 0001–0034 (68 ảnh) | 34 × 9 chữ số (SBD 6 + mã đề 3) = **306 chữ số × 2 ảnh**; nhãn: `ground_truth.csv` cột `sbd`, `exam_code` (VIẾT TAY – khác `sbd_bubble`) | **chỉ ĐO**, không huấn luyện (CLAUDE.md mục 4); chọn ngưỡng tin cậy |
| Phiếu 0035–0040 (12 ảnh) | 6 × 9 = **54 chữ số × 2 ảnh** | **TEST cuối, một lần, đăng ký trước** |
| `data/_eval/_gia_v4/` | 116 ảnh giả: `mo_dong*` / `mo_cheo*` / `mo_*` (mờ), `che_*`, `cat_*`, … có cả `D003` | đo theo mức mờ (mục 4) |

Lưu ý thống kê trung thực: test chỉ có **54 chữ số độc lập** (2 ảnh/phiếu không độc lập). 0 lỗi / 54 cho cận trên 95%
Clopper–Pearson ≈ **5,4%** – không thể "chứng minh" lỗi < 1%; báo cáo phải ghi đúng cận này (như Tuần 4: 26% cho 12 ảnh).
Vì vậy bằng chứng chính cho "lỗi im lặng = 0" đến từ dev (OOF trang D: 4 000 chữ số; phiếu 0001–0034: 306), test chỉ xác nhận.

**Đã biết (Q1):** 5 người viết × 2 trang. **Chưa biết:** ô có viền in sẵn hay không (ảnh hưởng cắt – mục 7 rủi ro R2).

## 1. Dữ liệu huấn luyện trước (công khai) – (a)

| Bộ | Quy mô | Giấy phép / nguồn | Ghi chú |
|---|---|---|---|
| **MNIST** (chọn làm chính) | 60 000 train + 10 000 test, 28×28, người viết là nhân viên điều tra dân số + học sinh | Dẫn xuất từ NIST SD-1/SD-3; trang gốc LeCun không ghi giấy phép riêng, nhiều bản sao ghi CC BY-SA 3.0 → **ghi nguồn + trích dẫn**, xác minh lại khi tải | 4 file idx `.gz`, đọc bằng `gzip` + NumPy, **không cần torchvision** |
| **EMNIST Digits** (tuỳ chọn, thí nghiệm M3) | 280 000 chữ số, nhiều người viết hơn | NIST SD-19 (công bố của chính phủ Mỹ); trích dẫn Cohen et al. 2017 | ~0,5 GB; chỉ tải nếu MNIST bị domain gap lớn |

Cách tải trên máy này: **chưa kiểm tra mạng / mirror** (phiên này không tải). Bước 1 tải bằng `urllib`/`curl` vào
`data/_ocr/nguon/` (đã được `.gitignore` vì `data/`), ghi **SHA-256** vào `data/_ocr/nguon/SHA.txt`, so với giá trị công bố. Ảnh MNIST
nền đen nét trắng → ảnh phiếu (giấy trắng, mực tối) phải đảo + chuẩn hoá kiểu MNIST (mục 3, bước 2).

**Chia tập – theo TRANG / PHIẾU, không theo chữ số** (cùng một người, cùng một trang → nét giống nhau, chia theo chữ số sẽ rò rỉ):

| Tập | Gồm | Dùng để |
|---|---|---|
| pretrain | MNIST train (giữ 5 000 làm val nội bộ) | học nét chữ số |
| **tinh chỉnh – CV** | D001–D010, **5-fold nhóm theo NGƯỜI VIẾT** (mỗi fold = 2 trang của 1 người, Q1), OOF | chọn kiến trúc / nguồn ảnh / số epoch / nhiệt độ / ngưỡng |
| dev-đo | phiếu 0001–0028 (không huấn luyện) | đo domain gap, chọn ngưỡng (cùng vai trò train của OMR) |
| **val** | phiếu 0029–0034 | kiểm tra giữ lại, chạy ở bước 9 trước khi chốt |
| **test** | phiếu 0035–0040 | đánh giá cuối MỘT lần (bước 11) |

Ranh giới trang chữ số phải thêm vào **`cv_engine/tap_du_lieu.py`** (nguồn duy nhất; ví dụ `TRANG_FOLD`), không định nghĩa ở nơi khác;
mọi công cụ mới gọi `chan_test()` trước khi đọc ảnh/nhãn phiếu 0035–0040 (cần `--xac-nhan-test`). `tools/tao_split.py` mở rộng hoặc
`tools/ocr_tao_split.py` mới → `data/ocr_split.csv`. Bước này sửa `tap_du_lieu.py` nên **hỏi người dùng** (mục 9).

## 2. Mô hình và tiêu chí so sánh – (b)

| Mốc | Mô hình | Vì sao |
|---|---|---|
| **M0** | HOG + hồi quy logistic (scikit-learn) huấn luyện MNIST | mốc đơn giản, có xác suất, xuất JSON được; đúng tinh thần Tuần 5 |
| **M1** | CNN nhỏ (2 Conv 3×3 + pool + Dense, ~100 k tham số) huấn luyện MNIST + augmentation (xoay ±10°, dịch ±2 px, co giãn, nhiễu, độ đậm nét) | phương án chính theo kế hoạch gốc |
| **M2** | M1 + **tinh chỉnh** trên D001–D010 (đóng băng Conv đầu, học lại Dense, lr nhỏ; so thêm "tinh chỉnh toàn bộ") | thu hẹp domain gap |
| M3 (nếu cần) | M2 từ EMNIST Digits | chỉ khi M2 còn lỗi nặng ở dạng viết lạ |

**Bảng 3 cột bắt buộc** (HUONG_DAN Tuần 6.4, lưu `ml_models.metrics`): MNIST/test-MNIST · MNIST/test-thật(dev) · tinh chỉnh/test-thật(dev),
mỗi cột báo accuracy + **F1 từng lớp** + confusion matrix + khoảng tin cậy Clopper–Pearson 95%. Thêm cột "theo điều kiện C1–C4".

**Tiêu chí chốt TRƯỚC khi thấy kết quả (ĐỀ XUẤT – chờ duyệt):**

| # | Tiêu chí | Ngưỡng |
|---|---|---|
| T1 | **Lỗi im lặng mức chữ số của CNN** = chữ số đọc sai mà KHÔNG bị gắn "cần xem" (OOF trang D + phiếu 0001–0034) | **= 0** (bắt buộc); báo cận trên CP |
| T2 | **Lỗi im lặng mức trường SBD / mã đề sau đối chiếu hai kênh** (phiếu 0001–0034, val, test) | **= 0** (bắt buộc) |
| T3 | Accuracy chữ số trên phiếu dev | ≥ 97% (mục tiêu; không phải điều kiện ĐẠT) |
| T4 | "Cần xem" thừa mức phiếu (phiếu toàn đúng nhưng bị gắn vì SBD / mã đề) | ≤ 10% phiếu |
| T5 | Thời gian CNN cho 9 ô | ≤ 50 ms (trung vị) |
| Chọn mô hình | Trong các cấu hình đạt T1–T2 trên OOF: maximin theo (acc trang D, acc phiếu dev), hoà → ít "cần xem" hơn → đơn giản hơn | |

**Độ tin cậy → "cần xem":** (1) softmax được **hiệu chỉnh nhiệt độ** trên OOF; (2) chữ số "chắc" khi `p_top1 ≥ τ` **và** `p_top1 − p_top2 ≥ δ`;
(3) ô **trống** (mực quá ít) / ô **không phải chữ số** (mực quá nhiều, nhiều thành phần) phát hiện bằng đặc trưng mực, KHÔNG phải lớp CNN;
(4) `τ, δ` chọn bằng OOF sao cho T1 = 0, rồi tối thiểu "thừa"; ngưỡng hệ thống hiện có `system_settings.ocr_min_confidence = 0,90` là giá trị so sánh, không mặc định tin;
(5) độ tin cậy trường = **min** theo chữ số (khớp `service.py` đang dùng `min` cho bubble).

**Quy tắc đối chiếu hai kênh (ĐỀ XUẤT)** – theo từng cột chữ số:

| Bubble (OMR) | Viết tay (CNN) | Kết quả |
|---|---|---|
| chữ số d, chắc | d, `p ≥ τ_khop` (thấp hơn τ) | **chắc** |
| d | khác d, hoặc không chắc | **cần xem** (hiện cả hai) |
| `?` (không tô / không đọc) | d, chắc | **cần xem** (gợi ý d; không tự nhận 1 kênh duy nhất) |
| d (chắc) | ô trống / không đọc được | **chắc theo bubble CHỈ KHI** SBD có trong danh sách thí sinh của kỳ thi (Q3; mã đề: có trong các mã đề của kỳ thi); thiếu → **cần xem** |
| `?` | không đọc được | cần xem |

Ca thử: **0001** (SBD viết `062384`, bubble `06238-` → cột 6 phải "cần xem", không im lặng); **0035** (mã đề viết `103`, KHÔNG tô bubble →
cần xem; nằm ở test nên chỉ xem ở bước 11).

## 3. Các bước nhỏ, "xong khi", điểm dừng – (f)

> Làm lần lượt; sau mỗi bước chạy pytest (cả test cũ, hiện 178), commit riêng (`git commit -F`, đường dẫn cụ thể), **dừng chờ người dùng ở các bước đánh dấu ⏸**.
> **Mốc báo cáo 17/10:** bước 0–5 (bảng 3 cột có số, chưa tích hợp). Bước 6–11 sau báo cáo (giống Phần A/B của Tuần 5).

| Bước | Việc | Xong khi |
|---|---|---|
| **0** ⏸ | Duyệt kế hoạch + trả lời mục 9 | người dùng duyệt tiêu chí T1–T5 và Q1–Q5 |
| **1** | Cài PyTorch (xin phép, mục 5) + tải MNIST; `requirements.txt` ghi chú "chỉ huấn luyện" | `import torch` chạy; 4 file MNIST có SHA khớp; ghi phiên bản vào kế hoạch; pytest cũ vẫn xanh |
| **2** | `tools/ocr_du_lieu.py`: cắt 400 ô/trang theo `digit_sheet_layout.json` và 9 ô/phiếu theo `layout.json` (từ `anh_nan` **và** `anh_chuan_hoa`), bỏ viền ô, chuẩn hoá kiểu MNIST (đảo, nhị phân mềm, khung 20×20 giữ tỉ lệ, đặt theo trọng tâm vào 28×28); xuất bảng đặc trưng mực; contact sheet HTML | cắt đủ 4 000 ô + 306×2 chữ số; ô trống / hỏng / dính viền được **liệt kê, xem bằng mắt 100%** contact sheet; nhãn khớp vị trí; không ghi vào `data/raw*` |
| **3** | `data/ocr_split.csv` (5 fold = 5 người viết) + test "tập phiếu dev/test cũ không đổi" + hằng trong `tap_du_lieu.py` + `chan_test`; kiểm "không phiếu 0035–0040 trong bất cứ file nào" | `--kiem` in 0 rò rỉ; 5 fold mỗi fold 2 trang, đủ 10 lớp |
| **4** | M0 trên MNIST; đo 3 chỗ: MNIST test, trang D (toàn bộ), phiếu 0001–0028 | số đo domain gap ghi vào mục KẾT QUẢ; tái tạo bằng 1 lệnh |
| **5** ⏸ | M1 (CNN) + augmentation; thí nghiệm `anh_nan` vs `anh_chuan_hoa` (mục 4a); **bảng 3 cột phần 1–2** | báo cáo `data/_eval/ocr/bao_cao_buoc5.md`; người dùng xem bảng + confusion matrix |
| **6** | M2 tinh chỉnh 5-fold OOF; hiệu chỉnh nhiệt độ; chọn `τ, δ`, phát hiện ô trống; T1 trên OOF | T1 = 0 trên OOF trang D **và** phiếu 0001–0028 (báo CP); nếu > 0: sửa trong phạm vi bước, không đụng val/test |
| **7** | Đo theo mức mờ trên `_gia_v4`; blur 4 hướng + trừ nhiễu; chỉnh lại `MO_MIN` (mục 4b) | bảng độ chính xác CNN theo mức mờ; `MO_MIN` mới có căn cứ; hồi quy Tuần 4–5 (xem dưới) không đổi ngoài ảnh mờ có chủ đích |
| **8** | Xuất mô hình (`models/ocr_*.json`, kèm siêu dữ liệu: ngày, git, SHA dữ liệu, fold, nhiệt độ, `τ, δ`, nguồn ảnh) + `cv_engine/ocr.py` (NumPy suy luận) + `tools/eval_ocr.py` độc lập (chỉ gọi `ocr.py`, đo vị trí cắt theo cách KHÁC) | `doc_chu_so()` khớp mô hình PyTorch (sai khác xác suất < 1e-4 trên 4 000 ô); pytest mới (ô trống, nhiễu, `ok=False` → `ValueError`, ca 0001) |
| **9** ⏸ | Kiểm tra giữ lại **val 0029–0034** (một lần, ghi lại mọi lần chạy lại sau sửa) | T1/T2 = 0 trên val; người dùng duyệt đi tiếp |
| **10** | Nối backend + frontend (mục 5b); kiểm đầu-cuối 56 ảnh train + `kiem_backend_dau_cuoi.py` | 0 phiếu SBD/mã đề sai mà không gắn "cần xem"; 178 test cũ xanh |
| **11** ⏸ | **Đăng ký trước** (commit riêng: tiêu chí, SHA mô hình, ngưỡng) rồi đánh giá **test 0035–0040 MỘT lần**, xem mù, báo cáo; ca 0035 | số liệu + CP ghi vào kế hoạch; không chỉnh gì sau khi xem |

## 4. Các yêu cầu đã chốt trong CLAUDE.md – (c)

**4a. Thử trên `anh_nan` và `anh_chuan_hoa`** (yêu cầu 07/10): cùng một mô hình, hai nguồn cắt, bước 5 và 6, OOF 5-fold; so T1, accuracy, F1 từng lớp,
theo C1–C4. Quy tắc chọn đã chốt trước: cấu hình đạt T1 = 0; hoà → maximin theo C1–C4 (như Tuần 5). Lưu ý đã biết: chuẩn hoá giảm nét/nhiễu
50,1 → 48,1 và tăng chênh mức nét giữa trang 29,7 → 32,9; với nét bút bi / chì mảnh có thể có lợi, không thể đoán trước.

**4b. Đo theo mức mờ và chỉnh `anh_mo`** (yêu cầu 06/10):
1. Dùng `data/_eval/_gia_v4` (`tools/kiem_verify.py tao-gia` để tái tạo): `mo_dong*`, `mo_cheo*`, `mo_*` cho `D003`, 0001_C1, 0005_C2, 0008_C4, 0015_C3. Chỉ ảnh **dev**.
2. Với mỗi mức: `blur_score`, `preprocess` ok/ly_do, accuracy CNN, tỉ lệ "cần xem" – vẽ đường cong lỗi theo mức mờ.
3. Đo blur 4 hướng (0/45/90/135°) + trừ nhiễu; gỡ `SAI_MA_DA_BIET` trong `tools/eval_preprocessing.py` khi sửa xong.
4. Chọn `MO_MIN` **theo hậu quả**: mức mờ nhỏ nhất mà (CNN **hoặc** OMR) bắt đầu có lỗi im lặng, trừ biên an toàn; ưu tiên từ chối (giáo viên chụp lại) hơn đọc sai.
   Hiện `MO_MIN = 0,012` (đo ở dev xấu nhất 0,221 → đã rất thoáng); chốt chặt hơn bao nhiêu phải dựa vào số đo, không đoán.
5. **Ràng buộc**: chỉ chỉnh bằng ảnh dev + ảnh giả. Phiếu 0035–0040 đã chạy `preprocess` một lần ở Tuần 4 Bước 7; đổi `MO_MIN` sau đó
   nghĩa là tham số đổi KHÔNG dựa trên test (ghi rõ trong báo cáo), và lần chạy test của bước 11 là lần đầu với `MO_MIN` mới.
6. Hồi quy sau khi đổi: `tools/eval_preprocessing.py` (dev 78/78 đúng, 0 lỗi im lặng), `tools/eval_omr.py` (M1 OOF 0 lỗi nặng), pytest.

## 5. Nối vào backend – (d)

**5a. Module `cv_engine/ocr.py`** (cùng phong cách `omr.py`; ổn định cho Tuần 7+):
```python
from cv_engine.ocr import doc_chu_so, nap_mo_hinh_ocr, doi_chieu_dinh_danh
mh = nap_mo_hinh_ocr()                         # models/ocr_*.json – nạp 1 lần
ocr = doc_chu_so(kq, nap_layout("phieu"), mh)  # kq.ok=True (không thì ValueError)
ocr.sbd    # 6 cột: chu_so ('?' nếu trống / không đọc), top_k [(d,p)...], p, trang_thai, can_xem, ly_do, anh_cat
ocr.ma_de  # 3 cột
dc = doi_chieu_dinh_danh(omr, ocr)             # bảng ở mục 2; trả sbd_cuoi, ma_de_cuoi, can_xem, ly_do, theo cột
```
Mã lý do mới `MA_LY_DO_OCR` (đề xuất): `o_trong`, `khong_phai_chu_so`, `tin_cay_thap`, `lech_bubble`, `thieu_bubble`. Câu / cột nào không chắc → `can_xem`, **không đoán**.

**5b. `backend/service.py`**: sau `omr.doc_phieu` gọi `doc_chu_so` + `doi_chieu_dinh_danh`; kết quả vào `omr_detail` (JSON, có thêm khoá `ocr`) và
**bảng `ocr_digits` đã có sẵn** (`field, position, predicted_digit, confidence, top_k, crop_image_path, corrected_digit`) – 9 dòng/phiếu, ảnh cắt lưu `storage/` như ảnh phiếu.
`detected_sbd` / `detected_exam_code` = kết quả đối chiếu; `sbd_confidence` = min. SBD lệch bubble → `review_queue` bằng lý do hiện có
`low_ocr_confidence` (+ `chi_tiet.loai`). **Không đổi ENUM / không ALTER** khi chưa hỏi (CLAUDE.md mục 9); nếu thấy cần lý do mới → xin phép riêng.
`service.danh_gia_phieu` vẫn là đường quyết định duy nhất. Khi giáo viên sửa SBD (`PUT /sheets/{id}/identity`) → ghi `ocr_digits.corrected_digit`
(dữ liệu cho fine-tune sau, đúng hướng "human-in-the-loop"; **không** tự động huấn luyện lại).
**API**: `GET /sheets/{id}` thêm `ocr` (từng chữ số + ảnh cắt, xác suất); `GET /sheets/{id}/digits/{field}/{pos}/image` (ảnh cắt, giống `/questions/{n}/image`).
Frontend F3/F4: hiển thị ảnh viết tay cạnh chữ số bubble (việc nhỏ, làm ở bước 10).
**Thời gian**: hiện `preprocess` ~0,58 s + OMR ~0,1 s; mục tiêu thêm ≤ 0,05 s (9 ô × CNN nhỏ bằng NumPy). Đo ở bước 8 và 10.

**5c. Thư viện – (e)** (dry-run `pip install --dry-run --no-deps` trong `.venv`, Python 3.14.7, win_amd64, 10/10/2026 – *chưa cài gì*):

| Gói | Kết quả | Quyết định |
|---|---|---|
| `torch` | **2.14.1 `cp314-cp314-win_amd64`** có sẵn | **Chọn để huấn luyện** (CPU đủ: ~100 k tham số, MNIST). Kích thước tải / dung lượng cài chưa đo – kiểm ở bước 1 |
| `tensorflow` | chỉ **2.22.0rc0** (bản thử, không có bản ổn định cho 3.14) | **Không dùng** (rủi ro; CLAUDE.md mục 8 đã cảnh báo) |
| `keras` | 3.15.1 (thuần Python, cần backend) | Không cần |
| `onnxruntime` | 1.31.0 có cp314 | Không cần (xem dưới) |
| `scikit-learn` | đã cài 1.9.1 | dùng cho M0 |

**Suy luận KHÔNG dùng PyTorch**: xuất trọng số ra JSON/`npz`, `ocr.py` chạy bằng NumPy (Conv 3×3 nhỏ trên 28×28 – vài ms) – giống
`omr.py` ("lúc chạy chỉ NumPy + OpenCV + JSON"). Lý do: backend không phụ thuộc thư viện nặng + Python 3.14, mô hình đọc được/đưa vào git, kiểm tra
tương đương số học ở bước 8. Đây là **thay đổi so với kế hoạch gốc** (`.keras`) → ghi vào báo cáo. Phương án dự phòng nếu cài torch gặp lỗi:
huấn luyện trên **Kaggle** (như CLAUDE.md mục 2), mang trọng số về. `requirements.txt`: ghi chú "chỉ để HUẤN LUYỆN (Tuần 6)".

## 6. Công cụ dự kiến (đều nhỏ, mỗi công cụ một việc)

`tools/ocr_du_lieu.py` (cắt + chuẩn hoá + contact sheet) · `tools/ocr_tao_split.py` (hoặc mở rộng `tao_split.py`) · `tools/huan_luyen_ocr.py`
(`mnist` → `cv` → `tinh-chinh` → `hieu-chinh` → `xuat`) · `tools/eval_ocr.py` (độc lập, chỉ gọi `ocr.py`: `run`, `report`, `mo` cho đường cong mờ) ·
`cv_engine/ocr.py` · `tests/test_ocr.py`. Mọi số đưa vào báo cáo tái tạo được bằng script (CLAUDE.md mục 9); ghi `data/_eval/ocr/`, `data/_ocr/`.

## 7. Rủi ro

| # | Rủi ro | Đối phó |
|---|---|---|
| R1 | **Domain gap** MNIST → ô 6×9 mm trên phiếu (bút chì mảnh, bút bi, nét chạm viền) | bảng 3 cột đo ngay ở bước 4; tinh chỉnh bằng trang D; M3 (EMNIST) nếu cần |
| R2 | Viền ô / chữ số chạm viền làm nhiễu khi cắt; chữ số lệch ô ~1 mm (OMR đã thấy lệch nội dung tới 2 mm ở C3) | cắt rộng hơn ô, loại viền bằng thành phần liên thông / mặt nạ, xem contact sheet 100%; dò lại vị trí giống OMR nếu cần |
| R3 | **Chỉ 54 chữ số test** → cận trên lỗi rộng (~5,4%) | nói thẳng trong báo cáo; bằng chứng chính từ dev; không chỉnh theo test |
| R4 | Chỉ 5 người viết trang D → ít đa dạng nét | CV theo người viết đo đúng "người chưa gặp"; báo từng người; phiếu dev/val/test do ai viết chưa rõ → ghi giới hạn |
| R5 | Nhập nhằng 1↔7, 4↔9, 3↔5, 6↔0 | hệ số δ (khoảng cách top1–top2) + đối chiếu bubble; xem confusion matrix |
| R6 | Nhãn viết tay sai (người viết nhầm / quên viết ô) | nhãn trang D theo vị trí → liệt kê ô trống; nhãn phiếu theo `ground_truth.csv` (đã audit); sửa nhãn chỉ khi người dùng so giấy xác nhận |
| R7 | Đổi `MO_MIN` làm phiếu tốt bị từ chối nhầm / bỏ lọt ảnh mờ | chỉnh theo hậu quả (4b), hồi quy Tuần 4–5, biên an toàn nghiêng về từ chối |
| R8 | Cài torch lỗi / nặng trên Python 3.14 | dry-run đã thấy wheel; dự phòng Kaggle |
| R9 | Tích hợp backend làm tăng "cần xem" thừa (SBD lệch bubble do bubble `?`) | đo T4 ở bước 10; chỉnh luật đối chiếu bằng dev, không bằng test |
| R10 | Ghi DB (`ocr_digits`, `ml_models`) | chỉ qua code backend / migration có hỏi; không chạy `run_all`; không ALTER khi chưa hỏi |

## 8. Phạm vi KHÔNG thuộc Tuần 6

Đăng nhập, hàng đợi nền, import sinh viên, nhận dạng tên viết tay, nhận dạng chữ cái, tự huấn luyện lại từ sửa của giáo viên (chỉ lưu `corrected_digit`).

## 9. Câu hỏi (ĐÃ TRẢ LỜI 10/10 – xem mục ★; giữ lại để đối chiếu)

1. **Ai viết D001–D010** (1 người hay nhiều)? Và phiếu 0001–0040 do mấy người viết SBD / mã đề tay? (quyết định cách đọc kết quả CV và R4)
2. Duyệt **tiêu chí T1–T5** và quy tắc đối chiếu hai kênh (mục 2) – đặc biệt T4 (≤ 10% phiếu "cần xem" thừa) có hợp lý không?
3. Khi **bubble đọc được nhưng ô viết tay trống**: chấp nhận bubble (như Tuần 5, ĐỀ XUẤT) hay luôn "cần xem" (an toàn hơn, nhiều việc cho giáo viên hơn)?
4. Cho phép **cài PyTorch vào `.venv` gốc** (CPU) ở bước 1, hay ưu tiên huấn luyện trên Kaggle?
5. Cho phép **sửa `cv_engine/tap_du_lieu.py`** thêm ranh giới trang chữ số (nguồn duy nhất) – đúng quy ước CLAUDE.md?

## 10. KẾT QUẢ

*(chưa có – điền từng bước khi làm)*
