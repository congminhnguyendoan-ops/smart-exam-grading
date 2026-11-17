# Lệnh AN – tiêu chí quyết định thay mô hình triển khai bằng CNN sâu (đăng ký TRƯỚC)

Ngày: 16/11/2026 · nhánh `cnn-sau` · commit riêng, trước mọi số đo của lệnh AN. Chưa đo gì trên val / test cho ứng viên tại thời điểm viết.
Tiêu chí (a)–(e) của `docs/tieu_chi_cnn_sau.md` và kết quả `docs/ket_qua_cnn_sau.md` (lệnh AM) KHÔNG bị sửa; tài liệu này là bước quyết định riêng mà AM đã nói phải đăng ký.

## 1. Mô hình
- **Hiện tại**: `models/ocr_cnn.json`, SHA-256 `6d87205c83a29fccc4eb450f0aec0c9d51ba56e1bb141664060041ab0f2fcad5` (Conv16–Conv32–Dense64, 105 866 tham số).
- **Ứng viên (chốt trước, KHÔNG chọn seed khác theo kết quả)**: `data/_eval/am/ocr_cnn_sau_seed2026.json`, SHA-256 `9e84b9093e12b45f6483419f569e46eba041bbac846f01898304aaddd14eb048` (`sau_2x2`, 467 818 tham số, seed 2026, T = 1,80, τ = 0,9995, δ = 0,99, τ_khop = 0,5). Seed 2026 là seed mặc định của mọi mô hình triển khai trước đây; seed 1 và 2 không được xét.
- Nếu thay: **triển khai đúng trọng số đã đo** (không huấn luyện lại – huấn luyện không tất định trên máy này nên mô hình huấn luyện lại là mô hình CHƯA đo). `tools/xuat_ocr.py` sẽ được mở rộng thêm chế độ ghi lại từ tệp ứng viên (thêm siêu dữ liệu, trọng số giống từng byte), thay vì chạy lại huấn luyện. Đây là chệch có chủ đích so với "ghi bằng xuat_ocr.py", ghi lại để báo cáo.

## 2. Kiểm kê dữ liệu đo (viết TRƯỚC khi đo; chỉ dùng siêu dữ liệu, không đọc nhãn / ảnh)
- Phiếu: **val 0029–0034** (12 ảnh) + **test 0035–0040** (12 ảnh) = 24 ảnh, ≤ 24 SBD + ≤ 24 mã đề = **≤ 48 trường** (432 chữ số). Ảnh bị từ chối (nếu có) loại khỏi cả hai mô hình và báo riêng.
- Người viết (theo `cv_engine/tap_du_lieu.py`, mỗi người 8 phiếu): val 0029–0032 = **người 4** (8 ảnh), 0033–0034 = **người 5** (4 ảnh); test 0035–0040 = **người 5** (12 ảnh). Tức 8 ảnh người 4 + 16 ảnh người 5.
- Trùng với dev: phiếu dev 0001–0028 do người 1–4 (người 4 chỉ 0025–0028). Người 4 có mặt ở dev (72 ô) và ở val; **người 5 không có phiếu dev**.
- **Tất cả hai người viết đều đã có trong dữ liệu huấn luyện của CẢ HAI mô hình** (tinh chỉnh trên trang D: người 4 = D007–D008, người 5 = D009–D010) → phép đo này chỉ cho biết **"nét chữ đã gặp"**, KHÔNG đo khả năng đọc người lạ (số người lạ nằm ở OOF 5-fold: 67,56% so với 83,63%, lệnh AM). Test toàn do một người (người 5) → mọi kết luận theo người viết suy ra từ val+test là một-người.
- **Val và test đã được dùng trước đó với CNN hiện tại** (val 20/10/2026: 0 lỗi im lặng, T3 98,1%, 2/12 ảnh cần xem; test 21/10/2026: H2–H5 đạt, lỗi im lặng 0). Lệnh AN dùng lại chúng cho một quyết định chọn mô hình ⇒ **không còn là dữ liệu "chưa thấy" tuyệt đối**; kết quả của ứng viên là lần đo đầu tiên của nó, nhưng việc đối chiếu với CNN hiện tại dùng số đã biết trước.
- **Giới hạn thống kê**: n ≤ 48 trường; 1 trường = 2,1 điểm phần trăm; đúng cả chuỗi dự kiến xấp xỉ 90–100% ở cả hai mô hình (nét đã gặp) nên khó có chênh lệch có ý nghĩa; so sánh (ii)/(iii) là so sánh số đếm điểm, không có kiểm định; lỗi im lặng = 0 trên 48 trường với số trường "nhận" nhỏ (cận trên Clopper–Pearson 95% còn lớn, ≈ 10–15%) chỉ là "không thấy lỗi".

## 3. Cách đo (cùng cho cả hai mô hình; cùng ảnh nắn, cùng OMR, chỉ đổi mô hình OCR)
Công cụ `tools/an_do_thay_mo_hinh.py` (chỉ đọc ảnh + nhãn viết tay của phiếu 0029–0040; test qua `chan_test` + cờ xác nhận): `preprocess` → `omr.doc_phieu` → `ocr.doc_chu_so(mô hình)` → `ocr.doi_chieu_dinh_danh(omr, hv, True, True, mo_hinh=mô hình)`; SBD / mã đề coi là "có trong danh sách" (kỳ thi mô phỏng đủ thí sinh, như `eval_ocr.py`). Mỗi ảnh có 2 trường (SBD 6 chữ số, mã đề 3 chữ số).
- **Trường đúng cả chuỗi (R4(a) của AK)**: chuỗi chữ số viết tay do CNN đọc (argmax từng ô; ô không qua bộ đọc = "?") bằng nhãn viết tay trong `ground_truth.csv` (`sbd`, `exam_code`).
- **Trường cần xem**: `doi_chieu_dinh_danh` trả "chắc" = False cho trường đó.
- **Lỗi im lặng**: trường "chắc" mà (giá trị nhận ≠ nhãn viết tay) hoặc (chuỗi bubble ≠ nhãn viết tay).
Báo theo val, test và gộp; điều kiện áp dụng trên **gộp val+test**.

## 4. Điều kiện thay (TẤT CẢ phải đạt; không đổi ngưỡng sau khi thấy số)
- **(i)** Lỗi im lặng của ứng viên = **0** trên val+test.
- **(ii)** Số trường đúng cả chuỗi của ứng viên **≥** CNN hiện tại (không kém hơn; hòa chấp nhận).
- **(iii)** Số trường cần xem của ứng viên **≤** CNN hiện tại (hòa chấp nhận).
- **(iv)** pytest sau khi thay **không giảm**: ≥ 570 đạt, đúng 1 bỏ qua (test đợt 2 có chủ đích); mọi test ghim SHA / mô hình được cập nhật CÓ CHỦ ĐÍCH và liệt kê; không nới / xoá kiểm tra để cho qua.
- **(v)** Kiểm đầu-cuối bằng hệ thống thật: chấm lại 56 ảnh phiếu dev bằng backend với mô hình mới (`tools/kiem_backend_dau_cuoi.py`, `OCR_MODEL` trỏ mô hình mới): **0 lỗi im lặng** (0 câu chấm sai không gắn cần xem; 0 SBD / mã đề nhận sai so với chữ viết tay; điểm chính thức khớp 56/56).

## 5. Quy trình và quyết định
1. Đo (i)–(iii) trên val+test. **Chưa thay `models/` cho đến khi (i)–(iii) đạt.**
2. Chỉ khi (i)–(iii) đạt: sao lưu `models/ocr_cnn.json` → `data/_eval/an/ocr_cnn_hien_tai_sao_luu.json` (kèm SHA); ghi `models/ocr_cnn.json` mới (mục 1); cập nhật test ghim; chạy (iv), (v). **Nếu (iv) hoặc (v) không đạt: khôi phục ngay bản sao lưu (SHA phải trùng `6d87205c…`) và báo.**
3. Không đạt bất kỳ điều kiện nào → **GIỮ CNN hiện tại**; CNN sâu chỉ dùng cho demo Máy học.
4. Chưa push; không đụng `main`, `hoan-thien`.
