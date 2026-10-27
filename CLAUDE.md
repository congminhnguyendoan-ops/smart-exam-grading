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
| Backend | **FastAPI 0.142** + uvicorn, psycopg 3, python-dotenv (`smart_exam_db/backend/`, mục 4d) | Bản demo 13/10/2026 (chưa auth) |
| Frontend | HTML + JS thuần (`smart_exam_db/frontend/`, phục vụ `/app/`, mục 4d); Streamlit / React = nợ kỹ thuật | Bản demo 09/10/2026 |
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
├── cv_engine/                    # Lõi xử lý ảnh (Tuần 4+; sau này roi/omr/ocr.py) – import từ smart_exam_db/
│   ├── __init__.py               #   (chốt 03/10/2026, theo HUONG_DAN.md Phần C)
│   ├── preprocessing.py          # preprocess()/preprocess_anh(): đọc ảnh → 4 marker → nắn → verify → chuẩn hoá
│   │                             #   (API: mục 4b). find_markers, verify, normalize, MA_LY_DO, nap_layout
│   ├── omr.py                    # Tuần 5: doc_phieu(kq, layout, mo_hinh) -> KetQuaOMR (API: mục 4c). dinh_vi (2 tầng),
│   │                             #   dac_trung_o, du_doan (NumPy + JSON), ap_luat_cau/ap_luat_cot, MA_LY_DO_OMR
│   ├── ocr.py                    # Tuần 6: tim_khung/cat_anh (cắt ô chữ số bỏ viền, chuẩn hoá MNIST), nap_mo_hinh_ocr + doc_chu_so
│   │                             #   (CNN NumPy + JSON, ~15 ms/phiếu, API: mục 4e), doi_chieu_cot/doi_chieu_truong/doi_chieu_dinh_danh
│   └── tap_du_lieu.py            # NGUỒN DUY NHẤT ranh giới dev/test (+ train/val OMR), chan_test(); Tuần 6: người viết 1–5, fold
├── backend/                      # Backend demo (mục 4d): main.py (API), schemas.py, service.py (ảnh → OMR → chấm → CSDL, luồng giáo viên),
│   │                             #   grading.py (chấm thuần), demo.py (dữ liệu mẫu), config.py (.env), db.py, migrate.py
│   └── migrations/               #   001_backend_bo_sung.sql – chỉ thêm cột / chỉ mục, chạy lại được (python -m backend.migrate)
├── frontend/                     # Giao diện demo (HTML + JS thuần): index.html, app.js, style.css – FastAPI phục vụ tại /app/ (mục 4d)
├── .env.example                  # mẫu cấu hình; .env thật (DATABASE_URL, STORAGE_DIR…) KHÔNG vào git. storage/ (ảnh phiếu) cũng không
├── models/                       # Tuần 5: omr_m1.json (logistic, train 0001–0028), omr_m0.json (ngưỡng) – trong git,
│                                 #   kèm sieu_du_lieu (ngày, git, SHA dữ liệu, fold). Sinh: tools/huan_luyen_omr.py xuat
│                                 #   Tuần 6: ocr_cnn.json (CNN chữ số, NumPy + JSON, xuất từ commit sạch b75453e). Sinh: tools/xuat_ocr.py
├── tests/                        # pytest (254 test, ~95 s): python -m pytest tests (từ smart_exam_db/).
│                                 #   Thiếu data/ → test cần dữ liệu tự SKIP
├── docs/                         # Tài liệu cho báo cáo (Tuần 1–3)
│   ├── ke_hoach_tuan4.md         # Kế hoạch 8 bước (0–7) của preprocessing: việc, cách đo, tiêu chí xong,
│   │                             #   kết quả + số liệu từng bước (nguồn chi tiết cho báo cáo Tuần 4)
│   ├── ke_hoach_tuan6.md         # Kế hoạch CNN chữ số (duyệt 10/10; mốc báo cáo 17/10): ★ quyết định, mục 10 KẾT QUẢ Bước 1–5, hạn chế, nợ
│   ├── ke_hoach_tuan5.md         # Kế hoạch OMR (đã duyệt 07/10): ★ quyết định, Phần A/B, mục 9 NỢ KỸ THUẬT,
│   │                             #   mục 10 KẾT QUẢ PHẦN A (A1–A4), mục 11 quyết định tự đưa ra
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
│   │                             #   (đo marker/độ phối cảnh), verify-ids (đọc "Mã phiếu" in sẵn, không qua
│   │                             #   preprocess → verify_ids.html). Nắn bằng preprocess(); mặc định chỉ dev
│   │                             #   (preview → preview_dev.html). Chạy từ smart_exam_db/
│   ├── check_labels.py           # <câu...>: cắt + đo từng câu → label_check.html. `audit`: quét phiếu dev
│   │                             #   (40 câu + bubble SBD/mã đề) so với nhãn → data/_prepare/label_audit_dev/,
│   │                             #   nhóm A (nhầm/thiếu/thừa ô, SBD lệch) / B (rõ↔mờ). Không sửa nhãn.
│   │                             #   Phiếu test chỉ sau Bước 7: `audit --split tat_ca --xac-nhan-test`
│   ├── eval_preprocessing.py     # Eval nắn ảnh (Tuần 4): run / finalize / report / run-gia → data/_eval/<pp>/
│   ├── kiem_*.py, marker_that.py # Khảo sát / kiểm từng bước Tuần 4 (load_image, verify, chuẩn hoá, marker)
│   ├── tao_tham_chieu.py         # Ảnh tham chiếu cho tests/ (data/_eval/tham_chieu_kiem_thu/)
│   ├── tao_split.py              # Tuần 5: data/split.csv (train 7 fold theo phiếu / val / test – từ tap_du_lieu), --kiem
│   ├── omr_du_lieu.py            # Tuần 5: dữ liệu cho HUẤN LUYỆN (đệm ảnh nắn data/_omr/anh/, nhãn ô); chặn val (Phần A) + test
│   ├── kiem_dinh_vi.py           # Tuần 5: thong-ke (56 ảnh train) / dich-gia (dịch 1 khoảng cách ô) -> data/_eval/omr/dinh_vi/
│   ├── huan_luyen_omr.py         # Tuần 5: dac-trung -> cv (M0/M1 7-fold, chọn nguồn ảnh) -> luat -> xuat (models/*.json)
│   ├── ocr_du_lieu.py            # Tuần 6: cat | xem | split | kiem – cắt ô chữ số -> data/_ocr/cat/, data/ocr_split.csv (5 fold = 5 người viết)
│   ├── huan_luyen_ocr.py         # Tuần 6 (CHỈ huấn luyện, cần torch): m0 (HOG+logistic) | m1 (CNN, MNIST) | m2 (tinh chỉnh, CV theo người)
│   ├── ocr_do_luong.py           # Tuần 6: omr | bao-cao (T, τ, δ, đối chiếu bubble, mức trường) -> data/_eval/ocr/
│   ├── ocr_phan_tich.py          # Tuần 6 Phần C B1: vì sao ~54% phiếu "cần xem" (theo cột / trường / phiếu, người viết, C1–C4)
│   ├── ocr_cai_tien.py           # Tuần 6 Phần C B2: chay | bang | luat-mem – thí nghiệm cải thiện CNN (tăng cường, ensemble, EMNIST),
│   │                             #   cùng luật đo T3 / T4 / lỗi im lặng; luat-mem = ĐỀ XUẤT luật mềm, KHÔNG áp dụng (chờ quyết định)
│   ├── xuat_ocr.py               # Tuần 6: xuất models/ocr_cnn.json TỪ COMMIT SẠCH + kiểm NumPy ↔ PyTorch (< 1e-4); cần torch
│   ├── eval_ocr.py               # Tuần 6: đánh giá ĐỘC LẬP hai kênh SBD / mã đề (chỉ ocr.py + omr.py): run --tap dev | val (--xac-nhan-val) [--xem]
│   ├── eval_he_thong.py          # Tuần 5–6: đánh giá cả hệ thống (nắn ảnh → OMR → CNN → chấm → giáo viên) độc lập; run --tap dev | test (--xac-nhan-test, đăng ký + khoá một lần)
│   ├── eval_omr.py               # Tuần 5: đánh giá ĐỘC LẬP (chỉ gọi doc_phieu): run --phuong-phap m0|m1, report
│   │                             #   -> data/_eval/omr/bao_cao_phan_a_train.md + <pp>/xem_bang_mat.html
│   └── check_task_pdf.py         # Trích phieu_giao_viec.pdf, so với ground_truth.csv hiện tại, commit đầu
│                                 #   399d48c và make_plan(seed 2026). Không sửa gì
├── answer_sheet/                 # Code phiếu trả lời + thu dữ liệu
│   ├── sheet_layout.py           # NGUỒN DUY NHẤT của mọi toạ độ/kích thước phiếu
│   ├── generate_sheets.py        # Vẽ PDF phiếu + trang chữ số, xuất layout.json, update_template.sql;
│   │                             #   --chi-mau-png: phieu_trang_300dpi.png (+ .json SHA) = mẫu định vị của omr.py (trong git)
│   ├── make_dataset_plan.py      # Sinh kịch bản tô: ground_truth.csv, cell_labels.csv, phieu_giao_viec.pdf
│   │                             #   --from-csv: sinh lại cell_labels.csv từ ground_truth.csv đã sửa
│   ├── check_layout.py           # Tô giả phiếu 0001, làm nghiêng/mờ, đọc lại bằng align() VÀ preprocess_anh()
│   │                             #   → phải in "KẾT QUẢ LAYOUT: KHỚP". align() lỗi thời – chỉ để tái tạo số liệu
│   ├── check_photos.py           # Kiểm tra ảnh chụp: tên file, độ phân giải, preprocess() (từ chối có mã lý do);
│   │                             #   ảnh nắn → data/_aligned/<thư mục>/ (JPEG, chỉ để xem); bỏ qua ảnh test
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
    ├── _prepare/                 # jpg/ (ảnh đã chuyển), mapping.csv, preview(_dev).html, measure/,
    │                             #   label_audit_dev/ (audit Bước 6); label_audit.* = bản 03/10 (cũ)
    ├── _aligned/                 # anh_nan JPEG q95 do check_photos.py ghi – CHỈ ĐỂ XEM, không dùng train
    ├── _eval/                    # Kết quả eval Tuần 4 (vân tay, truth_dev.csv từng phương pháp, ảnh giả _gia_v4/,
    │                             #   tham_chieu_kiem_thu/ cho pytest)
    ├── raw/                      # 80 ảnh gốc: 0001_C1.jpg … (KHÔNG BAO GIỜ sửa)
    ├── raw_digits/               # D001.jpg … D010.jpg
    ├── raw_rejected/             # 4 ảnh bị thay (marker bị khung hình cắt) – giữ lại, không dùng
    ├── ground_truth.csv          # Bản copy đã sửa theo thực tế
    ├── cell_labels.csv
    ├── split.csv                 # Tuần 5 (tools/tao_split.py): anh, phieu, dieu_kien, but, tap, fold
    └── _omr/                     # Tuần 5: đệm ảnh nắn, bảng đặc trưng, OOF, luat.json, mô hình từng fold (tái tạo được)
```

Ghi chú:
- Cấu trúc thư mục "đề xuất" trong `HUONG_DAN.md` (Phần C): đã có `cv_engine/`, `tests/` (trong `smart_exam_db/`);
  đã có thêm `backend/`, `models/`, `.env` (cục bộ); **chưa tạo** `frontend/`, `ml/`.
- `answer_sheet/output/overlay_check.png`, `synthetic_photo.jpg`, `synthetic_aligned.jpg`,
  `synthetic_aligned_preprocess.jpg` là ảnh do `check_layout.py` sinh ra.
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
| Ranh giới dev/test chỉ định nghĩa ở `cv_engine/tap_du_lieu.py`; công cụ nào chạm ảnh/nhãn test phải `chan_test()` trước khi đọc file, cần `--xac-nhan-test` (chốt 07/10/2026) | Tuần 5 (`split.csv`) và mọi công cụ dùng chung một nguồn – không lệch ranh giới, không vô tình mở tập test |

### 4b. API `cv_engine.preprocessing` (chốt Tuần 4 Bước 6, ổn định cho Tuần 5–10)

```python
from cv_engine.preprocessing import preprocess, preprocess_anh, nap_layout, MA_LY_DO
kq = preprocess("data/raw/0001_C1.jpg", nap_layout("phieu"))   # trang chữ số: nap_layout("chu_so")
kq = preprocess_anh(gray, nap_layout("phieu"), exif_orientation)  # backend: ảnh xám uint8 ĐÃ áp EXIF
if kq.ok:   ...kq.anh_nan / kq.anh_chuan_hoa...                  # uint8 2480×3508, toạ độ layout.json
else:       print(kq.ly_do, MA_LY_DO[kq.ly_do])                  # mã + thông báo cho giáo viên
```
- `KetQuaTienXuLy`: `ok`, `ly_do` ("" khi ok), `anh_nan` (xám đã nắn, chưa chuẩn hoá – đặc trưng OMR hiện đo ở đây),
  `anh_chuan_hoa` (chia nền cửa sổ ≈ 15 mm, **chỉ khi ok**), `marker` (4×2 tâm TL/TR/BR/BL trên ảnh gốc), `huong_xoay`
  (0/90/180/270), `blur_score`, `exif_orientation`, `chi_tiet`. Khi `ok=False`: `anh_nan` có thể có (chỉ để xem, KHÔNG chấm).
- `MA_LY_DO` (9 mã): `khong_doc_duoc`, `thieu_marker`, `marker_khong_dat`, `nhieu_phieu`, `marker_mo_ho`, `marker_cham_mep`,
  `anh_mo`, `khong_khop_bo_cuc`, `khong_ro_chieu`. Chiều phiếu sai không phải lỗi (tự xoay lại bằng nội dung).
- File không đọc được → `ok=False, ly_do='khong_doc_duoc'`; lỗi lập trình khác **vẫn ném ra** (không che lỗi code).
- Tuần 5 gọi `preprocess()` trực tiếp (~0,58 s/ảnh); `data/_aligned/` chỉ để xem. Công cụ huấn luyện OMR đệm ảnh nắn ở
  `data/_omr/anh/` (PNG không mất mát, kiểm vân tay v4 mỗi lần đọc); backend không đệm.

### 4c. API `cv_engine.omr` (Tuần 5 Phần A, 07/10/2026 – ổn định cho Tuần 7+; chi tiết `docs/ke_hoach_tuan5.md` mục 6, 10)

```python
from cv_engine.omr import doc_phieu, nap_mo_hinh, MA_LY_DO_OMR, sang_bubble_state
mo_hinh = nap_mo_hinh()                       # models/omr_m1.json – nạp 1 lần
omr = doc_phieu(kq, nap_layout("phieu"), mo_hinh)   # kq = preprocess(...) với kq.ok = True (không thì ValueError)
for c in omr.cau:  c.cau, c.trang_thai, c.dap_an, c.xac_suat, c.do_tin_cay, c.can_xem, c.ly_do
omr.sbd, omr.sbd_can_xem, omr.sbd_cot, omr.ma_de, omr.ma_de_can_xem, omr.can_xem, omr.dich_chuyen_mm, omr.thoi_gian_ms
```
- `trang_thai` câu: `trong` / `ro` / `mo` / `nhieu` → DB `bubble_state` qua `sang_bubble_state` (blank/filled/faint/multiple);
  `dap_an` = `selected_options` ('' / 'A' / 'AC'); `xac_suat` = `option_probs`. Cột chữ số không đọc được → `chu_so = '?'`.
- `MA_LY_DO_OMR` (6 mã): `o_mo`, `nhieu_o`, `khong_o_nao`, `tin_cay_thap`, `vi_tri`, `vet_nho` (27/10/2026: ô KHÔNG chọn có khối tối đặc ≥ 90 px sau phép mở 7×7 → câu cần xem, chỉ cộng cờ; chưa áp dụng cho bubble; `docs/ke_hoach_cai_tien_27-10.md` mục 6.3). Câu **trống chắc chắn KHÔNG cần xem**
  (chốt 07/10); trống mà có ô sát ngưỡng → `tin_cay_thap`. Câu mờ / nhiều ô luôn cần xem.
- Lúc chạy chỉ cần NumPy + OpenCV + `models/*.json` + `answer_sheet/output/phieu_trang_300dpi.png` (scikit-learn chỉ để huấn luyện).
  Định vị luôn trên `anh_nan`; nguồn đặc trưng theo mô hình (`anh_nan` – chọn bằng thí nghiệm A2). ~100 ms/ảnh.

---

### 4e. API `cv_engine.ocr` (Tuần 6 Phần C, 20/10/2026 – chi tiết `docs/ke_hoach_tuan6.md` mục 10)

```python
from cv_engine.ocr import doc_chu_so, nap_mo_hinh_ocr, doi_chieu_dinh_danh
mh = nap_mo_hinh_ocr()                                   # models/ocr_cnn.json – nạp 1 lần, KHÔNG cần torch
hv = doc_chu_so(kq, nap_layout("phieu"), mh)             # kq.ok = True (không thì ValueError); hv.sbd (6) / hv.ma_de (3): CotOCR
dc = doi_chieu_dinh_danh(omr, hv, sbd_trong_ds, ma_de_trong_ds, mo_hinh=mh)   # True / False / None (chưa kiểm được) – luật Q3
dc["sbd"] == (giá trị, chắc, lý do); dc["can_xem"]
```
- `CotOCR`: `chu_so` ('?' khi trống / không đọc được), `top_k`, `p` (đã hiệu chỉnh nhiệt độ), `o_trong`, `loi_o` ('' | `o_it_muc` | `khong_phai_chu_so`),
  `ok_vien`, `cnn_chac` (chỉ thông tin), `anh28`, `anh_o`. Ô trống / ít mực / bôi đen / nhiều mảnh KHÔNG qua CNN.
- Luật đối chiếu mỗi cột (τ_khop = 0,5, **Q3 nguyên vẹn**): bubble chắc + CNN cùng chữ số và p ≥ 0,5 → chắc; khác / p thấp → cần xem; bubble `?` hoặc OMR
  gắn cần xem → cần xem; ô viết tay trống + bubble chắc → chắc **chỉ khi** SBD (mã đề) có trong danh sách của kỳ thi; `loi_o` → cần xem.
  Lý do: `lech_bubble`, `tin_cay_thap`, `thieu_bubble`, `bubble_cx`, `o_trong_ngoai_ds`, `o_trong_chua_biet_ds`, `o_it_muc`, `khong_phai_chu_so`.
- Mô hình: CNN Conv16–Conv32–Dense64 (~106 k tham số), MNIST + tăng cường → tinh chỉnh D001–D010, T = 1,75. **T3 ≈ 92%, T4 ≈ 46–54% (chưa đạt 97% / 10%)**,
  lỗi im lặng mức trường = 0 trên dev. Luật mềm (nhận theo p_CNN của chữ số bubble): chỉ là đề xuất, chưa áp dụng.

### 4d. Backend (demo 13/10/2026; kế hoạch + nợ kỹ thuật: `docs/ke_hoach_demo.md`)
**Chạy** (từ `smart_exam_db\`, venv gốc đã bật; cần `.env` – sao chép `.env.example`, điền `DATABASE_URL`):
```powershell
python -m backend.migrate                    # 1 lần: thêm cột bổ sung (chạy lại an toàn, KHÔNG xoá gì)
python tools/nap_demo.py                     # 1 lần: kỳ thi "[DEMO] …" + 4 mã đề + đáp án giả lập + 28 thí sinh DEMO (chạy lại được)
python tools/nap_demo_khop.py                # tuỳ chọn: kỳ thi "[DEMO-2] …" (exam_id 178): đáp án mã đề 101 = bài làm phiếu 0005 → tải 0005_C1, duyệt đúng giấy = 34/40 câu, 8,5 điểm
uvicorn backend.main:app --port 8000         # server; Swagger http://127.0.0.1:8000/docs · ReDoc /redoc · OpenAPI /openapi.json
curl -F file=@data/raw/0002_C2.jpg http://127.0.0.1:8000/exams/<exam_id>/sheets      # tải 1 ảnh (exam_id do nap_demo in ra)
```
**Endpoint**: `GET /health` · `POST/GET /exams`, `GET /exams/{id}` · `POST /exams/{id}/sheets` (1 ảnh), `POST /exams/{id}/sheets/batch` (nhiều ảnh) ·
`GET /exams/{id}/sheets` · `GET /sheets/{id}` · `GET /sheets/{id}/image?kind=original|aligned` · `GET /sheets/{id}/review-questions`,
`GET /exams/{id}/review-questions` · `GET /sheets/{id}/questions/{n}/image` · `POST /sheets/{id}/questions/{n}/review` (`confirm` | `set`) ·
`PUT /sheets/{id}/identity` (SBD / mã đề; ghi `ocr_digits.corrected_digit`) · `GET /sheets/{id}/digits/{field}/{pos}/image` (ảnh ô viết tay; `field` = `sbd` | `exam_code`) · `GET /meta/reject-reasons` (mã từ chối + lời khuyên chụp lại) · `GET /exams/{id}/results` (bảng điểm: `score` CHỈ điểm chính thức, phiếu chưa duyệt chỉ ở `provisional_score`) · `GET /exams/{id}/export.xlsx` (sheet "Bảng điểm" + "Chi tiết", `backend/bang_diem.py`, openpyxl). **Giao diện**: `http://127.0.0.1:8000/` → `/app/` (F1 tải ảnh, F2 danh sách, F3 chi tiết, F4 duyệt, F5 bảng điểm + Xuất Excel; các bước demo: `docs/ke_hoach_demo.md`). Chưa có đăng nhập: người dùng = `DEMO_USER` (.env) hoặc header `X-User`.
**Quy tắc cốt lõi**: ảnh → `doc_anh` → `preprocess_anh` → `omr.doc_phieu` → chấm. Câu OMR "cần xem" **không bao giờ** được chấm như câu chắc
chắn (`is_correct = NULL`). Phiếu còn câu / SBD / mã đề cần xem: `status = needs_review`, CHỈ có điểm tạm (`answer_sheets.raw_score`) và mục
`review_queue`; điểm chính thức (`results`) chỉ có khi giáo viên xem hết (`confirmed`) hoặc máy không còn gì cần xem (`auto`). Ảnh bị từ chối:
`status = rejected` + `reject_code` + thông báo `MA_LY_DO`, không điểm. **SBD / mã đề đọc bằng HAI KÊNH** (Tuần 6 Phần C): bubble (OMR) + chữ viết tay (CNN `ocr.py`), đối chiếu theo mục 4e; trường không chắc → `needs_review` (`low_ocr_confidence`,
`details.sbd_ly_do`); `detected_sbd` = chữ số đọc từ bubble; 9 dòng `ocr_digits` + 9 PNG / phiếu; thiếu `OCR_MODEL` thì không khởi động. Một đường quyết định duy nhất: `service.danh_gia_phieu` (đối chiếu
`fn_grade_sheet` trước khi ghi điểm). **Không dùng `fn_process_sheet`** (không biết lý do cần xem của OMR). Test API chạy trên CSDL thật trong giao
dịch ROLLBACK (`tests/conftest.py`). Kiểm đầu-cuối độc lập: `python tools/kiem_backend_dau_cuoi.py` (56 ảnh train: 0 câu chấm sai không gắn cần xem; 0 SBD / mã đề nhận sai so với chữ viết tay; 26/56 ảnh có SBD hoặc mã đề cần xem).

### 4f. Đăng nhập + phân quyền theo lớp (nhánh `cai-tien-b`, 29/10/2026; chi tiết `docs/thiet_ke_dang_nhap.md`)
- **Chỉ có trên nhánh `cai-tien-b`** (từ `d3d0426`); `main` và tag `dang-ky-dot2` (mã khoá `ma-dot2-dong-bang-v3`) KHÔNG có. **Test đợt 2 chạy từ tag, không từ nhánh này**: cây sạch → `git switch --detach dang-ky-dot2` NGAY trong thư mục hiện tại
  (không worktree / clone mới vì `autocrlf=true` đổi xuống dòng → `kiem_dang_ky` lệch SHA) → `kiem_dang_ky` → chạy → `git switch cai-tien-b`. Nếu `kiem_dang_ky` từ chối vì xuống dòng: DỪNG, báo người dùng, không sửa file / SHA.
- `AUTH_MODE=on` (mặc định) | `demo` (hành vi cũ DEMO_USER / X-User, không kiểm quyền; `conftest.py` và `tools/*` tự đặt demo). `.env`: `AUTH_SECRET` (bắt buộc khi on, không mặc định trong code), `SESSION_HOURS`, `COOKIE_SECURE`.
  Phiên = cookie `se_session` HttpOnly + SameSite=Lax (hoặc `Authorization: Bearer`); mật khẩu scrypt; 5 lần sai / 15 phút → 429; mọi lỗi đăng nhập cùng một thông báo.
- API mới: `POST /auth/login`, `POST /auth/logout`, `GET|PATCH /me`, `POST /me/password`, `GET /me/classes`, `GET /classes/{id}/students`. `POST /exams` nhận `class_id` / `class_code` (lớp phải có sẵn và thuộc lớp mình). Kỳ thi / bảng điểm / Excel có môn + lớp.
  Phân quyền: admin tất cả; teacher = lớp trong `teacher_classes` + kỳ thi mình tạo hoặc thuộc lớp mình; student 403; ngoài quyền → 404 như không tồn tại; chưa đăng nhập 401.
- Tài khoản: `python -m backend.tai_khoan` (`tao` / `dat-lai-mat-khau` / `khoa` / `mo-khoa` / `--mau`; mật khẩu nhập bằng getpass). Mẫu: `admin`, `gv_an`, `gv_binh`. Dữ liệu mẫu: `tools/nap_giao_vien_demo.py [--ap-dung]`.
- **Test KHÔNG tự áp migration lên CSDL thật** (sự cố 27/10: 002 bị áp nhầm, giữ nguyên): `csdl_san_sang` chỉ kiểm migration đã áp (chưa áp → SKIP rõ); áp trong test cần `SMART_EXAM_TEST_MIGRATE=1`; áp thường: `python -m backend.migrate`.
  Nhánh này: pytest 345 đạt + 1 skip có chủ đích.

## 5. Cài đặt và chạy

Chạy trong Terminal của PyCharm, thư mục `answer_sheet/`, venv đã bật:

```powershell
pip install -r requirements.txt
python generate_sheets.py        # PDF + layout.json + update_template.sql
python make_dataset_plan.py      # ground_truth.csv + cell_labels.csv + phieu_giao_viec.pdf
python check_layout.py           # phải in "KẾT QUẢ LAYOUT: KHỚP" (cả align() lẫn preprocess)
python check_photos.py --dir ..\data\raw          # -> data/_aligned/raw/ + photo_report_raw.csv (bỏ qua ảnh test)
python check_photos.py --dir ..\data\raw_digits
```

Kiểm thử (từ `smart_exam_db\`): `python -m pytest tests` – 116 test, ~13 s (`pytest` chỉ để kiểm thử, có trong
`requirements.txt`). Test so ảnh với tham chiếu: cùng phiên bản cv2/numpy lúc ghi → từng byte; khác → dung sai + cảnh báo.

OMR Tuần 5 (từ `smart_exam_db\`): `python tools/tao_split.py --kiem` · `python tools/kiem_dinh_vi.py thong-ke|dich-gia` ·
`python tools/huan_luyen_omr.py dac-trung` → `cv` → `luat` → `xuat` · `python tools/eval_omr.py run --phuong-phap m0` / `m1`
→ `report`. Mẫu định vị: `python answer_sheet/generate_sheets.py --chi-mau-png` (không ghi lại PDF).

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
        0,85, rõ p5 0,88). Quét 38/40 phiếu (không quét được 0006, 0018 – đã quét được ở Tuần 4 Bước 6, mục 7).
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
      - Nhãn: audit 03/10 (38/40 phiếu, `align()`) đã sửa (mục 6). **Audit lại 07/10 (Bước 6, `preprocess()`):
        34/34 phiếu dev, 68/68 ảnh, gồm 0006, 0018** -> nhóm A 3 mục, cả 3 nhãn ĐÚNG (người dùng so giấy; xem yêu
        cầu Tuần 5); nhóm B 45 mục chưa đối chiếu từng mục (người dùng quyết không xem thêm) – lỗi còn lại sẽ lộ ra khi
        train/đánh giá OMR. **Audit test 0035–0040 xong 07/10 (sau Bước 7)**: 6/6 phiếu, 12/12 ảnh, nhóm A 0, nhóm B 17;
        8 mục rõ/mờ cả 2 ảnh cùng lệch nhãn đã so giấy 07/10 – **8/8 giữ nguyên** (ca thử Tuần 5 bên dưới).
        Sửa thêm: `check_labels.py` → người dùng xác nhận → sửa `answer_sheet/output/ground_truth.csv` →
        `make_dataset_plan.py --from-csv` → chép cả 2 CSV sang `data/`.
      - **Sao lưu `data/`** (chưa làm – `data/` không có trong git).
- [x] Script đổi tên ảnh: `tools/prepare_photos.py` (`plan` → `preview` → `apply`). 02/10/2026 đã chép
      80 ảnh → `data/raw/`, 10 trang → `data/raw_digits/` (khớp SHA-256 với nguồn; HEIC gốc giữ nguyên).
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
      (trung vị 0,62, 19 ảnh). Như mọi ảnh C3, `align()` cũ chọn nhầm marker trên IMG_4381; `preprocess()` nắn đúng.
- [x] Việc treo sau Bước 7 (xong 07/10): sửa hiển thị `report-cuoi` ("quy tắc số 3" chỉ in khi n ≥ 10) – không đổi số liệu
      (log trước/sau giống ngoài 7 ô quy tắc số 3); so giấy 8 mục rõ/mờ tập test – 8/8 giữ nguyên.
- [x] **TUẦN 4 XONG (07/10/2026) – Bước 0–7**: `preprocess()` (v6_api) nắn đúng 78/78 ảnh dev + 12/12 ảnh test, 0 lỗi im
      lặng, 0 từ chối nhầm (`align_cu`: 59/78, 9/12). Chi tiết từng bước bên dưới và `docs/ke_hoach_tuan4.md`.
      Tuần 4: `cv_engine/preprocessing.py` (phát triển từ `align()` trong `check_layout.py`), theo
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
      **Bước 6 xong 07/10/2026** (`v6_api`): API `preprocess(path, layout)` / `preprocess_anh(gray, layout, exif)` +
      `MA_LY_DO` + `nap_layout` (mục 4b); `cv_engine/tap_du_lieu.py` (ranh giới dev/test, `chan_test`). Hành vi không đổi:
      78/78 `anh_nan` = vân tay v4, `anh_chuan_hoa` = v5 từng byte; eval 78/78 đúng, 0 đổi. **4 công cụ dùng `preprocess()`**
      (`check_photos`, `prepare_photos`, `check_labels`, `check_layout`), từ chối in mã + thông báo, chốt chặn tập test,
      không ghi `data/raw*` (trước/sau: `check_photos` 19 ảnh nắn sai báo OK → 78/78 đúng; `preview` 17 không tin cậy → 0).
      **Audit nhãn 34/34 phiếu dev** (0006, 0018 lần đầu quét được). **pytest 41/41** (~8 s). Chi tiết:
      `docs/ke_hoach_tuan4.md` Bước 6.
      **Bước 7 xong 07/10/2026** – đánh giá cuối trên test 0035–0040, chạy MỘT lần theo đăng ký trước (commit X `d9e56d5` I/O,
      commit Y `d4aa953` đăng ký; ngưỡng `nguong.json` SHA `DF99086…A91780`), xem bằng mắt MÙ (người dùng kết luận 24 ảnh
      trước khi thấy máy). **`v6_api` ĐẠT: 12/12 đúng, 0 lỗi im lặng, 0 từ chối** (cận trên 95% Clopper–Pearson 26%; theo
      điều kiện n = 2–4 chỉ báo CP 60–84%); `align_cu` 9/12 (lỗi im lặng 0035_C3, 0038_C3, 0039_C3 – cả 3 ảnh C3). Gộp 90 ảnh
      (dev đã dùng để chỉnh): v6_api 90/90, align_cu 68/90. Máy/mắt: 0 ngược nhau; 0035_C3 v6 máy `xem` → mắt `dung`. Độ chính
      xác như nhau trên ảnh đúng ở cả hai (lech_trungvi 0,33 / 0,35 mm); thời gian 594 ms; độ phối cảnh test nhỏ nhất 0,618
      (0039_C3). Lỗi hiển thị "quy tắc số 3" > 100% khi n nhỏ trong `report-cuoi`: đã sửa sau Bước 7 (commit riêng, số liệu không đổi).
      Báo cáo: `data/_eval/bao_cao_cuoi_tuan4.md`; chi tiết `docs/ke_hoach_tuan4.md` Bước 7. Audit nhãn 0035–0040 xong
      (nhóm A 0). Commit: X `d9e56d5`, Y `d4aa953`, kết quả `2774def`.
- [ ] **Tuần 5: OMR** (`docs/ke_hoach_tuan5.md`, duyệt 07/10/2026). **PHẦN A XONG (07/10/2026)**, 5 commit (kế hoạch, A1–A4):
      A1 định vị 2 tầng (56 ảnh train 0 cờ, 0014_C2 đúng; dịch giả 54 880 lượt: 0 khớp nhầm không cờ) + PNG mẫu + `split.csv`;
      A2 đặc trưng + M0/M1, chọn `anh_nan` (chuẩn hoá hoà); A3 luật + API + `models/*.json`; A4 `eval_omr.py` độc lập.
      **M1 OOF 7-fold trên 56 ảnh train: 0 lỗi nặng / 2 744 lượt câu + cột (CP 95% ≤ 0,13%); F1 faint C1 0,989 · C2 0,935 ·
      C3 0,968 · C4 0,945; cần xem thừa 2,25% (C2 riêng 3,79% > 3%); lỗi nhẹ 5; SBD / mã đề 0 sai im lặng; ~100 ms/ảnh.**
      M0 (ngưỡng cố định): 2 lỗi nặng = đúng 2 ca thử 0019_C3 q24, 0020_C1 q33 (vết mờ đọc thành trống); F1 faint C2 0,844.
      **PHẦN B XONG (21/10/2026)**: nested CV (lỗi nặng 0, thừa gộp 1,91%); phép đo vị trí của eval kiểm bằng ảnh dịch giả (0 sai im lặng); HTML 541 câu
      "cần xem cần thiết"; **C2: `ro_min` 0,6 → 0,5** (luật chọn theo từng điều kiện: thừa 0,27 / 2,71 / 1,10 / 2,19%, nặng 0; mô hình xuất lại từ commit sạch `57aa46d`);
      CNN nhỏ (M2) kém M1 ngoài CI → giữ M1; **val OMR chạy MỘT lần (đăng ký mã `4902810`): lỗi nặng 0, SBD / mã đề 0 sai, ca 0033:4 đọc mờ cần xem cả 2 ảnh**
      (M0 bỏ sót 1); thừa gộp 1,54% (C2 4,50% với n nhỏ). Kết quả `docs/ke_hoach_tuan5.md` mục 12–14. **Test cuối cả hệ thống: kế hoạch soạn (`docs/ke_hoach_test_cuoi.md`),
      CHƯA chạy, chờ người dùng chốt mục 1 + gõ "chạy test hệ thống"; CNN test 0035–0040 cũng chưa chạy.**
      **Test cuối cả hệ thống (21/10/2026): công cụ `tools/eval_he_thong.py` đã viết + thử dev (H2–H5 = 0, điểm khớp 56/56, nhất quán nắn ảnh Tuần 4 56/56); ĐÃ ĐĂNG KÝ TRƯỚC
      (`docs/ke_hoach_test_cuoi.md`, `docs/dang_ky_test_he_thong.json`, mã `551b356`; OMR phương án A giữ `omr_m1.json`); ĐÃ CHẠY MỘT LẦN 21/10/2026: **H2–H5 đạt** (lỗi nặng 0/588, SBD / mã đề sai 0/12 + 0/12, chấm sai không cờ 0, điểm chính thức khớp 12/12; nhất quán nắn ảnh Tuần 4 12/12; 0035 mã đề không tô → cần xem),
      **H1 chờ kết luận mắt mù của người dùng** (`data/_eval/he_thong/test/xem_mu.html`, rồi `xem_may.html`); chỉ báo: T3 92,6%, T4 58,3% (7/12), cần xem thừa 3,68%, F1 mờ C2 0,70. KHÔNG chạy lại (khoá `da_chay_test.lock`).
      Chi tiết `docs/ke_hoach_test_cuoi.md` mục 9.**
      (Ghi cũ, Phần A) **Chờ người dùng**: xem `data/_eval/omr/m1/xem_bang_mat.html` (44 mục) bằng mắt. **Phần B** (sau báo cáo 13/10): M2–M4
      nếu cần, chọn nguồn ảnh kỹ, trả Nợ kỹ thuật (mục 9), kiểm tra cuối val 0029–0034 (gồm ca thử 0033 câu 4), đăng ký trước
      + đánh giá test 0035–0040 một lần + xem mù (8 mục rõ/mờ). Tuần 6: CNN chữ số + fine-tune.
      **Yêu cầu Tuần 5 (07/10/2026): dùng 8 mục rõ/mờ của tập test (nhãn ĐÃ XÁC NHẬN bằng giấy thật 07/10, 8/8 giữ nguyên)
      làm ca thử lớp faint/filled cho classifier 3 lớp** – 0036 câu 2, 10, 13; 0037 câu 1, 15, 31; 0040 câu 5 (nhãn mờ, cả 2
      ảnh vượt ngưỡng rõ 0,80 của audit); 0040 câu 10 (nhãn rõ, cả 2 ảnh dưới 0,80). Ranh giới rõ/mờ của ngưỡng cố định không
      khớp cách người phân biệt; đây là ca thuộc tập TEST – chỉ dùng ở đánh giá cuối, không dùng để chỉnh classifier.
      **[XONG A1] Yêu cầu Tuần 5 (07/10/2026): `split.csv` dùng lại `cv_engine/tap_du_lieu.py`** (`PHIEU_TRAIN/VAL/TEST`), không
      định nghĩa lại ranh giới.
      **Yêu cầu Tuần 5 (07/10/2026): ca thử cho classifier 3 lớp** – 3 ô `faint` có nhãn ĐÚNG (đã so giấy) nhưng độ tối
      tương đối n 0,23–0,26 SÁT ngưỡng cố định `MARK_MIN` 0,25 nên audit đọc lệch giữa 2 ảnh: **0019 câu 24 ô C** (C3 n 0,23 /
      C4 0,26), **0033 câu 4 ô C** (C1 0,26 / C2 0,24), **0020 câu 33 ô C** (C1 < 0,25 / C4 0,26). Classifier phải đọc `faint`
      ở cả 2 ảnh mỗi ca – minh hoạ giới hạn của ngưỡng cố định (`docs/ke_hoach_tuan4.md` Bước 6 dừng C).
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
      thật (giấy/ống kính), homography 4 điểm không sửa được (`docs/ke_hoach_tuan4.md` 3c dừng B). **Xác nhận trên test
      (Bước 7)**: 0035_C3 `lech_max` **2,06 mm** (dev: 0030_C3 2,31 mm) > dung sai 2,0 mm của ô đáp án khi đọc toạ độ cố định.
- [ ] **Tuần 6: CNN chữ số** (duyệt 10/10/2026). **Bước 0–5 xong 10/10; PHẦN C xong 20/10/2026** (commit `eb99898` … `b3d0ede`): phân tích 54% cần xem
      (CNN đọc sai ~8% chữ số là nguyên nhân gần như duy nhất; người 3 và ảnh C3 yếu); thử tăng cường mạnh / kiểu "1 móc, 7 gạch" / ensemble 3 seed / EMNIST Digits:
      **không cấu hình nào khác baseline có ý nghĩa** (kiểm định dấu p ≥ 0,07; dao động giữa seed lớn hơn) → chọn g0, 1 seed 2026; **T3 ≈ 92%, T4 ≈ 46–54%: chưa đạt
      97% / 10%** (ghi nguyên trạng); lỗi im lặng mức trường = 0. `cv_engine/ocr.py` suy luận NumPy + JSON (`models/ocr_cnn.json` từ commit sạch `b75453e`,
      khớp PyTorch 4 376 chữ số, 14 ms/phiếu); nối backend + giao diện F3/F4 (hai kênh cạnh nhau); kiểm đầu-cuối 56 ảnh dev: 0 sai im lặng, điểm chính thức khớp 56/56;
      pytest 220 đạt. **Đề xuất luật mềm (chưa áp dụng, chờ bạn quyết)**: T4 54% → 27% (τ 0,1) đổi lấy ~5× rủi ro nhận nhầm khi tô sai bubble (mô phỏng 0,67% → 3,3%).
      **ĐANG CHỜ**: (1) bạn xem giao diện F3/F4 trên trình duyệt (kỳ thi [THU] exam_id 509); (2) quyết định luật mềm; (3) gõ **"chạy val"** để chạy đánh giá val
      0029–0034 (đã **đăng ký trước** ở `docs/ke_hoach_tuan6.md` mục 11, mã `b3d0ede`, SHA mô hình `6d87205c…`; `python tools/eval_ocr.py run --tap val --xac-nhan-val --xem`).
      Còn lại: test cuối 0035–0040 (một lần, đăng ký trước, xem mù), đo theo mức mờ `_gia_v4` + chỉnh `MO_MIN`, nợ kỹ thuật Phần C (`ke_hoach_tuan6.md`).
- [x] **Backend demo XONG (07/10/2026)** cho báo cáo 13/10 (`docs/ke_hoach_demo.md`, commit B0–B5): config `.env`, migration 001, dịch vụ chấm,
      API FastAPI (12 đường dẫn), luồng review mỏng, dữ liệu DEMO. **Kiểm đầu-cuối 56 ảnh train: 0 câu chấm sai mà không gắn cần xem (1 672 câu
      chắc chắn); điểm chính thức sau giáo viên khớp điểm tính độc lập 56/56; ảnh giả 44 từ chối đúng mã, 27 nhận đúng, 0 lỗi im lặng.** Nợ kỹ
      thuật: `docs/ke_hoach_demo.md` mục NỢ KỸ THUẬT (auth, layout từ DB, hàng đợi nền, sửa đáp án + chấm lại, import SV, …).
- [ ] Backend (phần còn lại), frontend, luồng review đầy đủ cho giáo viên.
      **Việc Tuần 7 (07/10/2026): `system_settings.min_blur_score` = 100 trong DB là thang Laplacian thô cũ** (của
      `check_photos.py` bản đầu) ≠ `blur_score` của `preprocess()` (`phan_tu_huong`, ngưỡng `MO_MIN` 0,012) – đổi sang thang
      `mo_huong` khi làm backend (backend dùng `kq.ok` / `kq.ly_do == 'anh_mo'`). Không sửa DB trước khi hỏi người dùng.
- [ ] **GIAI ĐOẠN CẢI TIẾN (từ 27/10/2026)** – kế hoạch `docs/ke_hoach_cai_tien_27-10.md` (7 yêu cầu: tên môn/lớp, chụp–chấm liền, OCR thay CNN, ma trận ô tô, đủ 40 câu,
      rà 0–255, đăng nhập + phân quyền). **Xong mục 4/6 (27/10)**: `tests/test_omr_ma_tran_o_to.py` (ma trận ô tô 0–255, 22 test) + luật `vet_nho` (lỗ hổng chấm nhỏ đậm → trống không cờ);
      train: 0 thay đổi, lỗi nặng 0, điểm 56/56. **28/10: thang `S_anh` đo xong, KHÔNG có X thoả → chưa sửa (6.4); test chập chờn = lỗi môi trường của test, đã sửa (6.5); MÃ ĐÓNG BĂNG cho test đợt 2 (tag `ma-dot2-dong-bang`, `docs/dong_bang_ma_dot2.json`; 6 file đợt 2 ở `answer_sheet/dot2/`) – chỉ đổi docs/ + CLAUDE.md cho tới khi chạy đợt 2.** **`omr.py` đã đổi sau commit đăng ký test cuối `551b356`** → kết quả test cuối 21/10 là của bản cũ; kiểm lại phải đăng ký mới (người dùng quyết).
      Nợ: `vet_nho` cho bubble; thang `S_anh` phụ thuộc cả tờ (`ke_hoach_tuan5.md` mục 15).
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
- Mật khẩu DB `smartexam123`: backend và `tools/db_check.py` đã đọc từ `.env` (không còn trong code Python); **vẫn ghi cứng** trong
  `00_create_database.sql`, `run_all.bat/.sh`, `HUONG_DAN.md` (script tạo CSDL cần nó) – chấp nhận được khi làm local, cần lưu ý nếu công khai repo.
- Không gửi ảnh qua Zalo/Messenger (bị nén) – chỉ chép bằng cáp hoặc Google Drive.
- (Lịch sử, ĐÃ XỬ LÝ Tuần 4 Bước 3–6) `find_markers()`/`align()` cũ trong `check_layout.py` chọn nhầm marker mà không báo
  lỗi (dev: 19/78 lỗi im lặng – `data/_eval/align_cu/truth_dev.csv`; 4 nguyên nhân + cách sửa: `docs/ke_hoach_tuan4.md`).
  Mọi công cụ nay dùng `preprocess()`; `align()` chỉ còn để eval tái tạo số liệu "trước". `marker_centers()`
  (`verify-ids`, `measure`) vẫn có thể bắt nhầm marker ở ảnh C2 tối – chỉ dùng cho đọc mã phiếu / đo phối cảnh.
- **Tập test đã bị mở MỘT lần trước khi có quy tắc dev/test** (ghi trung thực cho báo cáo Bước 7): audit 03/10/2026 (bằng
  `align()`) đã mở ảnh + nhãn cả 40 phiếu, nhãn mã đề bubble của 0035 được sửa theo ảnh + giấy thật. **Sửa nhãn cho khớp
  giấy thật ≠ rò rỉ tham số**: không tham số/ngưỡng nào của preprocessing chọn theo ảnh test; **`preprocess()` chưa từng
  chạy trên 0035–0040** (kiểm 07/10: `data/_eval/` không có kết quả/ảnh/CSV nào của 0035–0040). Từ Bước 6 mọi công cụ chặn
  tập test bằng `cv_engine/tap_du_lieu.py` (`--xac-nhan-test`).
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
- Không bao giờ ghi vào `data/raw*` (kể cả thư mục con). Ảnh xử lý ghi ra thư mục khác (`data/_aligned/`, `data/_eval/`, …).
- Tập val 0029–0034 chỉ chạy khi người dùng gõ "chạy val" (đã đăng ký trước, `docs/ke_hoach_tuan6.md` mục 11); `tools/eval_ocr.py` khoá bằng `--xac-nhan-val`.
- Không đọc ảnh / nhãn của tập test 0035–0040 khi chưa tới đánh giá cuối: ranh giới và `chan_test()` ở
  `cv_engine/tap_du_lieu.py`; công cụ mới phải dùng lại, không tự định nghĩa ranh giới.
- Tên file: ảnh phiếu `NNNN_Ck.jpg` (NNNN = mã phiếu, k = 1–4), trang chữ số `DNNN.jpg`.
- Không đụng vào `ground_truth.csv` nếu người dùng chưa xác nhận thay đổi.
- Không bao giờ chạy `run_all.bat`/`run_all.sh` hoặc bất kỳ lệnh ghi/xoá dữ liệu PostgreSQL
  (DROP, DELETE, TRUNCATE, UPDATE, ALTER) khi chưa hỏi người dùng. Sau khi reset DB phải chạy lại
  `answer_sheet/output/update_template.sql`.
- Dùng `pathlib`, đọc/ghi UTF-8 (Windows). Thông báo in ra màn hình và comment bằng **tiếng Việt**.
- Nhãn lớp: `blank` / `filled` / `faint` (cấp ô); `blank` / đáp án / `multiple` (cấp câu).
- Mỗi con số đưa vào báo cáo phải tái tạo được bằng script.
- Khi `HUONG_DAN.md` (viết trước) khác CLAUDE.md thì **theo CLAUDE.md**.
