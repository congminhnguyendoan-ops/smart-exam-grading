# Cây thư mục dự án (Bảng 3.13)

Sinh bằng `python tools/xuat_cay_va_moc.py` từ `git ls-files` – nhánh `cai-tien-b`, HEAD lúc sinh `af4976c`.
Gốc repo: `smart_exam_db_1/`. Tệp **trong git**: 257 tệp (254 đã commit + 3 tệp mới chưa commit lúc sinh, không bị `.gitignore`). Không có `.venv/`, `.git/`, `data/`, `__pycache__/` (đều trong `.gitignore`).
Số trong ngoặc = số tệp bên trong thư mục (kể cả thư mục con).

```
smart_exam_db_1/
├── smart_exam_db/  (255 tệp)
│   ├── answer_sheet/  (31 tệp)
│   │   ├── demo_bv/  (5 tệp)
│   │   │   ├── demo_bv_dap_an.csv
│   │   │   ├── demo_bv_ke_hoach.xlsx
│   │   │   ├── demo_bv_kich_ban.csv
│   │   │   ├── phieu_demo_in.pdf
│   │   │   └── phieu_giao_viec_demo.pdf
│   │   ├── dot2/  (6 tệp)
│   │   │   ├── cell_labels_dot2.csv
│   │   │   ├── ground_truth_dot2.csv
│   │   │   ├── phan_cong_va_dap_an_dot2.xlsx
│   │   │   ├── phieu_danh_so_0101_0110.pdf
│   │   │   ├── phieu_giao_viec_0101_0110.pdf
│   │   │   └── phieu_mau_trong.pdf
│   │   ├── fonts/  (2 tệp)
│   │   │   ├── DejaVuSans-Bold.ttf
│   │   │   └── DejaVuSans.ttf
│   │   ├── output/  (11 tệp)
│   │   │   ├── cell_labels.csv
│   │   │   ├── digit_sheet_layout.json
│   │   │   ├── ground_truth.csv
│   │   │   ├── layout.json
│   │   │   ├── phieu_danh_so.pdf
│   │   │   ├── phieu_giao_viec.pdf
│   │   │   ├── phieu_trang.pdf
│   │   │   ├── phieu_trang_300dpi.json
│   │   │   ├── phieu_trang_300dpi.png
│   │   │   ├── trang_chu_so.pdf
│   │   │   └── update_template.sql
│   │   ├── check_layout.py
│   │   ├── check_photos.py
│   │   ├── generate_sheets.py
│   │   ├── HUONG_DAN_THU_DU_LIEU.md
│   │   ├── make_dataset_plan.py
│   │   ├── requirements.txt
│   │   └── sheet_layout.py
│   ├── backend/  (26 tệp)
│   │   ├── migrations/  (5 tệp)
│   │   │   ├── 001_backend_bo_sung.sql
│   │   │   ├── 002_lop_giao_vien.sql
│   │   │   ├── 003_xoa_anh_tam.sql
│   │   │   ├── 004_lop_trang_thai.sql
│   │   │   └── 005_nhat_ky_quan_tri.sql
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── bang_diem.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── demo.py
│   │   ├── don_anh.py
│   │   ├── grading.py
│   │   ├── loi_khuyen.py
│   │   ├── main.py
│   │   ├── mang.py
│   │   ├── migrate.py
│   │   ├── nguoi_dung.py
│   │   ├── nhat_ky.py
│   │   ├── phan_quyen.py
│   │   ├── phieu_trung.py
│   │   ├── quan_tri.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── tai_khoan.py
│   │   └── trang_bia.py
│   ├── cv_engine/  (5 tệp)
│   │   ├── __init__.py
│   │   ├── ocr.py
│   │   ├── omr.py
│   │   ├── preprocessing.py
│   │   └── tap_du_lieu.py
│   ├── database/  (9 tệp)
│   │   ├── tests/  (1 tệp)
│   │   │   └── test_multiple_marks.sql
│   │   ├── 00_create_database.sql
│   │   ├── 01_schema.sql
│   │   ├── 02_functions_triggers.sql
│   │   ├── 03_views.sql
│   │   ├── 04_seed.sql
│   │   ├── 05_demo_workflow.sql
│   │   ├── run_all.bat
│   │   └── run_all.sh
│   ├── docs/  (59 tệp)
│   │   ├── diagrams/  (14 tệp)
│   │   │   ├── 01_usecase.mmd
│   │   │   ├── 01_usecase.png
│   │   │   ├── 02_architecture.mmd
│   │   │   ├── 02_architecture.png
│   │   │   ├── 03_dfd0.mmd
│   │   │   ├── 03_dfd0.png
│   │   │   ├── 04_dfd1.mmd
│   │   │   ├── 04_dfd1.png
│   │   │   ├── 05_seq_grading.mmd
│   │   │   ├── 05_seq_grading.png
│   │   │   ├── 06_seq_review.mmd
│   │   │   ├── 06_seq_review.png
│   │   │   ├── 07_seq_import.mmd
│   │   │   └── 07_seq_import.png
│   │   ├── wireframes/  (7 tệp)
│   │   │   ├── 01_login.png
│   │   │   ├── 02_dashboard.png
│   │   │   ├── 03_exam.png
│   │   │   ├── 04_upload.png
│   │   │   ├── 05_review.png
│   │   │   ├── 06_stats.png
│   │   │   └── gen.py
│   │   ├── bao_cao_sua_de_xuat.md
│   │   ├── cay_thu_muc.md
│   │   ├── chay_server_va_tai_khoan.md
│   │   ├── chuyen_doi_ket_luan_dot2.txt
│   │   ├── dang_ky_h3_mo_phong.json
│   │   ├── dang_ky_h3_mo_phong.md
│   │   ├── dang_ky_test_dot2.json
│   │   ├── dang_ky_test_he_thong.json
│   │   ├── dong_bang_ma_dot2.json
│   │   ├── ERD.mermaid
│   │   ├── ERD.png
│   │   ├── huong_dan_cai_dat.md
│   │   ├── huong_dan_quan_tri.md
│   │   ├── ke_hoach_cai_tien_27-10.md
│   │   ├── ke_hoach_demo.md
│   │   ├── ke_hoach_test_cuoi.md
│   │   ├── ke_hoach_test_dot2.md
│   │   ├── ke_hoach_tuan4.md
│   │   ├── ke_hoach_tuan5.md
│   │   ├── ke_hoach_tuan6.md
│   │   ├── ket_luan_mat_dot2.csv
│   │   ├── ket_luan_mat_dot2_goc.txt
│   │   ├── ket_qua_dot2.json
│   │   ├── ket_qua_dot2.md
│   │   ├── ket_qua_h3_mo_phong.json
│   │   ├── ket_qua_h3_mo_phong.md
│   │   ├── khao_sat_camera_truc_tiep.md
│   │   ├── kich_ban_demo.md
│   │   ├── kich_ban_demo_bao_ve.md
│   │   ├── moc_commit.md
│   │   ├── nhat_ky_sua_bao_cao.md
│   │   ├── phan_tich_sau_chay_dot2.md
│   │   ├── sai_lech_dot2.csv
│   │   ├── sai_lech_dot2.md
│   │   ├── sha_anh_dot2.txt
│   │   ├── so_sanh_ocr_cnn.md
│   │   ├── thiet_ke_chup_dien_thoai.md
│   │   └── thiet_ke_dang_nhap.md
│   ├── frontend/  (13 tệp)
│   │   ├── app.js
│   │   ├── index.html
│   │   ├── ky_thi_dong.js
│   │   ├── loi_tai.js
│   │   ├── ly_do_cot.js
│   │   ├── m.css
│   │   ├── m.html
│   │   ├── m.js
│   │   ├── m_hang_doi.js
│   │   ├── m_kythi.js
│   │   ├── quan_tri.js
│   │   ├── style.css
│   │   └── ten_tep.js
│   ├── models/  (3 tệp)
│   │   ├── ocr_cnn.json
│   │   ├── omr_m0.json
│   │   └── omr_m1.json
│   ├── tests/  (52 tệp)
│   │   ├── js/  (6 tệp)
│   │   │   ├── hang_doi.test.js
│   │   │   ├── ky_thi_dong.test.js
│   │   │   ├── loi_tai.test.js
│   │   │   ├── ly_do_cot.test.js
│   │   │   ├── m_kythi.test.js
│   │   │   └── ten_tep.test.js
│   │   ├── conftest.py
│   │   ├── test_backend_api.py
│   │   ├── test_backend_dau_cuoi.py
│   │   ├── test_backend_grading.py
│   │   ├── test_backend_ly_do_omr.py
│   │   ├── test_backend_ocr.py
│   │   ├── test_bang_diem.py
│   │   ├── test_bo_demo.py
│   │   ├── test_buoc7_io.py
│   │   ├── test_chot_chan_cong_cu.py
│   │   ├── test_dang_nhap.py
│   │   ├── test_dat_lai_demo.py
│   │   ├── test_dien_thoai.py
│   │   ├── test_don_du_lieu_test.py
│   │   ├── test_eval_dot2.py
│   │   ├── test_eval_he_thong.py
│   │   ├── test_eval_ocr.py
│   │   ├── test_eval_omr.py
│   │   ├── test_frontend.py
│   │   ├── test_kiem_truoc_demo.py
│   │   ├── test_lenh_f.py
│   │   ├── test_load_image.py
│   │   ├── test_ly_do_chua_ghep.py
│   │   ├── test_mat_khau_csdl.py
│   │   ├── test_nhat_ky_quan_tri.py
│   │   ├── test_ocr_cat.py
│   │   ├── test_ocr_doi_chieu.py
│   │   ├── test_ocr_suy_luan.py
│   │   ├── test_omr_dac_trung.py
│   │   ├── test_omr_dinh_vi.py
│   │   ├── test_omr_luat.py
│   │   ├── test_omr_ma_tran_o_to.py
│   │   ├── test_omr_phan_b.py
│   │   ├── test_phieu_thieu_chi_tiet.py
│   │   ├── test_preprocess_dev.py
│   │   ├── test_quan_tri_ky_thi.py
│   │   ├── test_quan_tri_lop.py
│   │   ├── test_quan_tri_lop_ky_thi.py
│   │   ├── test_quan_tri_tai_khoan.py
│   │   ├── test_sao_luu_demo.py
│   │   ├── test_tap_du_lieu.py
│   │   ├── test_trang_bia.py
│   │   ├── test_trung_sbd.py
│   │   ├── test_trung_sbd_xu_ly.py
│   │   ├── test_tu_choi.py
│   │   └── test_xac_thuc_khong_csdl.py
│   ├── tools/  (55 tệp)
│   │   ├── chay_server_lan.py
│   │   ├── check_labels.py
│   │   ├── check_task_pdf.py
│   │   ├── dat_lai_demo.py
│   │   ├── db_check.py
│   │   ├── don_du_lieu_test.py
│   │   ├── eval_dot2.py
│   │   ├── eval_h3_mo_phong.py
│   │   ├── eval_he_thong.py
│   │   ├── eval_ocr.py
│   │   ├── eval_omr.py
│   │   ├── eval_preprocessing.py
│   │   ├── h3_mo_phong.py
│   │   ├── huan_luyen_ocr.py
│   │   ├── huan_luyen_omr.py
│   │   ├── kiem_anh_dot2.py
│   │   ├── kiem_backend_dau_cuoi.py
│   │   ├── kiem_bo_demo.py
│   │   ├── kiem_chuan_hoa.py
│   │   ├── kiem_dinh_vi.py
│   │   ├── kiem_load_image.py
│   │   ├── kiem_truoc_demo.py
│   │   ├── kiem_verify.py
│   │   ├── kiem_vi_tri_eval.py
│   │   ├── marker_that.py
│   │   ├── nap_bo_demo.py
│   │   ├── nap_demo.py
│   │   ├── nap_demo_khop.py
│   │   ├── nap_giao_vien_demo.py
│   │   ├── ocr_cai_tien.py
│   │   ├── ocr_do_luong.py
│   │   ├── ocr_du_lieu.py
│   │   ├── ocr_phan_tich.py
│   │   ├── omr_c2.py
│   │   ├── omr_cnn.py
│   │   ├── omr_du_lieu.py
│   │   ├── omr_long.py
│   │   ├── omr_s_anh.py
│   │   ├── omr_to_nhat.py
│   │   ├── omr_vet_nho.py
│   │   ├── prepare_photos.py
│   │   ├── sao_luu_demo.py
│   │   ├── so_sanh_ocr.py
│   │   ├── so_sanh_ocr_rapid.py
│   │   ├── tao_split.py
│   │   ├── tao_tham_chieu.py
│   │   ├── thu_bo_demo.py
│   │   ├── thu_dien_thoai.py
│   │   ├── thu_lenh_f.py
│   │   ├── thu_lenh_h.py
│   │   ├── thu_lenh_i.py
│   │   ├── thu_lenh_j.py
│   │   ├── thu_lenh_v.py
│   │   ├── xuat_cay_va_moc.py
│   │   └── xuat_ocr.py
│   ├── .env.example
│   └── HUONG_DAN.md
├── .gitignore
└── CLAUDE.md
```

## Chỉ có trên máy này (không trong git)
Bị `.gitignore` bỏ qua, ngoài `.venv/`, `data/`, `__pycache__/`; chỉ ghi tên và số tệp (không liệt kê nội dung – có thể chứa ảnh phiếu, cấu hình bí mật):

- `.idea/` – 6 tệp
- `smart_exam_db/.env` – 1 tệp
- `smart_exam_db/.pytest_cache/` – 5 tệp
- `smart_exam_db/answer_sheet/` – 11 tệp
- `smart_exam_db/storage/` – 202 tệp
