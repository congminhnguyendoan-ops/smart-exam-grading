# Lệnh AL – Tiêu chí chuyển CNN hiện tại sang CNN sâu (đăng ký TRƯỚC)

Ngày đăng ký: 16/11/2026 · nhánh `cnn-sau` · Tệp này được commit **trước** mọi công cụ / mã suy luận / huấn luyện của lệnh AL.
Tại thời điểm đăng ký: chưa viết mã suy luận, chưa huấn luyện lại, chưa sửa `models/`.

## 1. Mục tiêu

**Giảm số trường SBD / mã đề phải đưa giáo viên xem** (nhờ đọc đúng chuỗi chữ số hơn ở kênh viết tay).
KHÔNG nhằm tăng độ chính xác điểm: điểm đã được bảo vệ bởi đối chiếu hai kênh (bubble + CNN), lỗi im lặng mức trường hiện = 0.
Vì vậy an toàn (tiêu chí b) quan trọng hơn lợi ích (tiêu chí a).

## 2. Đối tượng so sánh

- **Hiện tại**: `models/ocr_cnn.json` – Conv16–Conv32–Dense64, 105 866 tham số, 1 thành viên, T = 1,75.
- **Ứng viên**: CNN sâu 2 khối × 2 conv (Conv32, Conv32, pool, Conv64, Conv64, pool, Dense128, Dense10; **467 818 tham số**), đã có ở `tools/ak_so_sanh_mo_rong.py` (`tao_cnn_sau`).
- Quy trình huấn luyện / hiệu chỉnh nhiệt độ của ứng viên giữ đúng quy trình CNN hiện tại (MNIST → tinh chỉnh trang chữ số D001–D010, CV theo người viết); không thêm thủ thuật chỉ áp cho ứng viên.

## 3. Tiêu chí (tất cả đo bằng script, tái tạo được)

**(a) Lợi ích.** Số trường (SBD 6 chữ số + mã đề 3 chữ số) đọc đúng **cả chuỗi** trên 504 ô phiếu dev (112 trường: 56 ảnh × 2 trường) của ứng viên **tăng ≥ 5 điểm phần trăm** so với CNN hiện tại.
Ứng viên: trung bình 3 seed (ghi thêm từng seed và độ lệch chuẩn). Cùng cách đo với R4(a) của lệnh AK (`docs/so_sanh_mo_rong_ak.md`), cùng 504 ô, cùng CNN hiện tại làm mốc.

**(b) An toàn.** **Lỗi im lặng = 0** (trường bị nhận "chắc" mà sai so với chữ viết tay thật, sau đối chiếu hai kênh) trên: (i) dev; (ii) 13 ảnh `data/anh_that_ag`. Chỉ cần MỘT ca ở bất kỳ seed nào là không đạt.

**(c) Suy luận NumPy khớp PyTorch.** Bản NumPy cho **cùng nhãn với PyTorch trên ≥ 99,9% ô kiểm tra**, và **mọi logit lệch ≤ 1e-4** (logit, chặt hơn test hiện có vốn đo xác suất; không nới ngưỡng sau khi thấy kết quả).

**(d) Chi phí và hồi quy.** ≤ **5 ms/ô** bằng NumPy (trung vị, máy phát triển, đã khởi động); toàn bộ pytest hiện có vẫn đạt như trước khi đổi (số đạt không giảm, không thêm skip).

**(e) Quyết định.** Nếu không đạt đủ (a)–(d) → **GIỮ CNN hiện tại** (`models/ocr_cnn.json` không đổi). CNN sâu chỉ được dùng làm đối tượng so sánh ở demo "Máy học". Không đổi tiêu chí sau khi có số.

## 4. Giới hạn đã biết (ghi trước để không bị đọc quá mức)

1. **13 ảnh AG đã bị nhìn thấy** (lệnh AG/AK; các hạn chế của chúng đã biết) → KHÔNG dùng để chọn kiến trúc, seed, ngưỡng hay nhiệt độ; chỉ dùng kiểm tiêu chí (b).
2. **1 trường ở giấy thật = 3,8 điểm** (13 ảnh × 2 trường = 26 trường) → giấy thật không đủ độ phân giải để chứng minh lợi ích; (a) chỉ đo ở dev, giấy thật chỉ để bắt lỗi im lặng.
3. **Dev lạc quan**: 4 người viết của phiếu dev có mặt trong dữ liệu huấn luyện (trang D) → mức tăng ở dev có thể cao hơn mức tăng với người viết lạ. Con số (a) là cận lạc quan; không được trình bày như độ chính xác triển khai.
4. Huấn luyện mạng không tất định trên máy này (lệnh AK, `kiem-tat-dinh`) → dùng 3 seed, báo cáo cả dao động; không chọn seed đẹp nhất.
5. Tiêu chí không bao gồm val 0029–0034, test 0035–0040 và đợt 2; nếu ứng viên đạt (a)–(d) thì việc đưa vào hệ thống cần đăng ký và kiểm thử riêng.
