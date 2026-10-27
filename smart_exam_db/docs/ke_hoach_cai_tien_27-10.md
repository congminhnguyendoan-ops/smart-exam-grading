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

**KẾT QUẢ (27/10/2026) – luật `vet_nho` ĐẠT cả 4 tiêu chí** (mã: `cv_engine/omr.py` `vet_nho_px`, `them_vet_nho`; commit `673f8a3`).
Luật chỉ CỘNG cờ `can_xem` + lý do `vet_nho` (mã mới trong `MA_LY_DO_OMR`); `trang_thai`, `dap_an`, `omr_m1.json` không đổi
(SHA `F8F87577…60AF` trước = sau).
| Chỉ số (56 ảnh train, `eval_omr.py run --phuong-phap m1`, OOF 7-fold) | Trước | Sau |
|---|---|---|
| Lỗi nặng (câu + cột) | 0 | 0 |
| Lỗi nhẹ | 6 | 6 |
| Cần xem thừa, câu rõ 1 ô: C1 / C2 / C3 / C4 / gộp | 0,27 / 2,71 / 1,10 / 2,19 / 1,57 % | giống hệt |
| Cần xem thừa, câu trống | 0 / 226 | 0 / 226 |
| Tổng câu cần xem | 563 (25,13%) | 563 (25,13%) |
| Điểm chính thức khớp (`kiem_backend_dau_cuoi.py`) | 56 / 56 | 56 / 56 |
| `doc_phieu` trung vị / max | 140,1 / 161,8 ms | 139,8 / 163,8 ms |
(1) lỗi nặng 0 ✓. (2) cần xem thừa +0,00 điểm % ở mọi điều kiện ✓: `cau/cot/o_train.csv` giống từng byte trước/sau (luật gắn
cờ 0 câu trên 56 ảnh, vì blank thật tối đa 65 px < 90). (3) chấm giả ≥ 0,3r xám 30 / 90 gắn cờ 100% ✓ (`tests/test_omr_ma_tran_o_to.py`:
40/40 câu, cả 0,2r). (4) 232 test cũ đạt; thêm 22 → 254 đạt. Cách "trước": cùng `eval_omr.py` với `omr.VET_PX = 10**9` (vô hiệu luật).
Tái tạo: `python -m pytest tests/test_omr_ma_tran_o_to.py` · `python tools/eval_omr.py run --phuong-phap m1` · `report` ·
`python tools/kiem_backend_dau_cuoi.py`. Ca bị bỏ: chấm nhỏ < ~0,15r (diện tích < 90 px) và chấm nhạt hơn 0,6 × giấy vành.
Chưa áp dụng cho bubble SBD / mã đề (chưa đo phân phối bubble, hai kênh bubble + CNN đã đối chiếu) → nợ kỹ thuật.

**Ghi trung thực**: `omr.py` đã đổi SAU commit đăng ký test cuối `551b356` → kết quả test cuối 21/10 là của phiên bản cũ.
KHÔNG chạy lại; kiểm lại phải ĐĂNG KÝ MỚI (người dùng quyết). Luật được chỉnh/đánh giá chỉ trên dev; 4 ô blank có hạt mực thật
(0023 q26B, 0010 q25B) nằm dưới ngưỡng, không bị gắn cờ.

### 6.4 Nợ "thang S_anh phụ thuộc cả tờ" – đo (28/10/2026) và QUYẾT ĐỊNH: CHƯA SỬA
Công cụ `tools/omr_s_anh.py` (chỉ đọc, 56 ảnh train, mô hình OOF theo fold; ghi `data/_eval/omr/s_anh/`: `bang_tat_ca.md`, `o_ro_chac.csv`,
`ld_thap.html`). Tái tạo: `python tools/omr_s_anh.py tat_ca`.

**a) S_anh**: min 0,400 · p50 0,682 · max 0,804; **0/56 ảnh chạm sàn 0,20** (C1 0,52–0,78; C2 0,40–0,77; C3 0,44–0,79; C4 0,55–0,80).
Mọi phiếu thật trong dev đều có đủ nét tô đậm, nên chưa quan sát được tờ "nhạt cả tờ" (đó là kịch bản cần phiếu 0105 ở đợt 2).

**b) ld tuyệt đối (1 − TB lõi / giấy vành) của ô "rõ chắc"** (câu 1 ô, không cờ; n = 1 451): p0,1 / p1 / p5 / p50 = 0,350 / 0,419 / 0,494 / 0,730.
Theo điều kiện: C1 0,515 / 0,532 / 0,556 / 0,740 · **C2 0,340 / 0,361 / 0,434 / 0,696** · C3 0,428 / 0,459 / 0,494 / 0,724 · C4 0,526 / 0,541 / 0,571 / 0,777.
Ô nhãn faint (366) máy đọc faint (360): p0,1 0,167 · p1 0,202 · p5 0,250 · p50 0,424; đọc filled (6): 0,373 / 0,379 / 0,405 / 0,628.

**c) Số ô "rõ chắc" ld < mức** (= câu thật bị gắn cờ thêm): < 0,35 → 2 (0,14%) · < 0,40 → 10 (0,69%) · < 0,45 → 24 (1,65%) · < 0,50 → 77 (5,31%).
Gần như toàn bộ nằm ở C2 (< 0,40: 10/360 = 2,78%; < 0,45: 23 = 6,39%; < 0,50: 55 = 15,28%) rồi C3.

**d) Ảnh giả** (nền đệm bút × vệt lạc 1 ô; ô = trạng thái / cờ [ld tuyệt đối của vệt]; ld vệt = 1 − xám/255: 120 → 0,53 · 150 → 0,41 · 170 → 0,33 ·
190 → 0,25 · 210 → 0,18 · 230 → 0,10):
| nền đệm (S_anh) | vệt 120 | vệt 150 | vệt 170 | vệt 190 | vệt 210 | vệt 230 |
|---|---|---|---|---|---|---|
| 30 (0,84) | mờ/XEM | mờ/XEM | mờ/XEM | mờ/XEM | mờ/XEM | trống/– |
| 90 (0,60) | **rõ/–** | mờ/XEM | mờ/XEM | mờ/XEM | mờ/XEM | trống/– |
| 150 (0,37) | **rõ/–** | **rõ/–** | **rõ/–** | **rõ/–** | mờ/XEM | trống/– |
| 190 (0,21) | **rõ/–** | **rõ/–** | **rõ/–** | **rõ/–** | **rõ/–** | trống/XEM |
Lỗ hổng xác nhận: vệt lạc xám 120–210 bị đọc "rõ chắc" không cờ trên nền đệm nhạt (in đậm ở trên).

**Luật ứng viên `nhat_tuyet_doi` + tiêu chí (chốt trước khi đo, theo lệnh 28/10)**: ô xếp "rõ chắc" mà ld < X → câu `can_xem` (lý do mới, chỉ cộng cờ).
(1) lỗi nặng 0 / 56 ảnh train; (2) cần xem thừa câu 1 ô không tăng quá +1,0 điểm % ở mỗi điều kiện so với bảng sau lệnh A (0,27 / 2,71 / 1,10 / 2,19 %);
(3) ảnh giả: vệt lạc đơn xám ≥ 150 trên mọi nền (30 / 90 / 150 / 190) bị gắn cờ 100%, ô đậm xám ≤ 80 trên nền 30 không bị gắn cờ; (4) test cũ vẫn đạt.

**Kết luận: KHÔNG có X thoả (2) và (3) – không nới tiêu chí, KHÔNG sửa `omr.py`.**
- (3) cần X > 0,4118 (vệt xám 150 có ld 0,4118) trên cả nền 150 và 190. Tại X = 0,412: C1 0 · **C2 +13 câu** · C3 0 · C4 0 → C2 +13/369 = **+3,5 điểm %** (mức cho phép +1,0 ≈ 3 câu).
- (2) cần X ≲ 0,355 (≤ 3 câu ở C2: ld thật p0,1 = 0,350 – chỉ 2 ô < 0,35) → không gắn cờ vệt xám 150 (ld 0,41).
- Nguyên nhân: ô "rõ chắc" thật ở C2 (ảnh tối / tương phản thấp) có ld 0,34–0,5, TRÙNG dải ld của vệt lạc giả 0,25–0,41. Một ngưỡng ld tuyệt đối đơn lẻ không tách được; cần đặc trưng khác
  (độ phủ đồng đều, so với mức nét của chính tờ…) – ngoài phạm vi luật ứng viên, chưa thử.
- Ghi chú về (3): vệt xám 230 (ld 0,10) mô hình đã xếp "trống" nên không thuộc luật "rõ chắc" – không tính vào tiêu chí.

**Giữ nợ kỹ thuật.** Việc kiểm tiếp: phiếu **0105 (tô nhạt cả tờ) ở đợt 2** (trên bản mã đóng băng, không chỉnh theo kết quả). Cần xem bằng mắt: `data/_eval/omr/s_anh/ld_thap.html`
(20 ô "rõ chắc" thật có ld thấp nhất).

### 6.5 Test chập chờn `test_val_bi_khoa_neu_khong_xac_nhan` (Bước 1, 28/10/2026) – ĐÃ TÌM RA, đã sửa (commit `5d99769`)
Không phải chập chờn mà phụ thuộc môi trường: tái tạo tất định khi KHÔNG đặt `PYTHONIOENCODING` (Bash của harness; PowerShell / vòng lặp có đặt thì đạt: 10/10 chạy riêng + 3/3 cả bộ, `data/_eval/pytest_lap/`).
Tiến trình con `eval_ocr.py` in thông báo có dấu "–" bằng cp1252 (byte 0x96); tiến trình cha `subprocess.run(text=True, encoding="utf-8")` giải mã lỗi trong luồng đọc → `r.stderr = None` → `None + str` = `TypeError`.
Sửa test (không đổi công cụ / tiêu chí): chạy tiến trình con với `PYTHONUTF8=1`. Các `subprocess.run` khác trong `tests/` chỉ nhận ASCII (git, node) nên không bị.

### 6.6 Luật mức tờ `to_nhat` (28/10/2026) – đo, chốt luật và tiêu chí TRƯỚC khi sửa code
Lý do: ở tờ nhạt cả tờ, vệt lạc nhạt bằng nét đáp án thì không đặc trưng riêng một ô nào phân biệt được (mục 6.4); nhưng trung vị ld của các ô "rõ chắc" cả tờ
(**T**) tách được. Quyết định người dùng 28/10: chưa có ảnh đợt 2 nào nên mở khoá đóng băng chưa làm mất tính khách quan; khoá lại v2 rồi không đổi mã cho tới khi chạy xong đợt 2.
Công cụ `tools/omr_to_nhat.py` (chỉ đọc; ghi `data/_eval/omr/to_nhat/`: `bang_*.md`, `t_thap.html`). Tái tạo: `python tools/omr_to_nhat.py tat_ca`.

**a) T trên 56 ảnh train** (T = trung vị ld của ô "rõ chắc" mỗi phiếu; n = số ô):
| điều kiện | T min | T p5 | T p50 | n min | p10 min | p25 min |
|---|---|---|---|---|---|---|
| C1 | 0,575 | 0,592 | 0,740 | 19 | 0,532 | 0,552 |
| C2 | **0,467** | 0,470 | 0,696 | 19 | 0,366 | 0,403 |
| C3 | 0,491 | 0,520 | 0,725 | 20 | 0,458 | 0,465 |
| C4 | 0,601 | 0,605 | 0,780 | 22 | 0,545 | 0,563 |
| tất cả | 0,467 | 0,507 | 0,731 | 19 | 0,366 | 0,403 |
5 ảnh T thấp nhất: 0022_C2 0,467 · 0010_C2 0,472 · 0022_C3 0,491 · 0025_C2 0,512 · 0013_C2 0,526 (đều ≥ 24 ô).

**b) Tờ giả một độ đậm** (40 câu, mỗi câu 1 ô): xám 30 / 60 / 90 / 120 / 150 / 190 → T = 0,882 / 0,765 / 0,647 / 0,529 / **0,412** / **0,255**; cả 40 câu đều "rõ/không cờ" ở mọi mức (lỗ hổng xác nhận).
**T giả chồng lấn T thật**: xám 120 (T 0,529) nằm TRONG dải T thật (0,467–0,80) → tờ bút nhạt vừa không tách được khỏi tờ thật bằng T; chỉ xám ≥ 150 tách được.
**c) Tờ nhạt + vệt lạc** (nền 150 / 190; câu 1 vệt 1 ô): hiện tại vệt 170 và 190 là "rõ/không cờ" ở cả hai nền; vệt 210 là "mờ/XEM" ở nền 150 và "rõ/không cờ" ở nền 190.

**Luật `to_nhat`**: sau khi có kết quả 40 câu (đã gồm `vet_nho`), tính T trên câu "rõ chắc"; nếu **n ≥ 10 và T < Xs** ⇒ phiếu "tô nhạt cả tờ": MỌI câu có ≥ 1 ô được chọn (rõ / mờ / nhiều ô)
thêm `can_xem = True`, lý do `to_nhat` (mã mới trong `MA_LY_DO_OMR`: "Phiếu tô nhạt cả tờ – nên kiểm tra lại các câu đã chọn."), và `KetQuaOMR.to_nhat = True` + `KetQuaOMR.do_toi_to = T` (cảnh báo mức phiếu).
Chỉ CỘNG cờ; không đổi trạng thái / đáp án; không đổi `models/*.json`.
**Xs = 0,44**: nằm giữa T thật nhỏ nhất 0,467 (biên 0,027) và T tờ giả xám 150 = 0,412 (biên 0,028) – trung điểm khoảng trống (0,412; 0,467). Biên hẹp ở phía thật: một phiếu bút chì 2B ở C2 chụp tối ở đợt 2
có thể rơi dưới 0,44 (sẽ là "cần xem thừa", không phải lỗi); ngược lại tờ nhạt thật có T ∈ [0,44; 0,53] không bị bắt (chồng lấn đã nêu ở b) – giới hạn đã biết.

**Tiêu chí đạt (chốt trước)**: (1) lỗi nặng vẫn 0 / 56 ảnh train (OOF); (2) số phiếu thật bị gắn `to_nhat` ≤ 1 / 56 và cần xem thừa câu 1 ô không tăng quá +1,0 điểm % ở mỗi điều kiện
so với bảng sau lệnh A (0,27 / 2,71 / 1,10 / 2,19 %); (3) tờ giả một độ đậm xám ≥ 150 bị gắn `to_nhat` 100% (mọi câu đã chọn có cờ), xám ≤ 80 KHÔNG gắn, xám 90–120 báo kết quả (không ràng buộc);
(4) toàn bộ test cũ vẫn đạt. Không có Xs thoả (1)–(3) thì KHÔNG nới tiêu chí: ghi "chưa sửa", giữ nợ, kiểm bằng phiếu 0105 ở đợt 2, giữ tag cũ.

**KẾT QUẢ (28/10/2026) – luật `to_nhat` ĐẠT cả 4 tiêu chí** (mã `cv_engine/omr.py` `them_to_nhat`, `TO_NHAT_X` = 0,44, `TO_NHAT_N` = 10; commit `5e04d01`).
| Chỉ số (56 ảnh train, `eval_omr.py run --phuong-phap m1`, OOF) | Trước (`TO_NHAT_X` = −1) | Sau |
|---|---|---|
| Lỗi nặng (câu + cột) | 0 | 0 |
| Cần xem thừa câu rõ 1 ô: C1 / C2 / C3 / C4 / gộp | 0,27 / 2,71 / 1,10 / 2,19 / 1,57 % | giống hệt |
| Tổng câu cần xem (`kiem_backend_dau_cuoi.py`) | 560 / 2240 | 560 / 2240 |
| Phiếu thật bị gắn `to_nhat` | – | **0 / 56** (T min 0,467 ≥ 0,44) |
| Điểm chính thức khớp độc lập | 56 / 56 | 56 / 56 |
| `doc_phieu` trung vị / max | 144,6 / 179,3 ms | 144,5 / 159,8 ms |
`cau/cot/o_train.csv` giống từng byte trước/sau. SHA `omr_m1.json` không đổi (`F8F87577…60AF`). Tiêu chí: (1) ✓; (2) ✓ (0 ≤ 1 phiếu; +0,00 điểm %);
(3) ✓ `tests/test_omr_ma_tran_o_to.py::test_to_nhat_*`: tờ giả xám 150 / 190 → 40/40 câu có cờ `to_nhat`, xám 30 / 60 / 80 → không; vệt lạc trên tờ nhạt (150+170, 150+190, 190+190, 190+210) → có cờ;
xám 90 (T 0,647) và 120 (T 0,529) KHÔNG bị gắn (T nằm trong dải T thật – giới hạn đã nêu ở b); (4) 264 test đạt (254 cũ + 10 mới).
Cách "trước": cùng `eval_omr.py` với `omr.TO_NHAT_X = -1.0` (vô hiệu luật). Tái tạo: `python -m pytest tests/test_omr_ma_tran_o_to.py` · `python tools/eval_omr.py run --phuong-phap m1` · `report` · `python tools/kiem_backend_dau_cuoi.py`.
Giới hạn: luật chưa từng được thử trên tờ nhạt THẬT (dev không có); chỉ bắt tờ có T < 0,44 (nhạt hơn xám ~143); tờ nhạt vừa (T 0,44–0,53) vẫn còn nợ cũ; n < 10 ô "rõ chắc" thì không đánh giá.
**Đổi mã này xảy ra TRƯỚC khi có bất kỳ ảnh đợt 2 nào.**

## 7. ĐÓNG BĂNG MÃ cho test đợt 2 (28/10/2026)
Quyết định người dùng: giữ N = 90 px (không hạ theo dữ liệu dev); bubble SBD / mã đề giữ nợ; test cuối mới đăng ký trên **đợt 2** (phiếu 0101–0110, chụp bằng điện thoại,
chưa có ảnh) ở lệnh sau. Mã đóng băng: tag cục bộ `ma-dot2-dong-bang` (commit `b53a343`); SHA-256 các file lõi + tham số: `docs/dong_bang_ma_dot2.json`.
Từ đây chỉ được đổi `docs/` và `CLAUDE.md` cho tới khi chạy test đợt 2. Sáu file đợt 2 chép nguyên vẹn vào `answer_sheet/dot2/` (commit `b53a343`).
- **Ghi trung thực**: `omr.py` đã đổi sau commit đăng ký `551b356` (luật `vet_nho`) nên kết quả test cuối 21/10 là của bản cũ; đợt 2 là phép kiểm MỚI trên bản đóng băng.
- **Giới hạn `vet_nho`**: ngưỡng 90 px nằm sát chấm bút bi cỡ ~1 mm (~110 px ở 300 DPI); phiếu đợt 2 dùng chấm ~1,5 mm (~250 px).
- Nợ `nhat_tuyet_doi` (mục 6.4) KHÔNG cài; đợt 2 kiểm bằng phiếu 0105 (tô nhạt cả tờ) – chỉ báo cáo, không chỉnh mã theo kết quả.

### 7b. Khoá lại v2 (28/10/2026)
Mở khoá để thêm `to_nhat` (mục 6.6), khoá lại: tag cục bộ `ma-dot2-dong-bang-v2`, SHA + tham số ở `docs/dong_bang_ma_dot2.json` (bản v1 giữ trong mục `lich_su`).
Từ tag v2: không sửa file hiện có của `cv_engine/`, `models/`, `backend/`, `answer_sheet/output/`, `docs/dong_bang_ma_dot2.json`; chỉ được thêm FILE MỚI vào `tools/`, `tests/`, `docs/`, `answer_sheet/dot2/` trước đăng ký.
Nợ `nhat_tuyet_doi` theo từng ô (mục 6.4) vẫn KHÔNG cài; luật mức tờ thay thế một phần.

### 7c. Phát hiện lỗi backend khi thử công cụ đợt 2 → khoá lại v3 (28/10/2026)
**Lỗi**: `tools/eval_dot2.py run --thu-gia` (ảnh giả hoá, phiếu 0105) dừng với `RuntimeError: phiếu …: điểm Python 1,25 ≠ fn_grade_sheet 1,75 (cần xem còn lại 2)`.
Nguyên nhân gốc: `backend/service.py` `LY_DO_OMR_CAU = {o_mo, tin_cay_thap, vi_tri}` – mã câu MỚI `vet_nho` (lệnh A) và `to_nhat` (lệnh này) chưa có trong tập. Khi mọi câu còn "cần xem"
chỉ mang mã mới thì `danh_gia_phieu` không gom được lý do → coi là "hết lý do" → chốt an toàn ném `RuntimeError` (không ghi điểm sai, nhưng phiếu lẽ ra vào hàng đợi giáo viên lại gây lỗi 500).
Không lộ ở lệnh A vì luật chưa từng gắn cờ câu nào trên 56 ảnh train. Sửa: thêm hai mã vào `LY_DO_OMR_CAU` (+ nhãn giao diện `frontend/app.js`, mô tả `schemas.py`) và test
`tests/test_backend_ly_do_omr.py` (mọi mã lý do câu của `MA_LY_DO_OMR` phải được backend xử lý; thất bại trên mã cũ, đạt trên mã mới). Commit `1eb3444`.
Đây là sửa BACKEND (phạm vi đóng băng) nên đóng băng v2 bị thay bằng **v3** (tag `ma-dot2-dong-bang-v3`); **vẫn TRƯỚC khi có bất kỳ ảnh đợt 2 nào** và không chỉnh theo dữ liệu nào.
Đầu-cuối sau sửa: `kiem_backend_dau_cuoi.py` 0 câu chấm sai không cờ, điểm 56/56; pytest 274 đạt.
Chạy thử công cụ trên ảnh giả hoá (`python tools/eval_dot2.py tao-gia` → `run --thu-gia --xem`, 20 ảnh): H2 / H3 / H4 / H5 = 0 lỗi, điểm cuối đúng 20/20; vết 60/60 gắn cờ; 0107 SBD "cần xem" (thieu_bubble) cả 2 ảnh;
0105 mọi câu có ô được chọn đều có cờ. CHỈ là số tham chiếu của công cụ (ảnh vẽ phẳng, không chữ viết tay), không đưa vào tiêu chí.

## 8. Yêu cầu 1 và 7 – tên môn / lớp + đăng nhập giáo viên + phân quyền theo lớp (nhánh `cai-tien-b`, 29/10/2026) – XONG
Thiết kế, bảng endpoint × quyền, tự rà, sự cố 002 và quy trình chạy đợt 2 an toàn: `docs/thiet_ke_dang_nhap.md`. Làm trên nhánh `cai-tien-b` (từ `d3d0426`); **không gộp về `main`, không đổi tag**; đợt 2 chạy từ tag `dang-ky-dot2`.
- Migration `002_lop_giao_vien.sql` (đã áp, chỉ thêm): `exams.class_id`, `teacher_classes`. Dữ liệu mẫu: `tools/nap_giao_vien_demo.py --ap-dung` (gv_an → CNTT-K22A / IT3080, gv_binh → CNTT-K22B / IT4040; 4 kỳ thi demo của gv_an gắn CNTT-K22A).
- Kết quả: pytest **345 đạt + 1 skip có chủ đích** (test đăng ký trên nhánh), gồm 44 test đăng nhập / phân quyền cần CSDL (không skip) + 27 không cần CSDL; hồi quy `kiem_backend_dau_cuoi.py` 56/56, 0 câu chấm sai không cờ; `cv_engine/` và `models/` không đổi so với `d3d0426`.
- Thử tay (token dựng từ hash trong CSDL, chỉ GET): gv_an thấy 5 kỳ thi + lớp CNTT-K22A (5 SV); gv_binh thấy 0 kỳ thi + lớp CNTT-K22B (5 SV); chéo lớp / chéo kỳ thi → 404; admin thấy tất cả; Excel có "Môn: …" (A4) và "Lớp: …" (F4). Ảnh chụp: `data/_eval/ui_b/`.
- Tái tạo: `python -m backend.migrate` · `python -m pytest tests` · `python tools/kiem_backend_dau_cuoi.py`.

