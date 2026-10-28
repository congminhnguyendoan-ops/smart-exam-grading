# Nhật ký sửa báo cáo đồ án (lệnh E, 28/10/2026, nhánh `cai-tien-b`)

Bản gốc: `C:\Users\MSI\Desktop\kì 7\đồ án chuyên ngành cntt\BaoCao_DoAnChuyenNganh.docx` – **chỉ đọc, không sửa, không ghi đè** (136 951 byte, sửa lần cuối 23/10/2026).
Đầu ra: `docs/bao_cao_sua_de_xuat.md` (đoạn Markdown kèm vị trí để dán tay; người dùng chọn cách này thay vì bản sao `.docx`). Chưa có thay đổi nào trong tệp Word.
Ràng buộc đã giữ: không sửa mã, không ghi CSDL, không đọc dữ liệu test. Hai lệnh chạy lại (pytest, hồi quy 56/56) chỉ ghi trong giao dịch ROLLBACK; `git status` sạch trước khi viết tài liệu.

## Thay đổi: trước → sau, nguồn

| # | Vị trí trong báo cáo | Trước | Sau | Nguồn số liệu |
|---|---|---|---|---|
| 1 | Mục 3.2.2, đoạn "Bản nắn ảnh ban đầu (hàm align)…" | nắn sai **23** ảnh | nắn sai **22** ảnh (19 dev + 3 test) | `data/_eval/bao_cao_cuoi_tuan4.md` bảng "Gộp dev + test": `align_cu | Tổng | 90 | 68 | 22`; dev `59/19`, test `9/3` (0035_C3, 0038_C3, 0039_C3). Chỉ MỘT chỗ ghi 23; không chỗ nào khác (Mở đầu, Bảng 3.6, nhận xét, danh mục) |
| 2 | Mục 1.5, câu cuối đoạn "Phương pháp thực nghiệm" | 232 kiểm thử | 380 đạt + 1 skip (hoặc giữ 232 kèm chú "tại 21/10") – chờ chọn | `python -m pytest tests -q` chạy 28/10/2026: `380 passed, 1 skipped in 109.73s` |
| 3 | Bảng 3.5, dòng "Kiểm thử" | 232 kiểm thử | 380 đạt, 1 bỏ qua có chủ đích | như dòng 2 |
| 4 | Sau mục 3.4.3, thêm **mục 3.5** "Các cải tiến sau góp ý (27–28/10/2026)" (7 cải tiến + bảng kiểm tra lại + điều chưa làm) | (chưa có) | xem `bao_cao_sua_de_xuat.md` mục C | từng số có nguồn bên dưới |
| 5 | "KẾT LUẬN" – "Ý 1", "Ý 2" (hiện chỉ có tiêu đề trống) | trống | viết ở `bao_cao_sua_de_xuat.md` mục D; đợt 2 ghi "đang chờ" + ô cập nhật | số của mục 3.4 (báo cáo gốc, trùng `docs/ke_hoach_test_cuoi.md` mục 9) và của mục 3.5 |
| 6 | Mục 3.1.4, sau Bảng 3.4 | (chưa có) | chú thích: `schema_migrations` là bảng kỹ thuật theo dõi migration đã áp, không thuộc nghiệp vụ chấm thi | `backend/migrate.py` dòng 2, 25–33 (`CREATE TABLE IF NOT EXISTS schema_migrations`, ghi tên tệp migration đã chạy) |
| 7 | (đề xuất, chưa quyết) Bảng 3.4 / "20 bảng" | 20 bảng | thêm `teacher_classes` (nhóm Người dùng) hoặc ghi chú ERD là bản thiết kế ban đầu | `backend/migrations/002_lop_giao_vien.sql` dòng 14 `CREATE TABLE teacher_classes` |
| 8 | Rà "cá nhân" / "nhóm" | – | chỉ liệt kê 7 mâu thuẫn + 3 phương án; **không sửa** | bìa báo cáo; `CLAUDE.md` mục 1; `docs/so_sanh_ocr_cnn.md` mục 5b |

## Nguồn của từng số trong mục 3.5 (tất cả tái tạo được)

| Số trong báo cáo | Nguồn |
|---|---|
| Môn/lớp: kiểm quyền 24/24, Excel A4 "Môn:" / F4 "Lớp:", lớp không tồn tại → 422 | `docs/ke_hoach_cai_tien_27-10.md` mục 5a; `docs/thiet_ke_dang_nhap.md` mục 2 |
| Chụp liên tục giả lập: 20 tờ mỗi 2 s, 0 lỗi, p50 0,79 s, p95 0,83 s, tổng 39,5 s; chọn nhiều 20 tờ → 10,4 s; ngắt mạng 2 tờ → gửi lại 2/2 | `docs/thiet_ke_chup_dien_thoai.md` mục 9; `python tools/thu_dien_thoai.py chay`; số thô `data/_eval/ui_m/lien_tuc/thoi_gian.json` |
| **Điện thoại thật qua Wi‑Fi 1,8 s; rớt Wi‑Fi gửi lại ~2 s** | **KHÔNG có tệp nguồn.** Lấy từ lời người dùng trong lệnh E; các tài liệu ghi "CHƯA thử điện thoại thật" (`ke_hoach_cai_tien_27-10.md` mục 2, `thiet_ke_chup_dien_thoai.md` mục 8, `kich_ban_demo_bao_ve.md`). Đưa vào báo cáo kèm chú thích, chờ người dùng xác nhận |
| OCR vs CNN vs M0 (mọi con số bảng 3.5.3, p-value, tham số, ms, T4 53,6% / 46,4% / 16,1% / 42,9%, 28 vs 5 chữ số p < 0,5) | `docs/so_sanh_ocr_cnn.md` mục 3a, 3b, 3c, 4, 5, 5b, 6; tái tạo: `python tools/so_sanh_ocr.py so-sanh` và `tools/so_sanh_ocr_rapid.py` (venv riêng); số thô `data/_eval/so_sanh_ocr/ket_qua.json` |
| `vet_nho`: N = 90 px, 4 tiêu chí đạt, bảng trước/sau; `to_nhat`: Xs = 0,44, 0/56 phiếu thật, 10 test mới | `docs/ke_hoach_cai_tien_27-10.md` mục 6.3, 6.6; `python tools/eval_omr.py run --phuong-phap m1` |
| Ma trận ô tô: 32 ca | `python -m pytest --collect-only -q tests/test_omr_ma_tran_o_to.py` → "32 tests collected" (28/10) |
| S_anh 0,400 / 0,682 / 0,804; 0/56 chạm sàn 0,20; không có X thoả; C2 +13 câu = +3,5 điểm % | `docs/ke_hoach_cai_tien_27-10.md` mục 6.4; `python tools/omr_s_anh.py tat_ca` |
| BV01–BV10: 10/10 khớp, BV07 → 40 câu `to_nhat`, BV10 không ghi điểm | `docs/ke_hoach_cai_tien_27-10.md` mục 5b; `python tools/thu_bo_demo.py chay` |
| Đăng nhập: scrypt, cookie HttpOnly + SameSite=Lax, 5 lần sai / 15 phút → 429, 3 test quét toàn bộ route, sự cố migration 002 | `docs/thiet_ke_dang_nhap.md` mục 2, 7, 8; `tests/test_xac_thuc_khong_csdl.py` |
| **pytest 380 đạt + 1 skip, 109,73 s** | chạy lại 28/10/2026 (`python -m pytest tests -q -p no:cacheprovider`) |
| **Hồi quy 56/56**; 0 chấm sai không cờ / 1 680 câu; câu cần xem 560/2 240 (25,0%); T4 26/56 (46,4%) | chạy lại 28/10/2026: `PYTHONUTF8=1 python tools/kiem_backend_dau_cuoi.py` (lần đầu lỗi in console cp1252, không phải lỗi mã; chạy lại với UTF‑8) |
| Mục 3.4 (H1–H5, T3 92,6%, T4 58,3%, 3,68%, F1 0,897…) | giữ nguyên số của báo cáo; trùng `docs/ke_hoach_test_cuoi.md` mục 9 |

## Điều chưa làm / chờ quyết định
- Đợt 2 chưa chạy → ghi "đang chờ", chừa ô cập nhật; không điền số.
- Chưa tạo `BaoCao_DoAnChuyenNganh_sua.docx` (người dùng chọn Markdown).
- Chưa sửa phần phân công/xưng hô (cần người dùng trả lời cá nhân hay nhóm, ai làm gì).
- Chờ xác nhận: nguồn của 1,8 s và ~2 s; cụm "ma trận 16 nhóm"; giữ 232 hay đổi 380; "20 bảng" hay 21.
- Báo cáo gốc cho thấy kết quả test cuối 21/10 là của mã trước `vet_nho`/`to_nhat` – đã ghi trong Kết luận và 3.5.9 như hạn chế.
