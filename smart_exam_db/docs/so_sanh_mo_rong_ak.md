# So sánh mở rộng CNN với các thuật toán khác – mức ô và mức hệ thống (lệnh AK, 06/11/2026)

Tiêu chí đăng ký TRƯỚC: `docs/tieu_chi_so_sanh_mo_rong.md` (commit `2e549da`, trước khi có công cụ). Công cụ: `tools/ak_so_sanh_mo_rong.py` (tái dùng giao thức lệnh AI).
Kết quả đầy đủ: `data/_eval/ak/ket_qua.md|json` (ngoài git). Không sửa `models/`, tệp đóng băng, mã hệ thống, CSDL.

## 1. Kết luận theo tiêu chí (không đổi tiêu chí sau khi thấy số)

| Tiêu chí | Kết quả | Số |
|---|---|---|
| **R3** mức ô (E2b, 5 người viết) | **ĐẠT** | CNN 95,40%; tốt nhất = CNN sâu 96,03% → thấp hơn **0,63 điểm** (ngưỡng 1,0). LeNet-5 cũng hơn CNN 0,33 điểm |
| **R4(a)** 504 ô phiếu dev (112 trường) | **KHÔNG ĐẠT** | đúng cả chuỗi: CNN **67,56%**, CNN sâu 81,25%, LeNet-5 78,27%, HOG+SVM 73,21% → CNN thấp hơn tốt nhất **13,69 điểm** |
| **R4(b)** 13 ảnh giấy thật (26 trường) | **KHÔNG ĐẠT** (sát ngưỡng thô) | CNN triển khai 92,31%; HOG+SVM 96,15% → chênh **3,85 điểm = đúng 1 trường** |
| **R5** chi phí | chỉ báo cáo | CNN 0,42 MB, 0,61 ms/ô (NumPy triển khai) |

**Vì vậy KHÔNG được nói “CNN hiện tại là tối ưu”.** Nói được: (i) mạng tích chập là họ thuật toán tốt nhất trong tập đã thử ở mức ô; (ii) CNN hiện tại đứng thứ ba ở E2b và không đạt R4;
(iii) mọi thuật toán đều có 0 ca “sai mà không cờ” nhờ đối chiếu bubble, nên chọn thuật toán không ảnh hưởng độ an toàn của điểm, chỉ ảnh hưởng số phiếu phải xem.
Mô hình triển khai **không đổi** (đúng yêu cầu lệnh).

## 2. R3 – mức ô, E2b (MNIST + ô thật, học 4 người, đo người thứ 5; TB 5 người ± SD giữa người)

| Thuật toán | E2b | ± SD | Ô phiếu dev (504) | Sai mà tự tin | Ghi chú |
|---|---|---|---|---|---|
| CNN sâu (2 khối × 2 conv, 467 818 tham số) | **96,03%** | 3,37 | 95,11% | 345 | mới, 3 seed |
| LeNet-5 (61 706 tham số) | 95,73% | 3,23 | – | 397 | mới, 3 seed |
| **CNN hiện tại (105 866 tham số)** | **95,40%** | 2,56 | 91,60% | 441 | trùng lệnh AI tuyệt đối |
| HOG + SVM RBF | 93,72% | 4,87 | – | 223 | mới |
| SVM RBF | 91,43% | 5,91 | – | 296 | trùng lệnh AI |
| MLP | 90,79% | 4,06 | – | 824 | lệch −0,17 so với lệnh AI (xem mục 5) |
| Random Forest | 90,46% | 5,46 | – | 638 | trùng |
| k-NN | 87,92% | 6,12 | – | 423 | trùng |
| Logistic regression | 83,53% | 7,71 | – | 407 | trùng |
| Naive Bayes Gaussian | 73,12% | 7,71 | – | 988 | mới |
| Decision Tree | 69,32% | 6,61 | – | 3463 | mới |
| HistGradientBoosting | **không chạy E2b** | | | | mục 5. Chỉ có E1: MNIST test 97,74% (CNN 98,94%, CNN sâu 99,48%) |

Kiểm định dấu cặp theo ô (phụ, seed 2026): CNN đúng / CNN sâu sai = 66, CNN sai / CNN sâu đúng = 78, p = 0,36 → ở mức ô **không phân biệt được** CNN và CNN sâu (chỉ 5 người).

## 3. R4 – mức hệ thống (thay bộ đọc chữ số, giữ đối chiếu bubble)

Chỉ số quyết định = tỉ lệ trường (SBD 6 chữ số, mã đề 3 chữ số) mà kênh viết tay đọc đúng CẢ chuỗi.

| Thuật toán | (a) dev 112 trường | (a) cần xem / 112 | (b) giấy thật 26 trường | Sai mà không cờ |
|---|---|---|---|---|
| CNN sâu | **81,25%** | 25,7 | 93,59% | 0 |
| LeNet-5 | 78,27% | 30,7 | 93,59% | 0 |
| HOG + SVM | 73,21% | 32,0 | **96,15%** | 0 |
| **CNN hiện tại** | **67,56%** | 42,3 | 92,31% (triển khai) | 0 |
| MLP | 62,50% | 49,0 | 79,49% | 0 |
| SVM RBF | 61,61% | 46,0 | 92,31% | 0 |
| Random Forest | 58,63% | 63,7 | 79,49% | 0 |
| k-NN | 57,14% | 52,0 | 61,54% | 0 |
| Logistic regression | 46,43% | 72,0 | 73,08% | 0 |
| Naive Bayes | 24,11% | 85,0 | 30,77% | 0 |
| Decision Tree | 20,54% | 100,3 | 26,92% | 0 |

Ý nghĩa thực tế: bộ đọc tốt hơn → **ít phiếu giáo viên phải xem** (CNN sâu 25,7 so với CNN 42,3 trên 112 trường, giảm ~39% trên dev), không phải ít lỗi im lặng hơn (đều 0).
Khoảng cách ở R4(a) (13,7 điểm) lớn hơn nhiều khoảng cách ở R3 (0,63) vì chuỗi 6 chữ số khuếch đại sai số từng ô (0,95⁶ ≈ 0,74 so với 0,92⁶ ≈ 0,60) và vì ô phiếu khó hơn ô trang D.

## 4. R5 – chi phí (không dùng để loại)

CNN 0,42 MB, 0,61 ms/ô bằng NumPy triển khai (0,21 ms bằng PyTorch); CNN sâu 1,87 MB, 0,76 ms/ô (PyTorch, không có bản NumPy); LeNet-5 0,25 MB; HOG+SVM 8,4 MB, 1,11 ms; SVM 30,7 MB; k-NN 41,2 MB; RF 87,7 MB.
Tuyệt đối đều nhỏ: CNN sâu vẫn chạy < 1 ms/ô, nhỏ hơn 2 MB. **Chi phí không phải lý do để không dùng CNN sâu**; lý do duy nhất là chưa qua quy trình đăng ký / kiểm thử mô hình mới.

## 5. Vì sao chọn CNN (3 lý do dựa trên số đo, nói đúng phạm vi)

1. **Độ đúng mức ô (R3)**: mạng tích chập chiếm 3 vị trí đầu E2b (96,03 / 95,73 / 95,40%); CNN hiện tại hơn HOG+SVM 1,7 điểm, SVM 4,0, MLP 4,6, RF 4,9, k-NN 7,5, LR 11,9. Không thuật toán không-tích-chập nào vượt CNN.
2. **Chi phí**: 0,42 MB, 0,6 ms/ô, chạy bằng NumPy thuần không cần PyTorch lúc chạy; SVM nặng 73×, RF 209×, k-NN 98× về dung lượng.
3. **Hệ thống an toàn nhờ đối chiếu hai kênh**: với MỌI thuật toán, 0 ca nhận nhầm SBD / mã đề; nên mô hình chỉ cần đủ tốt để không bắt giáo viên xem quá nhiều.
   **Giới hạn trung thực của lý do này:** về số phiếu phải xem, CNN hiện tại KHÔNG phải tốt nhất (R4 không đạt); CNN sâu và LeNet-5 tốt hơn. CNN hiện tại được chọn từ Tuần 6, trước khi có phép so sánh này.

## 6. Giới hạn và điểm đáng ngờ

- **Chỉ 5 người viết**; SBD / mã đề trên phiếu dev do chính 4 người này viết (lạc quan); 1 trường ở (a) = 0,89 điểm, ở (b) = 3,8 điểm (R4(b) “không đạt” chỉ vì đúng 1 trường).
- **HistGradientBoosting không chạy E2b**: đo thật một lần fit ≈ 40 s × 65 lần fit lồng ≈ 44 phút > giới hạn 30 phút của tiêu chí. Không cắt lưới / kiểm định lồng (sẽ là cắt giảm âm thầm); R3 xét 11 thuật toán thay vì 12. Kết quả E1 (MNIST 97,74%) cho thấy HGB không có lý do vượt CNN.
- **HOG cài bằng NumPy**, không bằng OpenCV: OpenCV 5.0 trong venv không còn `HOGDescriptor` (lệch với tiêu chí; tham số giữ nguyên: cell 7, block 14, bước 7, 9 bin, 324 chiều, chuẩn hoá L2-Hys). Phát hiện trước khi có bất kỳ kết quả nào.
- **Huấn luyện mạng không tất định**: tiền huấn luyện MLP seed 2026 hai lần giống hệt cho logit lệch tới ~18 và ~39/2000 nhãn khác (`kiem-tat-dinh`). Vì vậy MLP chạy lại lệch −0,17 điểm so với lệnh AI (vượt ngưỡng 0,05 đã đăng ký; không đổi kết luận vì MLP cách top > 5 điểm).
  LeNet-5 và CNN sâu cũng chịu nhiễu này (mỗi mạng huấn luyện một lần mỗi seed); CNN hiện tại dùng bộ đệm tiền huấn luyện nên trùng tuyệt đối. Biên R3 (0,63 < 1,0) lớn hơn nhiễu quan sát (~0,2) nhưng không lớn gấp nhiều lần.
- Hai mạng mới (LeNet-5, CNN sâu) là **hai lần thử**; chưa chỉnh siêu tham số nào (một cấu hình chốt trước mỗi mạng) nên không có chọn lọc theo kết quả.
- R4(b): mô hình khác CNN được huấn luyện lại trên MNIST + trang D (5 người) với w = giá trị chọn nhiều nhất qua 5 fold; CNN dùng mô hình triển khai. Ảnh AG không dùng để chọn bất cứ thứ gì và không gọi `ag_cham_that cham`.
- Mô hình “người 1 giữ ra” dùng ở trang trực tiếp là mô hình huấn luyện lại (một seed); trên người 1, CNN hiện tại 95,14% > CNN sâu 93,96% ở lần chạy đó, trái chiều với trung bình 5 người – nhắc rằng một người, một seed là nhiễu.
- **PP-OCRv6** (lệnh D) đúng hơn CNN 1,1 điểm (trang D) và 5,5 điểm (504 ô phiếu dev) nhưng nặng ~50 lần; không nằm trong R3 / R4 (khác giao thức).

## 7. Chạy lại

```powershell
python tools/ak_so_sanh_mo_rong.py chay            # E1 + E2b (~ 1 giờ 10 phút; CNN sâu E1 ≈ 5 phút/seed)
python tools/ak_so_sanh_mo_rong.py ag-cat          # cắt 117 ô của 13 ảnh data/anh_that_ag
python tools/ak_so_sanh_mo_rong.py ag-doc          # huấn luyện lại + đọc ô giấy thật
python tools/ak_so_sanh_mo_rong.py kiem-tat-dinh   # chứng minh huấn luyện không tất định
python tools/ak_so_sanh_mo_rong.py bang            # R3 / R4 / R5 -> data/_eval/ak/ket_qua.md
python tools/demo_may_hoc.py --so-sanh-truc-tiep --ra data\_eval\demo_3_phien\may_hoc_so_sanh.html   # ~ 6 giây; thêm --da-tinh-san để đọc kết quả đệm
```
