# Lệnh BB – kết quả luật "đen đủ dày" (21/11/2026): KHÔNG ĐẠT tiêu chí (b) → không sửa `omr.py` (mục (e))

Tiêu chí đăng ký trước: `docs/tieu_chi_luat_den_day.md` (commit `3c1309f`). Công cụ: `tools/bb_luat_den_day.py phan-bo | do` (chỉ đọc ảnh, không ghi CSDL, không đọc test); kết quả thô `data/_eval/bb/` (ngoài git). Luật được mô phỏng trong công cụ; `cv_engine/omr.py`, `models/` không đổi.

## Phân bố (train + val, ô nhãn một lựa chọn)

| nhãn | đặc trưng | n | min | p1 | p5 | trung vị | p95 | p99 | max |
|---|---|---|---|---|---|---|---|---|---|
| faint | phu_dam | 434 | 0,040 | 0,069 | 0,107 | 0,545 | 0,873 | 0,949 | 0,981 |
| faint | tuyet_doi | 434 | 0,297 | 0,348 | 0,399 | 0,560 | 0,747 | 0,788 | 0,817 |
| faint | phu_nhe | 434 | 0,459 | 0,554 | 0,640 | 0,862 | 0,997 | 1,000 | 1,000 |
| filled | phu_dam | 1792 | 0,026 | 0,403 | 0,888 | 0,995 | 1,000 | 1,000 | 1,000 |
| filled | tuyet_doi | 1792 | 0,367 | 0,498 | 0,597 | 0,780 | 0,890 | 0,912 | 0,965 |
| filled | phu_nhe | 1792 | 0,827 | 0,959 | 0,986 | 1,000 | 1,000 | 1,000 | 1,000 |

## Theo từng tiêu chí

| Mục | Kết quả | Kết luận |
|---|---|---|
| (a) 56 ảnh dev | lỗi nặng 0 → 0; câu cần xem 560 → 529 (−31); NHƯNG trong 31 câu đổi trạng thái có 23 câu nhãn `faint` (chỉ 8 câu nhãn `filled`) | KHÔNG ĐẠT điều kiện "mọi câu đổi phải có nhãn filled" |
| (b) biên với ô mờ | 26 / 434 ô nhãn mờ thoả cả ba điều kiện; `min g(c)` = −0,050 (cần ≥ +0,20) | **KHÔNG ĐẠT** |
| (b) phụ | 23 câu nhãn `faint` (train) bị đổi thành `ro` (cần 0) | KHÔNG ĐẠT |
| (c) 4 ô gạch chéo → `ro` | 23535 câu 13C, 21B, 28C và 23536 câu 10A đều thành `ro` | đạt |
| (c) 4 ô nhạt thật vẫn `mo` | 23536 câu 1, 33 và 23535 câu 10D, 40C vẫn `mo` | đạt |
| (d) 13 ảnh AG | 0 lỗi im lặng mới (cả theo kịch bản lẫn theo tệp lệch đã xác minh); 34 câu thoát hàng đợi, tất cả máy đọc đúng đáp án kịch bản | đạt |

## 4 phiếu 23533–23536 (câu cần xem trước → sau)

- 23533: không đổi (1, 30, 33).
- 23534: 5, 20, 21, 22, 23, 27, 31 → 5, 27, 31 (4 câu 20–23 thoát; ngoài 4 ô bạn nêu).
- 23535: 10, 13, 21, 28, 40 → 10, 40.
- 23536: 1, 10, 30, 33 → 1, 30, 33.
- Không phiếu nào mang cờ `to_nhat`.

## Vì sao (b) không đạt

Ô nhãn `faint` trong bộ train + val có nhiều ô đen đậm (`phu_dam` p99 0,949, `tuyet_doi` max 0,817, `phu_nhe` p95 0,997), nằm cùng dải với ô gạch chéo bạn nêu (`phu_dam` 0,872–0,954, `tuyet_doi` 0,684–0,817). Nhãn `faint` là ý định của kịch bản tô, không phải độ đen đo được (đã ghi ở mục 6: mờ p95 0,85, rõ p5 0,88). Ba đặc trưng này không tách được hai nhóm với biên 0,20 ở ngưỡng đã đăng ký; tôi chưa kiểm cho ngưỡng khác vì tiêu chí cấm chỉnh sau khi nhìn kết quả.

## Hệ quả thực tế của việc đổi `mo` → `ro` trên 23 ô nhãn mờ

Máy vẫn đọc đúng ô (đáp án máy = nhãn ở cả 31 câu đổi); thay đổi duy nhất là câu không còn vào hàng đợi duyệt. Điều chưa đo được: ý định của thí sinh với ô tô đậm nhưng người gán nhãn đặt là mờ.
