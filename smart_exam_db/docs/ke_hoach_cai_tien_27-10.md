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
`test_cham_nho_dam_phai_can_xem` đang `xfail(strict)`.

**Đo (Bước 2, chỉ 56 ảnh train, 6 766 ô blank / 366 faint / 1 828 filled)** – công cụ `tools/omr_vet_nho.py` (chỉ đọc;
ghi `data/_eval/omr/vet_nho/`: `vet_nho_o.csv`, `phan_phoi.md`, `vet_nho.html`). Tái tạo: `python tools/omr_vet_nho.py do`.

Hai biến thể đầu (theo đề: "mực thêm" = tối hơn giấy mà không tối ở mẫu phiếu trắng) ĐÃ THỬ VÀ LOẠI:
| Biến thể | Chấm giả 0,2r / 0,3r (xám 30) | Ô blank thật (tối đa) | Kết luận |
|---|---|---|---|
| 1. trừ nét in sẵn của mẫu, nở 4 px | 0 / 0 px | 61 px | chấm giữa ô bị chữ A–D che hết |
| 2. như 1 + mọi điểm < 0,4 × giấy | 113 / 253 px | 146 px | chữ A–D trên ảnh thật sắc nét hơn mẫu → lọt ra |
| 3. **phép mở elip 7×7** trên điểm lõi < 0,6 × giấy, lấy cụm lớn nhất (CHỌN) | 119 / 256 px | 65 px | tách được |

Biến thể 3: nét chữ dày ~3–4 px bị phép mở xoá, khối đặc còn lại. Phân phối (b) = `vet_px`, px @300 DPI (lõi ≈ 1 537 px):
| nhãn | n | p50 | p99 | p99,9 | max |
|---|---|---|---|---|---|
| blank (C1–C4) | 6 766 | 0 | 0 | 0 | 65 (C1 0 · C2 47 · C3 60 · C4 65) |
| faint | 366 | 174 | 1 394 | 1 473 | 1 488 |
| filled | 1 828 | 1 524 | 1 543 | 1 546 | 1 546 |
Chỉ 4 ô blank có (b) > 0: 0023 câu 26B (65 / 60 px, ảnh C4 / C3), 0010 câu 25B (47 / 40 px, C2 / C3) – hạt mực thật nhỏ,
thấy ở cả 2 ảnh của phiếu (xem `vet_nho.html`), không phải lỗi định vị (`vi_tri_xau` = 0). Chấm giả (min qua 40 câu, ô B,
`python tools/omr_vet_nho.py gia`): 0,2r → 119 px · 0,3r → 256 · 0,4r → 447 · 0,5r → 707, không đổi theo xám 30 / 90 / 150.

**Luật chốt (trước khi sửa code)**: với mỗi ô KHÔNG được chọn (p(có tô) < 0,5) trong câu, nếu `vet_px` ≥ **N = 90 px** thì câu
`can_xem = True`, lý do `vet_nho`. Không đổi `trang_thai` / `dap_an` (chỉ CỘNG cờ). N = 90 nằm giữa blank thật tối đa (65,
biên ×1,38) và chấm giả nhỏ nhất 0,2r (119, biên ×1,32). Chưa áp dụng cho bubble SBD / mã đề (chưa đo bubble; hai kênh
bubble + chữ viết tay đã đối chiếu) → nợ kỹ thuật.

**Tiêu chí đạt (chốt trước)**: (1) lỗi nặng vẫn 0 trên 56 ảnh train; (2) "cần xem thừa" ở câu trống chắc không tăng quá +1,0 điểm %
tuyệt đối ở mỗi điều kiện C1–C4 so với bảng gốc; (3) chấm nhỏ giả bán kính ≥ 0,3r xám ≤ 90 gắn cờ 100%; (4) toàn bộ 232 test cũ
vẫn đạt. Không đạt thì KHÔNG nới tiêu chí: ghi "chưa sửa được", giữ xfail.

Giới hạn: phép thử vẽ giả phẳng, chưa nhiễu thật; chấm nhỏ nhạt hơn 0,6 × giấy vành không bị bắt.
