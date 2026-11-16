# Lệnh AR – tiêu chí sửa 5 rủi ro ghi nhận ở lệnh AH (đăng ký TRƯỚC khi sửa)

Ngày: 16/11/2026 · nhánh `cnn-sau` · commit riêng, trước mọi thay đổi mã hệ thống của lệnh AR. Nguồn rủi ro: `docs/lenh_ah.md` mục 3 và 4 (R1 = mục 4 #1, R2 = #3, R3 = #4, R4 = #5, R5 = #2).
Sao lưu CSDL trước khi sửa: `data/_backup/smart_exam_db_20261116_133358_demo.dump` (`tools/sao_luu_demo.py`, pg_dump -Fc, `pg_restore -l` đọc được 237 mục).
Thay đổi CSDL duy nhất: migration 006 THÊM một bảng mới (`revoked_tokens`, cho R4), chạy lại an toàn, không xoá / đổi dữ liệu hiện có.

## 0. Tệp đóng băng (CLAUDE.md mục 4f / 4k, `docs/dong_bang_ma_dot2.json`, tag `ma-dot2-dong-bang-v3`) và cách xử lý
Tệp đóng băng: `models/omr_m1.json`, `models/ocr_cnn.json`, `answer_sheet/output/layout.json`, `answer_sheet/output/phieu_trang_300dpi.png`, `cv_engine/preprocessing.py`, `cv_engine/omr.py`,
`cv_engine/ocr.py`, `cv_engine/tap_du_lieu.py`, `backend/service.py`, `backend/schemas.py` (+ `cv_engine/__init__.py` theo CLAUDE.md mục 3). Lệnh AR cấm đổi `models/` và `cv_engine/`.
SHA-256 đầu lệnh (phải GIỮ NGUYÊN đến hết lệnh; kiểm bằng `git diff --stat` và băm lại ở cuối):
`backend/service.py` 128c109c6cd6e26de1c6d4d5266f1c0c10d3bf1f835f1a61ca2f336bd604d031 · `backend/schemas.py` 457a7e26df5cca12b784b7e33165e976633856e058045029dac1dd18c3bb14cc ·
`models/ocr_cnn.json` a151c078e159e003fb668b4e4a9e00ec38554f5fec9f870a9624d53b989ac6c8 · `models/omr_m1.json` f8f87577b42e28741def10bb9d42f4b6e937e6e3b37c025c5e63b8d8c81c60af ·
`cv_engine/ocr.py` e9b3e00fc0917341756441d5aecc39abc14a85861b35844e6506cae33a26b4be · `cv_engine/omr.py` 7e508fad51ffde2c8e9f278f27af38f63d7c700623b17f0132045d17c7a6027c ·
`cv_engine/preprocessing.py` 651f14fa720714fe4f3ff218694b296f66840dbf4c848a8b06b26b0060fe4352 · `cv_engine/tap_du_lieu.py` 3f030b71ece0b3117db0465c2ebbe3cf1948911140deb002f20a333d37fd9f01 ·
`cv_engine/__init__.py` 6335cfb073d26dc4a32db0be440f27b063b4a26f4e20b9034e55fd7dacbc5f62.
**R1 và R2 theo đề xuất gốc của AH sẽ sửa `backend/service.py`** (`danh_gia_phieu`, `_ghi_file`, `nhan_anh`) – tệp đóng băng. Lệnh nói: nếu buộc phải chạm tệp đóng băng thì DỪNG ở mục đó. **Cách làm để không phải chạm**: cả bốn sửa mã (R1, R2, R3, R5) nằm ở TẦNG ĐIỀU PHỐI mới `backend/dong_thoi.py` + `backend/main.py` (không đóng băng): khoá ở mức giao dịch CSDL (`pg_advisory_xact_lock`) lấy TRƯỚC khi gọi `service.nhan_anh`, và thử lại trong savepoint khi gặp `UniqueViolation`. `service.py`, `schemas.py`, `cv_engine/`, `models/` giữ nguyên từng byte.
Nếu trong lúc làm phát hiện không đạt được tiêu chí nào mà không chạm tệp đóng băng: mục đó ghi KHÔNG ĐẠT (hoặc DỪNG và báo), KHÔNG tự sửa tệp đóng băng.

## 1. Mốc "trước khi sửa"
- Băm đầu ra chấm lại 56 ảnh dev bằng backend (`python tools/kiem_backend_dau_cuoi.py`, rồi `python tools/ar_bam_dau_ra.py` – băm `data/_eval/backend/phieu_dau_cuoi.csv` bỏ cột `sheet_id`): **`54e54baacd0dbeef58323f5d0bf1ae17cb3e5d0cd706f6760b0b7b9bd5bd70f0`** (56 dòng).
- pytest: **600 đạt, 1 bỏ qua** (16/11/2026, HEAD `6bf707b`). `tools/kiem_truoc_demo.py`: 0 KHÔNG ĐẠT.
- `tools/ah_thu_dong_thoi.py` bản hiện có (A–E): A, B, C, D (chính thức ≤ 1), E đạt; các mục rủi ro đỏ (đo lại ở bước 2a của lệnh, số liệu thô `data/_eval/ah/ket_qua.json` lần chạy "trước AR").

## 2. Tiêu chí từng rủi ro (đo bằng `tools/ah_thu_dong_thoi.py`, máy chủ thử cổng 8010, ảnh giả hoá; mọi dữ liệu thử dọn trong `finally`)
**R1 – hai phiếu CÙNG SBD gửi đồng thời trong cùng kỳ.** ≥ **60 lần lặp** (50 cuộc đua tự nhiên + 10 cuộc đua ÉP bằng `LOCK TABLE results IN SHARE MODE`, mỗi lần một SBD mới, hai tài khoản, hai ảnh khác nhau, cổng chặn `Barrier`). ĐẠT khi CẢ 60 lần: (a) cả hai yêu cầu trả 201 (không 409, không 5xx, không lỗi mạng);
(b) cả hai phiếu được lưu (2 dòng `answer_sheets` cho SBD đó); (c) đúng 1 điểm chính thức (`results` status ≠ void) – **0 lần có hai điểm chính thức**; (d) phiếu còn lại ở `needs_review` với lý do `duplicate_sbd` – cùng kết quả như gửi TUẦN TỰ (đối chứng 10 SBD gửi tuần tự: phiếu đầu `graded` chính thức, phiếu sau `needs_review` + `duplicate_sbd`; chữ ký kết quả của mọi lần đua phải bằng chữ ký đối chứng).
**R2 – cùng MỘT tệp ảnh gửi hai lần đồng thời.** ≥ **60 lần lặp** (30 lần hai tài khoản + 30 lần cùng một tài khoản; mỗi lần SBD mới). ĐẠT khi CẢ 60 lần: không bao giờ 500 / lỗi mạng; cả hai yêu cầu 201; đúng 1 dòng `answer_sheets` cho băm ảnh đó; một yêu cầu `da_ton_tai = false`, yêu cầu kia `da_ton_tai = true` và **cùng `sheet_id`** – đúng như khi gửi tuần tự (đối chiếu 10 lần gửi tuần tự: lần hai `da_ton_tai = true`, cùng `sheet_id`).
**R3 – `/exams/{id}/sheets/batch`, hai lô chéo.** ≥ **100 lần lặp**: lô 1 = [p, q], lô 2 = [q', p'] (cùng hai thí sinh, thứ tự ngược nhau, ảnh khác nhau), SBD mới mỗi lần, hai tài khoản. ĐẠT khi CẢ 100 lần: cả hai lô 201; không ảnh nào có `error`; **0** `DeadlockDetected` trong log máy chủ và trong thân phản hồi; không 500; mỗi thí sinh ≤ 1 điểm chính thức.
**R4 – đăng xuất thu hồi token.** Lặp ≥ 3 lượt (mỗi lượt đăng nhập mới). ĐẠT khi: (a) sau `POST /auth/logout` bằng token T1, T1 (cả cookie lẫn `Authorization: Bearer`) trả **401 trên mọi đường dẫn có xác thực** kiểm (≥ 8: `/me`, `/me/classes`, `/exams`, `/exams/{id}/sheets`, `/exams/{id}/results`, `/sheets/{id}`, `/meta/ket-noi`, `POST /me/password`, `PATCH /me`);
(b) phiên khác T2 của CÙNG tài khoản vẫn 200 trên các đường dẫn đó; (c) token giả (chuỗi ngẫu nhiên, chữ ký sai, chữ ký đúng nhưng người dùng không tồn tại) vẫn 401 và gọi `/auth/logout` với token giả KHÔNG ghi dòng nào vào `revoked_tokens`; (d) đăng xuất lần hai (token đã thu hồi) và đăng xuất không có token đều 204, không 5xx; (e) chỉ ghi vào bảng mới `revoked_tokens` (băm SHA-256 của token, không lưu token thô).
**R5 – giới hạn chấm đồng thời.** Cấu hình qua biến môi trường `CHAM_DONG_THOI` (**mặc định 4, ≥ 2** để không ảnh hưởng hàng đợi tải 2 lượt của giao diện) và `CHAM_CHO_GIAY` (mặc định 30; thời hạn chờ trong hàng đợi); quá hạn → **503 kèm `Retry-After`** (số giây nguyên dương). Đo: 20 yêu cầu tải ảnh đồng thời (2 tài khoản, SBD khác nhau) trên máy chủ thử đặt `CHAM_DONG_THOI=3`, `CHAM_CHO_GIAY=8`.
ĐẠT khi: mỗi yêu cầu hoặc 201 hoặc 503 **có** `Retry-After`, không mã nào khác (không 500, không lỗi mạng); mọi 201 chấm đúng (phiếu sạch → `graded`, SBD đúng); đỉnh working set của máy chủ trong lượt đo **≤ 1 500 MB** (mốc cũ: ~150 MB mỗi yêu cầu, 12 yêu cầu ≈ 1,9–2,0 GB); không `MemoryError` trong log; và với cấu hình MẶC ĐỊNH, 2 yêu cầu song song của một tài khoản không bao giờ nhận 503 (test đơn vị + AH-E giữ nguyên).

## 3. Tiêu chí chung (phải đạt hết)
1. `pytest` (sau `Remove-Item Env:PUBLIC_BASE_URL`): **≥ 600 đạt, 1 bỏ qua** + test mới của AR; không test nào bị nới / xoá.
2. `tools/ah_thu_dong_thoi.py chay` chạy lại: các mục A–E cũ **vẫn đạt** và 5 mục R1–R5 đạt; dữ liệu thử dọn sạch (đếm lại = 0), kỳ thi demo 1380 / 1381 / 1632 / 1633 nguyên vẹn.
3. Chấm lại 56 ảnh dev bằng backend cho **điểm / SBD / mã đề / cờ y hệt trước khi sửa**: `tools/ar_bam_dau_ra.py` in đúng `54e54baa…70f0`.
4. `tools/kiem_truoc_demo.py`: 0 KHÔNG ĐẠT.
5. Thời gian xử lý: ghi trước / sau (một ảnh một mình, thông lượng E); chậm đi quá 15% ở một ảnh một mình hoặc ở thông lượng E phải được nêu rõ trong `docs/ket_qua_sua_ah.md` (không phải điều kiện ĐẠT / KHÔNG ĐẠT, nhưng không được giấu).
6. Mục nào không đạt: ghi KHÔNG ĐẠT, hoàn tác sửa của mục đó, KHÔNG nới tiêu chí.

## 4. Thiết kế dự kiến (có thể đổi nếu nêu lý do; không đổi tiêu chí)
- R1: `pg_advisory_xact_lock` mức kỳ thi lấy SAU khi `UniqueViolation` ở `uq_results_exam_student` rồi thử lại `service.nhan_anh` trong savepoint (lần thử lại thấy phiếu thắng cuộc đã commit → đi đường `duplicate_sbd` sẵn có). Lý do không khoá mức (kỳ thi, SBD) từ đầu: SBD chỉ biết SAU khi đọc ảnh (bên trong `service.nhan_anh`, tệp đóng băng); khoá mức kỳ thi từ đầu sẽ xếp hàng cả phần xử lý ảnh ~0,8 s của mọi ảnh cùng kỳ.
- R2: `pg_advisory_xact_lock` theo (kỳ thi, SHA-256 ảnh) lấy trước `service.nhan_anh`; yêu cầu thứ hai chờ giao dịch đầu commit rồi thấy phiếu cũ (`da_ton_tai = true`).
- R3: `/sheets/batch` lấy khoá mức kỳ thi (không gian khoá riêng) ngay đầu lô → hai lô cùng kỳ chạy lần lượt, không chéo khoá.
- R4: migration 006 `revoked_tokens(token_sha256 PRIMARY KEY, user_id → users ON DELETE CASCADE, revoked_at, expires_at)`; `/auth/logout` ghi băm token đã ký hợp lệ; `xac_thuc` kiểm bảng này ở mỗi yêu cầu.
- R5: `threading.BoundedSemaphore` quanh phần chấm của các endpoint tải ảnh; lấy TRƯỚC mọi khoá CSDL; quá `CHAM_CHO_GIAY` → 503 + `Retry-After`.
