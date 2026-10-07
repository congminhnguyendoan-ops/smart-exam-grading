# CLAUDE.md – Smart Exam Grading System

Đồ án chuyên ngành CNTT, làm cá nhân, kế hoạch 12 tuần. Người dùng là sinh viên, thích được
hướng dẫn **từng bước, chậm, bằng tiếng Việt**, và muốn hiểu *vì sao* chứ không chỉ *làm gì*.

---

## 1. Mục tiêu

Hệ thống quản lý kỳ thi trắc nghiệm và **chấm tự động từ ảnh chụp phiếu trả lời bằng điện thoại**:

- Nắn phẳng ảnh → đọc 40 câu × 4 ô (A–D) bằng **OMR** → so đáp án → tính điểm.
- Đọc **SBD và mã đề viết tay** bằng **CNN nhận diện chữ số**, đối chiếu với SBD tô bubble.
- Ghép điểm vào danh sách thí sinh; phiếu không chắc chắn thì đưa giáo viên xem lại.

Bài toán cốt lõi cần giải: **tránh ghi nhầm điểm** (đọc sai SBD, ô tô mờ, tô nhiều đáp án).

---

## 2. Công nghệ

| Hạng mục | Công nghệ | Trạng thái |
|---|---|---|
| Ngôn ngữ | Python 3.14 (venv `.venv`) | Đang dùng |
| Xử lý ảnh | OpenCV 5.0, NumPy 2.5 | Đang dùng |
| Sinh PDF / đọc PDF | ReportLab 5.0, PyMuPDF 1.28 | Đang dùng |
| Database | **PostgreSQL 17** (quản lý qua pgAdmin), DB `smart_exam`, user `smart_exam_app` | Đang dùng |
| Học máy | TensorFlow/Keras, train trên **Kaggle** | Kế hoạch (Tuần 5–6) |
| Backend | FastAPI hoặc Flask | Kế hoạch |
| Frontend | Streamlit hoặc React | Kế hoạch |
| Môi trường | Windows, PyCharm, PowerShell | |

---

## 3. Cấu trúc thư mục

Thư mục gốc dự án (mở trong PyCharm): **`C:\Users\MSI\PycharmProjects\smart_exam_db_1`**
(chứa `CLAUDE.md`, `.gitignore`, `.venv/`, `.idea/` và thư mục `smart_exam_db/` bên dưới).
Là git repo, nhánh `main`, tác giả cấu hình `--local`: `congminhnguyendoan-ops`.
Lưu ý: `answer_sheet/` cũng có `.venv/` và `.idea/` riêng (xem mục 8).

```
smart_exam_db/
├── HUONG_DAN.md                  # Hướng dẫn tổng: cài/chạy DB, giải thích thiết kế DB, lộ trình 12 tuần,
│                                 #   câu SQL hay dùng, lỗi thường gặp (viết TRƯỚC khi làm answer_sheet/)
├── database/                     # Bộ SQL PostgreSQL – chạy theo thứ tự 00 → 05
│   ├── 00_create_database.sql    # DROP + tạo DB smart_exam, role smart_exam_app (chạy bằng postgres)
│   ├── 01_schema.sql             # 10 ENUM + 20 bảng, FK, CHECK, index; seed system_settings (ngưỡng)
│   ├── 02_functions_triggers.sql # fn_grade_sheet, fn_process_sheet (match SBD → results/review_queue),
│   │                             #   fn_suggest_students, fn_resolve_review, fn_reject_review,
│   │                             #   fn_regrade_exam, fn_upsert_student; trigger updated_at, audit điểm
│   ├── 03_views.sql              # 8 view: v_exam_results, v_exam_summary, v_score_distribution,
│   │                             #   v_question_difficulty, v_review_pending, v_student_transcript,
│   │                             #   v_missing_results, v_ocr_correction_stats
│   ├── 04_seed.sql               # Dữ liệu mẫu: 10 SV, kỳ thi 10 câu, mã đề 101/102, 9 phiếu mô phỏng,
│   │                             #   mẫu phiếu "Phiếu chuẩn 40 câu A4" (layout_config tạm – bị
│   │                             #   update_template.sql ghi đè), 4 ml_models giả
│   ├── 05_demo_workflow.sql      # Chạy thử: chấm → match → review → sửa đáp án → chấm lại
│   ├── run_all.bat               # Chạy 00→05 trên Windows (cần psql trong PATH) – RESET toàn bộ DB
│   └── run_all.sh                # Bản Linux/macOS
├── cv_engine/                    # Lõi xử lý ảnh (Tuần 4+): preprocessing.py, sau này roi/omr/ocr.py
│   └── __init__.py               #   (chốt 03/10/2026, theo HUONG_DAN.md Phần C; import từ smart_exam_db/)
├── docs/                         # Tài liệu cho báo cáo (Tuần 1–3)
│   ├── ke_hoach_tuan4.md         # Kế hoạch 8 bước (0–7) của preprocessing: việc, cách đo, tiêu chí xong
│   ├── ERD.mermaid, ERD.png      # ERD 20 bảng
│   ├── diagrams/                 # *.mmd (Mermaid) + *.png: 01 use case, 02 kiến trúc,
│   │                             #   03 DFD mức 0, 04 DFD mức 1, 05 seq chấm, 06 seq review, 07 seq import
│   └── wireframes/               # 6 wireframe PNG (login, dashboard, exam, upload, review, stats)
│       └── gen.py                #   sinh bằng HTML + Playwright (playwright không có trong requirements)
├── tools/
│   ├── db_check.py               # Kiểm tra Python ↔ PostgreSQL (psycopg), đọc DATABASE_URL, in
│   │                             #   v_exam_summary và v_review_pending. Chạy từ smart_exam_db/
│   ├── prepare_photos.py         # Ảnh HEIC/JPG điện thoại → data/raw: plan (đổi JPG, đề xuất tên theo
│   │                             #   EXIF), preview, apply (chép), replace (thay ảnh chụp lại), measure
│   │                             #   (đo marker/độ phối cảnh), verify-ids (đọc "Mã phiếu" in sẵn trên 80
│   │                             #   ảnh, không qua align() → verify_ids.html). Chạy từ smart_exam_db/
│   ├── check_labels.py           # <câu...>: cắt + đo từng câu → label_check.html. `audit`: quét cả 40
│   │                             #   phiếu (40 câu + bubble SBD/mã đề) so với nhãn → label_audit.html/.csv,
│   │                             #   nhóm A (nhầm/thiếu/thừa ô, SBD lệch) / B (rõ↔mờ). Không sửa nhãn
│   └── check_task_pdf.py         # Trích phieu_giao_viec.pdf, so với ground_truth.csv hiện tại, commit đầu
│                                 #   399d48c và make_plan(seed 2026). Không sửa gì
├── answer_sheet/                 # Code phiếu trả lời + thu dữ liệu
│   ├── sheet_layout.py           # NGUỒN DUY NHẤT của mọi toạ độ/kích thước phiếu
│   ├── generate_sheets.py        # Vẽ PDF phiếu + trang chữ số, xuất layout.json, update_template.sql
│   ├── make_dataset_plan.py      # Sinh kịch bản tô: ground_truth.csv, cell_labels.csv, phieu_giao_viec.pdf
│   │                             #   --from-csv: sinh lại cell_labels.csv từ ground_truth.csv đã sửa
│   ├── check_layout.py           # Tô giả phiếu 0001, làm nghiêng/mờ, đọc lại → phải in "KHỚP"
│   │                             #   có hàm align() = bản đầu của preprocessing (Tuần 4)
│   ├── check_photos.py           # Kiểm tra ảnh chụp: tên file, blur, độ phân giải, 4 marker; lưu _aligned/
│   ├── requirements.txt
│   ├── HUONG_DAN_THU_DU_LIEU.md  # Quy trình thu dữ liệu chi tiết (đọc file này trước)
│   ├── fonts/                    # DejaVuSans(.ttf, -Bold) để in tiếng Việt trong PDF
│   └── output/                   # File sinh ra (không sửa tay, trừ ground_truth.csv)
│       ├── phieu_danh_so.pdf     # 40 phiếu có Mã phiếu 0001–0040 (thu dữ liệu)
│       ├── phieu_trang.pdf       # Phiếu dùng cho kỳ thi thật (không có Mã phiếu)
│       ├── phieu_giao_viec.pdf   # Kịch bản tô cho người tô, 2 phiếu/trang
│       ├── trang_chu_so.pdf      # 10 trang thu chữ số viết tay
│       ├── layout.json           # Toạ độ pixel @300 DPI của phiếu
│       ├── digit_sheet_layout.json
│       ├── update_template.sql   # Ghi layout vào bảng sheet_templates
│       ├── ground_truth.csv      # Nhãn cấp phiếu: SBD, mã đề (viết tay), sbd_bubble, exam_code_bubble
│       │                         #   (chữ số TÔ; '-' = cột không tô), bút, điều kiện chụp, 40 câu
│       ├── cell_labels.csv       # Nhãn cấp ô (blank/filled/faint) + question_state. 6 400 dòng ô đáp án
│       │                         #   (question 1–40, option A–D) rồi 3 600 dòng bubble (question sbd1–6 /
│       │                         #   exam_code1–3, option 0–9). OMR: lọc question là số
│       └── preview_phieu.png
└── data/                         # Không push lên GitHub (.gitignore) – chỉ có trên máy, cần sao lưu
    ├── raw_heic/                 # Ảnh gốc từ điện thoại IMG_xxxx (.HEIC; ảnh chụp lại là .JPG) – không sửa
    ├── _prepare/                 # jpg/ (ảnh đã chuyển), mapping.csv, preview.html, measure/
    ├── raw/                      # 80 ảnh gốc: 0001_C1.jpg … (KHÔNG BAO GIỜ sửa)
    ├── raw_digits/               # D001.jpg … D010.jpg
    ├── raw_rejected/             # 4 ảnh bị thay (marker bị khung hình cắt) – giữ lại, không dùng
    ├── ground_truth.csv          # Bản copy đã sửa theo thực tế
    ├── cell_labels.csv
    └── split.csv                 # (Tuần 5)
```

Ghi chú:
- Cấu trúc thư mục "đề xuất" trong `HUONG_DAN.md` (Phần C: `cv_engine/`, `backend/`, `frontend/`, `ml/`,
  `models/`, `tests/`, `.env`) **chưa được tạo**; code thực tế hiện chỉ có `answer_sheet/`.
- `answer_sheet/output/overlay_check.png`, `synthetic_photo.jpg`, `synthetic_aligned.jpg` là ảnh do
  `check_layout.py` sinh ra.
- 4 nhóm bảng DB (theo `HUONG_DAN.md` B1): Người dùng (`users`, `classes`, `students`, `student_imports`),
  Đề thi (`subjects`, `sheet_templates`, `exams`, `exam_students`, `questions`, `exam_codes`, `answer_keys`),
  Nhận diện (`ml_models`, `scan_batches`, `answer_sheets`, `sheet_answers`, `ocr_digits`),
  Kết quả (`results`, `review_queue`, `score_audit_logs`, `system_settings`).

---

## 4. Quyết định thiết kế đã chốt

| Quyết định | Lý do |
|---|---|
| Mọi toạ độ chỉ nằm trong `sheet_layout.py`; PDF, `layout.json`, SQL đều sinh từ đó | PDF, file toạ độ và database luôn khớp nhau. Đổi layout = sửa 1 file rồi chạy lại |
| 4 ô vuông đen 8×8 mm, tâm cách mép 14 mm (tâm–tâm ngang = **182 mm**) | Dễ tìm nhất để perspective transform. 182 mm dùng để kiểm tra bản in đúng tỉ lệ |
| Ô tròn Ø5 mm, cách 7 mm ngang / 11 mm dọc; chữ A–D xám 55% | Ô to, thưa → ảnh điện thoại hơi mờ vẫn đọc được |
| SBD/mã đề: ô viết tay 6×9 mm (1 chữ số/ô) **+** bubble 0–9 | Hai kênh độc lập: khớp → tin cậy; lệch → review. Không cần tách chữ |
| Thu dữ liệu "kịch bản trước – tô sau" | Nhãn có sẵn, không gán nhãn tay. Lớp hiếm (tô mờ, tô 2 ô) được tạo nhiều hơn thực tế |
| Nhãn phải khớp **cái có trên giấy**, không phải kịch bản | Người tô sai → sửa `ground_truth.csv` → `make_dataset_plan.py --from-csv` |
| Chia train/val/test **theo mã phiếu**: 0001–0028 / 0029–0034 / 0035–0040 | 2 ảnh cùng phiếu có cùng nét tô → chia theo ảnh sẽ rò rỉ dữ liệu |
| Classifier **cấp ô 3 lớp** (blank/filled/faint) + **luật cấp câu** (0 ô → blank, 1 → đáp án, ≥2 filled → multiple) | "Tô nhiều" là thuộc tính của câu, không phải của ô |
| Dùng classifier thay vì ngưỡng cố định | Bằng chứng: rule-based chỉ đúng 36/40 câu, sai toàn bộ ở ô tô mờ |
| Mất cân bằng lớp (faint ≈ 4%): augmentation + `class_weight`, báo cáo **F1 từng lớp** | Accuracy đơn thuần che giấu lỗi lớp hiếm |
| CNN chữ số: train MNIST → fine-tune bằng trang chữ số; **360 chữ số trên phiếu chỉ dùng để test** | Đo domain gap trước/sau fine-tune một cách khách quan |
| SBD là số ngẫu nhiên, không dùng tên/MSSV thật | Dữ liệu có thể công khai (Kaggle/GitHub) |
| PostgreSQL thay vì MySQL (kế hoạch ban đầu) | Đã chốt |
| Ảnh lưu trên đĩa, database chỉ lưu đường dẫn | Tránh database phình to |
| Code xử lý ảnh nằm trong `smart_exam_db/cv_engine/` (cạnh `answer_sheet/`, `tools/`), không tạo thư mục gốc `smart-exam/` như `HUONG_DAN.md` | Giữ một gốc dự án duy nhất; tên module theo `HUONG_DAN.md` Phần C |
| Chỉnh tham số `preprocessing` **chỉ dùng ảnh phiếu 0001–0034**; ảnh 0035–0040 chỉ chạy **một lần** ở bước đánh giá cuối (`docs/ke_hoach_tuan4.md` bước 7) | Tránh chỉnh theo tập test → số liệu báo cáo lạc quan giả. Trùng ranh giới test của OMR |
| Đánh giá nắn ảnh theo 3 loại: đúng / **lỗi im lặng** (nắn sai mà báo OK) / bị từ chối; mục tiêu lỗi im lặng = 0 | Nắn sai mà không báo = ghi nhầm điểm; từ chối thì còn giáo viên xem lại |
| Thêm đề mới **không cần train lại** | Mô hình chỉ đọc ô/chữ số; đáp án nằm trong DB. Chỉ train lại khi đổi mẫu phiếu |

---

## 5. Cài đặt và chạy

Chạy trong Terminal của PyCharm, thư mục `answer_sheet/`, venv đã bật:

```powershell
pip install -r requirements.txt
python generate_sheets.py        # PDF + layout.json + update_template.sql
python make_dataset_plan.py      # ground_truth.csv + cell_labels.csv + phieu_giao_viec.pdf
python check_layout.py           # phải in "KẾT QUẢ LAYOUT: KHỚP"
python check_photos.py --dir ..\data\raw
python check_photos.py --dir ..\data\raw_digits
```

Tạo/reset database (thư mục `smart_exam_db\database\`, **xoá sạch DB cũ**): `run_all.bat`
(cần `psql` trong PATH – xem mục 8). Kiểm tra kết nối Python: `python tools/db_check.py` từ `smart_exam_db\`.

Ghi layout vào DB: mở `output/update_template.sql` trong **pgAdmin Query Tool** (DB `smart_exam`) rồi Execute.
`psql` không có trong PATH; nếu cần dùng: `"C:\Program Files\PostgreSQL\17\bin\psql.exe"`.

In phiếu: **Scale = None / Actual size, Zoom 100%**, 1 mặt, trắng đen. Phần mềm in hay tự chọn
"Fit to printer margins" (thu nhỏ ~94%) – phải kiểm tra lại mỗi lần mở file.

---

## 6. Việc đã xong

- [x] Sinh toàn bộ file trong `output/`; `check_layout.py` → **KHỚP** (40/40 ô, SBD `062384`, mã đề `101`).
- [x] Baseline rule-based: 36/40 câu, 4 lỗi đều ở ô tô mờ (đã chụp màn hình cho báo cáo).
- [x] Chạy `update_template.sql` → `UPDATE 1` trên mẫu "Phiếu chuẩn 40 câu A4".
- [x] In phiếu đúng tỉ lệ 100% (đã sửa lỗi Fit to printer margins).
- [x] Tạo `.gitignore`, `git init`, commit đầu tiên `399d48c` (53 file) – 30/09/2026.
- [x] Sửa lỗi `multiple_marks` (02/10/2026): `fn_process_sheet` bước (4b) đưa phiếu có câu tô nhiều ô
      (`state='multiple'` hoặc `length(selected_options) > 1`) vào review, ghi `multiple_mark_questions`
      vào `details`. Kiểm thử `database/tests/test_multiple_marks.sql` (BEGIN…ROLLBACK, không để lại dữ liệu):
      3 phiếu A/B/C đúng mong đợi, in "KẾT LUẬN: ĐÃ SỬA". Đã cài vào DB qua pgAdmin.
      Cài lại riêng hàm này: trong pgAdmin bôi đen từ dòng `CREATE OR REPLACE FUNCTION fn_process_sheet`
      đến dòng `END $$;` ngay trước comment `-- 6. fn_suggest_students` rồi F5 (không chạy cả file).
- [x] Sửa 7 nhãn theo ghi chú người tô trên phiếu giao việc (03/10/2026), người dùng đã so với giấy thật:
      | Phiếu | Câu | Cũ (kịch bản) | Mới (trên giấy) |
      |---|---|---|---|
      | 0032 | 33 | `b` (B mờ) | `B` (tô đậm thay vì mờ) |
      | 0008 | 18 | `B` | `D` |
      | 0021 | 5 / 6 / 11 / 12 / 14 | `D` / `B` / `D` / `a` / `B` | `B` / `D` / `A` / `B` / `C` (tô nhầm ô; câu 12 còn tô rõ thay vì mờ) |
      Bằng chứng: `python tools/check_labels.py 0032:33 0008:18 0021:5,6,11,12,14` (ảnh C1; ô được tô có
      độ tối 0,79–0,85, các ô khác 0,27–0,33; ảnh 0021_C2 bị bỏ vì align() nắn sai). Sửa đúng 7 ô trong
      `ground_truth.csv` → `make_dataset_plan.py --from-csv` → `cell_labels.csv` đổi 18 dòng, chỉ ở 7 câu đó.
      Lớp ô `faint` 262 → **260** (vẫn 4,1% / 6 400 ô); `filled` 1 307 → 1 309. Bản trước khi sửa:
      `data/_prepare/backup/*_truoc_sua_20261003.csv`. Đã chép 2 file sang `data/`.
- [x] **Quét nhãn cả 40 phiếu + sửa lần 2 (03/10/2026)**:
      - **Ảnh tráo tên**: `0002_C3` ↔ `0003_C3` (IMG_4219 / IMG_4218; người chụp chụp 0003 trước 0002) → đã
        đổi tên, ghi `mapping.csv` (bản cũ `backup/mapping_truoc_doi_ten_20261003.csv`). `prepare_photos.py
        verify-ids`: 51/80 ảnh tự động khớp chắc chắn, 29 ảnh còn lại (C2 tối, C3 chữ nhỏ, 0006 nằm ngang)
        đọc bằng mắt → **80/80 khớp tên file**.
      - **Phiếu giao việc** (`check_task_pdf.py`): PDF = `make_plan(seed 2026)` = `ground_truth.csv` commit đầu
        (0 lệch). Lệch với bản hiện tại đúng 10 ô = các nhãn sửa có chủ đích (7 lần 1 + 3 lần 2).
      - **Audit** (`check_labels.py audit`): độ tối so với nền giấy quanh từng ô, dò lại vị trí từng hàng ±4 mm,
        thang tương đối theo từng ảnh. Ô trống p99 = 0,06, ô mờ p1 = 0,26 (tách rõ); mờ/rõ chồng lấn (mờ p95
        0,85, rõ p5 0,88). Quét 38/40 phiếu (không quét được 0006, 0018 – xem mục 8).
      - Người dùng so giấy rồi sửa: **0022 câu 20** `C`→`B` (người tô tô nhầm); **0011 câu 17** `BC`→`B` (quên tô
        C, chỉ có 1 chấm); **0021 câu 3** `a`→`A` (tô rõ). **Thêm cột `sbd_bubble`, `exam_code_bubble`**:
        0001 SBD viết `062384` nhưng chữ số 6 không tô → `06238-`; 0035 mã đề viết `103`, không tô ô nào → `---`.
        `make_dataset_plan.py` ghi thêm 3 600 dòng bubble vào `cell_labels.csv` (356 filled, 4 cột không tô).
      - Giữ nguyên (người dùng quyết): 0020 câu 33, 0033 câu 4 (sát ngưỡng) và toàn bộ 52 mục nhóm B (rõ↔mờ).
      - Ô đáp án: `faint` 260 → **259** (4,0%), `filled` 1 309, `blank` 4 832; `cell_labels.csv` đổi 10 dòng ô
        đáp án, chỉ ở 3 câu. Bản trước khi sửa: `backup/*_truoc_sua_20261003_lan2.csv`. Đã chép sang `data/`.
        Sau khi sửa, audit chỉ còn 2 mục nhóm A (0020:33, 0033:4); `check_layout.py` vẫn KHỚP.

## 7. Việc dang dở

- [x] **BỘ ẢNH ĐÃ XONG (03/10/2026)**: 80 ảnh phiếu trong `data/raw/`, 10 trang trong `data/raw_digits/`,
      4 ảnh bị loại trong `data/raw_rejected/` (`0014_C3`, `0028_C4`, `0032_C4`, `D007` – marker bị khung
      hình cắt). Quá trình ghi đầy đủ trong `data/_prepare/mapping.csv` (94 dòng, 90 tên mới, không trùng).
      Thay ảnh sau này: `prepare_photos.py measure <ảnh> --ref` → đọc mã ở `data/_prepare/measure/` → `replace`.
- [ ] Việc thu dữ liệu còn lại (không thuộc bộ ảnh):
      - Nhãn: đã quét 38/40 phiếu bằng `check_labels.py audit` và sửa (mục 6). **Chưa quét: 0006, 0018**
        (không có ảnh nắn đúng) và nhóm B (rõ↔mờ) chưa đối chiếu từng mục – lỗi còn lại sẽ lộ ra khi
        train/đánh giá OMR. Chạy lại audit khi Tuần 4 có `preprocessing.py` nắn được 0006/0018.
        Sửa thêm: `check_labels.py` → người dùng xác nhận → sửa `answer_sheet/output/ground_truth.csv` →
        `make_dataset_plan.py --from-csv` → chép cả 2 CSV sang `data/`.
      - **Sao lưu `data/`** (chưa làm – `data/` không có trong git).
- [x] Script đổi tên ảnh: `tools/prepare_photos.py` (`plan` → `preview` → `apply`). 02/10/2026 đã chép
      80 ảnh → `data/raw/`, 10 trang → `data/raw_digits/` (khớp SHA-256 với nguồn; HEIC gốc giữ nguyên).
- [ ] **`check_photos.py` CHƯA ĐÁNG TIN cho đến khi sửa `find_markers()` ở Tuần 4**: nó báo "OK" cho
      23/90 ảnh mà `align()` chọn nhầm marker và lưu ảnh nắn SAI vào `_aligned/` (xem mục 8). Đến lúc
      đó chỉ dùng nó để kiểm tra tên file / độ mờ / độ phân giải; không dùng `_aligned/` để cắt ô hay
      làm dữ liệu train. Kiểm tra nắn đúng/sai tạm thời bằng `python tools/prepare_photos.py preview`.
- [x] Chụp lại ảnh có marker bị khung hình cắt (02/10/2026), thay bằng
      `prepare_photos.py replace` (ảnh cũ DI CHUYỂN sang `data/raw_rejected/`, `mapping.csv` ghi cả hai):
      `0028_C4` ← IMG_4357 (BR cũ hụt 14%), `0032_C4` ← IMG_4358 (BR 33%), `D007` ← IMG_4359 (TR 16%).
      Ảnh mới: mã phiếu/trang đọc tay + SBD/mã đề khớp `ground_truth.csv`, 4 marker trong khung,
      `align()` nắn đúng. Ảnh chụp lại là JPG (iPhone "Most Compatible"), không phải HEIC – vẫn đủ
      4032×3024, EXIF đầy đủ. `0021_C2` giữ lại (4 marker nguyên vẹn, chỉ có tờ khác lọt vào góc).
- [x] **`0014_C3` ← IMG_4381** (03/10/2026). Ảnh cũ (IMG_4243) có marker BR bị cắt (hụt 13%). Chụp lại
      4 lần, đo bằng `prepare_photos.py measure`: IMG_4356 = 0,85, IMG_4361 = 0,80, IMG_4379 = 0,83 (chưa đủ
      nghiêng), **IMG_4381 = 0,63** (đạt; 4 marker trọn vẹn, gần mép nhất 90 px; mã phiếu 0014, SBD 897296,
      mã đề 102 đọc tay khớp `ground_truth.csv`; 4 marker đo được đã kiểm tra bằng mắt là marker thật).
      "Độ phối cảnh" = min(trên/dưới, trái/phải và nghịch đảo) của tứ giác 4 tâm marker. Tham chiếu
      (`measure --ref`, bỏ ảnh nằm ngang): **C1 0,82–0,99** (trung vị 0,89, 20 ảnh), **C3 0,60–0,73**
      (trung vị 0,62, 19 ảnh). Như mọi ảnh C3, `align()` chọn nhầm marker trên IMG_4381 (lỗi mục 8).
- [ ] Tuần 4: `cv_engine/preprocessing.py` (phát triển từ `align()` trong `check_layout.py`), theo
      `docs/ke_hoach_tuan4.md` (8 bước, làm từng bước, dừng chờ người dùng sau mỗi bước).
      Bước 0 (thư mục, quy tắc dev/test, kế hoạch) xong 03/10/2026.
      **Bước 1 xong 03/10/2026** – `tools/eval_preprocessing.py` (lệnh `run`, `tu-kiem`, `dung-sai`,
      `tam-marker`, `finalize`, `report`; chỉ ghi `data/_eval/`). Ngưỡng + căn cứ: `data/_eval/nguong.json`.
      Số liệu "trước" của `align()` cũ (`python tools/eval_preprocessing.py report`, từ
      `data/_eval/align_cu/truth_dev.csv`; 26 ảnh kết luận bằng mắt, 52 tự động):
      | Điều kiện | Ảnh | Đúng | Lỗi im lặng | Bị từ chối |
      |---|---|---|---|---|
      | C1 | 17 | 17 | 0 | 0 |
      | C2 | 18 | 14 | 4 | 0 |
      | C3 | 17 | **2** | **15** | 0 |
      | C4 | 16 | 16 | 0 | 0 |
      | D (trang chữ số) | 10 | 10 | 0 | 0 |
      | **Tổng dev** | **78** | **59** | **19** | **0** |
      Phát hiện kèm theo: OMR đọc toạ độ cố định chịu lệch 1,75 mm (bubble SBD) / 2,0 mm (ô đáp án), dò lại
      từng hàng 3,0 / 3,25 mm; 0014_C2 giấy cong (lệch cục bộ 4,2 mm) ⇒ **Tuần 5: OMR phải dò lại từng hàng**.
      Nội dung lệch xuống ~+0,3 mm có hệ thống, không do `align()` (khả dĩ nhất: máy in).
      **Bước 2 xong 03/10/2026** – `cv_engine/preprocessing.py`: `KetQuaTienXuLy`, `doc_anh()`/`load_image()`
      (đọc byte bằng `np.fromfile` cho đường dẫn Unicode; JPG: OpenCV + tự áp EXIF; HEIC: pillow-heif, ghi
      Orientation gốc). Kiểm tra bằng `tools/kiem_load_image.py` (chỉ ghi `data/_eval/`):
      (a) `exif` 8/8 ca đạt – EXIF 1/3/6/8 đúng chiều (MAD 0,04–0,49; chiều sai ≥ 31), HEIC thật IMG_4214 không
      xoay 2 lần (MAD 1,08), đường dẫn có dấu, file không tồn tại/hỏng → `LoiDocAnh`;
      (b) `so-pixel` **78/78** ảnh dev giống từng điểm ảnh `cv2.imdecode`;
      (c) eval `v2_load` (`load_image` + `align()` cũ): `finalize --ke-thua align_cu` đạt (số đo trùng khớp),
      `report --so-voi align_cu` = 0 ảnh đổi phân loại (59/19/0 như bảng trên). Phép thử chặn `--ke-thua`
      (scratchpad, 6/6 ca): lệch 1 số đo / 1 ảnh khác điểm ảnh → bị từ chối, không ghi `truth_dev.csv`.
      Lưu ý: luật hiện tại kết luận được cả 78 ảnh (26 ảnh xem bằng mắt ở Bước 1 đều trùng máy).
      **Bước 3b xong 06/10/2026**: 78/78 ảnh dev đủ 4 marker thật, 4,3 ứng viên/ảnh (bộ lọc cũ 384), hạng lớn
      nhất 5, K = 10 (`tim_ung_vien_marker()`; số liệu + ngưỡng: `docs/ke_hoach_tuan4.md` mục 3b).
      Kèm theo: sửa nhãn marker thật **0007_C3** (ô TR cũ thuộc tờ khác lọt khung; người dùng xác nhận bằng mắt) –
      xem bằng mắt marker phải vẽ tứ giác 4 điểm, không chỉ xem từng ô.
      **Bước 3 xong 06/10/2026** (3c: `find_markers()` – bộ 4 theo hình học K1 lồi / K2 phối cảnh / K3 cỡ / K4 hình dạng
      marker sau H ≤ 2,0 mm, thử 4 cách gán góc, từ chối `nhieu_phieu` / `marker_mo_ho` / `marker_khong_dat`; tâm dưới
      pixel `tam_phoi_canh()`). Eval `v3_hinh_hoc` (`report --so-voi align_cu`), 7 ảnh C3 kết luận bằng mắt:
      | Điều kiện | Ảnh | Đúng | Lỗi im lặng | Bị từ chối |
      |---|---|---|---|---|
      | C1 | 17 | 17 | 0 | 0 |
      | C2 | 18 | 18 | 0 | 0 |
      | C3 | 17 | **17** | 0 | 0 |
      | C4 | 16 | 16 | 0 | 0 |
      | D | 10 | 10 | 0 | 0 |
      | **Tổng dev** | **78** | **78** | **0** | **0** |
      (trước: 59 / 19 / 0). Không đạt: `lech_max` của ảnh đúng không giảm (0,90 → 0,91 mm TB) – lệch nằm giữa trang, không
      do tâm marker (±0,06 mm). 0006_C2/C3 đúng chiều là tình cờ – **Bước 4 phải quyết 0°/180° bằng nội dung**.
      Chi tiết: `docs/ke_hoach_tuan4.md` mục 3c.
      **Bước 4 xong 06/10/2026** (`v4_verify`): `verify()`/`preprocess()` – chiều 0°/180° bằng nội dung (0006_C2/C3 đúng
      nhờ nội dung), từ chối có mã (`anh_mo`, `khong_khop_bo_cuc`, `khong_ro_chieu`, `marker_cham_mep`, …; marker chạm mép
      → từ chối). Dev 78/78 đúng, 0 lỗi im lặng, 0 từ chối nhầm, 0 ảnh đổi so với v3 (ảnh nắn giống từng điểm ảnh).
      Ảnh giả `data/_eval/_gia_v4` (111, tái tạo bằng `tools/kiem_verify.py tao-gia`, không cần sao lưu): 0 lỗi im lặng,
      4 "sai mã, đã biết" (mờ chéo / mờ + nhiễu bị chặn bởi `khong_khop_bo_cuc` thay vì `anh_mo`). Hồi quy align_cu/v2/v3
      giống từng byte. Chi tiết + bảng: `docs/ke_hoach_tuan4.md` Bước 4. Ảnh nghiêng hơn K2 0,50 bị từ chối → đưa vào
      "Hướng dẫn chụp cho giáo viên" (Bước 7/báo cáo).
      **Bước 5 xong 07/10/2026** (`v5_chuan_hoa`): `normalize()` = chia nền ước lượng (`uoc_luong_nen`, cửa sổ ≈ 15 mm,
      `CACH_MAC_DINH = "chia_nen_20"`, chọn trong 12 cấu hình bằng 3 cổng + maximin AUC – `tools/kiem_chuan_hoa.py so-sanh`);
      `preprocess` điền `anh_chuan_hoa` khi ok, `anh_nan` giữ nguyên (78/78 giống vân tay v4 từng byte; eval, ảnh giả, hồi quy
      v2/v3/v4 giống từng byte). Bóng trung vị C1 0,24→0,04 · C2 0,57→0,10 · C3 0,14→0,06 · C4 0,28→0,05; faint/blank đặc trưng
      tuyệt đối: maximin AUC 0,994→0,999, p1−p99 âm→dương (C4: CI chạm 0); `local_darkness` 0 hàng lật. Giới hạn: mép bóng sắc
      (0032_C4 câu 21–30) hiệu theo hàng giảm tới −0,044; cửa sổ ở biên lưới. `preprocess` 523 → 578 ms trung vị.
      Chi tiết: `docs/ke_hoach_tuan4.md` Bước 5.
- [ ] Tuần 5: OMR classifier + `split.csv`. Tuần 6: CNN chữ số + fine-tune.
      **Yêu cầu Tuần 6 (06/10/2026): đo độ chính xác CNN theo mức mờ (dùng ảnh giả `data/_eval/_gia_v4`, tái tạo bằng
      `tools/kiem_verify.py tao-gia`), rồi chỉnh lại ngưỡng `anh_mo` theo hậu quả.** Ngưỡng hiện tại `MO_MIN = 0,012`
      (`cv_engine/preprocessing.py`, `blur_score` cách `phan_tu_huong`, đo trên `anh_nan` thu 150 DPI) là ngưỡng TẠM, THẬN
      TRỌNG: OMR chịu mờ tới Gauss σ ≈ 32 px / chuyển động 80 px (px ẢNH GỐC 4032×3024; ≈ 2,3 / 5,8 mm mặt phiếu ở C1),
      ngưỡng đặt chặt hơn nhiều chỉ vì CNN chưa đo (`docs/ke_hoach_tuan4.md` Bước 4).
      **Giới hạn đã biết**: `mo_huong` chỉ xét trục x/y; mờ chéo 45° và mờ có nhiễu lọt qua `anh_mo`, hiện bị chặn bởi
      `khong_khop_bo_cuc` (sai mã, vẫn an toàn). **Tuần 6: đo blur 4 hướng + trừ nhiễu, chọn lại ngưỡng `anh_mo` cùng lúc
      với đo CNN theo mức mờ** (gỡ `SAI_MA_DA_BIET` trong `tools/eval_preprocessing.py` khi sửa xong).
      **Yêu cầu Tuần 6 (07/10/2026): thử CNN chữ số trên cả `anh_nan` và `anh_chuan_hoa`** của trang chữ số – chuẩn hoá giảm
      nhẹ nét/nhiễu (50,1 → 48,1) và tăng chênh mức nét giữa trang (29,7 → 32,9) (`docs/ke_hoach_tuan4.md` Bước 5).
      **Yêu cầu Tuần 5 (07/10/2026): chọn `anh_nan` hay `anh_chuan_hoa` để train OMR bằng thí nghiệm F1 lớp `faint` theo
      C1–C4** (chuẩn hoá giúp đặc trưng tuyệt đối, nhưng ở mép bóng sắc 0032_C4 làm hiệu theo hàng giảm tới −0,044).
      **Yêu cầu Tuần 5 (06/10/2026): OMR bắt buộc dò lại từng hàng cho ảnh nghiêng mạnh** – sau khi nắn bằng 4 marker
      (đúng ±0,06 mm ở marker), nội dung ảnh C3 vẫn lệch TB +0,84 mm (0,37–1,30) ở giữa trang; ảnh giả C3 chỉ 0,1 mm ⇒ lệch
      thật (giấy/ống kính), homography 4 điểm không sửa được (`docs/ke_hoach_tuan4.md` 3c dừng B).
- [ ] Backend API, frontend, luồng review cho giáo viên.
- [ ] (Hướng phát triển) Lưu các lần giáo viên sửa làm dữ liệu train thêm (human-in-the-loop).

## 8. Lỗi / rủi ro đã biết

- `import fitz` bị cảnh báo deprecated → đổi sang `import pymupdf`.
- Python 3.14 rất mới: cần kiểm tra TensorFlow có hỗ trợ không trước khi chạy suy luận local;
  nếu không, tạo venv riêng Python 3.12 cho phần ML.
- Git: đã có `.gitignore` ở gốc (loại `.venv/`, `.idea/`, `data/`, `__pycache__/`, `.env`, ảnh
  `*.png/*.jpg` trong `answer_sheet/output/`). Chưa có remote GitHub.
- Có 2 venv: `smart_exam_db_1/.venv` và `smart_exam_db/answer_sheet/.venv`. **Chốt 03/10/2026: dùng
  `.venv` ở gốc** (terminal xác nhận `sys.executable` = `smart_exam_db_1\.venv\Scripts\python.exe`).
  `answer_sheet/.idea/misc.xml` còn trỏ tới đường dẫn cũ `~\Downloads\...` – không dùng.
- Mật khẩu DB `smartexam123` bị ghi cứng trong `00_create_database.sql`, `run_all.bat/.sh`,
  `tools/db_check.py`, `HUONG_DAN.md` – chấp nhận được khi làm local, cần lưu ý nếu công khai repo.
- Không gửi ảnh qua Zalo/Messenger (bị nén) – chỉ chép bằng cáp hoặc Google Drive.
- **`find_markers()`/`align()` trong `check_layout.py` chọn nhầm marker mà KHÔNG báo lỗi – phải xử lý ở
  Tuần 4 (`preprocessing.py`)** (phát hiện 02/10/2026 trên 90 ảnh thật): **23/90 ảnh** nắn sai
  (20/40 ảnh C3 đều sai, cộng 0021_C2, 0028_C4, 0032_C4, D007).
  **Con số này tự mâu thuẫn** (liệt kê ra là 24, chưa gồm 0013_C2, 0018_C2; 0014_C3 là ảnh C3) –
  KHÔNG dùng cho báo cáo; số "trước" lấy từ `data/_eval/align_cu/truth_dev.csv` (Tuần 4 Bước 1). Hàm chỉ lấy "vết đen gần vuông gần
  góc ẢNH nhất", không kiểm tra kết quả, nên 4 điểm sai vẫn cho ra ảnh "đã nắn". Bốn nguyên nhân:
  1. **Ngưỡng tỉ lệ w/h `0.7–1.4` quá chặt**: ảnh C3 bị phối cảnh làm marker xa thành w/h 1,40–1,51
     → bị loại. Nới thành `0.5–2.0` thì 15/18 ảnh C3 hết sai (thí nghiệm chỉ đổi đúng ngưỡng này).
  2. **Ô tròn đáp án/SBD và chữ số viết tay cũng lọt bộ lọc** (~170–480 ứng viên/ảnh, lẽ ra 4) → khi
     thiếu marker thật, ô gần góc nhất bị chọn (ví dụ câu 40-D làm BR, mẫu "Sai ✓" làm TL).
  3. **Marker chạm mép khung hình / dính bóng** (0014_C3, 0028_C4, 0032_C4, D007): contour méo (độ đặc
     0,41–0,50, 6 đỉnh) → bị loại. **Tờ khác lọt vào khung** (0021_C2): marker tờ khác gần góc ảnh hơn.
  4. **Ảnh nằm ngang** (0006_C2, 0006_C3: iPhone ghi EXIF Orientation=3 thay vì 6 khi chụp úp xuống):
     đủ 4 marker đúng nhưng gán TL/TR/BR/BL theo góc ảnh → phiếu bị nắn xoay 90°.
  Hướng xử lý: nới w/h; chọn 4 marker theo **hình học** (tứ giác lồi, tỉ lệ ~182:269 mm, cùng kích
  thước) thay vì "gần góc ảnh nhất"; xác định chiều phiếu bằng nội dung; **kiểm tra sau khi nắn** (tâm
  6×6 mm mỗi marker phải đen kín ≥ 0,5 – marker thật ~1,0, nhầm 0,03–0,43) và báo lỗi thay vì trả ảnh sai.
  Đã kiểm chứng tên ảnh không bị ảnh hưởng (đọc tay mã phiếu + đối chiếu SBD/mã đề với `ground_truth.csv`).
  Tái tạo danh sách 23 ảnh: `python tools/prepare_photos.py preview` (in các ảnh align() không tin cậy).
  Hệ quả: `check_photos.py` sẽ lưu ảnh nắn SAI vào `_aligned/` mà báo OK cho các ảnh này.
  **Phép kiểm tra marker của `check_align()` (ngưỡng 0,5) cũng lọt ảnh sai** (phát hiện 03/10/2026):
  `0013_C2` (đen 68%) và `0018_C2` (83%) nắn sai – góc trên trái bắt vào ô đã tô của tờ khác lọt vào khung.
  Mọi ảnh nắn đúng đều đen 100% → `check_labels.py audit` dùng ngưỡng 0,95 và loại thêm ảnh có thang S < 0,15
  (ô "tô rõ" theo nhãn lại trống = ảnh sai tên/nắn sai). Tuần 4 nên dùng ngưỡng chặt như vậy.
  `marker_centers()` (lệnh measure/verify-ids) cũng bắt nhầm marker ở vài ảnh C2 tối – không thay được align().
- **Ô TRỐNG trên ảnh thật có độ tối ~0,27–0,38** (`darkness()` của `check_layout.py`, 03/10/2026, ảnh
  0008_C1/0021_C1/0032_C1/0008_C4) vì viền tròn + chữ A–D in sẵn nằm trong ô. Ngưỡng của `read_sheet()`
  (> 0,25 = mờ) sẽ coi mọi ô trống là "mờ" trên ảnh thật (ảnh giả của `check_layout.py` không lộ lỗi
  này). Ô tô rõ đo được 0,79–0,91. Lưu ý khi làm baseline/đặc trưng ở Tuần 4–5: so tương đối trong
  hàng hoặc trừ nền ô trống, không dùng ngưỡng tuyệt đối.

### Điểm đã được người dùng chốt (30/09/2026) – `HUONG_DAN.md` lỗi thời ở các điểm này, theo CLAUDE.md

- **Không phải mâu thuẫn**: classifier **3 lớp cấp ô** (`blank/filled/faint`); ENUM `bubble_state`
  4 giá trị (`blank/filled/faint/multiple`) là **trạng thái cấp câu** của `sheet_answers.state`.
  Comment "4 lớp của OMR classifier" trong `01_schema.sql`, ghi chú "4 lớp" trong `04_seed.sql` và
  thư mục `data/cells/multiple/` ở `HUONG_DAN.md` Tuần 5 là cách diễn đạt cũ – không có lớp ô `multiple`.
- **PostgreSQL 17** (bỏ qua các chỗ ghi 16 trong `HUONG_DAN.md`, `run_all.bat`, `01_schema.sql`).
  `psql` vẫn **không** có trong PATH → `run_all.bat` sẽ báo lỗi nếu chưa thêm `...\PostgreSQL\17\bin`.
- **40 phiếu** (0001–0040) × 2 ảnh = 80 ảnh (bỏ qua "30–50 phiếu" ở `HUONG_DAN.md` Tuần 3).
- **Fine-tune CNN chữ số theo mục 4**: fine-tune bằng trang chữ số; 360 chữ số trên phiếu chỉ để
  test (bỏ qua "thu chữ số từ phiếu để fine-tune" ở `HUONG_DAN.md` Tuần 6).

### Mâu thuẫn còn mở (chưa sửa – chờ người dùng quyết)

1. ~~**Tô nhiều ô không vào review**: ENUM `review_reason` có `multiple_marks` nhưng `fn_process_sheet`
   **không bao giờ dùng** → câu tô 2 ô chỉ bị chấm sai rồi ghi điểm tự động (`status='auto'`).~~
   **ĐÃ SỬA 02/10/2026** – xem mục 6. Hệ quả: phiếu 6 của `04_seed.sql` giờ có lý do review
   `{low_omr_confidence, multiple_marks}`; luồng `05_demo_workflow.sql` không đổi.
2. **run_all.bat reset DB**: `00_create_database.sql` chạy `DROP DATABASE`, `04_seed.sql` ghi
   `layout_config` tạm (toạ độ cũ, không khớp `sheet_layout.py`). Chạy lại `run_all.bat` ⇒ **mất
   kết quả `update_template.sql`** (mục 6), phải chạy lại nó.
3. ~~**Cấu trúc thư mục**: chưa chốt vị trí `preprocessing.py`.~~ **ĐÃ CHỐT 03/10/2026**:
   `smart_exam_db/cv_engine/preprocessing.py` (mục 3, mục 4).
4. ~~**Thư viện**: `answer_sheet/requirements.txt` thiếu `psycopg`, `playwright`.~~ **ĐÃ XỬ LÝ 03/10/2026**:
   thêm `pillow>=12`, `psycopg[binary]>=3.2`, `playwright>=1.50` (giữ mức phiên bản cũ của các gói khác);
   cài vào **`.venv` ở gốc** (venv chốt dùng; `answer_sheet/.venv` không dùng nữa): pillow 12.3.0,
   pillow-heif 1.8.0, psycopg 3.3.6, playwright 1.63.0. **Chưa chạy** `playwright install chromium`
   (chỉ cần khi sinh lại wireframe).

---

## 9. Quy ước

- **Không sửa toạ độ ở đâu khác ngoài `sheet_layout.py`.** Sửa xong phải chạy lại `generate_sheets.py`,
  `check_layout.py` và `update_template.sql`.
- Toạ độ pixel luôn tính ở **300 DPI**, gốc toạ độ là ảnh đã nắn phẳng.
- Không bao giờ ghi đè `data/raw/`. Ảnh xử lý ghi ra thư mục khác (`_aligned/`, …).
- Tên file: ảnh phiếu `NNNN_Ck.jpg` (NNNN = mã phiếu, k = 1–4), trang chữ số `DNNN.jpg`.
- Không đụng vào `ground_truth.csv` nếu người dùng chưa xác nhận thay đổi.
- Không bao giờ chạy `run_all.bat`/`run_all.sh` hoặc bất kỳ lệnh ghi/xoá dữ liệu PostgreSQL
  (DROP, DELETE, TRUNCATE, UPDATE, ALTER) khi chưa hỏi người dùng. Sau khi reset DB phải chạy lại
  `answer_sheet/output/update_template.sql`.
- Dùng `pathlib`, đọc/ghi UTF-8 (Windows). Thông báo in ra màn hình và comment bằng **tiếng Việt**.
- Nhãn lớp: `blank` / `filled` / `faint` (cấp ô); `blank` / đáp án / `multiple` (cấp câu).
- Mỗi con số đưa vào báo cáo phải tái tạo được bằng script.
- Khi `HUONG_DAN.md` (viết trước) khác CLAUDE.md thì **theo CLAUDE.md**.
