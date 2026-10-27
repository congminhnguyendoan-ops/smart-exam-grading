# Kế hoạch cải tiến (bắt đầu 27/10/2026)

## Yêu cầu của người dùng (27/10/2026)

| # | Yêu cầu |
|---|---|
| 1 | Thêm tên môn, tên lớp |
| 2 | Chụp từ điện thoại, chấm liền, không chuyển file, không lưu ảnh / bước thừa |
| 3 | Tìm hiểu OCR/OMR; muốn OCR thay CNN vì giảng viên nói CNN khá lớn |
| 4 | Đủ các trường hợp ô tô |
| 5 | Chấm đủ 40 câu |
| 6 | Xem lại code vùng đậm–nhạt 0–255 |
| 7 | Đăng nhập giáo viên, phân quyền theo lớp (cá nhân, lớp dạy, học sinh) |

## 6. Rà độ tối 0–255 (`omr.py` `_do_o`, `dac_trung_o`)

Độ tối = 1 − TB lõi (0,75r) / giấy vành (1,15–1,45r) → không phụ thuộc độ sáng tuyệt đối của ảnh.
Bộ test ma trận: `tests/test_omr_ma_tran_o_to.py` (vẽ ô bằng điểm ảnh thật, chạy cả chuỗi `doc_phieu`).

### 6.1 Ranh giới rõ / mờ / trống phụ thuộc cả tờ
Mô hình đo độ tối theo thang của CHÍNH TỜ PHIẾU (`S_anh` trong `omr.py`). Với tờ bút đen (các câu khác xám 30):
xám ≤ 80 rõ · 120–205 mờ, cần xem · ≥ 235 trống · 220 vùng đệm. Tờ toàn bút chì nhạt (xám 150) thì xám 170–190
vẫn là "rõ" → một vệt nhạt lạc trên tờ toàn nét nhạt không bị gắn cờ. **Nợ kỹ thuật, chưa sửa** (thiên lệch an toàn
khi tờ đậm, không an toàn khi tờ nhạt).

### 6.2 Vùng đệm 205–235
Xám 100 (rõ/mờ, giấy tối) và 220 (mờ/trống) là vùng đệm: test không khẳng định trạng thái ở đó.

### 6.3 LỖ HỔNG: chấm nhỏ đậm → trống, không cần xem
Chấm bán kính 0,3r, xám 30 (≈ 11% diện tích lõi) bị đọc là TRỐNG và `can_xem = False` (câu bị bỏ sót không báo).
`test_cham_nho_dam_phai_can_xem` đang `xfail(strict)`. Luật phụ `vet_nho` sẽ chốt ở Bước 2–3 của phiên cải tiến
(điền kết quả vào đây).

Giới hạn của phép thử: ảnh vẽ giả phẳng, chưa có nhiễu thật.
