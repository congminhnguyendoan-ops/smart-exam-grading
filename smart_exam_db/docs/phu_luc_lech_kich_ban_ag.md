# Phụ lục – Lệch kịch bản khi thử giấy thật (lệnh AG2)

> **Đây là xác minh SAU khi đã có kết quả.** Phụ lục này KHÔNG sửa `data/_eval/ag/ket_qua.md`, `ket_qua.json`, KHÔNG đổi tiêu chí
> `docs/tieu_chi_thu_giay_that.md` (commit `18fd340`), không đổi ngưỡng / mô hình / mã hệ thống, không chạy lại bằng ảnh khác.
> **Kết luận chính thức giữ nguyên: C1 = KHÔNG ĐẠT, H3 = ĐẠT.**

## 1. Hai ca lệch

| # | Ảnh | Câu | Kịch bản | Người tô thực tế (theo lời nhóm) | Máy đọc (`ket_qua.json`) | Kết quả chính thức |
|---|---|---|---|---|---|---|
| 1 | T01.JPG | 37 | bỏ trống | tô ô **A** (lỡ tay) | `A`, trạng thái `ro`, KHÔNG cần xem; p(rõ) A = 0,921, p(có tô) A = 1,0 | **sai âm thầm** (ca duy nhất làm C1 KHÔNG ĐẠT) |
| 2 | T08.JPG | 21 | đáp án A (bình thường) | tô **hai ô A và C** | `AC`, trạng thái `nhieu`, cần xem (`nhieu_o`); p(có tô) A = 1,0, C = 1,0 | cần xem (đếm vào "câu bình thường bị cờ") |

## 2. Nguồn ghi nhận

- **Lời nhóm thử giấy thật**, báo lúc **21:36 ngày 04/11/2026** – SAU khi `ket_qua.md` / `ket_qua.json` đã được ghi (21:33:38 cùng ngày).
- Ghi chú trên phiếu lúc tô: **không rõ** (để trống).
- Hai ca này KHÔNG có trong kịch bản (`data/_eval/ag/kich_ban.json`) và không được báo trước khi chấm.

## 3. Bằng chứng

Ảnh cắt từ ảnh **nắn phẳng** (`preprocess()` trên đúng ảnh đã chấm, chỉ để cắt – không chấm lại), lưu ở `data/_eval/ag/phu_luc_lech/` (KHÔNG commit;
`data/` ngoài git). Mỗi ảnh: hàng câu đó + nửa hàng trên / dưới, phóng 2×.

| Tệp | Ảnh gốc (SHA-256) | Nhìn bằng mắt | Độ tối trung bình 0,6 R quanh tâm ô (0 trắng – 1 đen) |
|---|---|---|---|
| `T01_cau37.png` (SHA `D82A25BA…`) | T01.JPG `3472cb4c…` | Ô A tô kín, đậm như các câu tô thật bên cạnh; B, C, D trống | A 0,787 · B 0,318 · C 0,301 · D 0,280 |
| `T08_cau21.png` (SHA `C52BBF1A…`) | T08.JPG `0e87048c…` | Ô A và ô C cùng tô kín, đậm; B, D trống | A 0,903 · B 0,332 · C 0,944 · D 0,283 |

(Ô trống trên ảnh thật có độ tối ~0,27–0,38 do viền + chữ in sẵn – CLAUDE.md mục 8.) Ảnh và số đo khớp lời nhóm: trên giấy, T01 câu 37 có một ô A tô thật
(không phải vết), T08 câu 21 có hai ô tô thật. Bản ghi đo: `data/_eval/ag/phu_luc_lech/bang_chung.json`.

## 4. Bảng phụ "sau xác minh" (bên cạnh bảng chính thức, KHÔNG thay thế)

Cách tính: lấy nguyên kết quả máy đọc trong `ket_qua.json` (không đọc lại ảnh), chỉ thay "đáp án đúng" của hai câu trên bằng cái người tô đã tô
(T01:37 → `A`, loại "bình thường"; T08:21 → `AC`, loại "hai ô"). Công cụ: `python tools/ag_cham_that.py sau-xac-minh --lech-kich-ban data/_eval/ag/lech_kich_ban.json`
→ `data/_eval/ag/sau_xac_minh.md|json`. Công cụ tái tạo bảng chính thức từ `ket_qua.json` và dừng nếu không khớp; `cham` không bao giờ đọc tệp lệch.

| Loại | Số câu (CT / SXM) | Đọc đúng (CT / SXM) | Cần xem (CT) | Cần xem (SXM) | Sai âm thầm (CT / SXM) |
|---|---|---|---|---|---|
| bình thường (1 ô đậm) | 413 / 413 | 373 / 374 | 40/413 (9,7%) | 39/413 (9,4%) | 0 / 0 |
| bỏ trống | 23 / 22 | 22 / 22 | 0/23 (0,0%) | 0/22 (0,0%) | **1 / 0** |
| nhạt | 23 / 23 | 0 / 0 | 23/23 | 23/23 | 0 / 0 |
| hai ô | 23 / 24 | 0 / 0 | 23/23 | 24/24 | 0 / 0 |
| tẩy | 12 / 12 | 0 / 0 | 12/12 | 12/12 | 0 / 0 |
| vết | 26 / 26 | 12 / 12 | 14/26 | 14/26 | 0 / 0 |

CT = chính thức (`ket_qua.json`), SXM = sau xác minh. (Số câu "bình thường" giữ 413 vì T01:37 vào nhóm này và T08:21 rời nhóm này.)

- **Sai âm thầm** (câu + cột + trường): chính thức **1** → sau xác minh **0**. CP95 tỉ lệ câu sai âm thầm: [0,0; 0,0107] → [0,0; 0,0071] (520 câu).
- **Câu bình thường bị cờ**: 40/413 (9,7%) → **39/413 (9,4%)**; T08 câu 21 chuyển sang loại "hai ô" (cần xem – đúng quy ước "hai ô" chỉ chấp nhận cần xem).
- SBD / mã đề: không đổi (cột sai âm thầm 0/117, trường 0/26); **H3 không phụ thuộc hai câu này**.

## 5. Diễn giải và giới hạn

- Bảng phụ chỉ giải thích **vì sao** có một ca sai âm thầm: máy đọc đúng cái có trên giấy, còn nhãn (kịch bản) không khớp giấy. Theo quy ước dự án
  ("nhãn phải khớp cái có trên giấy"), đây là lỗi nhãn, không phải lỗi đọc – nhưng **tiêu chí chốt trước so với kịch bản**, nên kết luận chính thức
  vẫn là **C1 KHÔNG ĐẠT**.
- Lệch được ghi nhận **sau khi đã xem kết quả**: không loại trừ được thiên lệch "đi tìm lý do cho đúng ca lỗi". Chỉ có hai ca được báo, cả hai đều ở câu
  máy đọc khác kịch bản; không có rà soát độc lập cả 13 ảnh xem còn câu nào khác giấy mà máy đọc trùng kịch bản (kiểu lệch đó sẽ không lộ ra).
- Lần thử sau: ghi lệch kịch bản **lên phiếu ngay lúc tô**, nộp trước khi chấm.
