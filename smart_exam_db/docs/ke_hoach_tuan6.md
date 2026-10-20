# Kế hoạch Tuần 6 – `cv_engine/ocr.py` (CNN đọc chữ số viết tay: SBD, mã đề)

> Trạng thái: **ĐÃ DUYỆT (10/10/2026)** – lập cùng ngày, HEAD lúc lập `606a799`. Các quyết định duyệt ở mục ★ ngay dưới;
> chỗ nào mục ★ khác phần thân thì **theo mục ★**. **Mốc báo cáo: thứ Bảy 17/10/2026** (không phải 13/10).

## ★ Quyết định của người dùng khi duyệt (10/10/2026)

| # | Quyết định |
|---|---|
| Q1 | D001–D010 do **5 người viết, mỗi người 2 trang**: người 1 = D001–D002, người 2 = D003–D004, người 3 = D005–D006, người 4 = D007–D008, người 5 = D009–D010. **5-fold THEO NGƯỜI VIẾT** (mỗi fold = 2 trang của 1 người) để đo khả năng đọc nét người chưa gặp; báo kết quả **theo từng người viết** (chỉ ghi "người 1–5", không tên thật). |
| Q1b | **SBD / mã đề viết tay trên phiếu do cùng 5 người (người 1–5 như trang D), mỗi người 8 phiếu**: người 1 = 0001–0008, người 2 = 0009–0016, người 3 = 0017–0024, người 4 = 0025–0032, người 5 = 0033–0040. Dùng để báo kết quả theo người viết. **HẠN CHẾ phải nêu trong báo cáo:** tập test 0035–0040 hoàn toàn do **người 5** viết, mà người 5 cũng viết D009–D010 (dữ liệu tinh chỉnh) ⇒ test cuối chỉ đo **"nét chữ đã gặp"**; khả năng đọc nét chữ **người lạ** lấy từ phép chia theo người viết trên dev (OOF, mỗi fold bỏ 1 người). Val 0029–0032 thuộc người 4, 0033–0034 thuộc người 5 (cùng lưu ý). |
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

### Bước 1 (10/10/2026) – xong
- Dry-run + cài **torch 2.14.1+cpu** vào `.venv` gốc: wheel `cp314-cp314-win_amd64` **124 MB**; cài xong `site-packages/torch` **546 MB** (+ fsspec, networkx, sympy, mpmath, filelock, Jinja2, MarkupSafe, setuptools; numpy 2.5.3 và opencv không đổi). `torch.cuda.is_available() = False` (đúng, bản CPU).
- `requirements.txt`: dòng `torch>=2.14` ghi "chỉ để HUẤN LUYỆN"; backend / `ocr.py` không import torch.
- MNIST tải từ bản sao PyTorch (`ossci-datasets.s3.amazonaws.com/mnist`); **trang gốc yann.lecun.com không truy cập được từ máy này**. Giấy phép: Hugging Face `ylecun/mnist` ghi `license: mit` (nguồn gốc NIST SD-1/SD-3) – chưa xác minh trực tiếp ở trang gốc; ghi nguồn + trích dẫn LeCun, Cortes, Burges. SHA-256 (khớp giá trị MNIST được công bố rộng rãi) lưu ở `data/_ocr/nguon/SHA.txt` (ngoài git):
  `train-images 440fcabf…3609` · `train-labels 3552534a…255c` · `t10k-images 8d422c7b…c4e6` · `t10k-labels f7ae60f9…aec6`.

### Bước 2–3 (10/10/2026) – xong
- Viền ô in sẵn CÓ THẬT (ô 71×106 px, nét ~4–5 px) → `cv_engine/ocr.py`: `tim_khung` (thành phần liên thông cỡ ≈ ô, gán ô danh nghĩa gần nhất ≤ 40 px; ô liền kề trên phiếu chỉ cách ~12 px nên **không dò theo hàng / theo cạnh**: hai cách đó đã thử trước và bỏ vì bắt nhầm viền ô bên cạnh – phiếu SBD chỉ đúng 66%, D004–D006 lệch > 20 px), cắt vào trong 7 px, xoá vệt viền (dải 3 px của cạnh phủ > 50%) và mọi mảnh mực nằm gọn trong dải 5 px sát mép, chuẩn hoá kiểu MNIST (bbox → 20×20, trọng tâm → 28×28).
- Cắt 78/78 ảnh từ `preprocess()` (53–59 s): **4 000 ô trang D + 408 ô SBD + 204 ô mã đề** (phiếu dev 0001–0034) × 2 nguồn (`anh_nan`, `anh_chuan_hoa`). Dò được khung: trang D **96,8%** (128 ô không dò được → loại khỏi phép ĐO, ghi số ô bỏ), SBD **99,8%**, mã đề **87,3%** (khung dính đường kẻ ở phiếu 0006 chụp ngang / ảnh C3; dùng độ lệch trung vị của ảnh + tinh chỉnh cạnh, gắn `ok_vien = 0`). **0 ô trống** trong 4 612 ô → ngưỡng `NGUONG_TRONG` = 30 px mực **chưa được kiểm trên ô trống thật** (xem nợ kỹ thuật).
- Chọn `NUT_VIEN` = 7 bằng đo trên 4 trang (1 511 ô): 9 px cắt cụt chữ ở 35% ô, 7 px còn vệt viền ở 0,8% ô, 5 px ở 9% ô.
- Xem bằng mắt (tôi tự xem): lưới 20×20 của **D001, D005, D008** và các ô debug; nhãn theo vị trí khớp. **7 lưới còn lại (D002–D004, D006, D007, D009, D010) chưa xem** – `data/_ocr/cat/xem/D0xx_mnist.png`; danh sách ô đáng ngờ `data/_ocr/cat/xem/dang_ngo.csv` (220 ô).
- `tap_du_lieu.py`: thêm `ma_trang`, `nguoi_viet_trang`, `nguoi_viet_phieu`, `nguoi_viet`, `fold_nguoi_viet` (không đổi hằng / hàm cũ; `test_tap_cu_khong_doi` = vân tay SHA-256 của toàn bộ ranh giới cũ tính trước khi sửa, vẫn khớp). `data/ocr_split.csv` (`tools/ocr_du_lieu.py split | kiem`): 10 trang → 5 fold (mỗi fold = 2 trang của 1 người); ảnh phiếu test chỉ có tên; **0 phiếu test** trong dữ liệu cắt (`kiem` kiểm cả `anh_nan.csv`, `anh_chuan_hoa.csv`).

### Bước 4–5 (10/10/2026) – xong (số đo: `data/_eval/ocr/m0_buoc4.json`, `m1_buoc5.json`, `bao_cao_buoc5.json`)
Cách đọc: "trang D" = 3 872 chữ số D001–D010 (bỏ 128 ô không dò được khung); "phiếu dev" = 504 chữ số (0001–0028 × 2 ảnh × 9; **đo mọi ô**); khoảng tin cậy Clopper–Pearson 95% (2 ảnh cùng phiếu không độc lập → khoảng của phiếu hơi lạc quan). Nguồn ảnh: `anh_nan` (`anh_chuan_hoa` chênh ≤ 0,3 điểm % ở mọi số đo – trong nhiễu).

**Bảng 3 cột – mức CHỮ SỐ** (accuracy, argmax thuần, chưa gắn "cần xem")

| Mô hình | MNIST / test-MNIST (10 000) | MNIST / test-thật: trang D | MNIST / test-thật: phiếu dev | Tinh chỉnh / test-thật: trang D (người LẠ, OOF) | Tinh chỉnh / test-thật: phiếu dev (người LẠ, OOF) |
|---|---|---|---|---|---|
| M0 HOG + logistic | 97,9% [97,6–98,2] | 91,1% [90,2–92,0] | 88,1% [84,9–90,8] | – | – |
| M1 CNN (seed 2026) | 98,9% [98,7–99,1] | 93,7% [92,8–94,4] | 87,9% [84,7–90,6] | – | – |
| M1 seed 1 / 2 | 99,0 / 98,9 | 94,0 / 94,1 | **92,3 / 91,7** | – | – |
| **M2 CNN tinh chỉnh (toàn bộ, `anh_nan`)** | – | – | – | **95,8% [95,2–96,5]** (3 711/3 872) | **91,9% [89,1–94,1]** (463/504) |

Phiếu dev của M1 phụ thuộc seed mạnh (87,9% → 92,3%, cùng dữ liệu, cùng kiến trúc) – với 504 chữ số của 4 người, chênh ~4 điểm % là nhiễu của phép đo, không phải khác biệt thật giữa các seed. **Từ MNIST sang chữ thật mất ~5–7 điểm % ở trang D và ~7–10 điểm % ở phiếu**; tinh chỉnh với người lạ thu lại ~2 điểm % ở trang D (93,7 → 95,8).

**Theo người viết** (người 1–5; trang D = M1 / M2 OOF; phiếu dev chỉ người 1–4, người 4 chỉ 0025–0028 = 72 ô, người 5 không có phiếu dev):

| Người | Trang D M1 (MNIST) | Trang D M2 (người lạ) | Phiếu dev M2 (người lạ) |
|---|---|---|---|
| 1 | 92,8% | 95,1% | 94,4% (144 ô) |
| 2 | 92,6% | 94,3% | 93,1% (144 ô) |
| 3 | 89,2% | **93,0%** | **84,7%** (144 ô) |
| 4 | 97,7% | 98,5% | 98,6% (72 ô) |
| 5 | 95,6% | 98,0% | – (test) |

Theo điều kiện chụp (phiếu dev, M2): C1 96,0% · C2 93,7% · **C3 84,9%** · C4 92,9%. Lỗi chắc chắn nhất trên trang D (`data/_eval/ocr/sai_chac_chan.png`, 60 ô): chủ yếu **kiểu viết riêng của từng người**, không phải nhãn sai – người 2 viết "1" có nét hất dài đọc thành 7; người 3 viết "7" gạch ngang / thêm nét đọc thành 8; thêm vài ô "9 → 5" ở D001–D002 (xem mục cần mắt người dùng).

**Mức TRƯỜNG** (phiếu dev, 56 ảnh):

| | Cách đọc | SBD (6 chữ số) | Mã đề (3 chữ số) |
|---|---|---|---|
| M0 / M1 | CNN argmax, đúng MỌI chữ số | 50–55% / 50% | 71–73% / 59% |
| M2 (người lạ) | CNN argmax, đúng MỌI chữ số | 62,5% [48,6–75,1] (35/56) | 75,0% [61,6–85,6] (42/56) |
| **M2 + đối chiếu bubble** (luật mục 2, τ_khop = 0,5) | **nhận tự động** | **29/56 = 51,8%** | **42/56 = 75,0%** |
| | **lỗi im lặng** | **0 / 29 nhận** (CP95% ≤ 11,9%) | **0 / 42** (≤ 8,4%) |
| | "cần xem" | 27 (21 lệch bubble, 5 tin cậy thấp, 2 thiếu bubble = 0001 × 2 ảnh – đúng chỗ) | 14 (lệch bubble) |

**Kết quả so với tiêu chí (mục 2) – KHÔNG ĐẠT toàn bộ, ghi thẳng:**

| Tiêu chí | Kết quả | Đánh giá |
|---|---|---|
| T2 lỗi im lặng mức trường = 0 | **0** trên phiếu dev (SBD 0/29, mã đề 0/42) | đạt – **có điều kiện**: kênh bubble là OMR mô hình cuối (đã học trên 0001–0028 → hơi lạc quan); lỗi im lặng mức trường chỉ có thể xảy ra khi bubble sai im lặng VÀ CNN cùng sai đúng chữ số đó |
| T1 lỗi im lặng mức chữ số của CNN = 0 | **0** nhưng chỉ ở **τ = 0,9995, δ = 0,99 → 77% chữ số trang D / 75% phiếu dev bị gắn "cần xem"** (T = 1,75; lưới τ, δ; OOF trang D, 161 ô sai, CP95% lỗi im lặng trên ô sai ≤ 2,3%). Nới ngưỡng: phiếu dev τ = 0,9 → cần xem 22,8% nhưng 5/41 lỗi lọt; τ = 0,99 → 47,6%, 3/41 lọt | đạt về kỹ thuật, **vô dụng thực tế** → CNN KHÔNG thể là kênh duy nhất; chính đối chiếu bubble mới cho T2 |
| T3 accuracy chữ số phiếu dev ≥ 97% | 91,9% (người lạ) | **chưa đạt** |
| T4 cần xem thừa ≤ 10% phiếu | **53,6%** (30/56 ảnh có SBD hoặc mã đề bị gắn; 2 ảnh 0001 gắn đúng vì bubble thiếu) | **chưa đạt** – CNN sai ~8%/chữ số → SBD 6 chữ số sai ít nhất 1 chữ ~38%; độ nhạy τ_khop (chỉ tham khảo, KHÔNG chốt vì phiếu dev là tập đo): 0,5 → nhận 71/112 trường, 0,3 → 81, 0,2 → 86, 0,1 → 96 |
| T5 ≤ 50 ms / ảnh | cắt 9 ô 47 ms (trung vị, gồm bản đồ tối cả trang) + CNN PyTorch 9 ô 1,1 ms ≈ **48 ms**; suy luận NumPy chưa viết (Bước 8) | sát ngưỡng; cắt chiếm gần hết – giảm được bằng bản đồ tối theo cửa sổ |

### Quyết định tự đưa ra trong Bước 0–5 (đều theo hướng an toàn / ghi để báo cáo)
1. **M2 sơ bộ làm ngay trong Bước 5** (kế hoạch để Bước 6) để điền cột "tinh chỉnh / test-thật": 5-fold theo người, 2 kiểu (đóng băng Conv: lr 1e-3; toàn bộ: lr 3e-4; 6 epoch) × 2 nguồn ảnh, chọn theo maximin accuracy theo người trên trang D OOF → **`toan_bo/anh_nan`** (min người 0,930; `anh_chuan_hoa` 0,926 – chênh trong nhiễu; `anh_nan` cũng là nguồn định vị của OMR). Phiếu của người k đọc bằng mô hình bỏ người k.
2. HOG viết bằng NumPy (`hog28`) vì **OpenCV 5.0 không còn `HOGDescriptor`**; M0 chọn C = 10 trong lưới {0,1; 1; 10} bằng 5 000 ảnh MNIST giữ lại (C ở biên lưới – M0 chỉ là mốc, không chỉnh thêm).
3. Phiếu dev chỉ **0001–0028**; 0029–0034 (val) chưa đo (ảnh đã được cắt vào cache nhưng chưa dùng). Phiếu test: không đọc ảnh, không đọc dòng nhãn.
4. Trang D loại ô `ok_vien = 0` khỏi phép ĐO (128 / 124 ô); phiếu đo mọi ô.
5. Hiệu chỉnh nhiệt độ T và (τ, δ) chọn trên **OOF trang D** (không dùng phiếu dev để chọn); `τ_khop = 0,5` chọn trước, không chỉnh theo dữ liệu.
6. Luật đối chiếu cài trong `cv_engine/ocr.py` (`doi_chieu_cot`, `doi_chieu_truong`, 8 test): bubble `?` hoặc bị OMR gắn cần xem → luôn cần xem (không nhận một kênh duy nhất); ô viết tay trống + bubble chắc → chỉ nhận khi SBD trong danh sách (Q3).

### Hạn chế (phải nêu trong báo cáo)
- **Test 0035–0040 toàn do người 5 viết, người 5 cũng viết D009–D010 → test cuối chỉ đo "nét chữ đã gặp"**; khả năng đọc nét chữ người lạ chỉ lấy từ 5-fold theo người viết (số trên). Người 5 là người dễ nhất ở trang D (98,0%) → số test sẽ **lạc quan** so với 5-fold.
- Chỉ **5 người viết**; phiếu dev của người 4 chỉ 72 ô; kiểu viết riêng (1 giống 7, 7 gạch ngang) chiếm phần lớn lỗi chắc chắn.
- Phiếu dev 504 chữ số (252 độc lập về phiếu) → khoảng tin cậy rộng; chênh giữa seed (87,9 / 92,3 / 91,7%) cho thấy nhiễu ~±2 điểm %.
- Kênh bubble trong số đo mức trường: OMR đã học trên 0001–0028 (lạc quan).

### Nợ kỹ thuật sau Bước 5
1. **Chưa đạt T3, T4** (xem bảng) → Bước 6: cải tiến mô hình (EMNIST Digits, tăng cường kiểu "1 có hất", "7 gạch ngang", nét mảnh / nhạt ở C3), giảm độ nhạy seed (trung bình nhiều seed / ensemble), xét luật đối chiếu mềm (p_CNN của chữ số bubble thay vì argmax).
2. Ngưỡng ô trống `NGUONG_TRONG` chưa kiểm trên ô trống thật (bộ ảnh không có ô trống) → cần ca thử giả (xoá chữ) hoặc chụp thêm.
3. Khung ô không dò được: mã đề 12,7% ở phiếu dev (đường kẻ dính khung, ảnh C3 / 0006 ngang); cần cải tiến hoặc coi `ok_vien = False` là "cần xem" khi nối backend.
4. Bản đồ tối tính cả trang (~40 ms) → tính theo cửa sổ.
5. Suy luận NumPy + JSON chưa viết (`doc_chu_so`, Bước 8); `torch` chỉ dùng huấn luyện.
6. Xem bằng mắt lưới D002–D004, D006, D007, D009, D010.

### Phần C (20/10/2026) – đưa CNN chữ số vào hệ thống (Bước 1–4; số liệu: `data/_eval/ocr/*.json`, tái tạo bằng lệnh ghi kèm)

**Trạng thái đầu phiên:** HEAD `a83ebd3`, cây sạch, không commit mới của người khác từ 12/10, pytest 198 đạt. Chỉ dùng dev 0001–0028 + D001–D010 (5-fold theo người viết); **không đọc / không chạy 0029–0040**.

#### Bước 1 – vì sao ~54% phiếu "cần xem" (`python tools/ocr_phan_tich.py`; M2 OOF người lạ, luật đối chiếu hiện hành, τ_khop 0,5)
| Mức | Kết quả |
|---|---|
| **Cột** (504 chữ số) | chắc 456 (90,5%) · **hai kênh lệch vì CNN đọc sai 38 (7,5%)** · CNN cùng chữ số nhưng p < 0,5: 5 (1,0%) · dò ô thất bại + lệch: 3 (0,6%) · bubble không đọc được (0001 × 2): 2 (0,4%) · **bubble sai mà CNN đúng: 0** · hai kênh cùng khác nhãn: 0 |
| **Phiếu** (30/56 = 53,6% bị gắn) – nguyên nhân ưu tiên | CNN đọc sai (lệch bubble) **22** · dò ô thất bại **3** · CNN không chắc **3** · thiếu bubble **2** |
| Trường | SBD 27/56 bị gắn (21 phiếu có ≥ 1 cột lệch do CNN sai, 5 cột p thấp, 2 thiếu bubble) · mã đề 14/56 (11 lệch do CNN, 3 do dò ô) |
| Theo người viết (ảnh bị gắn) | người 1 7/16 (43,8%) · người 2 6/16 (37,5%) · **người 3 14/16 (87,5%)** · người 4 3/8 (37,5%) |
| Theo điều kiện | C1 6/14 (42,9%) · C2 6/14 (42,9%) · **C3 11/14 (78,6%)** · C4 7/14 (50,0%) |
| Dò ô (`ok_vien`) | SBD 1/336 ô không dò được (0,3%) · **mã đề 18/168 (10,7%)** – toàn ảnh C3; chỉ 3 ô trong đó bị gắn (15 ô còn lại CNN đọc đúng, khớp bubble) |

**Kết luận:** nguyên nhân gần như duy nhất là **CNN đọc sai ~8% chữ số** (mà bubble thì đúng 100% ở dev) → muốn T4 ≤ 10% dưới luật đối chiếu hiện hành thì mỗi chữ số phải đúng ≥ ~99% (0,99⁹ ≈ 91%); T3 hiện ~92%. Dò ô mã đề chỉ gây tối đa 3/56 phiếu → **không làm mục (d)** (xem nợ). Người 3 và ảnh C3 là điểm yếu (kiểu viết "7 gạch", ảnh nghiêng).

#### Bước 2 – thử nghiệm cải thiện (`python tools/ocr_cai_tien.py chay` → `bang`; cùng luật cho mọi cấu hình, τ_khop 0,5 CỐ ĐỊNH)
Tiêu chí chốt TRƯỚC khi chạy: lỗi im lặng mức trường = 0 → T4 thấp nhất → nếu khác biệt T4 không có ý nghĩa (kiểm định dấu cặp theo ảnh, p ≥ 0,05) chọn cấu hình **đơn giản hơn**. Tất cả đo trên phiếu dev 0001–0028 (56 ảnh, 504 chữ số), người lạ (OOF); CI = Clopper–Pearson 95%.

| Cấu hình | Mô tả | 1 seed (2026): T3 [CI] · T4 [CI] | 3 seed riêng: T3 · T4 | Ensemble 3 seed: T3 · T4 | Lỗi im lặng |
|---|---|---|---|---|---|
| **g0 (gốc)** | MNIST, tăng cường cũ, tinh chỉnh toàn bộ | **91,9% [89,1–94,1] · 53,6% [40–67]** | 91,9 / 92,1 / 90,9 · 53,6 / 62,5 / 60,7 | 92,9% [90,2–95,0] · 55,4% [41–69] | 0 |
| a1 | (a) tăng cường mạnh khi huấn luyện trước (xoay ±12°, co giãn 2 trục, nghiêng, độ dày nhiều kiểu, nhoè) | 92,5% [89,8–94,6] · 51,8% [38–65] | 92,5 / 92,3 / 91,3 · 51,8 / 64,3 / 53,6 | 92,5% · 62,5% [49–75] | 0 |
| a2 | a1 + sinh kiểu "1 có móc / hất", "7 có gạch ngang" (~12 k ảnh sinh từ MNIST) | 90,7% [87,8–93,1] · 60,7% [47–73] | 90,7 / 91,1 / 93,1 · 60,7 / 57,1 / 51,8 | 91,9% · 53,6% [40–67] | 0 |
| a3 | a2 + tăng cường mạnh cả lúc tinh chỉnh | 90,1% [87,1–92,5] · 64,3% [50–77] | 90,1 / 91,3 / 93,2 · 64,3 / 57,1 / 53,6 | 92,1% · 53,6% [40–67] | 0 |
| c1 | (c) huấn luyện trước MNIST + **EMNIST Digits** (240 k ảnh) | 91,3% [88,5–93,6] · 50,0% [36–64] | 91,3 / 92,7 / 93,2 · 50,0 / 57,1 / 46,4 | 93,4% [90,9–95,5] · 51,8% [38–65] | 0 |
| c2 | c1 + a3 | 91,7% [88,9–93,9] · 58,9% [45–72] | 91,7 / 90,9 / 92,7 · 58,9 / 60,7 / 58,9 | 92,9% · 58,9% [45–72] | 0 |

- Kiểm định dấu cặp (1 seed so với g0): a1 p = 1,00 · a2 0,29 · a3 0,07 · c1 0,73 · c2 0,58; ensemble: 0,22–1,00 → **không cấu hình nào khác g0 có ý nghĩa**. Dao động giữa các seed (T4 46–64% trong cùng một cấu hình) **lớn hơn** khác biệt giữa cấu hình.
- **Chọn: g0, một seed (2026)** (hoà trong nhiễu → đơn giản nhất; 2026 là seed mặc định có từ Bước 5, không chọn sau khi thấy số). Ensemble chỉ tăng T3 ~1 điểm, T4 không đổi trong nhiễu → không dùng.
- (c) EMNIST: không có trang gốc lấy nhanh – `biometrics.nist.gov/cs_links/EMNIST/gzip.zip` (562 MB) chỉ tải ~70 KB/s nên bỏ giữa chừng (SHA không so được); dùng **bản sao tệp idx của chính EMNIST Digits** trên Hugging Face `tanganke/emnist_digits` (240 000 ảnh, 24 000 / lớp – kiểm cấu trúc idx; SHA-256 ở `data/_ocr/nguon_emnist_hf/SHA.txt`: ảnh `6eb25994…2df2`, nhãn `53a1c3be…4c54`; trang HF không ghi giấy phép; dữ liệu gốc NIST SD-19, trích dẫn Cohen et al. 2017). Không đưa vào mô hình xuất.
- (d) dò ô mã đề: **không làm** (xem Bước 1: ≤ 3/56 phiếu; sửa `tim_khung` đổi mọi cache cắt ô và mọi số đo).
- **T3 ≥ 97% và T4 ≤ 10%: CHƯA ĐẠT** (T3 ≈ 92%, T4 ≈ 50–60%). Ghi nguyên trạng, không nới tiêu chí.

**Đề xuất luật đối chiếu MỀM – KHÔNG áp dụng, chờ quyết định của bạn** (`python tools/ocr_cai_tien.py luat-mem`; dev, mô hình g0 seed 2026 OOF): nhận cột khi bubble chắc và **p_CNN(chữ số bubble) ≥ τ_mềm** thay cho "argmax trùng và p ≥ 0,5". Vì dev không có ca người thi tô sai bubble (OMR đọc đúng 100%) nên "lỗi im lặng thật" luôn 0 và **không đo được rủi ro**; cột cuối là **mô phỏng**: thay chữ số bubble của một cột bằng chữ số SAI bất kỳ (9 khả năng) rồi đếm luật nhận nhầm.
| Luật | Trường nhận / 112 | T4 (ảnh gắn) | Mô phỏng 1 cột bubble sai bị nhận nhầm |
|---|---|---|---|
| hiện hành (argmax + p ≥ 0,5) | 71 | 53,6% | 20 / 2 988 = 0,67% |
| mềm τ = 0,3 | 81 | 44,6% | 49 / 3 393 = 1,44% |
| mềm τ = 0,2 | 86 | 41,1% | 62 / 3 537 = 1,75% |
| mềm τ = 0,1 | 96 | 26,8% | 130 / 3 933 = 3,31% |
| mềm τ = 0,05 | 100 | 19,6% | 209 / 4 086 = 5,12% |
| mềm τ = 0,02 | 104 | 14,3% | 332 / 4 185 = 7,93% |
Nhận xét: hạ T4 từ 54% xuống 27% phải trả bằng việc tăng gấp ~5 lần khả năng nhận nhầm khi thí sinh tô sai bubble; **kể cả τ = 0,02 cũng chưa đạt T4 ≤ 10%**. Khuyến nghị: giữ luật hiện hành; chỉ cân nhắc luật mềm sau khi có dữ liệu thật về ca tô sai bubble (hoặc cho giáo viên chọn mức nhạy).

#### Bước 3 – suy luận NumPy + JSON
- `cv_engine/ocr.py`: `nap_mo_hinh_ocr`, `du_doan_xac_suat` (NumPy: im2col qua `sliding_window_view` + einsum; ensemble nếu nhiều thành viên), `doc_chu_so(kq, layout, mo_hinh)` (cắt 9 ô trên `anh_nan`, bản đồ tối **cục bộ** thay cả trang; ô trống / quá ít mực / bôi đen / nhiều mảnh KHÔNG qua CNN, `chu_so = '?'`; `kq.ok = False` → `ValueError`), `doi_chieu_dinh_danh(omr, ocr, sbd_trong_ds, ma_de_trong_ds)` (luật Q3 nguyên vẹn; `doi_chieu_cot` thêm `loi_o`: ô không đọc được ≠ ô trống → cần xem, không nhận theo bubble).
- **`models/ocr_cnn.json`** (1,3 MB) xuất bằng `tools/xuat_ocr.py` **từ commit sạch `b75453e`**: g0, seed 2026, tinh chỉnh trên 3 872 ô trang D (5 người), T = 1,750, τ = 0,9995, δ = 0,99 (chỉ báo cáo – `cnn_chac`), τ_khop = 0,5; siêu dữ liệu: ngày, `git_head`, `git_sach = true`, seed, cấu hình, SHA-256 dữ liệu (cache cắt ô, MNIST), nhiệt độ, số đo OOF, kết quả kiểm tương đương. SHA-256 file `6d87205c…fcad5`.
- **NumPy ↔ PyTorch trên 4 376 chữ số dev: cùng nhãn 100%, chênh xác suất lớn nhất 7,2e-7** (< 1e-4; pytest dựng lại CNN torch từ chính trọng số JSON).
- **Thời gian cắt 9 ô + suy luận: trung vị 14,0 ms (max 17,6 ms) trên 12 ảnh; 16,4 ms trên 56 ảnh** (T5 ≤ 50 ms: đạt; trước đó chỉ cắt đã 47 ms vì tính bản đồ tối cả trang). Ô cắt giống cache từng byte (108/108).
- Sau khi xuất, `ocr.py` thêm 2 kiểm "ô bôi đen" (`fr_toi` > 0,30; `ti_le_muc` > 0,36). Dev (4 504 ô): `fr_toi` max 0,21, `ti_le_muc` max 0,25 → **không ô thật nào bị ảnh hưởng, số đo dev không đổi**; trọng số không đổi (commit `00e92e7` ghi nhận). Phát hiện kèm: ô bị phủ đen > 50% làm "nền = trung vị" đảo → `ink_px` sai (đọc ra '8' p 0,63) – trước đó chưa có chốt chặn.

#### Bước 4 – nối backend + giao diện
- `service.nhan_anh`: OMR → `doc_chu_so` → `doi_chieu_dinh_danh` (SBD "có trong danh sách" = `tim_sinh_vien` trên chữ số bubble; mã đề = có trong `exam_codes`; bubble có `?` → chưa kiểm được → cần xem). Trường không chắc → `can_xem` + `reasons` (`lech_bubble`, `tin_cay_thap`, `thieu_bubble`, `bubble_cx`, `o_trong_ngoai_ds`, `o_trong_chua_biet_ds`, `o_it_muc`, `khong_phai_chu_so`) → `review_queue` lý do `low_ocr_confidence` + `details.sbd_ly_do / ma_de_ly_do`. **`detected_sbd` giữ nghĩa cũ (đọc từ bubble)**; gợi ý của CNN chỉ nằm ở từng cột (`handwriting`). `sbd_confidence` = min(độ tin cậy bubble, p CNN) theo cột.
- 9 dòng `ocr_digits` mỗi phiếu (`predicted_digit`, `confidence`, `top_k`, `crop_image_path`) + 9 PNG ô cắt trong `storage/ocr/…`; `answer_sheets.ocr_model_id` + `ml_models` (`ocr_digit`, `is_active = FALSE`); `sua_dinh_danh` ghi `corrected_digit` (chỉ khi độ dài khớp 6 / 3). **Không ALTER, không migration mới** (cột đã có sẵn). Thiếu `OCR_MODEL` (`models/ocr_cnn.json`) thì backend không khởi động (không lặng lẽ quay về chỉ-bubble).
- API: `GET /sheets/{id}` thêm `bubble` + `handwriting` (`pos`, `chu_so`, `p`, `top_k`, `o_trong`, `loi_o`, `ok_vien`, `corrected`, `has_crop`) từng cột và `reasons` từng trường; `GET /sheets/{id}/digits/{field}/{pos}/image` (PNG); `/health` có `ocr_model`.
- Giao diện: **F3** bảng hai kênh (ô tô ↔ ảnh ô viết tay ↔ chữ số máy đọc + %, hàng "GV đã chốt", lý do); **F4** hai kênh cạnh nhau, **không điền sẵn** khi trường cần xem, nút "Lấy theo ô tô" / "Lấy theo chữ viết tay" (chỉ điền ô nhập, giáo viên vẫn phải bấm Lưu).
- **Kiểm đầu-cuối `tools/kiem_backend_dau_cuoi.py` (56 ảnh dev, CSDL thật, giao dịch ROLLBACK): 0 câu chấm sai không cờ (1 672 câu chắc), 0 SBD sai im lặng, 0 mã đề sai im lặng** (nay so với chữ VIẾT TAY thật), điểm chính thức sau giáo viên **= điểm tính độc lập 56/56**; ảnh giả 44 từ chối đúng, 27 nhận đúng, 0 lỗi im lặng; ảnh có SBD hoặc mã đề cần xem **26/56 (46,4%)** (SBD 23, mã đề 14). Mô hình xuất đã tinh chỉnh trên cả 5 người ở trang D nên con số này lạc quan hơn "người lạ" (53,6%).
- **Đo độc lập `python tools/eval_ocr.py run --tap dev`** (chỉ gọi `ocr.py` + `omr.py`): T3 **92,7%** (467/504, CI 90,0–94,8) · T4 **46,4%** (26/56, CI 33,0–60,3) · **lỗi im lặng mức trường 0** (SBD 33 trường nhận, mã đề 42; CP95% trên số trường nhận ≤ 4,8%) · lý do cần xem: `lech_bubble` 31, `tin_cay_thap` 5, `thieu_bubble` 2 · theo người viết T4: 1 43,8% · 2 37,5% · **3 68,8%** · 4 25,0%; theo điều kiện: C1 35,7% · C2 35,7% · **C3 78,6%** · C4 35,7%.
- Thử giao diện bằng kỳ thi **[THU] mới (exam_id 509, 6 phiếu dev: 0001_C1, 0002_C2, 0010_C3, 0019_C4, 0014_C3, 0006_C3)**; `[DEMO]` / `[DEMO-2]` không đụng. Tôi không có trình duyệt trong phiên này → đã kiểm hiển thị bằng cách chạy các hàm dựng HTML của `app.js` với JSON thật của API (node) và gọi thật các endpoint; **chưa nhìn bằng mắt trên trình duyệt** (cần bạn xem).
- **pytest 220 đạt** (~67 s): thêm `test_ocr_suy_luan.py` (7), `test_backend_ocr.py` (8), `test_eval_ocr.py` (5); các test OMR cũ dùng `ocr_khop` (CNN giả khớp bubble giả) để vẫn kiểm đường chấm / chốt điểm.

### Nợ kỹ thuật mới (Phần C)
1. **T3 ≥ 97% / T4 ≤ 10% chưa đạt**: nguyên nhân là CNN sai ~8% chữ số (người 3, ảnh C3); (a)–(c) không cải thiện có ý nghĩa. Hướng còn lại: nhiều người viết hơn / dữ liệu thật (human-in-the-loop từ `corrected_digit`), mô hình mạnh hơn, hoặc luật mềm có kiểm soát (cần dữ liệu ca tô sai bubble).
2. Luật mềm: chưa có tập ca "tô sai bubble" thật để đo rủi ro (chỉ mô phỏng).
3. **`NGUONG_TRONG` / `NGUONG_IT_MUC` / ngưỡng bôi đen** chưa kiểm trên ô trống thật (dev 0 ô trống; test giả bằng xoá chữ / nhiễu); ngưỡng "bôi đen" đặt ≈ 1,4 × max dev.
4. Dò khung ô mã đề C3 (10,7% ô không dò được): chưa sửa `tim_khung`.
5. Mô hình xuất tinh chỉnh trên cả 5 người ở trang D ⇒ val / test (0029–0040 do người 4, 5) chỉ đo "nét đã gặp"; T, τ, δ chọn từ OOF (người lạ) nên hơi bi quan cho dev, lạc quan cho val / test về mức nét.
6. `ocr_digits` lưu 9 PNG / phiếu trên đĩa (không dọn dẹp); `corrected_digit` chỉ ghi khi độ dài SBD = 6, mã đề = 3.
7. EMNIST lấy từ bản sao Hugging Face (không đối chiếu SHA với NIST).
8. Giao diện chưa kiểm bằng trình duyệt trong phiên này; F4 chưa cho giáo viên sửa từng chữ số riêng (chỉ nhập cả SBD / mã đề).
9. Tên cột `OChuSo` thêm `fr_toi` (mặc định 0,0) – cache `data/_ocr/cat` (làm trước khi có trường này) vẫn dùng được.

## 11. ĐĂNG KÝ TRƯỚC – đánh giá kiểm tra giữ lại **val 0029–0034** (viết 20/10/2026; CHƯA CHẠY)

> Chỉ chạy khi người dùng gõ **"chạy val"**. Lệnh: `python tools/eval_ocr.py run --tap val --xac-nhan-val --xem` (từ `smart_exam_db/`). Chạy **MỘT lần**; mọi lần chạy lại sau khi sửa phải ghi vào mục này kèm lý do. Không chỉnh mô hình / ngưỡng / luật sau khi thấy số val.

| Hạng mục | Giá trị đã khoá |
|---|---|
| **Mã** | commit **`b3d0ede7099d9bf9ec79514aa43af5a323805028`** (`cv_engine/ocr.py`, `cv_engine/omr.py`, `tools/eval_ocr.py`, `backend/`). Các commit sau chỉ được đổi tài liệu (`docs/`, `CLAUDE.md`); kiểm trước khi chạy: `git diff b3d0ede HEAD --stat -- smart_exam_db/cv_engine smart_exam_db/models smart_exam_db/tools smart_exam_db/backend smart_exam_db/answer_sheet` phải rỗng |
| Mô hình chữ số | `models/ocr_cnn.json`, SHA-256 `6d87205c83a29fccc4eb450f0aec0c9d51ba56e1bb141664060041ab0f2fcad5`, xuất từ commit sạch `b75453e` (g0, seed 2026, 1 thành viên, T = 1,750) |
| Mô hình OMR | `models/omr_m1.json`, SHA-256 `6ddee713428c2ab6a9aa7894313a33e173011c504d432338aebe0b60f3c6cf33` |
| Mẫu phiếu / layout | `answer_sheet/output/layout.json` SHA-256 `a35ccb7e259f5f7a30355d85d79ba4ef267a0d465f29c09b8fd05906cfc0ecbd`; `phieu_trang_300dpi.png` `7b7db1a95344564a95460af9c076ed74833e75583fc117028f83bb86e1bbf30f` |
| Luật đối chiếu | **Q3 nguyên vẹn**: `doi_chieu_cot` (argmax CNN trùng bubble và p ≥ **τ_khop = 0,5**; ô viết tay trống chỉ nhận theo bubble khi bubble chắc VÀ SBD / mã đề có trong danh sách; `loi_o` → cần xem) – **KHÔNG dùng luật mềm** |
| Ngưỡng ô | `NGUONG_TRONG` 30 · `NGUONG_IT_MUC` 100 · `NGUONG_TI_LE_MUC` 0,36 · `NGUONG_N_TP` 7 · `NGUONG_FR_TOI` 0,30 (trong `ocr.py`) |
| Dữ liệu | phiếu 0029–0034 × 2 ảnh = **12 ảnh, 108 chữ số, 12 SBD + 12 mã đề**; nhãn SBD / mã đề VIẾT TAY từ `data/ground_truth.csv` (chỉ dòng 29–34 được đọc). SBD / mã đề coi là "có trong danh sách" (kỳ thi mô phỏng đủ thí sinh). Người viết: 0029–0032 = người 4 (8 ảnh), 0033–0034 = người 5 (4 ảnh) |
| **Tiêu chí ĐẠT (bắt buộc)** | **lỗi im lặng mức trường = 0** cho cả SBD và mã đề (trường được nhận tự động mà ≠ chữ viết tay thật), `tu_choi` = 0 ảnh hợp lệ; ảnh bị từ chối thì ghi lý do. Báo CP 95% của số lỗi im lặng trên số trường nhận |
| Tiêu chí mục tiêu (báo, không phải điều kiện ĐẠT) | T3 ≥ 97% chữ số; T4 ≤ 10% ảnh cần xem ở SBD / mã đề; thời gian `doc_chu_so` ≤ 50 ms |
| **Dự đoán đăng ký trước** (để so, không chỉnh theo kết quả) | T3 ≈ 92–95% (người 4 dễ: dev 98,6–100%; người 5 dễ nhất ở trang D); **T4 ≈ 25–55% → không đạt ≤ 10%**; lỗi im lặng 0; thời gian ≈ 15 ms |
| Hạn chế phải nêu | val chỉ 6 phiếu / 12 ảnh (2 ảnh cùng phiếu không độc lập); mô hình đã thấy nét người 4 và 5 ở trang D (D007–D010) ⇒ chỉ đo "nét chữ đã gặp"; OMR chưa từng thấy val; CP lỗi im lặng 0 / ~15–20 trường nhận ≈ 15–20% (rất rộng) |
| Xem bằng mắt | `--xem` ghi `data/_eval/ocr/xem_val.html`: mỗi ảnh một hàng 9 ô (ảnh ô viết tay, chữ số ô tô, chữ số máy đọc + %, ô cần xem tô vàng). Người dùng đọc ảnh ô viết tay **trước**, rồi mới đối chiếu cột "máy đọc"; ghi lại mọi ô máy đọc sai mà không tô vàng (= lỗi im lặng mức chữ số, nên chỉ chấp nhận được nếu bubble bắt được) và mọi ô nghi nhãn `ground_truth` sai (liệt kê, KHÔNG tự sửa) |
| Sau khi chạy | ghi số liệu + CP + bảng theo người / điều kiện vào mục 10 (Phần C); nếu lỗi im lặng > 0: dừng, phân tích nguyên nhân, không sửa trong cùng phiên chạy |
