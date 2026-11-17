# Đăng ký trước – phép thử mô phỏng H3 "ô tô trống, chữ viết tay có" (lệnh T, 30/10/2026)

Bản máy đọc: `docs/dang_ky_h3_mo_phong.json` (SHA tệp, SHA 20 ảnh gốc, kế hoạch 20 ca). Commit này được gắn tag **`dang-ky-h3-mo-phong`** TRƯỚC khi chạy.

## 1. Vì sao
Tiêu chí H3 của đợt 2 có điều kiện "phiếu 0107: cột SBD thứ 3 không tô bubble nhưng có chữ viết tay → hệ thống phải để cần xem". Trên giấy thật,
người tô đã tô ô đó (đợt 2 đọc ra 8), nên điều kiện **không xảy ra** và H3-0107 chưa được kiểm chứng. Phép thử này tạo lại điều kiện bằng **ảnh chỉnh**.

## 2. Mã được kiểm
- Commit `9ea19093276067433129e572f1796d6afee5bae2` (nhánh `cai-tien-b`, đã gộp vào main ở tag `sau-dot2-hop-nhat-30-10`).
- `cv_engine/` giống hệt tag `dang-ky-dot2` (`git diff dang-ky-dot2 9ea1909 -- smart_exam_db/cv_engine` rỗng). Lúc chạy, công cụ từ chối nếu
  `cv_engine/`, `models/`, `backend/`, `answer_sheet/output/` khác commit này, nếu có sửa chưa commit, hoặc nếu SHA bất kỳ tệp trong JSON khác.
- KHÔNG sửa mã hệ thống. Không sửa `tools/eval_dot2.py`, `docs/dong_bang_ma_dot2.json`, `docs/dang_ky_test_dot2.json`, `docs/ket_luan_mat_dot2.csv`,
  `data/dot2/*`, `data/raw_dot2/*`. Ảnh gốc chỉ được ĐỌC (SHA kiểm theo `docs/sha_anh_dot2.txt` trước khi dùng).

## 3. Cách tạo ảnh chỉnh (`tools/h3_mo_phong.py`, tất định)
1. Đọc ảnh bằng `doc_anh` (đúng mảng xám hệ thống dùng) → `preprocess_anh` → 4 tâm marker cuối. Phép nắn của hệ thống chỉ là một phép phối cảnh
   4 điểm nên nghịch đảo chính xác: **sửa trực tiếp trên toạ độ ảnh gốc**.
2. **Chọn ca** (hạt giống **2026**, lần lượt theo tên ảnh đã sắp xếp): một trường rồi một cột có đúng một ô tô, tức nhãn có chữ số VÀ bubble đợt 2 đọc
   đúng chữ số đó, không bị `bubble_cx`. Cách này loại cột vốn trống, ví dụ 0107 cột 3. **Chỉ chọn trường mà đợt 2 đã NHẬN**, để "cần xem" quy được cho
   việc xoá ô. Phiếu 0103 không có trường nào như vậy nên chọn trong mọi trường và đánh dấu riêng (2 ca).
3. **Ô nguồn: ô trống CÙNG HÀNG, cột kề** trong cùng trường. Đây là chỗ lệch có chủ đích so với chữ của lệnh T ("cùng cột, hàng khác"). Lý do: ô bubble
   có in sẵn chữ số xám bên trong. Chép từ hàng khác làm ô bị xoá hiện SAI chữ số, và diễn tập 0001_C1 còn chép theo cả một chấm mực. Ảnh diễn tập
   `data/_eval/h3/mau_truoc_sau.png` cho thấy rõ; người dùng đã chọn biến thể cùng hàng ngày 30/10/2026.
4. Định vị ô thật trên ảnh nắn bằng khớp mẫu phiếu trắng (cả khối ±30 px, từng ô ±8 px). Chép: điểm ảnh gốc → toạ độ nắn → dời sang ô nguồn → ngược
   về ảnh gốc → lấy mẫu song tuyến. Trọng số 1 trong R+6 px, giảm về 0 ở R+12 px (@300 DPI). **Không chỉnh độ sáng.** Chữ viết tay không bị chạm.
5. Lưu **PNG không mất mát** (không lưu JPEG: nén lại đổi mọi điểm ảnh, làm T3 lẫn tác động nén với tác động sửa). Bảng: `data/h3_mo_phong/bang.{csv,json}`
   (ảnh, trường, cột, chữ số xoá, ô nguồn, tâm ô, vùng sửa trên ảnh gốc, độ tối trước / sau, SHA ảnh chỉnh).

## 4. Kế hoạch 20 ca (tính từ nhãn + kết quả đợt 2, chưa mở ảnh)
| Ảnh | Trường | Cột | Chữ số xoá | Ô nguồn (cột, hàng) |
|---|---|---|---|---|
| 0101_C1 | mã đề | 2 | 0 | (1, 0) |
| 0101_C2 | mã đề | 1 | 1 | (2, 1) |
| 0102_C2 | mã đề | 3 | 2 | (2, 2) |
| 0102_C3 | SBD | 5 | 6 | (4, 6) |
| 0103_C3 | SBD | 2 | 8 | (1, 8) – trường đã cần xem ở đợt 2 |
| 0103_C4 | mã đề | 3 | 3 | (2, 3) – trường đã cần xem ở đợt 2 |
| 0104_C1 | mã đề | 1 | 1 | (2, 1) |
| 0104_C4 | SBD | 1 | 2 | (2, 2) |
| 0105_C1 | SBD | 1 | 5 | (2, 5) |
| 0105_C2 | SBD | 6 | 4 | (5, 4) |
| 0106_C2 | SBD | 2 | 6 | (1, 6) |
| 0106_C3 | mã đề | 2 | 0 | (1, 0) |
| 0107_C3 | SBD | 4 | 2 | (3, 2) |
| 0107_C4 | SBD | 6 | 3 | (5, 3) |
| 0108_C1 | mã đề | 3 | 4 | (2, 4) |
| 0108_C4 | SBD | 1 | 4 | (2, 4) |
| 0109_C1 | SBD | 3 | 7 | (2, 7) |
| 0109_C2 | SBD | 2 | 9 | (1, 9) |
| 0110_C2 | mã đề | 1 | 1 | (2, 1) |
| 0110_C3 | mã đề | 2 | 0 | (1, 0) |

## 5. Chạy (`tools/eval_h3_mo_phong.py run --xac-nhan-h3`)
Đi qua API công khai (TestClient, CSDL thật trong giao dịch ROLLBACK, kho ảnh tạm), cùng thứ tự và cùng cách chia kỳ thi A/B như đợt 2. Giáo viên oracle
chốt câu cần xem theo nhãn, SBD / mã đề theo chữ viết tay đúng. Mỗi ca ghi: bubble đọc gì, CNN đọc gì (p), cần xem / nhận, lý do hiển thị, trạng thái
phiếu khi tải và sau oracle, điểm chính thức so với điểm thật.

## 6. Tiêu chí bắt buộc
- **T1**: số ca hệ thống NHẬN (không cần xem) trường đã bị xoá bubble = **0**. Ảnh bị từ chối khi nắn tính riêng, không tính là nhận.
- **T2**: số phiếu tự chốt sai hoặc điểm chính thức sai (sau oracle) = **0**.
- **T3** (đối chứng): ở mỗi ảnh chỉnh, trường KHÔNG sửa giống kết quả đợt 2 (`data/_eval/dot2/that/ket_qua.json`): cần xem + lý do của trường; từng cột
  (bubble, chữ số CNN, cần xem, lý do).
- **KT0** (kiểm công cụ, không phải tiêu chí): 20 ảnh gốc lưu PNG, không sửa, tải vào kỳ thi C/D riêng; cả hai trường giống đợt 2.

## 7. Dự đoán
T1: 20/20 cần xem (0 nhận) · T2: 0 · T3: khớp ≥ 19/20 · KT0: 20/20.

## 8. Một lần
Chỉ chạy MỘT lần. Khoá `data/_eval/h3/da_chay.lock` được tạo NGAY khi bắt đầu; nếu đã có thì công cụ từ chối, kể cả khi lần trước lỗi giữa chừng.
Lỗi kỹ thuật (không phải kết quả) phải được báo cáo trước khi chạy lại. Ca thất bại được GHI NHẬN NGUYÊN TRẠNG; không sửa mã trước khi báo cáo.

## 9. Giới hạn (biết trước)
Ảnh chỉnh bằng phần mềm, không phản ánh đặc tính quang học thật của ô trống (vết tẩy, lõm giấy); chỉ kiểm logic hai kênh; một điện thoại; 20 ca
không độc lập (hai ảnh / phiếu); chưa thay thế phép thử bằng giấy thật.

## 10. Diễn tập trước đăng ký (không tính vào kết quả)
Ảnh dev 0001_C1, 0002_C2 (`tools/h3_mo_phong.py dien-tap`, `tools/eval_h3_mo_phong.py dien-tap`): cả hai biến thể đều cho bubble `?` (`thieu_bubble`),
CNN đọc đúng (0 với p 1,00; 1 với p 0,96), trường cần xem, điểm chính thức sau oracle đúng (2,25 / 2,25), trường không sửa khớp 2/2. Chưa chạy trên ảnh đợt 2.
