# Kế hoạch đánh giá test cuối CẢ HỆ THỐNG trên 0035–0040 (SOẠN 21/10/2026 – **CHƯA CHẠY, chưa đăng ký**)

> Mục đích: một lần duy nhất đo toàn chuỗi **nắn ảnh → OMR → CNN chữ số + đối chiếu → chấm điểm → giáo viên** trên 12 ảnh test (6 phiếu).
> Chỉ chạy khi người dùng gõ **"chạy test hệ thống"** SAU khi (a) duyệt kế hoạch này, (b) quyết các điểm ở mục 1, (c) có commit đăng ký (mục 4).
> Đã chạy trên test trước đó: nắn ảnh (07/10, Tuần 4 Bước 7, 12/12 đúng). OMR và CNN **chưa** chạy trên test.

## 1. Quyết định cần người dùng chốt TRƯỚC khi đăng ký
1. **Mô hình OMR cho test**: (A, khuyến nghị) giữ nguyên `models/omr_m1.json` đã kiểm val (huấn luyện trên 0001–0028) – không thêm thay đổi chưa kiểm; hay (B) huấn luyện lại trên 0001–0034 (nợ Tuần 5 #7) với siêu tham số + ngưỡng khoá (`ro_min` 0,5): thêm 12 ảnh dữ liệu nhưng mô hình mới **không còn tập giữ lại** để kiểm trước test. Mặc định đề xuất: A.
2. **Mô hình CNN**: giữ `models/ocr_cnn.json` (g0, seed 2026, SHA `6d87205c…`; đã kiểm val). Không huấn luyện lại.
3. **Luật đối chiếu**: Q3 nguyên vẹn, τ_khop 0,5 (người dùng đã chốt GIỮ, không dùng luật mềm).
4. **Đáp án chấm**: như `kiem_backend_dau_cuoi.py` – kỳ thi mô phỏng, 4 mã đề đáp án giả lập (`demo.khoa_demo`), danh sách thí sinh = SBD viết tay thật của 6 phiếu (nhãn `ground_truth.csv` dòng 35–40); điểm "đúng thật" tính độc lập từ nhãn người tô.
5. **MO_MIN** giữ 0,012 (chưa chỉnh; đo theo mức mờ còn nợ) – ghi rõ trong đăng ký.

## 2. Công cụ (viết SAU khi duyệt: `tools/eval_he_thong.py`; thử trên dev trước; khoá test bằng `chan_test` + `--xac-nhan-test`)
Chỉ gọi API công khai (backend qua TestClient trong giao dịch **ROLLBACK**, thư mục ảnh tạm – không ghi CSDL thật; `omr`, `ocr`). Bộ đọc nhãn và bộ đếm riêng. Chạy một lần, tự chặn chạy lại bằng file khoá `data/_eval/he_thong/da_chay_test.lock`. Pha 1: tải ảnh không can thiệp; pha 2: giáo viên oracle chốt đúng như giấy (như `kiem_backend_dau_cuoi.py`).

## 3. Chỉ số và tiêu chí
**ĐẠT (bắt buộc, tất cả):**
| # | Tiêu chí | Ngưỡng |
|---|---|---|
| H1 | Nắn ảnh sai mà không bị từ chối (lỗi im lặng) | = 0 / 12 |
| H2 | OMR: lỗi nặng (câu + cột) không gắn cần xem | = 0 / 480 câu + 108 cột |
| H3 | SBD / mã đề được nhận tự động mà ≠ chữ viết tay thật | = 0 / 12 SBD + 12 mã đề |
| H4 | Câu chấm sai mà không gắn cần xem; điểm tạm / tối đa không bao điểm thật; phiếu tự chốt sai điểm | = 0 |
| H5 | Sau giáo viên oracle: điểm chính thức = điểm tính độc lập, đúng sinh viên | 12/12 ảnh (mỗi ảnh một kỳ thi như dev) |

Báo kèm, **không là điều kiện ĐẠT**: số ảnh bị từ chối (lý do), lỗi nhẹ OMR, cần xem thừa (mục tiêu ≤ 3%), F1 mờ theo C1–C4 (n rất nhỏ), T3 chữ số CNN (mục tiêu ≥ 97%), T4 ảnh có SBD / mã đề cần xem (mục tiêu ≤ 10%), thời gian / ảnh, CP 95% cho mọi tỉ lệ 0 / n (n nhỏ → cận trên rộng, ghi rõ).

**Ca thử bắt buộc báo riêng:**
- **0035: mã đề viết `103` nhưng KHÔNG tô bubble** (nhãn `---`): hệ thống PHẢI gắn mã đề cần xem (`thieu_bubble`); nhận / chấm tự động = vi phạm H3.
- **8 mục rõ / mờ** (nhãn đã so giấy 07/10, 8/8 giữ nguyên): 0036 câu 2, 10, 13; 0037 câu 1, 15, 31; 0040 câu 5 (nhãn mờ), câu 10 (nhãn rõ) – báo dự đoán so với nhãn; mờ đọc thành rõ chắc chắn = lỗi nhẹ (không tính ĐẠT).
- **0035_C3** (nội dung lệch 2,06 mm > dung sai cố định 2,0 mm) và **0039_C3** (độ phối cảnh 0,618, nhỏ nhất): định vị phải đúng hoặc gắn `vi_tri`.
- Cả 12 ảnh do **người 5** viết, người 5 cũng viết D009–D010 (dữ liệu tinh chỉnh CNN) → CNN chỉ đo "nét đã gặp", **lạc quan** so với người lạ (OOF T3 ≈ 92%).

## 4. Đăng ký trước (commit riêng, TRƯỚC khi chạy)
Ghi: commit mã đóng băng (cv_engine, backend, tools/eval_he_thong.py, models); SHA-256 `omr_m1.json` / `ocr_cnn.json` / `layout.json` / `phieu_trang_300dpi.png`; `MO_MIN`, `ro_min`, τ_khop, ngưỡng ô; tiêu chí H1–H5; dự đoán (H1–H5 đều 0; T4 ≈ 25–50%; thời gian ≈ 0,75 s/ảnh); hạn chế (12 ảnh / 6 phiếu, CP rộng; một người viết; test đã được mở một lần ở Tuần 4 cho nắn ảnh và audit nhãn – không tham số nào chọn theo test). Kiểm `git diff <commit> HEAD` mã = rỗng ngay trước khi chạy.

## 5. Xem bằng mắt (mù)
Công cụ xuất `data/_eval/he_thong/xem_test_mu.html`: mỗi ảnh gồm ảnh nắn, hàng 9 ô viết tay, các câu cần kiểm – **chưa** có kết quả máy. Người dùng đọc SBD / mã đề viết tay, các câu mờ / nhiều ô và kết luận ảnh nắn đúng / sai TRƯỚC; sau đó mới mở `xem_test_may.html`. Mọi ca máy ≠ mắt được liệt kê; nghi nhãn `ground_truth.csv` sai → người dùng so giấy, KHÔNG tự sửa.

## 6. Sau khi chạy
Ghi số liệu + CP vào mục KẾT QUẢ của tài liệu này; không chỉnh gì rồi chạy lại. Nếu H1–H5 có lỗi: ghi nguyên trạng, phân tích, sửa ở phiên bản sau và chỉ kiểm lại trên dev (không chạy lại test).

## 7. Lệnh dự kiến (KHÔNG chạy bây giờ)
`python tools/eval_he_thong.py run --tap dev` (thử công cụ) → duyệt → commit đăng ký → người dùng gõ "chạy test hệ thống" → `python tools/eval_he_thong.py run --tap test --xac-nhan-test --xem` → mở HTML mù → `report`.
