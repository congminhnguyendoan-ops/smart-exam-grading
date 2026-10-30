# HƯỚNG DẪN THỰC HIỆN ĐỒ ÁN – SMART EXAM GRADING SYSTEM

Tài liệu này đi kèm bộ database PostgreSQL và hướng dẫn bạn làm từng bước theo đúng kế hoạch 12 tuần.

---

## PHẦN A. CÀI ĐẶT & CHẠY DATABASE (làm ngay – Tuần 2)

### Bước 1: Cài PostgreSQL trên Windows
1. Tải bộ cài tại https://www.postgresql.org/download/windows/ (bản 16 hoặc 17).
2. Khi cài, **nhớ mật khẩu user `postgres`**, giữ port `5432`, tick cài cả **pgAdmin 4**.
3. Thêm `C:\Program Files\PostgreSQL\16\bin` vào biến môi trường **PATH**
   (Start → "Edit the system environment variables" → Environment Variables → Path → New).
4. Mở CMD mới, gõ `psql --version` để kiểm tra.

### Bước 2: Tạo database và nạp dữ liệu
```bat
cd smart_exam_db\database
run_all.bat
```
Script sẽ hỏi mật khẩu `postgres` một lần, sau đó tự làm lần lượt:

| File | Nội dung |
|---|---|
| `00_create_database.sql` | Tạo user `smart_exam_app` (mật khẩu `smartexam123`) và database `smart_exam` UTF-8 |
| `01_schema.sql` | 10 kiểu ENUM + 20 bảng, khóa chính/ngoại, CHECK, index |
| `02_functions_triggers.sql` | Logic chấm điểm, match SBD, hàng đợi review, audit log |
| `03_views.sql` | 8 view cho dashboard, thống kê, tra cứu, đối soát |
| `04_seed.sql` | Dữ liệu mẫu: 10 SV, 1 kỳ thi 10 câu, 2 mã đề, 9 phiếu mô phỏng |
| `05_demo_workflow.sql` | Chạy thử cả luồng: chấm → match → review → sửa đáp án → chấm lại |

> Chạy lại `run_all.bat` bất cứ lúc nào để reset database về trạng thái sạch.

### Bước 3: Xem database bằng giao diện
- **pgAdmin 4**: Servers → localhost → Databases → smart_exam → Schemas → public → Tables.
- Xuất ERD tự động: chuột phải `smart_exam` → **ERD For Database** → đưa ảnh vào báo cáo.
- Hoặc dùng **DBeaver** (miễn phí) – ERD đẹp hơn.
- File `docs/ERD.mermaid` là ERD dạng code (dán vào https://mermaid.live để sửa/xuất ảnh), `docs/ERD.png` là ảnh sẵn.

---

## PHẦN B. HIỂU THIẾT KẾ DATABASE (để viết báo cáo & bảo vệ)

### B1. Các nhóm bảng
| Nhóm | Bảng | Vai trò |
|---|---|---|
| Người dùng | `users`, `classes`, `students`, `student_imports` | Tài khoản, danh sách SV gốc (SBD = `student_code`), lịch sử import Excel |
| Đề thi | `subjects`, `sheet_templates`, `exams`, `exam_students`, `questions`, `exam_codes`, `answer_keys` | Mẫu phiếu, kỳ thi, SV dự thi, câu gốc, mã đề đảo câu, đáp án từng mã đề |
| Nhận diện (CV/ML) | `ml_models`, `scan_batches`, `answer_sheets`, `sheet_answers`, `ocr_digits` | Phiên bản model, lô ảnh upload, kết quả OCR/OMR từng phiếu, từng ô, từng chữ số |
| Kết quả | `results`, `review_queue`, `score_audit_logs`, `system_settings` | Điểm chính thức, hàng đợi human-in-the-loop, lịch sử sửa điểm, ngưỡng confidence |

> Kế hoạch gốc ghi "13 bảng, MySQL". Bản này có 20 bảng trên PostgreSQL – nhớ sửa lại mục 5.2 và mục Tuần 2/7 trong báo cáo cho khớp.

### B2. Luồng "match SBD tự động điền điểm" (`fn_process_sheet`)
```
Ảnh phiếu ──► Pipeline OpenCV + OMR classifier + OCR CNN (Python)
          ──► INSERT answer_sheets / sheet_answers / ocr_digits
          ──► SELECT * FROM fn_process_sheet(sheet_id)
                 1. Ảnh mờ? (blur_score < min_blur_score)           → poor_image_quality
                 2. Chấm theo mã đề; không tìm thấy mã đề            → exam_code_not_found
                 3. Confidence SBD/mã đề < ocr_min_confidence (0.90) → low_ocr_confidence
                 4. Có ô confidence < 0.80 hoặc ô tô mờ              → low_omr_confidence
                 5. SBD không có trong danh sách dự thi              → sbd_not_found
                 6. SV này đã có điểm từ phiếu khác                  → duplicate_sbd
              Không có lỗi nào → INSERT results (status = 'auto')
              Có ≥ 1 lỗi       → INSERT review_queue, KHÔNG ghi điểm
```
Giáo viên xử lý review bằng:
- `fn_suggest_students(sheet_id)` – gợi ý SV có SBD lệch 1 chữ số (lỗi OCR hay gặp nhất).
- `fn_resolve_review(review_id, student_id, teacher_id, ghi_chú)` – xác nhận và ghi điểm.
- `fn_reject_review(review_id, teacher_id, lý_do)` – loại phiếu (quét trùng, ảnh hỏng).
- `fn_regrade_exam(exam_id, user_id)` – chấm lại cả kỳ thi khi sửa đáp án.

Mọi thay đổi điểm được trigger ghi vào `score_audit_logs` (đáp ứng rủi ro "ghi nhầm điểm" ở mục 6).

### B3. Các điểm thiết kế nên nhấn mạnh khi bảo vệ
- **Chặn ghi điểm 2 lần**: unique index `results(exam_id, student_id) WHERE status <> 'void'` + unique `image_hash` để phát hiện upload trùng ảnh.
- **Đảo mã đề nhưng vẫn thống kê theo câu gốc**: `answer_keys.question_id → questions`, nên `v_question_difficulty` gộp được độ khó qua mọi mã đề.
- **Dữ liệu cho fine-tune**: khi giáo viên sửa SBD, ghi `ocr_digits.corrected_digit` → export ra làm tập dữ liệu thật cho Tuần 6; `v_ocr_correction_stats` đo độ chính xác thực tế (domain gap).
- **Quản lý model**: `ml_models` lưu metrics (acc MNIST / acc dữ liệu thật) và chỉ 1 model active cho mỗi loại → bảng so sánh trước/sau fine-tune lấy thẳng từ đây.
- **Ngưỡng cấu hình được**: đổi ngưỡng trong `system_settings` mà không phải sửa code.

---

## PHẦN C. LỘ TRÌNH TỪNG BƯỚC 12 TUẦN

### Cấu trúc thư mục dự án đề xuất
```
smart-exam/
├── database/            ← bộ SQL này
├── cv_engine/           ← preprocessing.py, roi.py, omr.py, ocr.py
├── ml/notebooks/        ← notebook Kaggle (OMR classifier, digit CNN)
├── models/              ← *.keras, *.joblib
├── backend/             ← FastAPI: app/main.py, routers/, db.py, schemas.py
├── frontend/            ← Streamlit: app.py, pages/
├── data/                ← raw/, cells/, digits_real/ (không push ảnh lớn lên Git)
├── tests/
├── .env                 ← DATABASE_URL=postgresql://smart_exam_app:smartexam123@localhost:5432/smart_exam
└── requirements.txt
```

### Giai đoạn 1 – Phân tích & thiết kế (Tuần 1–3)
**Tuần 1**
1. Viết SRS sơ bộ: tác nhân Admin / Giáo viên / Sinh viên; liệt kê use case (đăng nhập, tạo đề, nhập đáp án, sinh mã đề, import SV, upload phiếu, đối soát, xem thống kê, tra cứu điểm).
2. Vẽ Use case diagram (draw.io hoặc PlantUML).
3. Tạo repo GitHub + board Trello với các cột To do / Doing / Review / Done.

**Tuần 2**
1. Chạy `run_all.bat` (Phần A), đọc kỹ Phần B.
2. Vẽ sơ đồ kiến trúc: `Streamlit ↔ FastAPI ↔ PostgreSQL`, `FastAPI → cv_engine (OpenCV + Keras)`.
3. Vẽ DFD mức 0, 1 và Sequence diagram "upload phiếu → chấm → match SBD → results/review_queue" (dựa theo sơ đồ B2).
4. Xuất ERD từ pgAdmin đưa vào báo cáo.

**Tuần 3**
1. `python -m venv venv` → `pip install opencv-python numpy tensorflow scikit-learn fastapi uvicorn "psycopg[binary]" sqlalchemy streamlit pandas openpyxl reportlab`.
2. Chạy `python tools/db_check.py` để kiểm tra Python kết nối được DB.
3. Thiết kế & in phiếu trả lời có **4 ô vuông đen ở 4 góc** (marker để căn chỉnh), SBD 6 cột × 10 hàng, mã đề 3 cột, lưới 40 câu × 4 ô. Ghi toạ độ vào `sheet_templates.layout_config`.
4. Nhờ bạn bè tô 30–50 phiếu, chụp bằng điện thoại ở nhiều điều kiện ánh sáng.
5. Vẽ wireframe 6 màn hình: Đăng nhập, Dashboard, Quản lý đề, Upload, Hàng đợi review, Thống kê.
6. ✅ **Milestone 1**: nộp GVHD kiến trúc + ERD + các sơ đồ.

### Giai đoạn 2 – Lõi CV/ML & Backend (Tuần 4–9)
**Tuần 4 – `cv_engine/preprocessing.py`**
1. `cv2.imread` → `cvtColor(GRAY)` → `GaussianBlur(5,5)` → `adaptiveThreshold`.
2. Đo độ nét: `cv2.Laplacian(gray, cv2.CV_64F).var()` → lưu vào `answer_sheets.blur_score`.
3. Tìm 4 marker góc bằng `findContours` (lọc contour vuông, diện tích lớn) → `getPerspectiveTransform` + `warpPerspective` về kích thước chuẩn 2480×3508.

**Tuần 5 – OMR classifier**
1. Cắt từng ô theo `layout_config` → lưu ảnh ô 32×32 vào `data/cells/{blank,filled,faint,multiple}/`. (Lớp `multiple` xác định ở mức câu: nhiều ô `filled` trong 1 câu.)
2. Baseline: HOG + SVM (scikit-learn). Cải tiến: CNN nhỏ (2 lớp Conv) trên Kaggle.
3. Báo cáo accuracy, confusion matrix trên tập validation; ghi vào `ml_models`.
4. Output mỗi câu: `state`, `selected_options`, `confidence = max(softmax)` → bảng `sheet_answers`.

**Tuần 6 – OCR chữ số**
1. Kaggle Notebook: CNN trên MNIST (+ augmentation xoay ±10°, dịch, nhiễu) → acc test MNIST.
2. Thu 200–500 chữ số viết tay thật từ phiếu → đo acc (domain gap).
3. Fine-tune (freeze các lớp Conv đầu, train lại lớp Dense với learning rate nhỏ) → đo lại.
4. Lập bảng 3 cột: MNIST/test-MNIST, MNIST/test-thật, fine-tune/test-thật → lưu `ml_models.metrics`.
5. Confidence SBD = **tích** (hoặc min) confidence từng chữ số → `answer_sheets.sbd_confidence`; từng chữ số → `ocr_digits`.

**Tuần 7 – Backend FastAPI**
1. `backend/db.py`: kết nối bằng SQLAlchemy/psycopg đọc `DATABASE_URL` từ `.env`.
2. Endpoint gợi ý:
   - `POST /auth/login` (JWT, kiểm tra `users.password_hash` bằng passlib/bcrypt)
   - `CRUD /exams`, `/exams/{id}/codes`, `/exams/{id}/answer-keys`
   - `POST /students/import` – đọc Excel bằng pandas, gọi `fn_upsert_student(...)` từng dòng trong 1 transaction, ghi `student_imports`
   - `POST /exams/{id}/sheets` – nhận ảnh, lưu file, chạy cv_engine, insert kết quả, gọi `fn_process_sheet`, trả JSON kèm confidence
3. Mỗi request có user đăng nhập: chạy `SET LOCAL app.current_user_id = '<id>'` đầu transaction để audit log ghi đúng người sửa.
4. Test bằng Swagger tại `http://localhost:8000/docs`.

**Tuần 8 – Quản lý đề & match SBD**
1. Sinh mã đề: dùng `random.Random(seed).shuffle` trên danh sách câu gốc → insert `exam_codes` (lưu `shuffle_seed`) + `answer_keys` (giữ `question_id` gốc).
2. Sinh PDF phiếu/đề bằng reportlab → lưu đường dẫn vào `exam_codes.pdf_path`, `sheet_templates.pdf_path`.
3. Sửa đáp án → gọi `fn_regrade_exam(exam_id, user_id)`.
4. Endpoint review: `GET /reviews` (view `v_review_pending`), `GET /reviews/{id}/suggestions` (`fn_suggest_students`), `POST /reviews/{id}/resolve`, `POST /reviews/{id}/reject`.
5. Demo nội bộ pipeline end-to-end.

**Tuần 9 – Khung Frontend (Streamlit)**
1. Trang đăng nhập (lưu token trong `st.session_state`).
2. Dashboard: đọc `v_exam_summary`.
3. Upload nhiều ảnh (`st.file_uploader(accept_multiple_files=True)`), import SV từ Excel.
4. Hàng đợi review: hiển thị ảnh gốc + SBD nhận diện + danh sách gợi ý.
5. ✅ **Milestone 2**.

### Giai đoạn 3 – Hoàn thiện (Tuần 10–12)
**Tuần 10**: màn hình đối soát cho chọn SV từ danh sách, sửa từng câu (update `sheet_answers.manually_edited = TRUE`), ghi `ocr_digits.corrected_digit`; thống kê phổ điểm (`v_score_distribution`), độ khó câu (`v_question_difficulty`); trang SV tra cứu (`v_student_transcript`).

**Tuần 11**: đo trên tập phiếu thật: accuracy OMR, OCR trước/sau fine-tune, tỉ lệ match tự động (`v_exam_summary.auto_match_rate_pct`), thời gian xử lý (`AVG(processing_time_ms)`); test quét trùng (phải ra `duplicate_sbd`); viết pytest cho cv_engine và API.

**Tuần 12**: kiểm thử người dùng, viết báo cáo, slide, quay video demo theo đúng kịch bản `05_demo_workflow.sql` (phiếu chuẩn → SBD mờ → SBD sai → quét trùng → sửa đáp án chấm lại). ✅ **Milestone 3**.

---

## PHẦN D. MỘT SỐ CÂU SQL HAY DÙNG
```sql
-- Bảng điểm 1 kỳ thi
SELECT * FROM v_exam_results WHERE exam_id = 1 ORDER BY student_code;
-- Đổi ngưỡng confidence
UPDATE system_settings SET setting_value = '0.85' WHERE setting_key = 'ocr_min_confidence';
-- Kích hoạt model mới (tắt model cũ trước)
UPDATE ml_models SET is_active = FALSE WHERE model_type = 'ocr_digit';
UPDATE ml_models SET is_active = TRUE  WHERE model_type = 'ocr_digit' AND version = '2.0';
-- Xuất dữ liệu chữ số đã được giáo viên sửa để fine-tune
SELECT crop_image_path, corrected_digit FROM ocr_digits WHERE corrected_digit IS NOT NULL;
-- Backup / restore
--   pg_dump -U postgres -F c smart_exam > smart_exam.backup
--   pg_restore -U postgres -d smart_exam smart_exam.backup
```

## PHẦN E. LỖI THƯỜNG GẶP
| Lỗi | Cách xử lý |
|---|---|
| `'psql' is not recognized` | Chưa thêm thư mục `bin` vào PATH, mở lại CMD |
| Tiếng Việt bị lỗi font trong CMD | `chcp 65001` (đã có trong run_all.bat) hoặc dùng pgAdmin |
| `password authentication failed for smart_exam_app` | Kiểm tra mật khẩu trong `00_create_database.sql` và `run_all.bat` giống nhau |
| `database "smart_exam" is being accessed by other users` | Đóng pgAdmin/DBeaver đang mở DB rồi chạy lại |

---
## Phụ lục – Đăng nhập giáo viên (nhánh cai-tien-b, 29/10/2026)
- Trong `.env` cần `AUTH_SECRET` (chuỗi bí mật ≥ 32 ký tự; sinh: `python -c "import secrets; print(secrets.token_hex(32))"`) và `AUTH_MODE=on`. Chạy server như cũ: `uvicorn backend.main:app --port 8000`, mở `http://127.0.0.1:8000/` → màn đăng nhập.
- Tạo / đặt lại tài khoản: `python -m backend.tai_khoan --mau` (admin, gv_an, gv_binh với mật khẩu ngẫu nhiên, in MỘT lần) hoặc `python -m backend.tai_khoan dat-lai-mat-khau <username>` (nhập mật khẩu bằng bàn phím, không hiện trên màn hình).
- Mỗi giáo viên chỉ thấy lớp, sinh viên, kỳ thi, phiếu của lớp mình (trang "Lớp của tôi", "Hồ sơ"); admin thấy tất cả. Gán lớp mẫu: `python tools/nap_giao_vien_demo.py --ap-dung`.
- Chi tiết thiết kế, bảng quyền và quy trình chạy test đợt 2 an toàn: `docs/thiet_ke_dang_nhap.md`.

## Phụ lục – Chụp bằng điện thoại, chấm ngay (nhánh cai-tien-b, 27/10/2026)
1. Một lần (PowerShell **quản trị**, hệ thống không tự chạy): `New-NetFirewallRule -DisplayName "SmartExam-8000-LAN" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Public,Private -RemoteAddress LocalSubnet`
   – chỉ máy cùng mạng nội bộ vào được, không mở ra Internet. Không dùng nữa thì xoá: `Remove-NetFirewallRule -DisplayName "SmartExam-8000-LAN"`.
2. Chạy server cho điện thoại (từ `smart_exam_db\`): `python tools/chay_server_lan.py` (in địa chỉ `http://<IP>:8000/m` + mã QR). Lệnh `uvicorn backend.main:app --port 8000` cũ chỉ cho máy này.
3. Điện thoại cùng Wi‑Fi → quét QR (hoặc nút **📱 Kết nối điện thoại** trên máy tính) → đăng nhập → chọn kỳ thi → **Chụp phiếu**. Kết quả (điểm TẠM, câu cần xem) hiện ngay trên điện thoại;
   phiếu mới tự hiện ở "Danh sách phiếu" trên máy tính – giáo viên duyệt ở máy tính.
4. Wi‑Fi trường chặn kết nối giữa các thiết bị → bật hotspot trên điện thoại, máy tính nối vào, chạy lại bước 2.
5. Ảnh tạm: server ở bước 2 xoá ảnh của phiếu đã chốt (điểm chính thức) / bị từ chối sau 24 giờ (`ANH_GIU_GIO`), giữ phiếu chờ duyệt và kỳ thi `[DEMO…]`; điểm, đáp án, lý do
   vẫn giữ. Không muốn xoá: `--khong-xoa-anh`. Xem trước: `python -m backend.don_anh`. Ảnh trong thư viện ảnh của điện thoại phải tự xoá tay.
Chi tiết: `docs/thiet_ke_chup_dien_thoai.md`.

