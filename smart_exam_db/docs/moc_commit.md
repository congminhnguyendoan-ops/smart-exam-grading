# Các mốc commit (Bảng 3.14)

Sinh bằng `python tools/xuat_cay_va_moc.py` từ `git log --all --date=short` – **mọi nhánh**: `cai-tien-b`, `chay-dot2`, `main`, `origin/main` (nhánh hiện tại `cai-tien-b`, HEAD lúc sinh `36c91d6`).
Tổng **156 commit**, từ 2026-09-30 đến 2026-10-30, trong **13 ngày có commit**; 154 commit nằm trong `cai-tien-b`, **2** commit chỉ có ở nhánh khác (đánh dấu † ở mục 3). **7 tag.**
Ngày = ngày tác giả (author date). Chỉ liệt kê đúng những gì git ghi lại.

## 1. Tóm tắt theo ngày

| Ngày | Số commit | Chỉ ở nhánh khác | Commit đầu | Commit cuối |
|---|---|---|---|---|
| 2026-09-30 | 2 | 0 | `399d48c` | `9bd64ac` |
| 2026-10-02 | 3 | 0 | `fc6cb2f` | `7fb1ad1` |
| 2026-10-03 | 13 | 0 | `218e1c2` | `fbbb9f7` |
| 2026-10-06 | 3 | 0 | `310dac8` | `7fb691c` |
| 2026-10-07 | 20 | 0 | `591c19b` | `3064af4` |
| 2026-10-09 | 4 | 0 | `1bd20a9` | `606a799` |
| 2026-10-10 | 6 | 0 | `752b82d` | `a83ebd3` |
| 2026-10-20 | 10 | 0 | `eb99898` | `57aa46d` |
| 2026-10-21 | 6 | 0 | `4902810` | `63a1af2` |
| 2026-10-27 | 36 | 0 | `069c31d` | `d6872c2` |
| 2026-10-28 | 14 | 0 | `a540bca` | `ddf6a85` |
| 2026-10-29 | 18 | 1 | `5ecd0ef` | `9c7f22f` |
| 2026-10-30 | 21 | 1 | `b61f106` | `36c91d6` |

## 2. Tag (7)

| Tag | Ngày | Commit | Trong `cai-tien-b` | Nhánh chứa tag | Tiêu đề commit |
|---|---|---|---|---|---|
| `ma-dot2-dong-bang` | 2026-10-27 | `b53a343` | có | `cai-tien-b`, `chay-dot2`, `main` | data: chep nguyen ven 6 file dot 2 (phieu 0101-0110) vao answer_sheet/dot2/ |
| `ma-dot2-dong-bang-v2` | 2026-10-27 | `ea4ddf4` | có | `cai-tien-b`, `chay-dot2`, `main` | docs: ket qua to_nhat (4/4 tieu chi), DONG BANG v2 (SHA, lich_su v1) |
| `ma-dot2-dong-bang-v3` | 2026-10-27 | `2543647` | có | `cai-tien-b`, `chay-dot2`, `main` | docs: loi backend vet_nho/to_nhat (muc 7c), DONG BANG v3 (SHA, lich_su v1+v2) |
| `dang-ky-dot2` | 2026-10-27 | `d3d0426` | có | `cai-tien-b`, `chay-dot2`, `main` | fix(dang ky dot 2): SHA ghi chu thuong (cung dinh dang sha_file), tai lieu .md chi tham khao; test dang ky that khop cay lam viec |
| `dang-ky-dot2-bo-sung` | 2026-10-29 | `85d00e1` | không | `chay-dot2` | docs(N1): đăng ký bổ sung đợt 2 – SHA nhãn đã sửa 0103 (sbd_bubble cột 4 = 3, câu 3 = B, câu 5 = C) theo giấy thật, mục 4 kế hoạch; chỉ đổi docs/, trước khi máy đọc ảnh đợt 2 |
| `sau-dot2-hop-nhat-30-10` | 2026-10-30 | `1d3433f` | không | `main` | Gộp cai-tien-b: cải tiến sau góp ý, đợt 2, quản trị web, lớp học |
| `dang-ky-h3-mo-phong` | 2026-10-30 | `1dc17ca` | có | `cai-tien-b` | docs+tools(T): ĐĂNG KÝ TRƯỚC phép thử mô phỏng H3 "ô tô trống, chữ viết tay có" – chưa chạy trên ảnh đợt 2 |

## 3. Toàn bộ commit theo ngày (cũ → mới; † = không nằm trong `cai-tien-b`)

### 2026-09-30 (2 commit)

- `399d48c` Khởi tạo repo: phiếu trả lời, database PostgreSQL, tài liệu
- `9bd64ac` docs: cập nhật CLAUDE.md sau khi rà soát dự án

### 2026-10-02 (3 commit)

- `fc6cb2f` fix(db): đưa phiếu tô nhiều ô vào review (multiple_marks)
- `30bea4b` feat(tools): chuẩn bị ảnh dữ liệu HEIC->JPG + chẩn đoán lỗi align()
- `7fb1ad1` feat(tools): thêm lệnh apply/replace cho prepare_photos, thay 3 ảnh lỗi marker

### 2026-10-03 (13 commit)

- `218e1c2` feat(tools): thêm lệnh measure, thay 0014_C3 – hoàn tất bộ ảnh
- `d9c9794` fix(data): sửa 7 nhãn theo ghi chú người tô + công cụ check_labels
- `1c6ced9` fix(data): quét nhãn 40 phiếu, sửa 3 câu + thêm cột bubble SBD/mã đề
- `bebf086` docs(tuan4): bước 0 – thư mục cv_engine, kế hoạch preprocessing 8 bước, quy tắc dev/test
- `ba960e7` feat(tools): eval_preprocessing.py – lệnh run chấm phương pháp nắn ảnh (Tuần 4 bước 1)
- `b2c388e` docs(tuan4): ca tự kiểm chứng 5,8 mm, chiều phiếu theo nội dung, mục tiêu độ chính xác
- `d388065` feat(tools): eval_preprocessing – dưới pixel, tu-kiem trên trang mẫu, tam-marker
- `7b9f6b6` feat(tools): eval_preprocessing – tu-kiem trên ảnh thật, lệnh dung-sai
- `b2719ec` feat(tools): eval_preprocessing – luật kết luận theo nguong.json, finalize/report
- `1c03c86` docs(tuan4): xong Bước 1 (bảng "trước" vào CLAUDE.md), viết lại Bước 2–7
- `de2ee59` feat(cv_engine): Tuần 4 bước 2 – load_image (Unicode, EXIF, HEIC), kiểm tra hồi quy v2_load
- `8e6052a` fix(eval): finalize bắt buộc kết luận bằng mắt cho mọi ảnh máy kết luận 'sai'/'xem'
- `fbbb9f7` feat(tools): marker_that – marker thật 78 ảnh dev + số "trước" khâu tìm (Tuần 4 bước 3a)

### 2026-10-06 (3 commit)

- `310dac8` feat(cv_engine): Tuần 4 bước 3b – lọc ứng viên marker (tu_giac, muc_vien, nền cục bộ), 78/78 ảnh dev đủ 4 marker, 4,3 ứng viên/ảnh
- `5898809` feat(cv_engine): Tuần 4 bước 3c – chọn bộ 4 marker theo hình học, v3_hinh_hoc 78/78 ảnh dev đúng, 0 lỗi im lặng
- `7fb691c` feat(cv_engine): Tuần 4 bước 4 – verify() chiều 0°/180° bằng nội dung, từ chối có lý do; v4_verify 78/78 dev đúng, 0 lỗi im lặng

### 2026-10-07 (20 commit)

- `591c19b` feat(cv_engine): Tuần 4 bước 5 – normalize() chia nền (cửa sổ ~15 mm), v5_chuan_hoa: anh_nan giống v4 từng byte, bóng C1–C4 giảm, 0 hàng faint lật
- `fc4946b` feat(cv_engine): Tuần 4 bước 6A – preprocess_anh, MA_LY_DO, tap_du_lieu (chốt dev/test), pytest 35 test, v6_api giống v5 từng byte
- `8cf334c` refactor(tools): Tuần 4 bước 6B – check_photos/prepare_photos/check_labels/check_layout dùng preprocess(), chốt chặn tập test mọi công cụ, đầu ra ra khỏi data/raw*
- `0176ad8` docs(tuan4): bước 6 xong – audit 34/34 phiếu dev, API preprocess trong CLAUDE.md
- `d9e56d5` feat(eval): Tuần 4 bước 7 – chuẩn bị I/O tập test (xem mù, chạy một lần, report-cuoi), chưa chạy test
- `d4aa953` docs(tuan4): bước 7 – đăng ký trước đánh giá cuối trên tập test (chưa chạy test)
- `2774def` docs(tuan4): bước 7 – kết quả đánh giá cuối trên test: v6_api 12/12 đúng, 0 lỗi im lặng (ĐẠT)
- `aa2748b` docs(tuan4): audit nhãn tập test (nhóm A 0), 8 mục rõ/mờ chờ so giấy – TUẦN 4 XONG (bước 0–7)
- `09157e9` chore(tuan4): xác nhận 8 nhãn rõ/mờ tập test bằng giấy + sửa hiển thị quy tắc số 3 (không đổi số liệu Bước 7)
- `3a3b44f` docs(tuan5): kế hoạch Tuần 5 OMR – đã duyệt, chia Phần A/B, nợ kỹ thuật
- `e0bc951` feat(omr): Tuần 5 A1 – định vị 2 tầng + PNG mẫu + split.csv
- `d0c9574` feat(omr): Tuần 5 A2 – đặc trưng ô + M0/M1 7-fold, chọn anh_nan
- `8d2db8f` feat(omr): Tuần 5 A3 – luật ô→câu/cột, API doc_phieu, mô hình JSON
- `3bcf190` feat(eval): Tuần 5 A4 – eval_omr.py độc lập, bảng M0 vs M1 – PHẦN A XONG
- `ec757a0` chore(omr): B0 – xuất lại mô hình từ commit sạch, bỏ cờ git_chua_commit
- `a86610e` feat(backend): B1 – cấu hình .env, kết nối CSDL, migration bổ sung
- `b17e8df` feat(backend): B2 – lớp dịch vụ chấm phiếu (ảnh -> OMR -> chấm -> CSDL) + dữ liệu mẫu DEMO
- `50f1f38` feat(backend): B3 – API FastAPI (kỳ thi, tải ảnh 1/nhiều, kết quả, câu cần xem, review)
- `dd85f7f` test(backend): B4 – kiểm đầu-cuối độc lập trên ảnh dev 0001-0028, ảnh giả, đường tự chốt
- `3064af4` docs: B5 – CLAUDE.md mục 4d (backend: chạy, API, nạp demo), tiến độ; NỢ KỸ THUẬT demo

### 2026-10-09 (4 commit)

- `1bd20a9` feat(frontend): F1–F4 giao diện HTML+JS thuần, phục vụ tại /app; /meta/reject-reasons, thêm trường danh sách phiếu; test
- `3952edc` docs: frontend – các bước demo, nợ kỹ thuật 17–21, CLAUDE.md; favicon
- `8892876` feat(backend,frontend): bảng điểm + xuất Excel (F5)
- `606a799` feat(demo): [DEMO-2] đáp án lấy từ bài làm phiếu 0005 (tools/nap_demo_khop.py)

### 2026-10-10 (6 commit)

- `752b82d` docs: kế hoạch Tuần 6 (CNN chữ số) – đã duyệt, mốc báo cáo 17/10
- `a97064d` docs: kế hoạch Tuần 6 – bổ sung Q1b (người viết phiếu; hạn chế test chỉ có người 5)
- `cb1b926` chore(ocr): Bước 1 – cài torch CPU (chỉ huấn luyện), tải MNIST + SHA; ghi vào kế hoạch
- `52025cf` feat(ocr): Bước 2–3 – cắt ô chữ số (dò khung ô, bỏ viền, chuẩn hoá MNIST), split theo người viết
- `82429ea` feat(ocr): Bước 4–5 – M0 (HOG+logistic), M1 (CNN), M2 sơ bộ (CV theo người viết), đối chiếu bubble, đo lường
- `a83ebd3` docs: Tuần 6 – kết quả Bước 1–5, hạn chế, nợ kỹ thuật; CLAUDE.md cập nhật

### 2026-10-20 (10 commit)

- `eb99898` feat(ocr): Phần C Bước 1–2 – phân tích 53,6% cần xem + công cụ thí nghiệm cải thiện CNN
- `b75453e` feat(ocr): Phần C Bước 3 – suy luận CNN chữ số bằng NumPy + JSON, doc_chu_so, đối chiếu định danh; công cụ xuất mô hình
- `00e92e7` feat(ocr): Phần C Bước 3 – models/ocr_cnn.json (xuất từ commit sạch b75453e), test NumPy ↔ PyTorch, eval_ocr độc lập
- `70e0947` feat(backend,frontend): Phần C Bước 4 – SBD / mã đề đọc bằng hai kênh (bubble + CNN chữ viết tay), luật Q3, giao diện F3/F4
- `b3d0ede` feat(ocr): eval_ocr --xem (lưới ảnh ô viết tay để xem bằng mắt); đổi tên trường siêu dữ liệu
- `9255f2a` docs: Tuần 6 Phần C – kết quả Bước 1–4, đăng ký trước val 0029–0034 (chưa chạy), nợ kỹ thuật; CLAUDE.md cập nhật
- `97b2269` docs: kết quả val 0029–0034 (chạy một lần theo đăng ký trước): lỗi im lặng 0, T3 98,1%, T4 16,7%
- `555e410` feat(omr): Tuần 5 Phần B1 – nested CV (số không lạc quan), kiểm phép đo vị trí của eval, HTML "cần xem cần thiết"
- `417311a` feat(omr): Tuần 5 Phần B2 – cần xem thừa C2: ro_min chọn theo từng điều kiện (0,6 -> 0,5), so 5 ứng viên bằng nested CV
- `57aa46d` feat(omr): Tuần 5 Phần B3 – so sánh M1 logistic với M2 CNN nhỏ trên ảnh ô (nested 7 fold): giữ M1

### 2026-10-21 (6 commit)

- `4902810` feat(omr): xuất lại models/omr_m0.json, omr_m1.json từ commit sạch 57aa46d (ro_min 0,6 -> 0,5, B2)
- `4ee59b9` docs: Tuan 5 Phan B1-B3 ket qua + dang ky truoc val OMR 0029-0034 (ma 4902810, chua chay)
- `9c8529c` docs: Tuan 5 Phan B – ket qua val OMR (loi nang 0; 0033:4 doc mo can xem), ke hoach test cuoi he thong (chua chay); CLAUDE.md
- `551b356` feat(eval): tools/eval_he_thong.py – danh gia ca he thong (nan anh -> OMR -> CNN -> cham diem -> giao vien), doc lap, chot chan test
- `5e7e4b2` docs: DANG KY TRUOC danh gia test he thong 0035-0040 (ma 551b356, SHA mo hinh/nguong; chua chay)
- `63a1af2` docs: KET QUA test he thong 0035-0040 (chay mot lan): H2-H5 dat, H1 cho mat mu; T3 92,6%, T4 58,3%

### 2026-10-27 (36 commit)

- `069c31d` test(omr): ma tran o to 0-255 (16 nhom dat + 1 xfail lo hong cham nho dam), ke hoach cai tien 27/10
- `aef05db` tools: omr_vet_nho.py do phan phoi vet toi nho (56 anh train); chot luat vet_nho N=90 px + tieu chi truoc khi sua code
- `673f8a3` feat(omr): luat phu vet_nho (o khong chon co khoi toi dac >= 90 px -> cau can xem), bo xfail cham nho, them 6 test
- `184a527` docs: ket qua luat vet_nho (4/4 tieu chi), no ky thuat, CLAUDE.md 4c/7; ghi omr.py doi sau 551b356
- `5d99769` fix(test): test_val_bi_khoa chay tien trinh con voi PYTHONUTF8=1 (cp1252 -> giai ma loi -> stderr None -> TypeError)
- `cbfb948` tools+docs: omr_s_anh.py do thang S_anh; muc 6.4 khong co X thoa (2)+(3) -> giu no ky thuat; muc 6.5 nguyen nhan test chap chon
- `b53a343` data: chep nguyen ven 6 file dot 2 (phieu 0101-0110) vao answer_sheet/dot2/
- `435be55` docs: DONG BANG MA cho test dot 2 (tag ma-dot2-dong-bang, SHA + tham so), ghi gioi han vet_nho
- `d966047` docs: CLAUDE.md ghi trang thai dong bang ma dot 2
- `21a9929` tools+docs: omr_to_nhat.py do thong ke muc to T; chot luat to_nhat (Xs=0,44) + tieu chi truoc khi sua code (muc 6.6)
- `5e04d01` feat(omr): luat muc to to_nhat (T < 0,44, n >= 10 -> moi cau da chon can xem; KetQuaOMR.to_nhat/do_toi_to), +10 test
- `ea4ddf4` docs: ket qua to_nhat (4/4 tieu chi), DONG BANG v2 (SHA, lich_su v1)
- `1eb3444` fix(backend): vet_nho / to_nhat vao LY_DO_OMR_CAU (cau can xem bi bo qua -> RuntimeError chot an toan); test bat moi ma ly do OMR moi
- `8a2be05` tools: eval_dot2.py cham dot 2 (nhan vet, khoa mot lan, dang ky, sua nhan theo giay, anh gia hoa --thu-gia) + 9 test
- `2543647` docs: loi backend vet_nho/to_nhat (muc 7c), DONG BANG v3 (SHA, lich_su v1+v2)
- `4a2ce35` docs: DANG KY TRUOC test dot 2 (tieu chi H1-H5, du doan, gioi han, SHA ma khoa v3 + eval_dot2 + nhan)
- `d3d0426` fix(dang ky dot 2): SHA ghi chu thuong (cung dinh dang sha_file), tai lieu .md chi tham khao; test dang ky that khop cay lam viec
- `742a694` docs: thiet ke ten mon/lop + dang nhap giao vien + phan quyen theo lop (cai-tien-b)
- `150d48b` feat(auth): dang nhap (scrypt + token HMAC + cookie HttpOnly), phan quyen theo lop (chong IDOR), mon/lop cua ky thi, /me, /me/classes, /classes/{id}/students, migration 002 (CHUA AP), giao dien dang nhap/ho so/lop, backend.tai_khoan, nap_giao_vien_demo; 26 test khong can CSDL
- `9dcb244` test+fix(auth): 44 test can CSDL (phan quyen/IDOR/mon-lop/ho so/lop), bang endpoint x quyen + tu ra soat, db.ket_noi khong doi AUTH_SECRET, thong bao lop thong nhat, test dang ky skip co thong bao tren nhanh
- `e3f8bd9` docs+test: su co 002, quy trinh chay dot 2 an toan, van hanh tai khoan; csdl_san_sang khong tu ap migration; CLAUDE.md 4f, HUONG_DAN, ke hoach muc 8
- `5a46d89` data: chep nguyen ven 5 file bo demo bao ve vao answer_sheet/demo_bv/
- `7d8bfed` tools: kiem_bo_demo.py (kiem doc lap kich ban BV01-BV10: khop 10/10) + nap_bo_demo.py (xem truoc mac dinh, chi INSERT, idempotent) + 11 test
- `5f07ff7` tools: thu_bo_demo.py - cham dau-cuoi 10 phieu demo BV01-BV10 (anh gia hoa, token gv_an/gv_binh, AUTH_MODE=on, ROLLBACK): khop 10/10
- `e7c8373` fix(frontend): ten ky thi khong con bi cat o thanh ben
- `f73b6e3` docs: kich ban demo bao ve [DEMO-BV]; ke hoach muc 5 (nap CSDL, quyen 24/24, dau-cuoi 10/10); CLAUDE.md 4f + cay thu muc
- `b9ae088` docs: thiet ke chup bang dien thoai -> cham ngay (/m, QR, IP LAN, tuong lua Private, bao mat, chinh sach anh tam)
- `687d13c` fix(an toan CSDL): cong cu chi KIEM migration, khong tu ap; migration tuy chon (TUY_CHON) khong chan test
- `763c6ff` feat(dien thoai): trang /m chup bang camera goc -> cham ngay; Ket noi dien thoai (QR); tu lam moi; anh tam (migration 003 CHUA AP)
- `3cf69d3` tools: nap_bo_demo.py --ban-tap (2 ky thi [DEMO-BV-TAP] giong E1/E2, chi INSERT, idempotent; CHUA GHI) + test; thu_dien_thoai --ghi-that doi dung GV theo ky thi
- `4264c3d` fix(tuong lua): dung hai lenh nguoi dung chot (Public,Private + RemoteAddress LocalSubnet; Remove sau demo), bo luat chi-Private va goi y doi ho so mang
- `71ff051` docs: chup dien thoai -> cham ngay (ket qua: 003 da ap, ky thi TAP 1632/1633, p50/p95, tuong lua LocalSubnet); ke hoach muc 2; kich ban demo 5b; HUONG_DAN; CLAUDE.md 4f; .env.example
- `2d1ad20` docs+tools: huong dan chay server va tai khoan (lenh nguyen van, duong dan da kiem); thu_bo_demo xuat (10 anh gia hoa + README); ghi viec xoa 21 phieu thu cua ky thi TAP
- `32275dc` feat(dien thoai): chup LIEN TUC – hang doi gui nen (toi da 2 song song), khong cho ket qua to truoc
- `9cf5900` docs: chup lien tuc (thiet ke muc 9, so do, kich ban demo, ke hoach muc 2, CLAUDE.md); khao sat camera truc tiep getUserMedia (HTTPS/mkcert, tunnel, co Chrome) – KHONG lam truoc bao ve
- `d6872c2` tools+docs: so sanh CNN chu so voi M0 (OCR cho duyet cai dat) – chi do dev; test hanh vi trung SBD (ROLLBACK)

### 2026-10-28 (14 commit)

- `a540bca` tools+docs: lenh D – do OCR A' (PP-OCRv6 nhan dang + onnxruntime, venv rieng) tren cung tap chu so dev voi M0 / CNN
- `6705b48` docs: lenh E – doan sua bao cao do an (22/90, muc 3.5 cai tien, ket luan, chu thich schema_migrations) + nhat ky sua; bao cao goc khong dung
- `a00bd28` docs: lenh E2 – hoan thien de xuat sua bao cao (380/232, so bang 22+8 view tu SELECT, dien thoai that 27/10, ngoi nhom + 12 o dien sau, bo "16 nhom"); sua tai lieu docs/ con ghi chua thu dien thoai that
- `3e7c77c` docs(F1): CLAUDE.md – da thu dien thoai that 27/10 (iPhone/Safari, chua Android), ket qua lenh D (OCR dung hon CNN nhung nang hon, giu CNN cho bao ve); khong sua "lam ca nhan"
- `56e56c3` feat(F2): phieu trung SBD – canh bao o Bang diem/Excel, nut "Bo phieu chup lai" / "Dung phieu nay thay phieu cu" (1 giao dich, score_audit_logs, 409 khi dong thoi), +8 test
- `47c8def` fix(F3): o chon ky thi lam moi so phieu sau moi lan tai / duyet / tham do (khong con "(0 phieu)" khi da co phieu)
- `63accbe` feat(F4): /m khoi phuc danh sach to sau khi tai lai trang (sessionStorage sieu du lieu, hoi lai GET /sheets/{id}; to chua gui xong = "mat", phai chup lai); +2 test Node, +3 test pytest, tools/thu_lenh_f.py (Playwright, chi ROLLBACK)
- `3a78fdd` docs(F): CLAUDE.md – F3/F4, pytest 391 + 1 skip
- `d1c45b2` feat(G1): tools/don_du_lieu_test.py – don phiếu test thua o ky thi 1632/1633 (xem truoc mac dinh chi doc; --thuc-hien: sao luu CSV+anh, go "XOA", 1 giao dich, lech so dong thi hoan tac, xoa tep anh); +8 test (ROLLBACK)
- `de85c04` feat(G2): rut gon ten tep anh khi hien thi (>24 ky tu: 10 dau + … + duoi, title = ten day du) o Danh sach phieu, Bang diem, Hang doi, Chi tiet, /m; +5 test Node + 1 test pytest
- `ab22610` fix(G3): Bang diem – cau ly do phieu "can xem" chua ghep duoc thi sinh dung nguyen nhan (SBD co trong danh sach nhung may chua chac -> "can giao vien chot"; ngoai danh sach -> cau cu); chi doi cau chu, khong sua service.py/schemas.py; +3 test (dong giao dien app.js nam o commit G2)
- `5d2efaa` docs+tools(G): thu_lenh_f.py g2 (trinh duyet gia lap: ten tep rut gon, cau ly do G3), CLAUDE.md lenh G, pytest 402
- `0f25ea5` fix(G): thu_lenh_f.py – thoat \s trong chuoi JS
- `ddf6a85` docs(G): CLAUDE.md pytest 403

### 2026-10-29 (18 commit)

- `5ecd0ef` tools(K): kiem_anh_dot2.py – kiểm ảnh đợt 2 chỉ đọc (tên/cặp điều kiện, kích thước, EXIF, SHA-256, 4 marker bằng find_markers; không nắn, không chấm)
- `73bbec1` docs(L1): khoá ảnh đợt 2 – SHA-256 + dung lượng 20 ảnh data/raw_dot2 (khoá 29/10/2026 17:47, kiểm 20/20 khớp; chưa chạy test)
- `da286fb` docs(L2): sai lệch phiếu 0103 đợt 2 (SBD bubble cột 4, câu 3, câu 5) – lời nhóm khai 29/10/2026 trước khi máy đọc ảnh, chưa đối chiếu; không sửa nhãn đăng ký
- `85d00e1` † docs(N1): đăng ký bổ sung đợt 2 – SHA nhãn đã sửa 0103 (sbd_bubble cột 4 = 3, câu 3 = B, câu 5 = C) theo giấy thật, mục 4 kế hoạch; chỉ đổi docs/, trước khi máy đọc ảnh đợt 2
- `963314e` docs(P): sai lệch 0103 đợt 2 – người dùng đã xác nhận trên giấy thật 29/10/2026 (bubble SBD cột 4 = 3, câu 3 B đậm, câu 5 C đậm; không ô nào khác sai), trước khi máy đọc ảnh
- `a4da472` Khoá kết luận xem mù đợt 2 (29/10/2026)
- `dbf4a50` docs(S): kết quả đợt 2 và phân tích sau chạy – lưu kết quả chính thức (H2, H3 không đạt theo đăng ký; H4, H5 đạt; H1 chưa đóng) + kiểm giấy thật 20:19 29/10/2026 sau khi chạy (0107 SBD cột 3, 0110 câu 21, 0101 câu 3, 0103 câu 8), không đổi nhãn / mã / đăng ký
- `dff9dea` feat(H1): admin quản lý kỳ thi trên web – /admin/exams (danh sách, tạo + gán giáo viên phụ trách, sửa tên / ngày, đóng / mở, xoá khi chưa có phiếu), trang #/admin
- `05b54fa` feat(H2): admin quản lý tài khoản giáo viên – tạo, đặt lại mật khẩu, vô hiệu hoá / kích hoạt lại, gán / bỏ gán kỳ thi (/admin/users)
- `ca6d397` fix(H1): không xoá kỳ thi [DEMO…] hoặc kỳ thi đã có danh sách dự thi (xoá dây chuyền sẽ mất exam_students) – chỉ đóng
- `a1ed174` feat(H3): trang bìa kỳ thi (PDF + mã QR /m?kythi=<id>) và chọn sẵn kỳ thi trên trang điện thoại /m
- `7dd87d9` test(H): kiểm toán route nhận chi_admin – mọi route /admin/... phải phụ thuộc chi_admin; route quản trị được miễn kiểm quyền đối tượng (admin thấy tất cả)
- `56518f9` test: test_sao_luu_va_xoa_tep ghi tệp chữ Việt với encoding utf-8 (lỗi có sẵn: mã hoá mặc định cp1252 khi Python không chạy UTF-8 mode)
- `da64467` docs(H4): hướng dẫn quản trị – tạo kỳ thi, tài khoản giáo viên, in trang bìa, quy trình chụp phiếu theo kỳ thi, lưu ý bảo mật; CLAUDE.md mục lệnh H
- `a3227a3` feat(I1): admin quản lý lớp – /admin/classes (danh sách, tạo, sửa tên / năm học, vô hiệu hoá / kích hoạt lại, xoá khi chưa gắn kỳ thi và chưa có sinh viên), thẻ Quản trị → Lớp học
- `3ff7703` feat(I2): gán giáo viên vào lớp (nhiều – nhiều) – thêm / bỏ giáo viên ở Quản trị → Lớp học, tick nhiều lớp ở Tài khoản giáo viên, chọn lớp ngay khi tạo tài khoản
- `0dc1a18` feat(I3): lớp của kỳ thi chọn từ danh sách lớp đang hoạt động (tạo + sửa kỳ thi), quy tắc quyền = phụ trách HỢP lớp
- `9c7f22f` docs(I4): hướng dẫn quản trị – lớp học, gán giáo viên vào lớp (nhiều – nhiều), quan hệ lớp – kỳ thi – giáo viên (phụ trách HỢP lớp), migration 004; CLAUDE.md mục lệnh I

### 2026-10-30 (21 commit)

- `b61f106` fix(J1): sau đăng xuất / đăng nhập lại về đúng trang của vai trò, xoá dữ liệu phiên trước
- `ae548ae` test(J2): tools/thu_lenh_j.py – thử trình duyệt (Playwright, ROLLBACK) đăng xuất / đăng nhập lại
- `9ea1909` feat(J3): don_du_lieu_test.py --chi-ids – chỉ xét đúng các phiếu --ids, không gộp 1632 / 1633
- `1d3433f` † Gộp cai-tien-b: cải tiến sau góp ý, đợt 2, quản trị web, lớp học
- `1dc17ca` docs+tools(T): ĐĂNG KÝ TRƯỚC phép thử mô phỏng H3 "ô tô trống, chữ viết tay có" – chưa chạy trên ảnh đợt 2
- `300cc64` docs(T): kết quả phép thử mô phỏng H3 (chạy MỘT lần 30/10/2026 08:23, theo tag dang-ky-h3-mo-phong)
- `844ca4c` feat(U1): tools/kiem_truoc_demo.py – kiểm tra trước ngày demo bằng một lệnh (CHỈ ĐỌC)
- `ebd10d4` feat(U2): tools/dat_lai_demo.py – đặt lại dữ liệu demo (mặc định XEM TRƯỚC; xoá thật chỉ với --xac-nhan DAT_LAI)
- `23db4f3` feat(U3): tools/sao_luu_demo.py – pg_dump -Fc vào data/_backup/smart_exam_<ngày giờ>_demo.dump, kiểm bằng pg_restore -l
- `c1d7fa5` docs(U4): kịch bản demo 8–10 phút – 7 bước (admin + trang bìa QR, chụp điện thoại, điểm tạm / cần xem, duyệt hai kênh SBD, phiếu trùng SBD, bảng điểm + Excel, phân quyền), "Nếu hỏng thì" (Wi‑Fi chặn, camera, server, CSDL, ảnh bị từ chối, khoá đăng nhập), danh sách chuẩn bị, sao lưu / khôi phục (pg_restore chưa thử thật)
- `301bdbd` docs(U5): hướng dẫn cài đặt từ đầu trên Windows mới – Python / venv / requirements, PostgreSQL 17, run_all.bat + update_template.sql, .env + migration 001–004, tài khoản + dữ liệu demo, server LAN + tường lửa, kiểm tra, sao lưu; mỗi bước ghi [ĐÃ KIỂM] / [SUY RA]; lưu ý exam_id demo khác trên máy mới (kiem_truoc_demo / dat_lai_demo cố định id của máy này)
- `a449ca2` fix(V0): dat_lai_demo – hậu kiểm phiếu xoá chỉ thuộc đúng id cố định 1380/1381/1632/1633, CLI từ chối phạm vi khác
- `7ce81a2` feat(V1): phân biệt lỗi mạng (Gửi lại) với máy chủ từ chối rõ (409 kỳ thi đóng, 404 …) ở /m và màn Tải ảnh
- `870cd77` feat(V2): ẩn kỳ thi đã đóng khỏi ô chọn kỳ thi (thanh bên /app/ và "Chọn kỳ thi" /m), tuỳ chọn "Hiện cả kỳ thi đã đóng"
- `6822fc3` feat(V3): lý do cần xem SBD / mã đề nói rõ theo từng cột (chỉ đổi câu chữ hiển thị)
- `19aacf7` feat(V4): nhật ký thao tác quản trị – migration 005 (chỉ thêm bảng admin_audit_log), GET /admin/audit, thẻ "Nhật ký"
- `f43b488` test(V5): tools/thu_lenh_v.py – thử trình duyệt thật (Playwright, ROLLBACK) Việc 1–4 trên máy tính và Pixel 7
- `a0ab3e8` docs(V5): hướng dẫn quản trị (Nhật ký, ẩn kỳ thi đóng, migration 005), kịch bản demo (lỗi mạng / bị từ chối, lý do theo cột, phạm vi + diễn tập đặt lại demo), hướng dẫn cài đặt (migration 001–005), CLAUDE.md lệnh V
- `67c7156` fix(W1): bỏ mật khẩu CSDL viết cứng trong 00_create_database.sql, run_all.bat, run_all.sh – đọc SMART_EXAM_DB_PASSWORD
- `af4976c` fix(W2): GET /sheets/{id} không còn 500 với phiếu không có chi tiết đọc SBD / mã đề (omr_detail NULL / thiếu khoá)
- `36c91d6` docs(W3): cây thư mục (docs/cay_thu_muc.md, Bảng 3.13) và mốc commit (docs/moc_commit.md, Bảng 3.14), sinh từ git bằng tools/xuat_cay_va_moc.py
