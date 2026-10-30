# Nhật ký sửa báo cáo đồ án (lệnh E 28/10/2026, hoàn thiện bằng lệnh E2, nhánh `cai-tien-b`)

Bản gốc: `C:\Users\MSI\Desktop\kì 7\đồ án chuyên ngành cntt\BaoCao_DoAnChuyenNganh.docx` – **chỉ đọc, không sửa, không ghi đè** (136 951 byte, sửa lần cuối 23/10/2026).
Đầu ra: `docs/bao_cao_sua_de_xuat.md` (đoạn Markdown kèm vị trí để dán tay). Chưa có thay đổi nào trong tệp Word.
Ràng buộc đã giữ: không sửa mã, test, `CLAUDE.md`; CSDL chỉ `SELECT` (E2). Pytest / hồi quy chỉ ghi trong giao dịch ROLLBACK.

## 1. Thay đổi trong báo cáo: trước → sau, nguồn

| # | Vị trí trong báo cáo | Trước | Sau | Nguồn |
|---|---|---|---|---|
| 1 | Mục 3.2.2, đoạn "Bản nắn ảnh ban đầu (hàm align)…" | nắn sai **23** ảnh | **22** ảnh (19 dev + 3 test) | `data/_eval/bao_cao_cuoi_tuan4.md` bảng "Gộp dev + test": `align_cu | Tổng | 90 | 68 | 22`. Chỉ MỘT chỗ ghi 23 |
| 2 | Mục 1.5, câu cuối "Phương pháp thực nghiệm" | 232 kiểm thử | "380 (tính đến 28/10/2026; 232 tại 21/10/2026)" + câu giải thích số tăng do cải tiến sau góp ý | pytest 28/10: `380 passed, 1 skipped, 109.73s` |
| 3 | Bảng 3.5, dòng "Kiểm thử" | 232 kiểm thử | như dòng 2 | như dòng 2 |
| 4 | Sau 3.4.3: **mục mới 3.5** (7 cải tiến, bảng kiểm tra lại, điều chưa làm) | (chưa có) | `bao_cao_sua_de_xuat.md` mục C | từng số ở mục 3 bên dưới |
| 5 | KẾT LUẬN – "Ý 1", "Ý 2" | trống | `bao_cao_sua_de_xuat.md` mục D; đợt 2 ghi "đang chờ" + ô cập nhật; dùng cách viết "380 (…; 232 …)" | số mục 3.4 và 3.5 |
| 6 | Mục 3.1.4: đoạn "20 bảng" và Bảng 3.4 | 20 bảng | giữ 20 cho ERD gốc; thêm `teacher_classes` (nhóm Người dùng, ghi "thêm sau cải tiến") và `schema_migrations` (bảng kỹ thuật, có chú thích); tổng thực tế **22 bảng + 8 view** | SELECT chỉ-đọc `information_schema.tables` 28/10/2026 (mục 2); `backend/migrations/001–003` |
| 7 | Mục 3.5.4 | "ma trận 16 nhóm" (lệnh E) | **bỏ**; dùng 32 ca | `pytest --collect-only -q tests/test_omr_ma_tran_o_to.py` → "32 tests collected" (đếm lại 28/10) |
| 8 | Mục 3.5.2 | điện thoại thật 1,8 s, ~2 s "chưa có nguồn" | ghi rõ: đo trực tiếp 27/10/2026, một iPhone (Safari), cùng Wi‑Fi; có ảnh chụp màn hình và nhật ký làm việc 27/10; chưa thử Android; chưa đo 40 tờ liên tục qua Wi‑Fi thật | lời người dùng (lệnh E2); ảnh chụp màn hình và nhật ký **không nằm trong dự án** nên chưa tự đối chiếu |
| 9 | Ngôi "nhóm" / phân công | xem mục 4 | xem mục 4 | lệnh E2 |

## 2. Số bảng đếm từ CSDL (SELECT chỉ-đọc, `information_schema.tables`, schema `public`, 28/10/2026)
**30 đối tượng = 22 bảng + 8 view.** Không ghi, không migration.
- **20 bảng nghiệp vụ gốc:** answer_keys, answer_sheets, classes, exam_codes, exam_students, exams, ml_models, ocr_digits, questions, results, review_queue, scan_batches, score_audit_logs, sheet_answers, sheet_templates, student_imports, students, subjects, system_settings, users.
- **1 bảng nghiệp vụ thêm sau cải tiến:** `teacher_classes` (migration 002).
- **1 bảng kỹ thuật:** `schema_migrations` (3 dòng: 001, 002, 003).
- **8 view:** v_exam_results, v_exam_summary, v_missing_results, v_ocr_correction_stats, v_question_difficulty, v_review_pending, v_score_distribution, v_student_transcript.
- **Cột thêm bằng migration:** 001 → `sheet_answers` (needs_review, review_reasons, omr_state, omr_selected_options, reviewed_by, reviewed_at), `answer_sheets` (reject_code, omr_detail, original_filename); 002 → `exams.class_id`; 003 → `answer_sheets.image_deleted_at`. Kiểm trực tiếp `exams.class_id` và `answer_sheets.image_deleted_at` tồn tại. ERD gốc không đổi.

## 3. Nguồn của từng số trong mục 3.5 (tái tạo được)

| Số trong báo cáo | Nguồn |
|---|---|
| Môn/lớp: kiểm quyền 24/24, Excel A4 "Môn:" / F4 "Lớp:", lớp không tồn tại → 422 | `docs/ke_hoach_cai_tien_27-10.md` mục 5a; `docs/thiet_ke_dang_nhap.md` mục 2 |
| Chụp liên tục giả lập: 20 tờ mỗi 2 s, 0 lỗi, p50 0,79 s, p95 0,83 s, tổng 39,5 s; chọn nhiều 20 tờ → 10,4 s; ngắt mạng 2 tờ → gửi lại 2/2 | `docs/thiet_ke_chup_dien_thoai.md` mục 9; `python tools/thu_dien_thoai.py chay`; số thô `data/_eval/ui_m/lien_tuc/thoi_gian.json` |
| Điện thoại thật: 1,8 s (một tờ, một lần), ~2 s rớt Wi‑Fi gửi lại (ước chừng) | Người dùng đo trực tiếp 27/10/2026, một iPhone/Safari; ảnh chụp màn hình + nhật ký 27/10 (ngoài dự án, chưa đối chiếu). Đã ghi vào `thiet_ke_chup_dien_thoai.md` mục 8, `kich_ban_demo_bao_ve.md`, `ke_hoach_cai_tien_27-10.md` mục 2 |
| OCR vs CNN vs M0 (bảng 3.5.3, p-value, tham số, ms, T4 53,6% / 46,4% / 16,1% / 42,9%) | `docs/so_sanh_ocr_cnn.md` mục 3a, 3b, 3c, 4, 5, 5b, 6; `python tools/so_sanh_ocr.py so-sanh`, `tools/so_sanh_ocr_rapid.py`; `data/_eval/so_sanh_ocr/ket_qua.json` |
| `vet_nho` (N = 90 px), `to_nhat` (Xs = 0,44): bảng trước/sau, 0/56 phiếu thật | `docs/ke_hoach_cai_tien_27-10.md` mục 6.3, 6.6; `python tools/eval_omr.py run --phuong-phap m1` |
| S_anh 0,400 / 0,682 / 0,804; không có X thoả; C2 +13 câu = +3,5 điểm % | `docs/ke_hoach_cai_tien_27-10.md` mục 6.4; `python tools/omr_s_anh.py tat_ca` |
| BV01–BV10: 10/10 khớp, BV07 → 40 câu `to_nhat`, BV10 không ghi điểm | `docs/ke_hoach_cai_tien_27-10.md` mục 5b; `python tools/thu_bo_demo.py chay` |
| Đăng nhập: scrypt, cookie HttpOnly + SameSite=Lax, 5 lần sai / 15 phút → 429, 3 test quét route, sự cố migration 002 | `docs/thiet_ke_dang_nhap.md` mục 2, 7, 8; `tests/test_xac_thuc_khong_csdl.py` |
| pytest 380 đạt + 1 skip, 109,73 s | `python -m pytest tests -q -p no:cacheprovider`, 28/10/2026 |
| Hồi quy 56/56; 0 chấm sai không cờ / 1 680 câu; câu cần xem 560/2 240; T4 26/56 | `PYTHONUTF8=1 python tools/kiem_backend_dau_cuoi.py`, 28/10/2026 |
| Mục 3.4 (H1–H5, T3 92,6%, T4 58,3%, 3,68%, F1 0,897…) | giữ số báo cáo gốc; trùng `docs/ke_hoach_test_cuoi.md` mục 9 |

## 4. Ngôi "nhóm" và phân công (E2: đồ án NHÓM theo bìa; không tự điền tên, không suy từ commit)
Giữ nguyên sự thật: cả nhóm tham gia thu dữ liệu (tô và viết phiếu); đợt 2 do 5 người cùng tô. `CLAUDE.md` KHÔNG sửa (vẫn ghi "làm cá nhân" – lệch với bìa, chỉ ghi nhận).
Đã xử lý 7 chỗ mâu thuẫn của lệnh E (chi tiết bảng ở `bao_cao_sua_de_xuat.md` mục F):

| # trong E | Chỗ | Xử lý |
|---|---|---|
| 1 | Bìa + bảng 5 thành viên | giữ nguyên |
| 2 | `CLAUDE.md` "làm cá nhân" | không sửa |
| 3 | Thân báo cáo dùng "nhóm" (#33, 49, 50, 54, 55, 56, 111, 115, 151, 160, 164) | giữ nguyên (đúng ngôi) |
| 4 | Mục 3.4.1 (#191), 3.4.2 (#193) "người thực hiện" | → "nhóm" / câu bị động + ô điền sau (ô 1) |
| 5 | #204 "một người viết" | → "một người viết tay" (dữ liệu) |
| 6 | Văn phong "em" ở `so_sanh_ocr_cnn.md` 5b | không dán vào báo cáo; tài liệu nội bộ không đổi |
| 7 | 5 tờ thuyết trình theo thành viên | ngoài báo cáo, không sửa |

### Danh sách ô `[ĐIỀN SAU – nhóm xác nhận]` (12 ô – điền một lần)
| # | Vị trí | Nội dung cần điền |
|---|---|---|
| 1 | Mục 3.4.1 / 3.4.2 (#191, #193) | thành viên xem mù ảnh kiểm tra cuối |
| 2 | Mục 3.5.2 (đo điện thoại 27/10) | người đo |
| 3 | Bảng "Phân công công việc" (mới, cuối Chương 1 hoặc Phụ lục) – Thiết kế phiếu và bố cục | người phụ trách |
| 4 | – Chụp ảnh phiếu | người phụ trách |
| 5 | – Tiền xử lý ảnh (nắn phẳng) | người phụ trách |
| 6 | – Nhận dạng ô tô (OMR) | người phụ trách |
| 7 | – Nhận dạng chữ số (CNN) và so sánh OCR | người phụ trách |
| 8 | – Cơ sở dữ liệu | người phụ trách |
| 9 | – Backend, đăng nhập và phân quyền | người phụ trách |
| 10 | – Giao diện web và trang điện thoại | người phụ trách |
| 11 | – Đánh giá, kiểm thử, xem mù | người phụ trách |
| 12 | – Viết báo cáo | người phụ trách |
(Hai dòng đã điền bằng sự thật: "Thu dữ liệu: tô và viết phiếu – cả nhóm"; "Kiểm tra đợt 2 (tô phiếu) – cả 5 thành viên".)

## 5. Tài liệu trong `docs/` đã sửa cho đúng thực tế điện thoại thật (27/10/2026)
| Tệp | Trước | Sau |
|---|---|---|
| `thiet_ke_chup_dien_thoai.md` mục 8 | "CHƯA thử bằng điện thoại thật cùng mạng (người dùng sẽ thử và báo lại)" | "ĐÃ thử … 27/10/2026" (một iPhone/Safari; chụp 1 tờ 1,8 s, chụp liên tục, rớt Wi‑Fi gửi lại ~2 s, chụp mờ bị từ chối, chọn nhiều ảnh, xuất Excel, phân quyền gv_binh/K22A); chưa Android; chưa đo 40 tờ liên tục qua Wi‑Fi thật. Câu loopback trỏ tới ghi chú này |
| `kich_ban_demo_bao_ve.md` | "CHƯA thử bằng điện thoại thật cùng mạng…" | "ĐÃ thử điện thoại thật 27/10/2026 …; CHƯA thử Android; chưa đo 40 tờ…" |
| `ke_hoach_cai_tien_27-10.md` mục 2 (tiêu đề + dòng "Còn lại") | "CHƯA thử điện thoại thật"; "Còn lại: thử điện thoại thật…" | "ĐÃ thử điện thoại thật 27/10 …"; Còn lại: Android, 40 tờ qua Wi‑Fi thật, camera trực tiếp |
| `khao_sat_camera_truc_tiep.md` dòng 5 | "(không có điện thoại thật)" | thêm: từ 27/10 đã thử luồng `capture` trên một iPhone, CHƯA thử `getUserMedia` |
`CLAUDE.md` vẫn ghi "CHƯA thử điện thoại thật" (mục 4f) – không sửa theo yêu cầu E2; cần bạn cập nhật tay nếu muốn.

## 6. Còn chờ / chưa kiểm chứng
- Đợt 2 chưa chạy → "đang chờ", ô cập nhật.
- Ảnh chụp màn hình điện thoại và nhật ký 27/10 không nằm trong dự án; số 1,8 s và ~2 s dựa trên lời người dùng.
- 12 ô `[ĐIỀN SAU]` chờ nhóm.
- Chưa tạo `BaoCao_DoAnChuyenNganh_sua.docx` (đầu ra là Markdown).
- Kết quả test cuối 21/10 là của mã trước `vet_nho`/`to_nhat` (đã ghi trong Kết luận và 3.5.9).
