# Lệnh AR – kết quả sửa 5 rủi ro lệnh AH

Ngày: 16/11/2026 · nhánh `cnn-sau` · tiêu chí ĐÃ đăng ký trước: `docs/tieu_chi_sua_ah.md` (commit `e1a4ef4`), không đổi · kịch bản đo `tools/ah_thu_dong_thoi.py` (máy chủ thử cổng 8010, ảnh giả hoá, dữ liệu thử dọn trong `finally`: đếm lại = 0, kỳ thi demo nguyên vẹn) · số liệu thô `data/_eval/ah/ket_qua_ar_*.json` (ngoài git).
Sao lưu CSDL trước khi sửa: `data/_backup/smart_exam_db_20261116_133358_demo.dump`. Thay đổi CSDL duy nhất: migration 006 (bảng mới `revoked_tokens`, chỉ thêm).
**Không dừng mục nào vì tệp đóng băng**: R1 / R2 / R3 / R5 được làm ở tầng điều phối mới `backend/dong_thoi.py` + `backend/main.py`; `backend/service.py`, `backend/schemas.py`, `cv_engine/`, `models/` giữ nguyên từng byte (băm kiểm lại ở cuối + test `test_r1_tep_dong_bang_khong_bi_cham`).

## Bảng R1–R5 (theo đúng tiêu chí đã đăng ký)
| Rủi ro | Tiêu chí | TRƯỚC (mã cũ, đo 16/11) | SAU | Commit |
|---|---|---|---|---|
| **R1** hai phiếu cùng SBD đồng thời | 60 lần (50 tự nhiên + 10 ép): cả hai 201, 2 phiếu lưu, đúng 1 điểm chính thức, kết quả = gửi tuần tự | 17/60 đạt; **43 lần 409 + mất phiếu**; 0 lần hai điểm chính thức | **60/60 ĐẠT**; 0 lần 409, 0 mất phiếu, 0 lần hai điểm chính thức | `185e071` |
| **R2** cùng một tệp gửi hai lần đồng thời | 60 lần: không 500; hai 201; 1 phiếu theo băm; một `da_ton_tai` false + một true, cùng `sheet_id` | **0/60** đạt; 13 lần 500 / lỗi mạng, 47 lần 409 | **60/60 ĐẠT**; 0 lần 500, 0 lần 409 | `c012bcb` |
| **R3** `/sheets/batch` hai lô chéo | 100 lần: không deadlock, không 500, không ảnh lỗi | **0/100** đạt; 100/100 lần `DeadlockDetected` (cả trong thân phản hồi lẫn log) | **100/100 ĐẠT**; 0 deadlock (thân + log), 0 lỗi 500 | `5a150fc` |
| **R4** đăng xuất thu hồi token | ≥ 3 lượt: token cũ 401 trên ≥ 8 đường dẫn (cookie + Bearer); phiên khác sống; token giả 401, không ghi bảng; đăng xuất lặp lại 204 | token cũ vẫn 200 sau đăng xuất (không thu hồi) | **3/3 lượt ĐẠT** (9 đường dẫn); mỗi lượt đúng 1 dòng `revoked_tokens` | `d305d23` |
| **R5** giới hạn chấm đồng thời | 20 yêu cầu: mỗi cái 201 hoặc 503 + `Retry-After`; đỉnh bộ nhớ ≤ 1 500 MB; mặc định ≥ 2 | 20 × 201, **đỉnh 3 158 MB** (không giới hạn) | 20 × 201 (máy chủ thử 3 chỗ / chờ 8 s), **đỉnh 602–620 MB**; mặc định 4 chỗ / 30 s | `5befb21` |
Kịch bản sửa kỳ vọng A / C cho các kỳ thi AR và R4 dùng GV2: `23078be`.

**Tiêu chí chung**
| Điều kiện | Kết quả |
|---|---|
| pytest ≥ 600 đạt + 1 bỏ qua + test mới | **626 đạt, 1 bỏ qua** (221 s; 26 test mới ở `tests/test_ar_dong_thoi.py`) |
| `ah_thu_dong_thoi.py chay`: A–E vẫn đạt + R1–R5 đạt | **A, B, C, D, D-ép, D-ảnh trùng, D-lô chéo, E, E-thang tải, R1–R5: tất cả ĐẠT** (A–E cũ trước AR: D-ảnh trùng và D-lô chéo KHÔNG ĐẠT theo tiêu chí cũ; nay đạt) |
| Chấm lại 56 ảnh dev: băm đầu ra y hệt | **`54e54baa…70f0` = mốc** (56 dòng, bỏ cột `sheet_id`); 0 câu chấm sai không cờ, điểm chính thức 56/56 |
| `kiem_truoc_demo.py` | 27 ĐẠT, 1 CẢNH BÁO (`PUBLIC_BASE_URL` có sẵn), **0 KHÔNG ĐẠT** |
| Tệp đóng băng | không đổi (băm trước = sau) |

## Thời gian xử lý (có chậm đi không?)
Đo bằng chính `ah_thu_dong_thoi.py` (cùng máy, cùng ảnh; "trước" = chạy lại `6bf707b` trong cây làm việc riêng, "sau" = bản này):
| | Trước | Sau |
|---|---|---|
| Một ảnh, tuần tự (B, 18 ảnh), trung vị | 830 ms | 747 ms (không chậm) |
| B đồng thời (3 GV × 2 luồng), trung vị | 2 114 ms | 1 565 ms |
| E (60 ảnh, 6 đồng thời): thông lượng | 2,93 ảnh/s | 2,95 ảnh/s |
| E: trung vị / p95 độ trễ | 2 087 / 2 247 ms | 1 679 / 2 783 ms |
| E: đỉnh bộ nhớ máy chủ | 1 028 MB | 693 MB |
Không chậm đi ở ảnh đơn và thông lượng. **Chậm hơn ở hai chỗ có chủ đích**: (1) yêu cầu thứ 5+ khi đã đủ 4 chỗ chờ trong hàng đợi (p95 E tăng 2,2 → 2,8 s, đổi lại bộ nhớ thấp hơn); (2) bên thua trong cuộc đua cùng SBD (R1) bị chấm LẠI một lần: trung vị mỗi cuộc đua 1 048 → 1 756 ms (chỉ khi xảy ra đua, không ảnh hưởng ảnh bình thường). Hai lô cùng kỳ (R3) chạy lần lượt: độ trễ mỗi lô ~2,9 s như trước (không chồng lên nhau nữa).

## Rủi ro CÒN LẠI (nói thẳng)
1. **R2 chỉ phủ đường tải MỘT ảnh.** `/sheets/batch` không khoá theo ảnh (khoá giữ tới hết cả lô có thể tạo vòng chờ với yêu cầu đơn). Cùng một tệp gửi ĐỒNG THỜI qua lô và qua đường đơn vẫn có thể gặp 409 / 500 (chưa đo; giao diện không dùng lô).
2. **R1 dùng "thử lại" chứ không khoá từ đầu** (SBD chỉ biết sau khi đọc ảnh, bên trong `service.py` đóng băng). Tối đa 3 lần thử; thử lại tốn thêm một lần chấm. Bên thua cuộc đua ép thường đi qua đường `duplicate_sbd` sẵn có (giữ `needs_review`).
3. **R3**: hai lô cùng kỳ thi xếp hàng (không song song). Lô vs yêu cầu đơn cùng kỳ: chưa chứng minh không thể có vòng chờ (chưa gặp trong 100 + 60 + 60 lượt).
4. **R4**: bảng `revoked_tokens` chỉ tăng (mỗi lần đăng xuất một dòng nhỏ; có `expires_at` để dọn sau, chưa có công cụ dọn). Bộ nhớ trong tiến trình làm thu hồi tức thì ở một worker; nhiều worker uvicorn chỉ dựa vào bảng (khe ms giữa commit và yêu cầu kế tiếp). Backend từ nay **không khởi động** khi `AUTH_MODE=on` mà chưa áp migration 006 (cố ý, an toàn). Đổi mật khẩu vẫn vô hiệu hoá mọi token như trước. Token cũ phát hành trước AR (không có nonce) vẫn dùng được và thu hồi được.
5. **R5**: giới hạn tính theo TIẾN TRÌNH (n worker → n × 4 chỗ). Phép đo sống không gặp 503 (chờ 8 s đủ cho 20 yêu cầu qua 3 chỗ); đường 503 + `Retry-After` được kiểm bằng test đơn vị và test endpoint, chưa quan sát trên máy chủ thật. Yêu cầu đang chờ giữ một kết nối CSDL (tối đa ~40 luồng) – chưa có pool (rủi ro #7 của AH, không đổi).
6. Không đụng: rủi ro #6 của AH (khoá đăng nhập theo (tên, IP), bộ đếm trong bộ nhớ), #7 (pool kết nối), nhiều worker, máy yếu hơn, điện thoại thật cùng lúc, hai giáo viên cùng duyệt một phiếu.
