# Tiêu chí so sánh MỞ RỘNG CNN với các thuật toán khác – mức ô và mức hệ thống (lệnh AK) – ĐĂNG KÝ TRƯỚC

Ngày 06/11/2026, nhánh `hoan-thien`. Tệp này được commit **riêng, trước mọi lần chạy** công cụ `tools/ak_so_sanh_mo_rong.py` (công cụ chưa tồn tại lúc commit).
Không đổi tiêu chí sau khi thấy số. Không đổi mô hình triển khai (`models/ocr_cnn.json`), tệp đóng băng, mã hệ thống, CSDL dù kết quả thế nào.

Mục đích: chỉ ra CNN có phải lựa chọn tốt nhất **cho hệ thống này trong tập thuật toán đã thử** theo tiêu chí đặt trước. **Không** tuyên bố "tối ưu tuyệt đối".
Nếu có thuật toán đúng hơn CNN thì ghi đúng tên và độ chênh.

Kế thừa nguyên văn giao thức lệnh AI (`docs/tieu_chi_so_sanh_thuat_toan.md`, commit `253a4b5`): cùng ảnh 28×28 (`cv_engine.ocr.ve_mnist`), cùng chia 5 người viết
(leave-one-writer-out), cùng seed (2026, 1, 2), cùng mẫu con (MNIST 10 000 cho scikit-learn ở E2b; SVM E1 20 000), cùng trọng số ô thật w ∈ {1; 5; 20} chọn lồng,
cùng hiệu chỉnh nhiệt độ T (cực tiểu NLL trên toàn bộ OOF trang D của chính mô hình / seed đó), cùng τ_khop = 0,5.

## 1. Tập thuật toán (R3 xét cả 12)

6 thuật toán cũ giữ nguyên (LR, k-NN, SVM RBF, Random Forest, MLP, CNN hiện tại). **Mất bộ đệm `data/_eval/ai/tam/`** (đã xoá bằng `don` sau lệnh AI) nên
logit từng ô của 6 thuật toán này **chạy lại bằng đúng mã cũ** (`ai_so_sanh_thuat_toan`, cùng seed); kết quả mới phải **trùng** số macro E2b đã ghi ở
`data/_eval/ai/ket_qua.json` (|chênh| ≤ 0,05 điểm; CNN phải trùng bộ đệm `oof_g0_goc`, chênh logit ≤ 1e-4). Không trùng → dừng và báo.

6 thuật toán MỚI (siêu tham số chốt ở đây; chọn trong lưới chỉ bằng 5 000 mẫu kiểm định MNIST nội bộ ở E1, và w ở E2b bằng kiểm định lồng; không nhìn người bị giữ ra):

| # | Thuật toán | Cài đặt | Lưới | Ngẫu nhiên? |
|---|---|---|---|---|
| 7 | Decision Tree | `DecisionTreeClassifier(criterion="gini")` | max_depth ∈ {10; 20; None} | có – 3 seed |
| 8 | Naive Bayes Gaussian | `GaussianNB` trên điểm ảnh /255 | var_smoothing ∈ {1e-9; 1e-3; 1e-1} | không |
| 9 | HistGradientBoosting | `HistGradientBoostingClassifier(max_iter=100, learning_rate=0.1, max_leaf_nodes=31, early_stopping=False)` | không (cố định) | không |
| 10 | HOG + SVM RBF | HOG của OpenCV (`cv2.HOGDescriptor`: cửa sổ 28, block 14, bước block 7, cell 7, 9 bin → 324 chiều) rồi `SVC(rbf, gamma="scale")` | C ∈ {1; 10} | không |
| 11 | LeNet-5 | PyTorch: Conv6 5×5 (pad 2) – pool – Conv16 5×5 – pool – FC120 – FC84 – FC10, ReLU, **61 706 tham số**; huấn luyện GIỐNG HỆT CNN (tiền huấn luyện MNIST 10 epoch Adam 2e-3 + cosine, tinh chỉnh lr 3e-4, 6 epoch, lô 64) | không | có – 3 seed |
| 12 | CNN sâu | PyTorch: [Conv32–Conv32–pool]–[Conv64–Conv64–pool] (3×3, pad 1, ReLU) – Dense128 (Dropout 0,3) – 10; ~**0,47 triệu tham số**; quy trình huấn luyện như trên | không | có – 3 seed |

Chỉ chạy **E1** (chọn siêu tham số) và **E2b**; **không** chạy E2a cho thuật toán mới (không cần cho R3 / R4). PyTorch chỉ dùng trong `tools/`; `cv_engine/` không đổi.
Thuật toán nào không chạy được (lỗi, quá 20 phút một lần `fit`) thì **ghi tên + lý do** vào báo cáo, không bỏ im lặng và không thay cấu hình khác để chọn.
Nếu tổng thời gian của một thuật toán vượt 30 phút: dừng, báo, không cắt giảm âm thầm.

## 2. R3 – mức ô (E2b theo người viết)

Độ đúng macro 5 người (TB 3 seed với thuật toán ngẫu nhiên) trên ô trang D của người bị giữ ra.
**R3 đạt** nếu CNN hiện tại **không thấp hơn thuật toán tốt nhất trong 12 quá 1,0 điểm phần trăm.** Không đạt → nêu thuật toán nào đúng hơn và chênh bao nhiêu.
Kèm phụ (không quyết định): ± SD giữa 5 người, sai mà tự tin (p ≥ 0,5), kiểm định dấu cặp theo ô CNN so với thuật toán đúng nhất khác.

## 3. R4 – mức hệ thống (thay bộ đọc chữ số, giữ nguyên phần còn lại)

Thay riêng **bộ đọc chữ số viết tay** bằng từng thuật toán; kênh bubble (OMR) và luật đối chiếu hai kênh **giữ nguyên** (`ocr.doi_chieu_cot`, `ocr.doi_chieu_truong`, τ_khop = 0,5).
Xác suất của mỗi thuật toán = softmax(z / T) như mục đầu. Đơn vị phân tích: **trường** (SBD 6 chữ số, mã đề 3 chữ số) của một ảnh.

Các chỉ số (mỗi thuật toán, cộng / TB theo seed như AI):
1. **Đúng cả chuỗi (kênh viết tay một mình)**: argmax của thuật toán ở MỌI ô của trường đều bằng chữ số viết. **Đây là chỉ số quyết định R4.** Báo riêng SBD (6), mã đề (3) và gộp.
2. Sau đối chiếu hai kênh: số trường **nhận** (chắc, và trường nằm trong danh sách), trong đó **sai mà không cờ** (nhận nhưng giá trị ≠ chữ số viết), số trường **cần xem**, và trong số đó **cờ thừa** (cần xem dù giá trị đúng).
3. Ô cắt bằng `doc_chu_so` mà hệ thống không đưa vào bộ đọc (`o_trong`, `loi_o`) được xử lý **như nhau cho mọi thuật toán** (giữ nguyên cờ của hệ thống; ô đó tính là "chưa đọc" ở chỉ số 1).

**(a) 504 ô SBD / mã đề của phiếu dev 0001–0028** (56 ảnh × 9 ô = 56 SBD + 56 mã đề = 112 trường). Logit = OOF E2b (người viết bị giữ ra; ô phiếu chưa bao giờ nằm trong huấn luyện của fold đó
và phiếu không dùng để huấn luyện). Kênh bubble = `data/_ocr/omr_dev.json` (đọc OMR đã có). Dev không có ô trống (504/504 `trong = 0`). `trong_danh_sach = True` (dev: SBD / mã đề thật nằm trong danh sách).

**(b) Ảnh giấy thật AG: 13 ảnh × 9 ô = 117 ô = 26 trường** (`data/anh_that_ag/T01…T10` + `_kho`), **nếu còn đủ dữ liệu**: ảnh còn, cắt ô được bằng `preprocess` + `ocr.doc_chu_so`, nhãn từ
`data/_eval/ag/kich_ban.json` (`sbd`, `ma_de`, `thieu_bubble`). Mô hình: CNN = **mô hình triển khai** `models/ocr_cnn.json`; các thuật toán khác **huấn luyện lại trên MNIST + trang D001–D010 của cả 5 người**
(siêu tham số = lựa chọn E1; w = giá trị được chọn nhiều nhất qua 5 fold E2b, hoà → w nhỏ hơn; mạng nơ-ron: tiền huấn luyện + tinh chỉnh toàn bộ như E2b), T = T của OOF trang D cùng thuật toán / seed.
Kênh bubble = `doc_phieu` hiện tại. `trong_danh_sach` tính như `ag_cham_that.doc_anh` (SBD thuộc danh sách kỳ thi 1633, mã đề thuộc danh sách mã đề). **Không** gọi `ag_cham_that cham` (kết quả chính thức AG giữ nguyên); công cụ AK chỉ đọc ảnh và nhãn.
Ảnh giấy thật **không dùng để chọn hay chỉnh** bất cứ thứ gì.

**R4 đạt** nếu CNN **không thấp hơn thuật toán tốt nhất quá 1,0 điểm phần trăm** ở chỉ số 1 (đúng cả chuỗi, gộp SBD + mã đề) **ở cả (a) lẫn (b)**. Mỗi nhánh nêu riêng; nhánh nào không đạt / thiếu dữ liệu thì ghi rõ.
Số "sai mà không cờ" là chỉ báo (ca hiếm, không có ngưỡng); nêu mọi ca.

Giới hạn biết trước: (a) 5 người viết, SBD / mã đề trên phiếu do chính họ viết (người 5 không có phiếu) → lạc quan; mỗi trường sai = 0,9 điểm trên 112 trường (khó phân biệt với nhiễu);
(b) chỉ 26 trường, mỗi trường = 3,8 điểm; hiếm ca "sai không cờ" vì bubble độc lập thường đúng.

## 4. R5 – chi phí (chỉ báo cáo, **không** dùng để loại)

Kích thước mô hình (pickle với scikit-learn; trọng số float32 với mạng), số tham số, ms / ô (trung vị 300 lần, lô 1, CPU, 1 luồng). CNN / MLP đo cả bản NumPy triển khai lẫn PyTorch; LeNet-5 và CNN sâu chỉ đo PyTorch
(không có bản NumPy) – ghi rõ để không so lẫn hai loại. Chi phí **không được dùng để thay R3 / R4** trong kết luận.

## 5. PP-OCRv6

Không chạy lại. Trang trình diễn ghi nguyên số đo lệnh D (`docs/so_sanh_ocr_cnn.md`, chỉ DEV, giao thức khác – mô hình tiền huấn luyện sẵn, không leave-one-writer-out):
**PP-OCRv6 đúng hơn CNN 1,1 điểm trên trang D (96,9% so với 95,8%) và 5,5 điểm trên 504 ô phiếu dev (98,2% so với 92,7%) nhưng nặng ~50 lần (≈ 5,3 triệu so với 105 866 tham số)**. PP-OCRv6 không nằm trong R3 / R4
(khác giao thức, không có logit để dùng chung quy trình đối chiếu); ghi như một ứng viên ngoài tập, đúng hơn.

## 6. Quy tắc

- Chạy **một lần** theo đúng tiêu chí này. Lỗi lập trình được sửa thì chạy lại toàn bộ và ghi lại trong báo cáo.
- Tiêu chí không đạt thì nêu rõ, không đổi tiêu chí sau.
- Không đọc phiếu val 0029–0034, test 0035–0040, đợt 2. Chỉ dev, trang D, và (R4b) 13 ảnh AG.
