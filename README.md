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
| OMR / CNN chữ số | Suy luận bằng NumPy + tệp mô hình JSON (`models/`); huấn luyện bằng PyTorch (chỉ lúc huấn luyện) |
| Backend | FastAPI + uvicorn, psycopg 3 |
| Cơ sở dữ liệu | PostgreSQL 17 (20 bảng, hàm, trigger, view trong `database/`) |
| Frontend | HTML + JavaScript thuần (phục vụ tại `/app/`, điện thoại tại `/m`) |
| Sinh phiếu / đọc PDF | ReportLab, PyMuPDF |
| Triển khai công khai | Docker, Caddy, `render.yaml` |

## Kết quả chính

Số liệu lấy từ `smart_exam_db/docs/ket_qua_*.md` (đọc kèm giới hạn ở từng tệp):

- **CNN sâu thay CNN cũ cho chữ số viết tay** (`ket_qua_cnn_sau.md`, `ket_qua_thay_mo_hinh_an.md`): trên 504 ô chữ số của phiếu dev, tỉ lệ trường đọc đúng cả chuỗi tăng từ 67,56% lên 83,63%; trên 48 trường val + test, đúng cả chuỗi 41/48 (cũ 39/48), cần xem 9/48 (cũ 13/48), lỗi im lặng 0. Kiểm đầu-cuối 56 ảnh dev: 0 câu chấm sai mà không gắn "cần xem", điểm chính thức khớp 56/56, số ảnh có SBD / mã đề cần xem 20/56 (cũ 26/56). Giới hạn: 48 trường quá ít để kết luận thống kê, dev lạc quan.
- **Test đợt 2 trên giấy thật** (`ket_qua_dot2.md`, chạy một lần theo tiêu chí đăng ký trước): chấm sai không cờ 0 và điểm chính thức sau giáo viên đúng 20/20 (**đạt**); tiêu chí OMR lỗi nặng không cờ = 0 (2/980 cột) và tiêu chí SBD của phiếu 0107 **không đạt** – kết quả được giữ nguyên, không sửa tiêu chí sau khi thấy số.
- **Đồng thời / nhiều tài khoản** (`ket_qua_sua_ah.md`): đã sửa 5 rủi ro khi nhiều người cùng chấm (mất phiếu do trùng SBD, lỗi 500 khi gửi cùng tệp, deadlock lô, đăng xuất không thu hồi token, tốn RAM khi chấm song song).
- Bộ kiểm thử: **729 test đạt, 1 bỏ qua có chủ đích**.

## Chạy demo

Từ thư mục `smart_exam_db\` (PowerShell, đã bật venv, đã có CSDL PostgreSQL và tệp `.env`; xem `smart_exam_db/docs/huong_dan_chay_3_demo.md`):

```powershell
python tools/chay_demo.py xla     # demo xử lý ảnh (công cụ ngoại tuyến, không cần đăng nhập / CSDL)
python tools/chay_demo.py ml      # demo máy học: CNN chữ số, so sánh các thuật toán
python tools/chay_demo.py dacn    # demo hệ thống đầy đủ: tải ảnh → chấm → duyệt → bảng điểm
```

Mỗi lệnh kiểm môi trường, đặt lại dữ liệu của riêng demo đó, mở trình duyệt và in các bước thao tác.
Chạy server cho điện thoại: `python tools/chay_server_lan.py`.

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
Đã build và chạy thử bằng Docker Compose trên máy phát triển; **chưa thử trên Render thật**.

## Về dữ liệu

- Mọi dữ liệu trong hệ thống là **dữ liệu giả**: SBD là số ngẫu nhiên / tuần tự, họ tên sinh viên trong dữ liệu mẫu là tên bịa, không có thông tin thật của ai.
- Thư mục `data/` (ảnh phiếu chụp thật, ảnh chữ số, kết quả đánh giá) **không nằm trong repo** (đã loại bằng `.gitignore`); tệp `.env`, `storage/` cũng không. Các test và công cụ cần chúng sẽ tự bỏ qua hoặc báo thiếu khi chạy trên máy chỉ có mã nguồn.
