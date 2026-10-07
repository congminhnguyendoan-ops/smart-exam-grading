# Kế hoạch demo báo cáo 13/10/2026 – khối BACKEND

Nguyên tắc (người dùng, 07/10/2026): **"mỏng ở bên trong, không mỏng ở chỗ nối"** – code đặt đúng chỗ, dùng lâu dài; chỗ làm
tạm ghi vào mục NỢ KỸ THUẬT (cuối file). Câu OMR "cần xem" **không bao giờ** được chấm như câu chắc chắn. Demo và test chỉ dùng
ảnh 0001–0028 (không đụng 0029–0040).

| Mốc | Việc | Trạng thái |
|---|---|---|
| B0 | Xuất lại mô hình OMR từ commit sạch | xong |
| B1 | Cấu hình CSDL qua `.env` + migration bổ sung | xong |
| B2 | Lớp dịch vụ chấm phiếu | xong |
| B3 | API FastAPI | xong |
| B4 | Kiểm chứng (pytest + đầu-cuối so với điểm tính độc lập) | xong |
| B5 | CLAUDE.md | xong |

## B0 – xuất lại mô hình OMR từ commit sạch (07/10/2026)
- `python tools/huan_luyen_omr.py xuat` chạy khi cây làm việc sạch, HEAD `3bcf190` → `models/omr_m{0,1}.json`:
  `git_head` `d0c9574` → `3bcf190`, `git_chua_commit` `[omr.py, huan_luyen_omr.py]` → `[]`.
- Phần mô hình (hệ số, chuẩn hoá, ngưỡng luật) **giống hệt** bản cũ (so JSON từng trường, trừ `sieu_du_lieu`).
- **Dự đoán trên 56 ảnh train giống hệt**: `omr.doc_phieu` với bản cũ và bản mới trên 56 ảnh (ảnh nắn đệm `data/_omr/anh`),
  so toàn bộ `KetQuaOMR` (trừ `thoi_gian_ms`): 56 ảnh, **0 ảnh khác**.

## B1 – cấu hình CSDL qua `.env` + migration (07/10/2026)
- `backend/config.py` đọc `smart_exam_db/.env` (`python-dotenv`, biến môi trường thật thắng); **không có mật khẩu mặc định trong
  code** – thiếu `DATABASE_URL` thì `LoiCauHinh` báo rõ. `.env` đã nằm trong `.gitignore` (kiểm: `git check-ignore`);
  `.env.example` có mẫu (mật khẩu giả). `tools/db_check.py` nay đọc cấu hình từ `backend.config` (bỏ chuỗi kết nối có mật khẩu
  khỏi code). `storage/` (ảnh phiếu backend lưu) thêm vào `.gitignore`.
- `backend/migrate.py` + `backend/migrations/001_backend_bo_sung.sql`: **chỉ thêm cột / chỉ mục**, `IF NOT EXISTS`, ghi bảng
  `schema_migrations`. Đã áp lên CSDL `smart_exam` (người dùng cho phép thay đổi bổ sung): `sheet_answers.{needs_review,
  review_reasons, omr_state, omr_selected_options, reviewed_by, reviewed_at}`, `answer_sheets.{reject_code, omr_detail,
  original_filename}`. Chạy lại 2 lần liên tiếp OK; áp lại trực tiếp file SQL 2 lần (rollback) OK. **Không xoá / reset gì**;
  số dòng các bảng không đổi (exams 1, answer_sheets 9, sheet_answers 90, results 8, review_queue 5).
- Chưa động tới: mật khẩu trong `00_create_database.sql`, `run_all.bat/.sh`, `HUONG_DAN.md` (script tạo CSDL cần nó) – nợ.

## B2 – lớp dịch vụ chấm phiếu (07/10/2026)
Mã: `backend/grading.py` (chấm thuần), `backend/service.py` (dịch vụ + CSDL), `backend/demo.py` + `tools/nap_demo.py` (dữ liệu mẫu).
- **Chuỗi**: byte → ghi `storage/uploads/<exam>/<sha[:2]>/<sha>.<đuôi>` → `doc_anh` → `preprocess_anh` → (từ chối: lưu phiếu
  `status='rejected'` + `reject_code` + `error_message` = `MA_LY_DO[mã]`, **không có điểm**) → `omr.doc_phieu` → lưu `answer_sheets`
  (+ ảnh nắn JPEG q92 cho giáo viên xem, `omr_detail` JSONB: cột SBD / mã đề, độ dịch định vị, nguồn ảnh) + `sheet_answers`
  (trạng thái OMR, `needs_review`, `review_reasons`, máy đọc gốc) → `danh_gia_phieu`. Cùng ảnh (SHA-256) tải lại trong một kỳ thi → trả phiếu cũ.
- **Một đường quyết định duy nhất** `danh_gia_phieu` (gọi sau khi nhận ảnh VÀ sau mỗi lần giáo viên sửa): chấm các câu chắc chắn
  (`grading.cham_diem`: câu cần xem → `is_correct = NULL`, không vào điểm tạm; chỉ `state='filled'` mới tính) → gom lý do
  (`low_omr_confidence` ← mờ / lưng chừng / vị trí; `multiple_marks` ← nhiều ô; `low_ocr_confidence` ← cột SBD / mã đề cần xem;
  `exam_code_not_found`, `sbd_not_found`, `duplicate_sbd`) → còn lý do: `status='needs_review'` + mục `review_queue` (điểm tạm ở
  `raw_score`, **không có dòng `results`**); hết lý do: **đối chiếu `fn_grade_sheet` của CSDL** (lệch thì dừng, không ghi điểm) rồi
  ghi `results` (`auto` nếu máy tự chốt, `confirmed` nếu đã qua review).
- **Không dùng `fn_process_sheet`** (ghi chú để Phần sau): hàm đó chỉ nhìn `confidence` < 0,8 / `faint` / nhiều ô, không biết các
  lý do "cần xem" của OMR (lưng chừng, vị trí) nên có thể tự chấm một phiếu mà OMR đã gắn cờ, và tính ô `faint` là đáp án.
  Service tự quyết định; vẫn dùng trigger audit, `fn_grade_sheet` (đối chiếu) và các bảng / enum sẵn có.
- **Giáo viên**: `xu_ly_cau` (`confirm` = nhận cách máy đọc, trừ câu cần xem vì vị trí → bắt buộc `set`; `set` = chốt lựa chọn, `''` =
  bỏ trống), `sua_dinh_danh` (chốt SBD / mã đề). Cả hai chỉ cho phiếu `needs_review`, rồi chạy lại `danh_gia_phieu`.
- **Dữ liệu mẫu** `python tools/nap_demo.py`: kỳ thi `[DEMO] Phiếu thu dữ liệu 0001–0028 (đáp án giả lập)` (exam_id 6 trên máy này), mã
  đề 101–104 × 40 câu, đáp án DEMO tất định (`random.Random("2026-<mã>")`), 28 thí sinh DEMO (SBD viết tay của phiếu 0001–0028 từ
  `data/ground_truth.csv`, lọc `PHIEU_TRAIN`), danh sách dự thi. Chạy lại: 0 bản ghi mới, không ghi đè. Đã nạp (INSERT thêm, không
  xoá / sửa): exams 1→2, exam_codes 2→6, answer_keys 20→180, students 10→38, exam_students 9→37.
- **Quan sát** (thử trong giao dịch rollback): phần lớn ảnh dev có câu cần xem (bộ dữ liệu cố ý nhiều ô mờ / nhiều ô – rủi ro R7), vd
  0002_C2 10 câu cần xem; 0001 SBD `06238?` → cần xem SBD. Phiếu "sạch" hiếm ⇒ demo chủ yếu đi qua luồng giáo viên.

## B3 – API FastAPI (07/10/2026)
Mã: `backend/main.py` (endpoint mỏng), `backend/schemas.py` (hợp đồng pydantic, hiện trong Swagger). Chạy: `uvicorn backend.main:app --port 8000`
(từ `smart_exam_db/`) → Swagger `http://127.0.0.1:8000/docs`, ReDoc `/redoc`, OpenAPI `/openapi.json`. Đã chạy thử server thật (đọc: `/health`,
`/exams`, `/docs`, `/openapi.json`; 422 khi gửi sai). Mỗi yêu cầu một kết nối + một giao dịch (`get_conn`: commit / rollback; có test
`test_get_conn_rollback_khi_loi`).

| Endpoint | Việc |
|---|---|
| `GET /health` | sống + nối được CSDL + phiên bản mô hình OMR (503 nếu mất CSDL) |
| `POST /exams` · `GET /exams` · `GET /exams/{id}` | tạo kỳ thi + mã đề + đáp án (chuỗi `ABCD…`), liệt kê, xem (kèm đáp án, số phiếu theo trạng thái) |
| `POST /exams/{id}/sheets` | tải MỘT ảnh, chấm ngay (ảnh bị từ chối vẫn 201, `status=rejected` + `reject_code` + thông báo) |
| `POST /exams/{id}/sheets/batch` | tải NHIỀU ảnh (một lô, `scan_batches`); lỗi một ảnh không kéo cả lô |
| `GET /exams/{id}/sheets?status=` · `GET /sheets/{id}` | danh sách phiếu; kết quả một phiếu (điểm chính thức / tạm / tối đa, từng câu, SBD, mã đề, review) |
| `GET /sheets/{id}/review-questions` · `GET /exams/{id}/review-questions` | câu "cần xem" còn chờ (máy đọc, lý do, xác suất từng ô) |
| `POST /sheets/{id}/questions/{n}/review` | giáo viên xác nhận (`confirm`) / sửa (`set`) MỘT câu → tính lại; hết mục cần xem thì chốt `results` |
| `PUT /sheets/{id}/identity` | giáo viên chốt SBD / mã đề (khi cột cần xem hoặc không khớp danh sách) |
| `GET /sheets/{id}/image?kind=original\|aligned` · `GET /sheets/{id}/questions/{n}/image` | ảnh phiếu; ảnh cắt hàng câu để giáo viên xem |

- Không có đăng nhập (nợ): người dùng = `DEMO_USER` hoặc header `X-User`.
- **pytest `tests/test_backend_api.py` (29)**: CSDL thật trong giao dịch ROLLBACK + thư mục ảnh tạm (`conftest.py`: `conn_thu`, `client`; fixture
  kiểm số dòng 12 bảng trước = sau). Phủ: tạo / xem đề + 8 trường hợp sai; ảnh hỏng → `khong_doc_duoc` / `thieu_marker` / ảnh giả mờ,
  không có điểm, không review được; phiếu thật 0002_C2: chưa có điểm chính thức + câu cần xem `is_correct = NULL` + điểm tạm ≤ tối
  đa → sửa 1 câu → xử lý hết → `graded` + `confirmed` + audit; tải lại cùng ảnh; `confirm` bị từ chối cho câu vị trí; yêu cầu sai;
  0001_C1 SBD `06238?` → giáo viên chốt SBD → chốt; SBD không có trong danh sách; trùng SBD (phiếu thứ hai vào review, không ghi đè);
  lô nhiều ảnh có ảnh hỏng; kỳ thi 10 câu; ảnh không thoát thư mục lưu trữ; migration chạy lại; thiếu `.env` báo lỗi rõ.

## B4 – kiểm chứng (07/10/2026)
**Công cụ độc lập** `tools/kiem_backend_dau_cuoi.py` (báo cáo `data/_eval/backend/bao_cao_dau_cuoi.md` + CSV): gọi API qua TestClient trên CSDL thật
trong một giao dịch ROLLBACK + thư mục ảnh tạm (CSDL sau chạy: số dòng 12 bảng không đổi). **Không dùng code chấm của backend**: điểm thật tính lại từ
`data/ground_truth.csv` (chỉ phiếu 0001–0028; nhãn người tô) + đáp án đọc từ `GET /exams/{id}` bằng luật riêng: *đúng ⇔ người tô đúng MỘT ô và ô đó = đáp án*
(ô mờ cũng tính, đúng chính sách `faint_counts_as_answer`), 0,25 điểm / câu. Hai kỳ thi cùng đáp án (ảnh thứ nhất của mỗi phiếu → A, ảnh thứ hai → B) để
không dính `duplicate_sbd`.
- **Pha 1 – tải ảnh, không can thiệp**: câu KHÔNG gắn cần xem phải có `is_correct` khớp đúng/sai thật; cách đọc, SBD, mã đề khớp nhãn; điểm tạm ≤ điểm thật ≤ điểm tối đa;
  câu cần xem phải `is_correct = NULL`; phiếu tự chốt phải đúng điểm.
- **Pha 2 – giáo viên oracle**: chốt từng câu cần xem đúng như tờ giấy (`action=set`), chốt SBD / mã đề → điểm chính thức cuối phải = điểm thật, đúng sinh viên, `confirmed`.

**Kết quả chạy đầy đủ (56 ảnh train 0001–0028, 86 giây):**

| | C1 | C2 | C3 | C4 | Tổng |
|---|---|---|---|---|---|
| Ảnh / câu | 14 / 560 | 14 / 560 | 14 / 560 | 14 / 560 | 56 / 2 240 |
| Câu OMR gắn cần xem | 138 | 147 | 142 | 141 | **568 (25,4%)** |
| Câu chắc chắn (không cờ) | 422 | 413 | 418 | 419 | 1 672 |
| **Câu chấm sai mà KHÔNG gắn cần xem** | 0 | 0 | 0 | 0 | **0** |
| Câu đọc sai mà không gắn cần xem | 0 | 0 | 0 | 0 | 0 |
| SBD / mã đề sai im lặng · điểm tạm-tối đa không bao điểm thật · tự chốt sai | | | | | 0 · 0 · 0 · 0 |
| Máy đọc sai nhưng có cờ (an toàn) | | | | | 0 |
| Phiếu tự chốt khi tải (không cần xem) | 0 | 0 | 0 | 0 | 0 / 56 (mọi phiếu dev đều có ≥ 4 câu cần xem) |
| **Điểm chính thức sau giáo viên = điểm tính độc lập, đúng sinh viên** | 14 / 14 | 14 / 14 | 14 / 14 | 14 / 14 | **56 / 56** |

- **Ảnh giả** `data/_eval/_gia_v4` (layout phiếu, 74 ảnh mong đợi `tu_choi` hoặc `ok`): **44 từ chối đúng mã, 27 nhận đúng (gồm ảnh xoay 90 / 180 / 270°), 3 từ chối
  với mã khác mong đợi nhưng là giới hạn ĐÃ BIẾT của Tuần 4 (`SAI_MA_DA_BIET`: mờ chéo / mờ nhiễu → `khong_khop_bo_cuc`), 0 lỗi im lặng (ảnh lẽ ra bị từ chối mà
  vẫn có điểm), 0 từ chối nhầm**. Ảnh bị từ chối không có dòng `results`, không có điểm (kiểm trong CSDL).
- Vì phiếu dev luôn có câu cần xem, **đường tự chốt (`results` = `auto`) được kiểm bằng dữ liệu tạo ra**: monkeypatch `omr.doc_phieu` trả `KetQuaOMR` sạch (3 test:
  tự chốt đúng điểm + đối chiếu `fn_grade_sheet`; một câu mờ / nhiều ô duy nhất cũng khiến cả phiếu không chốt, điểm tạm 9,75, câu đó `is_correct = NULL`; mã đề
  không có trong kỳ thi → không chấm).
- **pytest toàn bộ: 166 đạt** (116 cũ + 50 mới; ~50 giây): `test_backend_grading` (14), `test_backend_api` (33), `test_backend_dau_cuoi` (3, mẫu 7 ảnh C1–C4 + 12 ảnh giả).

## NỢ KỸ THUẬT (mọi chỗ làm tạm / chưa làm của bản demo)
**An ninh / vận hành**
1. **Chưa có đăng nhập / phân quyền**: người dùng = `DEMO_USER` hoặc header `X-User` (ai gọi API cũng sửa được điểm). Không CORS, không giới hạn tốc độ. → Tuần 7–8.
2. **Mật khẩu CSDL** còn ghi cứng ở `00_create_database.sql`, `run_all.bat/.sh`, `HUONG_DAN.md`; `.env` cục bộ chứa mật khẩu thật (đã `.gitignore`).
3. **Mỗi yêu cầu một kết nối CSDL** (không pool); log mặc định, không mã yêu cầu.
4. **Xử lý ảnh đồng bộ trong yêu cầu HTTP** (~0,7 s / ảnh; lô nhiều ảnh xử lý tuần tự trong một yêu cầu → lô lớn sẽ quá thời gian). Cần hàng đợi nền (RQ / Celery) + trạng thái `processing` thật.
5. **Ảnh lưu thư mục `storage/`** cục bộ, không dọn dẹp, không quét virus; chỉ giới hạn dung lượng (`MAX_UPLOAD_MB`). Ảnh HEIC gốc phục vụ nguyên trạng. Tải lại đúng ảnh cũ (SHA-256) trả phiếu cũ, kể cả phiếu từng bị từ chối.

**Dữ liệu / nghiệp vụ**
6. **Layout phiếu đọc từ `answer_sheet/output/layout.json`** (`nap_layout`), chưa lấy từ `sheet_templates.layout_config`; mẫu định vị `phieu_trang_300dpi.png` cố định.
7. **`blur_score` KHÔNG ghi vào `answer_sheets.blur_score`**: `system_settings.min_blur_score` (100) là thang Laplacian cũ ≠ thang của `preprocess()` – ghi vào sẽ coi mọi phiếu là mờ. Ảnh mờ do `preprocess` từ chối (`anh_mo`). (Đã ghi ở CLAUDE.md mục 7; sửa CSDL cần hỏi người dùng.)
8. **Chưa có CNN chữ số / `ocr_digits`**: SBD và mã đề đọc từ bubble (kênh viết tay chưa có – Tuần 6); `sbd_confidence` = min `do_tin_cay` các cột (chỉ để tham khảo, quyết định theo `can_xem` của OMR).
9. **Không dùng `fn_process_sheet` / `fn_resolve_review` / `fn_reject_review` / `fn_regrade_exam`**: `fn_process_sheet` không biết lý do cần xem của OMR (có thể tự chấm phiếu đã bị gắn cờ, tính ô `faint` là đáp án). Hệ quả: gọi `fn_regrade_exam` sẽ tính ô `faint` của phiếu `needs_review` là đáp án (điểm tạm lệch) → cần sửa / thay các hàm CSDL cho khớp chính sách "cần xem" (hỏi người dùng trước khi sửa CSDL).
10. **Chưa có**: sửa đáp án + chấm lại, sinh nhiều mã đề, import danh sách sinh viên, loại phiếu (`fn_reject_review`), tải lại ảnh thay ảnh bị từ chối, huỷ điểm cũ khi trùng SBD (`p_void_existing`), phân trang (giới hạn cứng 200 / 500), thống kê (view `v_*` chưa phơi ra API), xuất bảng điểm.
11. **Giáo viên chỉ chốt từng câu**; không có xem hàng loạt, không ghi chữ số đã sửa vào `ocr_digits` để fine-tune, không lưu "máy sai" thành dữ liệu train (hướng phát triển).
12. **Đáp án DEMO giả lập** (`random.Random("2026-<mã>")`) – điểm chỉ có ý nghĩa kiểm thử hệ thống; danh sách thí sinh nạp từ `ground_truth.csv` (chỉ phiếu 0001–0028). Mọi phiếu dev đều có ≥ 4 câu cần xem nên demo chủ yếu đi qua luồng giáo viên; đường tự chốt (`auto`) chỉ kiểm bằng dữ liệu tạo ra.
13. **Một mô hình OMR duy nhất** nạp lúc khởi động (`OMR_MODEL`); đổi mô hình cần khởi động lại. Bản ghi `ml_models` tạo lúc tải ảnh đầu tiên (`is_active = FALSE`, không đụng bản đang active).

**Kiểm thử**
14. Test API dùng CSDL thật trong giao dịch rollback (chưa có CSDL thử riêng); nhánh commit thật của `get_conn` chưa test tự động (chạy thử tay). Đường tự chốt kiểm bằng `KetQuaOMR` dựng tay (monkeypatch `doc_phieu`).
15. Kiểm đầu-cuối chỉ trên ảnh dev 0001–0028 (+ ảnh giả sinh từ ảnh dev); val 0029–0034 và test 0035–0040 chưa chạy qua backend (đúng quy tắc – Phần B Tuần 5).
16. Migration chỉ tiến, không có bản lùi; theo dõi bằng `schema_migrations`.
