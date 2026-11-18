# Smart Exam Grading System – Hệ thống chấm thi trắc nghiệm từ ảnh chụp phiếu trả lời

Đồ án chuyên ngành CNTT – **Nhóm 12**. Giảng viên hướng dẫn: **Trần Nguyên Bảo**.

## Hệ thống làm gì

Giáo viên chụp phiếu trả lời trắc nghiệm bằng điện thoại, hệ thống tự chấm và ghép điểm vào danh sách thí sinh:

1. **Nắn phẳng ảnh** theo 4 ô vuông đen ở góc phiếu (OpenCV); ảnh mờ, thiếu góc, chiều sai… bị từ chối kèm lý do và lời khuyên chụp lại.
2. **OMR**: đọc 40 câu × 4 ô (A–D), phân loại từng ô (trống / tô rõ / tô mờ) rồi suy ra đáp án từng câu.
3. **CNN nhận diện chữ số** đọc SBD và mã đề viết tay, đối chiếu với SBD / mã đề tô bubble (hai kênh độc lập).
4. **Chấm điểm** theo đáp án của mã đề. Câu hoặc SBD không chắc chắn (tô mờ, tô nhiều ô, hai kênh lệch nhau…) **không được chấm tự động**: phiếu vào hàng đợi để giáo viên duyệt, trước đó chỉ có điểm tạm.
5. **Giáo viên duyệt** trên giao diện web (có thể chụp bằng điện thoại ở trang `/m`), rồi xem **bảng điểm** và xuất Excel.

Bài toán cốt lõi là **tránh ghi nhầm điểm**: máy sai nhưng không báo (lỗi im lặng) phải bằng 0; khi không chắc thì chuyển cho người.

## Công nghệ

| Hạng mục | Công nghệ |
|---|---|
| Ngôn ngữ, xử lý ảnh | Python 3.14, OpenCV, NumPy |
| OMR / CNN chữ số | Khi chạy: chỉ NumPy + OpenCV + tệp mô hình JSON (`models/`). Lúc huấn luyện: CNN chữ số dùng PyTorch (`tools/huan_luyen_ocr.py`, `tools/xuat_ocr.py`), OMR (hồi quy logistic) dùng scikit-learn |
| Backend | FastAPI + uvicorn, psycopg 3 |
| Cơ sở dữ liệu | PostgreSQL 17 (24 bảng sau migration 001–006, kèm hàm, trigger và 8 view; schema trong `database/`, migration trong `backend/migrations/`) |
| Frontend | HTML + JavaScript thuần (phục vụ tại `/app/`, điện thoại tại `/m`) |
| Sinh phiếu / đọc PDF | ReportLab, PyMuPDF |
| Triển khai công khai | Docker, Caddy, `render.yaml` |

## Kết quả chính

Số liệu lấy từ `smart_exam_db/docs/ket_qua_*.md` (đọc kèm giới hạn ở từng tệp):

- **CNN sâu thay CNN cũ cho chữ số viết tay** (`ket_qua_cnn_sau.md`, `ket_qua_thay_mo_hinh_an.md`): trên 504 ô chữ số của phiếu dev, tỉ lệ trường đọc đúng cả chuỗi tăng từ 67,56% lên 83,63%; trên 48 trường val + test, đúng cả chuỗi 41/48 (cũ 39/48), cần xem 9/48 (cũ 13/48), lỗi im lặng 0. Kiểm đầu-cuối 56 ảnh dev: 0 câu chấm sai mà không gắn "cần xem", điểm chính thức khớp 56/56, số ảnh có SBD / mã đề cần xem 20/56 (cũ 26/56). Giới hạn: 48 trường quá ít để kết luận thống kê, dev lạc quan. Ở mức từng ô chữ số, CNN sâu và CNN cũ **không khác biệt có ý nghĩa thống kê** (kiểm định dấu theo ô, p = 0,36; số này ở `so_sanh_mo_rong_ak.md`); khác biệt nằm ở mức trường đọc đúng cả chuỗi và số câu / trường cần xem.
- **Test đợt 2 trên giấy thật** (`ket_qua_dot2.md`, chạy một lần theo tiêu chí đăng ký trước): chấm sai không cờ 0 và điểm chính thức sau giáo viên đúng 20/20 (**đạt**); tiêu chí OMR lỗi nặng không cờ = 0 (2/980 câu và cột: 0 câu, 2 cột) và tiêu chí SBD của phiếu 0107 **không đạt** – kết quả được giữ nguyên, không sửa tiêu chí sau khi thấy số.
- **Đồng thời / nhiều tài khoản** (`ket_qua_sua_ah.md`): đã sửa 5 rủi ro khi nhiều người cùng chấm (mất phiếu do trùng SBD, lỗi 500 khi gửi cùng tệp, deadlock lô, đăng xuất không thu hồi token, tốn RAM khi chấm song song).
- Bộ kiểm thử: **729 test đạt, 1 bỏ qua có chủ đích**.

## Chạy demo

Chạy từ thư mục `smart_exam_db\`, trên máy đã cài môi trường (PowerShell, venv đã bật). Mỗi lệnh trước hết kiểm nhánh git và SHA mô hình `models/ocr_cnn.json`, rồi đặt lại (sao lưu trước khi xoá) phiếu của riêng kỳ thi của demo đó, mở máy chủ hoặc dựng trang, mở trình duyệt và in các bước "bấm gì, nói gì". Chi tiết: `smart_exam_db/docs/huong_dan_chay_3_demo.md`.

| Lệnh | Là gì | Địa chỉ | CSDL, đăng nhập |
|---|---|---|---|
| `python tools/chay_demo.py xla` | **Công cụ ngoại tuyến riêng** (không phải hệ thống chính): chọn ảnh phiếu, xem từng bước nắn ảnh → OMR → CNN → đối chiếu hai kênh → điểm tạm. Chỉ nghe ở máy này; ảnh tải lên ở thư mục tạm và bị xoá ngay | `http://127.0.0.1:8765/` | Không cần CSDL, không đăng nhập (chỉ *cố* đặt lại kỳ `[XLA] Xử lý ảnh` nếu nối được CSDL) |
| `python tools/chay_demo.py ml` | **Trang HTML tĩnh** tổng hợp kết quả máy học (dữ liệu, mô hình, so sánh thuật toán, giới hạn), có phần chạy CNN thật trên ô phiếu dev; không có máy chủ | tệp `data\_eval\demo_3_phien\may_hoc_chay_demo.html` | Không cần CSDL, không đăng nhập (chỉ *cố* đặt lại kỳ `[ML] Máy học` nếu nối được) |
| `python tools/chay_demo.py dacn` | **Hệ thống thật**: khởi động server FastAPI (như `tools/chay_server_lan.py`, dọn ảnh tạm tắt) cùng một trang "Lý thuyết các môn"; đăng nhập, tải ảnh vào kỳ `[ĐACN] Đồ án chuyên ngành`, duyệt, bảng điểm, xuất Excel, phân quyền theo lớp, trang quản trị | `http://127.0.0.1:8000/` | **Cần CSDL và đăng nhập**; dừng nếu không đặt lại được kỳ `[ĐACN]`. Mật khẩu tài khoản demo không nằm trong git: tự đặt bằng `python -m backend.tai_khoan dat-lai-mat-khau` |

Ba kỳ thi `[XLA]`, `[ML]`, `[ĐACN]` được nạp vào CSDL bằng `python tools/nap_bo_demo.py --ba-mon --ap-dung`. Ảnh phiếu demo BV01–BV10 và các ảnh thử nằm trong `data/` (không có trong repo): sinh lại ảnh BV bằng `python tools/thu_bo_demo.py xuat`.
Tuỳ chọn chung: `--chi-in` (chỉ kiểm tra và in hướng dẫn), `--khong-dat-lai`, `--khong-mo`, `--cong N`. Chạy server cho điện thoại (trang `/m`): `python tools/chay_server_lan.py`.

## Chạy kiểm thử

```powershell
python -m pytest tests            # từ smart_exam_db\, khoảng 4 phút; test cần data/ hoặc CSDL tự SKIP nếu thiếu
```

## Cấu trúc thư mục chính

```
smart_exam_db/
├── answer_sheet/    # mẫu phiếu (nguồn toạ độ duy nhất), sinh PDF, kịch bản thu dữ liệu, bộ phiếu demo
├── cv_engine/       # lõi xử lý ảnh: preprocessing (nắn ảnh), omr (đọc ô), ocr (CNN chữ số)
├── models/          # mô hình OMR và CNN chữ số (JSON)
├── backend/         # FastAPI: API, chấm điểm, đăng nhập, phân quyền theo lớp, quản trị
├── frontend/        # giao diện web (HTML + JS thuần)
├── database/        # SQL PostgreSQL: schema, hàm, trigger, view, dữ liệu mẫu
├── tools/           # công cụ đánh giá, demo, khởi tạo / nạp dữ liệu
├── tests/           # pytest
├── docs/            # kế hoạch, tiêu chí đăng ký trước, kết quả, hướng dẫn
└── Dockerfile, docker-compose.yml, deploy/   # triển khai công khai
```

`CLAUDE.md` ghi chi tiết các quyết định thiết kế và lịch sử từng giai đoạn.

## Triển khai công khai

Hướng dẫn từ máy trắng (Docker + Caddy, hoặc Render), biến cấu hình, sao lưu / khôi phục, nạp dữ liệu demo và các việc chưa làm: [`smart_exam_db/docs/trien_khai_public.md`](smart_exam_db/docs/trien_khai_public.md).
Đã build và chạy thử bằng Docker Compose trước khi thêm công cụ nạp dữ liệu demo; image mới nhất chưa build lại; chưa thử trên Render thật.

## Về dữ liệu

- Mọi dữ liệu trong hệ thống là **dữ liệu giả**: SBD là số ngẫu nhiên / tuần tự, họ tên sinh viên trong dữ liệu mẫu là tên bịa, không có thông tin thật của ai.
- Thư mục `data/` (ảnh phiếu chụp thật, ảnh chữ số, kết quả đánh giá) **không nằm trong repo** (đã loại bằng `.gitignore`); tệp `.env`, `storage/` cũng không. Các test và công cụ cần chúng sẽ tự bỏ qua hoặc báo thiếu khi chạy trên máy chỉ có mã nguồn.
