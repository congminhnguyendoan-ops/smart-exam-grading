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
├── docs/                         # Tài liệu cho báo cáo (Tuần 1–3)
│   ├── ERD.mermaid, ERD.png      # ERD 20 bảng
│   ├── diagrams/                 # *.mmd (Mermaid) + *.png: 01 use case, 02 kiến trúc,
│   │                             #   03 DFD mức 0, 04 DFD mức 1, 05 seq chấm, 06 seq review, 07 seq import
│   └── wireframes/               # 6 wireframe PNG (login, dashboard, exam, upload, review, stats)
│       └── gen.py                #   sinh bằng HTML + Playwright (playwright không có trong requirements)
├── tools/
│   ├── db_check.py               # Kiểm tra Python ↔ PostgreSQL (psycopg), đọc DATABASE_URL, in
│   │                             #   v_exam_summary và v_review_pending. Chạy từ smart_exam_db/
│   └── prepare_photos.py         # Ảnh HEIC/JPG điện thoại → data/raw: plan (đổi JPG, đề xuất tên theo
│                                 #   EXIF), preview, apply (chép), replace (thay ảnh chụp lại), measure
│                                 #   (đo marker/độ phối cảnh). Chạy từ smart_exam_db/
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
│       ├── ground_truth.csv      # Nhãn cấp phiếu (SBD, mã đề, 40 câu, bút, điều kiện chụp)
│       ├── cell_labels.csv       # Nhãn cấp ô (blank/filled/faint) + question_state
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

## 7. Việc dang dở

- [x] **BỘ ẢNH ĐÃ XONG (03/10/2026)**: 80 ảnh phiếu trong `data/raw/`, 10 trang trong `data/raw_digits/`,
      4 ảnh bị loại trong `data/raw_rejected/` (`0014_C3`, `0028_C4`, `0032_C4`, `D007` – marker bị khung
      hình cắt). Quá trình ghi đầy đủ trong `data/_prepare/mapping.csv` (94 dòng, 90 tên mới, không trùng).
      Thay ảnh sau này: `prepare_photos.py measure <ảnh> --ref` → đọc mã ở `data/_prepare/measure/` → `replace`.
- [ ] Việc thu dữ liệu KHÔNG thuộc bộ ảnh, chưa ghi nhận là đã làm: đối chiếu `ground_truth.csv` với
      cái thực sự có trên giấy (người tô sai → sửa CSV → `make_dataset_plan.py --from-csv`), sao lưu `data/`.
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
- [ ] Tuần 4: `preprocessing.py` (phát triển từ `align()` trong `check_layout.py`).
- [ ] Tuần 5: OMR classifier + `split.csv`. Tuần 6: CNN chữ số + fine-tune.
- [ ] Backend API, frontend, luồng review cho giáo viên.
- [ ] (Hướng phát triển) Lưu các lần giáo viên sửa làm dữ liệu train thêm (human-in-the-loop).

## 8. Lỗi / rủi ro đã biết

- `import fitz` bị cảnh báo deprecated → đổi sang `import pymupdf`.
- Python 3.14 rất mới: cần kiểm tra TensorFlow có hỗ trợ không trước khi chạy suy luận local;
  nếu không, tạo venv riêng Python 3.12 cho phần ML.
- Git: đã có `.gitignore` ở gốc (loại `.venv/`, `.idea/`, `data/`, `__pycache__/`, `.env`, ảnh
  `*.png/*.jpg` trong `answer_sheet/output/`). Chưa có remote GitHub.
- Có 2 venv: `smart_exam_db_1/.venv` và `smart_exam_db/answer_sheet/.venv` – cần xác định PyCharm
  đang dùng cái nào để tránh cài thư viện nhầm chỗ.
- Mật khẩu DB `smartexam123` bị ghi cứng trong `00_create_database.sql`, `run_all.bat/.sh`,
  `tools/db_check.py`, `HUONG_DAN.md` – chấp nhận được khi làm local, cần lưu ý nếu công khai repo.
- Không gửi ảnh qua Zalo/Messenger (bị nén) – chỉ chép bằng cáp hoặc Google Drive.
- **`find_markers()`/`align()` trong `check_layout.py` chọn nhầm marker mà KHÔNG báo lỗi – phải xử lý ở
  Tuần 4 (`preprocessing.py`)** (phát hiện 02/10/2026 trên 90 ảnh thật): **23/90 ảnh** nắn sai
  (20/40 ảnh C3 đều sai, cộng 0021_C2, 0028_C4, 0032_C4, D007). Hàm chỉ lấy "vết đen gần vuông gần
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
3. **Cấu trúc thư mục**: `HUONG_DAN.md` đề xuất `smart-exam/cv_engine/preprocessing.py`; CLAUDE.md
   mục 7 ghi `preprocessing.py` (chưa nói đặt ở đâu). Cần chốt vị trí trước Tuần 4.
4. **Thư viện**: `answer_sheet/requirements.txt` chỉ có reportlab/opencv/numpy/pymupdf (ghi `>=4.0`,
   `>=4.8`, `>=1.24`…), không có `psycopg` (cần cho `tools/db_check.py`) hay `playwright`
   (cần cho `docs/wireframes/gen.py`). Phiên bản ở bảng mục 2 chưa đối chiếu với venv thực tế.

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
