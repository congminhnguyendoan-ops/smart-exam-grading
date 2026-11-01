# Lệnh AD – Huấn luyện lại CNN chữ số bằng EMNIST Digits + ô phiếu giả (01/11/2026, nhánh `hoan-thien`)

Mục tiêu: thử xem EMNIST Digits + "ô phiếu giả" có làm CNN đọc chữ số tốt hơn mô hình hiện tại (`models/ocr_cnn.json`, cấu hình `g0_goc`,
seed 2026, MNIST → tinh chỉnh trang D001–D010) không. **Không thay mô hình thật** trong lệnh này; ứng viên (nếu có) chỉ nằm ở
`data/_eval/ad/ocr_cnn_ung_vien.json`.

## Bước 0 – Bối cảnh mã hiện có (tóm tắt)

- Đường chạy thật một ô (`cv_engine/ocr.py`): ảnh đã nắn `anh_nan` → `tim_khung` (dò viền in sẵn) → `cat_o`: cắt vào trong khung
  `NUT_VIEN` = 7 px → bản đồ mực `(nền − xám) / (0,5·nền)` (nền = trung vị ô) → bỏ hạt bẩn < 10 px, bỏ mảnh viền sát cạnh →
  `ve_mnist`: bbox mực co về **20×20** giữ tỉ lệ, trọng tâm đặt vào (14, 14) của 28×28, nền 0 / nét 255 → `_hop_ly_o` (ô trống, ít mực,
  bôi đen, nhiều mảnh KHÔNG qua CNN) → CNN (chia 255, Conv16–Conv32–Dense64–10, 105 866 tham số) → softmax(z / T).
- Huấn luyện cũ (`tools/huan_luyen_ocr.py`, `tools/ocr_cai_tien.py`, `tools/xuat_ocr.py`): tiền huấn luyện MNIST 55 000 ảnh (bỏ 5 000 val nội bộ,
  hoán vị seed 2026), 10 epoch, Adam 2e-3 + cosine, tăng cường cơ bản; tinh chỉnh toàn bộ trên ô trang D của 4 người (lr 3e-4, 6 epoch,
  lô 64), đo trên người thứ 5 (5 fold = 5 người viết, OOF). Nhiệt độ T chọn trên OOF trang D. Ô phiếu dev 0001–0028 (56 ảnh) chỉ để ĐO
  (phiếu của người k đọc bằng mô hình bỏ người k).
- **EMNIST Digits đã được thử ở Tuần 6 Phần C** (`c1_emnist`, `c2_emnist_aug`): không khác baseline có ý nghĩa. Lần đó EMNIST đưa vào
  THÔ (chuyển vị), không qua `ve_mnist` – EMNIST chuẩn hoá khác MNIST (chữ số ~24 px, căn bbox). Lệnh AD khác ở hai điểm: EMNIST qua
  đúng `ve_mnist`, và thêm ô phiếu giả cho qua đúng `cat_o`.

## Bước 1 – EMNIST Digits

`python tools/ad_nap_emnist.py` → `data/nguon_ngoai/emnist_digits.npz` (chỉ đọc 4 tệp idx digits trong zip, không giải nén). Train 240 000
(24 000 / lớp), test 40 000 (4 000 / lớp). Đã chuyển vị về đúng chiều MNIST (xem `data/_eval/ad/emnist_mau.png`); trùng từng byte với bản
Hugging Face dùng ở Tuần 6. Bản `x_train_chuan` = qua `ocr.ve_mnist`.

## Bước 2 – Ô phiếu giả

`python tools/ad_sinh_o_gia.py that | so-sanh | sinh`. Vẽ chữ số (MNIST 55 000 + EMNIST train) thành ô 300 DPI có viền, ô bên cạnh, nền giấy +
vân, bóng, sáng / gamma, nhoè Gauss / chuyển động, nhiễu, JPEG, xoay / nghiêng, dịch lệch, lấn viền, nét đứt, nét mảnh / dày, rồi cho qua
**đúng** `ocr.cat_o` + `ocr._hop_ly_o`. Tham số chỉnh CHỈ theo trang D001–D010 (dữ liệu huấn luyện), không nhìn ô phiếu.
Tham số cuối: hằng `TS` trong `tools/ad_sinh_o_gia.py`. Lần chỉnh: (1) nền giả quá tối / phẳng, viền quá nhạt, nét quá dày, kẻ ô bên cạnh
sai; (2) viền 5–6 px lọt vào vùng cắt → nhiễu nền giả có đuôi dài (p75 14 so với 6,8) → viền 3–4 px; (3) nhoè quá mạnh, chữ quá bé →
giảm nhoè, bỏ chữ cao < 28 px. Lệch còn lại: nét giả dày hơn ở đuôi (p95 10,7 so với 7,7 px), chữ giả hơi rộng (trung vị 36 so với 30 px).

## Bước 3 – TIÊU CHÍ CHỐT TRƯỚC KHI HUẤN LUYỆN (01/11/2026, commit chứa tệp này có trước mọi lần huấn luyện của lệnh AD)

**Baseline** = quy trình `g0_goc` (MNIST → tinh chỉnh), dựng lại bằng mã cũ. **Ứng viên duy nhất `ad1`** = tiền huấn luyện trên MNIST 55 000 +
EMNIST Digits train 240 000 (qua `ve_mnist`) + ô giả `data/_eval/ad/o_gia.npz`, 4 epoch (như `c1_emnist`), Adam 2e-3 + cosine, tăng cường
cơ bản; tinh chỉnh GIỐNG HỆT baseline. Không thử thêm cấu hình khác để chọn.

Cả hai bên: 5 fold leave-one-writer-out (giữ ra 1 trong 5 người), **3 seed (2026, 1, 2)**, mỗi seed một mô hình đơn (không ensemble – mô hình
thật là 1 seed). Xác suất đã hiệu chỉnh nhiệt độ T (chọn trên OOF trang D của chính seed đó, như cũ). Chỉ đo trên Ô THẬT của người bị giữ ra.

Ứng viên chỉ được **đề nghị thay** nếu ĐỒNG THỜI:

1. **Độ đúng chữ số**: trung bình 5 người (macro) của độ đúng trên ô trang D (ô dò được khung) của người bị giữ ra, trung bình 3 seed,
   **tăng ≥ 1,0 điểm phần trăm** so với baseline.
2. **Sai mà tự tin**: số chữ số đọc SAI với p ≥ 0,5 (= `tau_khop`, ngưỡng nhận của luật đối chiếu SBD / mã đề trong `cv_engine/ocr.py`),
   đếm tuyệt đối trên ô thật của người bị giữ ra (trang D + ô có mực trên phiếu dev 0001–0028), cộng 3 seed: **ứng viên ≤ baseline**.
3. **Cần xem**: tỉ lệ cột chữ số SBD / mã đề (56 ảnh phiếu dev × 9 cột) bị gắn "cần xem" sau đối chiếu bubble (`ocr.doi_chieu_cot`, luật Q3,
   τ_khop 0,5, SBD / mã đề coi như có trong danh sách), trung bình 3 seed: **ứng viên ≤ baseline**.

Thiếu một trong ba → **"không đạt, giữ mô hình cũ"**. Số phụ (không quyết định): độ đúng ô phiếu dev, theo từng người, ma trận nhầm lẫn
(8↔6, 1↔7, 0↔6), tỉ lệ ẢNH có SBD / mã đề cần xem (T4), lỗi im lặng mức trường (bắt buộc 0), số liệu riêng seed 2026.

Giới hạn biết trước: chỉ 5 người viết; SBD / mã đề trên phiếu 0001–0040 do chính 5 người này viết, nên số trên phiếu là "người lạ" chỉ trong
nghĩa OOF (cùng phong cách với trang D của họ đã bị giữ ra) – vẫn lạc quan so với người dùng thật. Không đọc phiếu val 0029–0034 / test 0035–0040.

## Bước 4–6 – Kết quả

(điền sau khi chạy – mục dưới)
