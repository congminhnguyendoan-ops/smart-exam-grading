# Tiêu chí so sánh CNN với các thuật toán khác trên chữ số (lệnh AI) – ĐĂNG KÝ TRƯỚC

Ngày 04/11/2026, nhánh `hoan-thien`. Tệp này được commit **riêng, trước mọi lần chạy** công cụ `tools/ai_so_sanh_thuat_toan.py`
(công cụ chưa tồn tại lúc commit). Không đổi tiêu chí sau khi thấy số. Không đổi mô hình triển khai (`models/ocr_cnn.json`) dù kết quả thế nào.

Mục đích: trả lời "vì sao dùng CNN" bằng số liệu trung thực. Nếu CNN không phải thuật toán đúng nhất thì ghi rõ thuật toán nào đúng hơn và chênh bao nhiêu.

## 1. Dữ liệu và biểu diễn đầu vào (chung cho mọi thuật toán)

- Mọi thuật toán nhận **cùng ảnh 28×28** (nền 0, nét 255, chuẩn hoá kiểu MNIST: bbox → 20×20, trọng tâm → 28×28 như `cv_engine.ocr.ve_mnist`).
  Mô hình scikit-learn dùng vectơ 784 điểm ảnh chia 255; CNN / MLP dùng tensor [1, 28, 28] chia 255. **Không** dùng đặc trưng thủ công (HOG đã đo ở lệnh D).
- MNIST: train 60 000 → **55 000 huấn luyện + 5 000 kiểm định nội bộ** (hoán vị seed 2026, đúng tập tiền huấn luyện CNN cũ: `ocr_cai_tien.du_lieu_truoc("mnist")`); test 10 000.
- EMNIST Digits test **40 000** (`data/nguon_ngoai/emnist_digits.npz`, trích từ `emnist-digits-test-*-ubyte` trong zip ở lệnh AD). Bản **chính** = `x_test_chuan`
  (qua `ve_mnist`, cùng cách chuẩn hoá với ô thật); bản thô (chỉ chuyển vị) báo phụ. EMNIST train KHÔNG dùng.
- Ô chữ số thật: trang **D001–D010** (5 người viết × 2 trang × 400 ô), bộ đệm `data/_ocr/cat/anh_nan.npz`; chỉ ô `ok_vien = 1` (**3 872 ô**), đúng `huan_luyen_ocr.tap_do("anh_nan")`.
  Phụ: 504 ô SBD / mã đề trên phiếu dev 0001–0028 (người 1–4). **Không đọc** phiếu val 0029–0034, test 0035–0040, đợt 2, giấy thật AG.

## 2. Thuật toán và siêu tham số (lưới chốt trước)

| # | Thuật toán | Cài đặt | Lưới chọn | Ngẫu nhiên? |
|---|---|---|---|---|
| 1 | Logistic regression (softmax) trên điểm ảnh | `sklearn LogisticRegression` lbfgs, max_iter 300 | C ∈ {0,01; 0,1; 1} | không (1 lần chạy) |
| 2 | k-NN | `KNeighborsClassifier`, Euclid, trọng số đều | k ∈ {1, 3, 5, 7, 9} | không |
| 3 | SVM nhân RBF | `SVC(kernel="rbf", gamma="scale")` | C ∈ {1; 10} | không |
| 4 | Random Forest | `RandomForestClassifier(n_estimators=300, max_features="sqrt", n_jobs=-1)` | min_samples_leaf ∈ {1; 3} | **có – 3 seed** |
| 5 | MLP một lớp ẩn | PyTorch: 784 → 128 (ReLU, Dropout 0,3) → 10 (**101 770 tham số**, ≈ cỡ CNN) | không (cố định, huấn luyện GIỐNG HỆT CNN) | **có – 3 seed** |
| 6 | **CNN hiện tại** | Conv16–Conv32–Dense64 (**105 866 tham số**), `huan_luyen_ocr.tao_cnn` | không (đúng quy trình `g0_goc`) | **có – 3 seed** |

Seed: 2026, 1, 2 (như lệnh AD). Mô hình không ngẫu nhiên chạy một lần (seed 2026 cho mẫu con nếu có).
Chọn siêu tham số **chỉ** trên dữ liệu kiểm định nằm trong tập huấn luyện; không bao giờ nhìn người viết bị giữ ra hay tập test.

**Giới hạn thời gian / mẫu con (chốt trước):** SVM ở E1 huấn luyện trên **mẫu con 20 000** ảnh của 55 000 (phân tầng theo lớp, seed 2026). Ở E2(b), MỌI mô hình
scikit-learn dùng **mẫu con MNIST 10 000** (phân tầng, seed 2026) + ô thật (để kiểm định lồng chạy được); CNN / MLP tiền huấn luyện trên đủ 55 000.
Nếu một lần `fit` vượt **20 phút**, công cụ ghi lại, và lần chạy đó coi là "quá giới hạn"; báo cáo ghi rõ (không thay bằng cấu hình khác để chọn).

## 3. Thí nghiệm

**E1 – dữ liệu chuẩn.** Huấn luyện trên MNIST 55 000 (SVM: mẫu con 20 000), chọn siêu tham số trên 5 000 kiểm định nội bộ, đo trên MNIST test 10 000
và EMNIST Digits test 40 000. CNN: mô hình tiền huấn luyện `pre_mnist_co_ban_{seed}.pt` (đúng bước 1 của quy trình triển khai; 10 epoch, Adam 2e-3 + cosine,
tăng cường cơ bản). MLP: cùng quy trình đó.

**E2 – QUAN TRỌNG NHẤT, dữ liệu thật của nhóm: leave-one-writer-out** (5 fold = 5 người viết; mô hình học 4 người, đo người thứ 5).
- **E2(a)** chỉ ô thật của 4 người.
  - scikit-learn: chọn siêu tham số bằng leave-one-writer-out **lồng** trong 4 người (độ đúng macro), rồi huấn luyện lại trên cả 4 người.
  - CNN / MLP: huấn luyện từ đầu, cấu hình cố định (không chỉnh): Adam 2e-3 + cosine, lô 64, **30 epoch**, tăng cường cơ bản.
- **E2(b)** MNIST + ô thật của 4 người.
  - CNN / MLP: tiền huấn luyện MNIST 55 000 (E1) rồi tinh chỉnh toàn bộ trên ô thật của 4 người (lr 3e-4, 6 epoch, lô 64 – đúng `ocr_cai_tien.oof`).
    CNN E2(b) dựng lại bằng mã cũ và phải trùng bộ đệm `data/_ocr/cap/oof_g0_goc_{seed}.npz` (chênh logit ≤ 1e-4), không thì dừng.
  - scikit-learn: gộp mẫu con MNIST 10 000 + ô thật của 4 người; **trọng số ô thật w ∈ {1; 5; 20}** (k-NN: nhân bản ô thật w lần vì k-NN không có trọng số mẫu)
    chọn bằng leave-one-writer-out lồng trong 4 người (macro); siêu tham số giữ giá trị đã chọn ở E1.

## 4. Chỉ số

Đo trên ô trang D của người bị giữ ra (chính), và ô phiếu dev của người đó (phụ).
1. **Độ đúng trung bình theo người viết (macro 5 người)**, trung bình qua 3 seed (mô hình ngẫu nhiên), **± độ lệch chuẩn giữa 5 người**; độ đúng từng người;
   độ lệch chuẩn giữa seed (phụ).
2. **Sai mà tự tin**: đọc sai với xác suất lớn nhất ≥ 0,5 (= `tau_khop` của luật đối chiếu SBD / mã đề), cộng 3 seed (mô hình không ngẫu nhiên: ×1, ghi rõ).
   Xác suất **đã hiệu chỉnh nhiệt độ** cho MỌI thuật toán theo đúng cách của CNN hiện tại: p = softmax(z / T), T ∈ [0,5; 6] cực tiểu NLL (`ocr_do_luong.chon_nhiet`) trên
   toàn bộ OOF trang D của chính mô hình / seed đó. z: CNN / MLP = logit; LR = log xác suất; SVM = `decision_function` (ovr); RF, k-NN = log(p + 1e-6).
   (E1: T chọn trên 5 000 kiểm định nội bộ MNIST.)
3. **Ma trận nhầm lẫn** (E2(b), cộng 3 seed) và các cặp nhầm hay gặp.
4. **Kích thước mô hình trên đĩa**: scikit-learn = `pickle` của mô hình E2(b) (người 1 giữ ra, seed 2026); CNN / MLP = trọng số float32 (và tệp JSON triển khai cho CNN).
5. **Thời gian suy luận mỗi ô trên CPU**: trung vị 300 lần gọi một ô (lô 1), cùng máy; CNN đo bằng bản NumPy triển khai (`cv_engine.ocr`), MLP bằng NumPy; scikit-learn bằng `predict_proba` / `decision_function`.
6. **Cài được bằng NumPy thuần không** (đánh giá định tính: LR, MLP, CNN có; k-NN có nhưng phải mang theo toàn bộ dữ liệu huấn luyện; SVM có, cần vectơ hỗ trợ; RF có thể nhưng phải tự viết duyệt cây).

## 5. Quy tắc kết luận (chốt trước)

- **(R1)** CNN được coi là **hợp lý về độ đúng** nếu trên **E2(b)** độ đúng macro (TB 3 seed) **không thấp hơn thuật toán tốt nhất quá 1,0 điểm phần trăm**.
  Nếu không, báo cáo nêu thẳng thuật toán nào đúng hơn và chênh bao nhiêu. Kèm kiểm định dấu cặp theo ô (phụ, không quyết định).
- **(R2)** Kích thước và tốc độ chỉ là **lý do phụ**; không được dùng để thay R1 (không "CNN thua về độ đúng nhưng thắng vì nhỏ / nhanh" trong kết luận R1).
- E1, E2(a), sai mà tự tin, phiếu dev: chỉ báo cáo, không quyết định.
- Chạy **một lần** theo đúng tiêu chí này. Lỗi lập trình được sửa thì chạy lại toàn bộ và ghi lại trong báo cáo.

## 6. Giới hạn biết trước

- Chỉ **5 người viết** → độ lệch chuẩn giữa người lớn; chênh < 1 điểm khó phân biệt với nhiễu.
- SBD / mã đề trên phiếu 0001–0040 do **chính 5 người này** viết → số trên phiếu (kể cả OOF) lạc quan so với người dùng thật.
- MNIST và EMNIST là **ảnh scan sạch**, khác ảnh chụp điện thoại; E1 không đại diện cho hệ thống.
- CNN có quy trình đã được chọn ở Tuần 6 trên chính dữ liệu trang D (chọn cấu hình đơn giản nhất vì các thay đổi không có ý nghĩa) → có thể hơi lợi cho CNN.
  Ngược lại CNN / MLP ở E2(a) không được chỉnh siêu tham số (bất lợi cho chúng). Mẫu con MNIST 10 000 ở E2(b) có thể bất lợi cho scikit-learn.
- Nhiệt độ T chọn trên toàn bộ OOF (gồm người bị giữ ra) – giống quy trình CNN hiện tại, áp như nhau cho mọi thuật toán; hơi lạc quan cho chỉ số "sai mà tự tin".
