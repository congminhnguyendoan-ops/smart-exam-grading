# Hướng dẫn chạy 3 demo theo môn (lệnh AP, 16/11/2026)

Ba buổi demo, mỗi buổi MỘT lệnh. Chạy từ thư mục `smart_exam_db\` (PowerShell, venv gốc đã bật: `..\.venv\Scripts\Activate.ps1`), nhánh `cnn-sau`.

| Demo | Lệnh | Địa chỉ (tự mở trình duyệt) | Cần CSDL? | Đăng nhập? |
|---|---|---|---|---|
| Xử lý ảnh | `python tools/chay_demo.py xla` | http://127.0.0.1:8765/ (chỉ máy này) | không (đặt lại kỳ [XLA] nếu nối được) | không |
| Máy học | `python tools/chay_demo.py ml` | `data\_eval\demo_3_phien\may_hoc_chay_demo.html` (tệp, không máy chủ) | không (đặt lại kỳ [ML] nếu nối được) | không |
| Đồ án chuyên ngành | `python tools/chay_demo.py dacn` | http://127.0.0.1:8000/ (+ tab "Lý thuyết các môn"; điện thoại: QR do `chay_server_lan.py` in) | CÓ | CÓ |

Mỗi lệnh làm theo thứ tự: (1) kiểm nhánh git = `cnn-sau` và SHA `models/ocr_cnn.json` = `a151c078…` (CNN sâu); (2) đặt lại RIÊNG kỳ thi của demo đó về 0 phiếu (`tools/dat_lai_demo.py --ky-thi …`, tự sao lưu CSV + ảnh vào `data\_eval\sao_luu_don_du_lieu\` trước khi xoá); (3) mở máy chủ / dựng trang; (4) mở trình duyệt; (5) in 9 dòng "bấm gì, nói gì" ra màn hình.
Tuỳ chọn chung: `--chi-in` (chỉ kiểm tra + in hướng dẫn, không đặt lại / mở gì) · `--khong-dat-lai` · `--khong-mo` · `--bo-qua-kiem-tra` (chỉ để thử) · `--cong N`; riêng `ml`: `--da-tinh-san` (không chờ ~6 giây so sánh trực tiếp).

## Chuẩn bị một lần
1. Ba kỳ thi theo môn (đã nạp 16/11/2026; chạy lại không tạo trùng): `python tools/nap_bo_demo.py --ba-mon` (xem trước) rồi thêm `--ap-dung`. Tạo `[XLA] Xử lý ảnh`, `[ML] Máy học`, `[ĐACN] Đồ án chuyên ngành` (exam_id 9694 / 9695 / 9696 trên máy này – id có thể khác ở máy khác): mỗi kỳ 40 câu, mã đề 101–104 có đáp án, môn XLA / ML / DACN, lớp CNTT-K22A, giáo viên `gv_an`, dự thi 220001–220009 (220010 cố ý NGOÀI danh sách, là phiếu BV10).
2. Ảnh phiếu demo `data\_eval\demo_bv\anh_gia\BV01.jpg … BV10.jpg` (thiếu → `python tools/thu_bo_demo.py xuat`) và ảnh `data\_eval\demo_3_phien\T05_thuong.JPG`, `T03_kho.JPG`, `T05_mo_phong_nhe.jpg`, `T05_mo_phong_nang.jpg`. Ảnh BV là ảnh GIẢ HOÁ (vẽ phẳng, không có chữ viết tay); `T05_thuong` / `T03_kho` là ảnh chụp thật; hai ảnh `mo_phong` là MÔ PHỎNG.
3. Tài khoản (dacn): `gv_an` (giáo viên của kỳ [ĐACN]), `gv_binh` (lớp khác – để chứng minh phân quyền: không thấy kỳ của `gv_an`), `admin`. **Mật khẩu KHÔNG nằm trong git và không in ở đâu**: bạn tự đặt bằng `python -m backend.tai_khoan dat-lai-mat-khau gv_an` (nhập bằng getpass; xem `docs/chay_server_va_tai_khoan.md` mục 3).

## Demo 1 – Xử lý ảnh (`xla`)
Thứ tự: BV01 (phiếu tốt: ảnh gốc → độ mờ → 4 góc → nắn → chuẩn hoá ánh sáng (4b) → lưới → OMR) → BV03 (câu bỏ trống / tô hai ô: khung cảnh báo + bảng câu cần xem + LÝ DO + bước 9 điểm tạm) → BV07 (tô nhạt cả tờ) / BV10 (SBD ngoài danh sách) → bước 10 "CNN là gì?" → "Chọn tệp ảnh…" `T05_mo_phong_nang.jpg` (bị TỪ CHỐI kèm lý do). Dùng `T05_thuong` để thấy chữ viết tay thật và đối chiếu hai kênh (bước 7–8).
Công cụ ngoại tuyến: không đăng nhập, không CSDL, chỉ nghe ở 127.0.0.1; ảnh tải lên chỉ ở thư mục tạm và bị xoá ngay. Đáp án để tính điểm tạm lấy từ `answer_sheet\demo_bv\demo_bv_dap_an.csv` (cùng đáp án với kỳ thi [XLA] trong CSDL). Dừng: Ctrl+C.

## Demo 2 – Máy học (`ml`)
Trang mở sẵn các mục: Dữ liệu → Hai mô hình → CNN và CNN sâu bằng lời → Hai mạng cạnh nhau kèm mã NumPy thật → Vì sao chuyển sang CNN sâu (AM / AN) → So sánh trực tiếp các thuật toán → Chạy CNN sâu thật (485/504 ô lúc dựng trang) → CNN cũ so với 5 thuật toán → 11 thuật toán (AK) → Kích thước và tốc độ → Kết quả không đạt → Giới hạn. Lời dẫn mẫu: `docs/kich_ban_3_phien.md` (phiên 2). Phải nói đúng giới hạn: 48 trường val + test chưa có ý nghĩa thống kê; dev lạc quan; chưa đo người viết lạ; lỗi im lặng 0 nhờ đối chiếu hai kênh.

## Demo 3 – Đồ án chuyên ngành (`dacn`)
Lệnh mở máy chủ giống `tools/chay_server_lan.py` (dọn ảnh tạm TẮT), chờ `/health`, mở `http://127.0.0.1:8000/` và trang "Lý thuyết các môn" (`data\_eval\demo_3_phien\ly_thuyet_cac_mon.html`).
Thứ tự: đăng nhập `gv_an` → chọn kỳ `[ĐACN]` (0 phiếu) → Tải ảnh (BV01–BV05, nhiều ảnh một lượt) → danh sách phiếu (điểm TẠM) → Duyệt (BV03: phím A–D, Enter) → Bảng điểm (chỉ phiếu đã duyệt có điểm chính thức) → Xuất Excel → tải lại BV01 để thấy phiếu trùng SBD → đăng nhập `admin` → Quản trị → Nhật ký → tab "Lý thuyết các môn". Điện thoại (tuỳ chọn): quét QR in lúc khởi động, trang `/m`; tường lửa do BẠN tự chạy (lệnh in ở `chay_server_lan.py`), công cụ không chạy lệnh mạng.
Trang "Lý thuyết các môn" **suy ra môn từ chính hệ thống** (CSDL, web/API, an toàn thông tin, kiểm thử, phân tích thiết kế, xử lý ảnh, học máy) vì chưa biết nhóm đã học môn nào – đó là **giả định**, ghi ngay trên trang; bỏ mục môn chưa học khi trình bày. Số bảng / số đường dẫn API đếm lúc dựng trang; không đếm được thì ghi "chưa đếm được".
Làm lại từ đầu: chạy lại lệnh (tự đặt lại kỳ [ĐACN] về 0 phiếu); đặt lại riêng không chạy demo: `python tools/dat_lai_demo.py --ky-thi dacn` (xem trước) rồi thêm `--xac-nhan DAT_LAI` (xoá thật). Công cụ chỉ chạm đúng kỳ thi đó (tìm theo tiêu đề nguyên văn, phải có đúng một); các kỳ [DEMO-BV] / [DEMO-BV-TẬP] có lệnh riêng (`dat_lai_demo.py` không tham số).

## Khi lỗi
| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| "DỪNG: kiểm tra nhánh / mô hình không đạt" | đang ở nhánh khác, hoặc `models/ocr_cnn.json` không phải CNN sâu | `git switch cnn-sau`; kiểm `git status`; khôi phục mô hình: `git checkout cnn-sau -- models/ocr_cnn.json` |
| "Không đặt lại được (OperationalError…)" | PostgreSQL chưa chạy / `.env` sai | bật dịch vụ PostgreSQL; kiểm `DATABASE_URL`; `python tools/db_check.py`. `xla` và `ml` vẫn chạy được; `dacn` dừng |
| "cần đúng 1 kỳ thi '[…]'" | chưa nạp kỳ thi, hoặc có hai kỳ trùng tiêu đề | `python tools/nap_bo_demo.py --ba-mon --ap-dung`; trùng tiêu đề thì hỏi trước khi xoá |
| `dacn`: "máy chủ không trả lời" sau 60 giây | thiếu `AUTH_SECRET` / `.env`, cổng 8000 bị chiếm | đọc lỗi uvicorn ngay phía trên; `netstat -ano` rồi tìm `:8000`; dùng `--cong 8010` |
| `xla`: cổng 8765 bận | công cụ cũ còn chạy | tắt cửa sổ cũ (Ctrl+C) hoặc `--cong 8766` |
| Trình duyệt không tự mở | chính sách máy / không có trình duyệt mặc định | mở tay địa chỉ in trên màn hình (hoặc tệp HTML ở trên); `--khong-mo` |
| Trang `xla` báo "Không thấy ảnh BV" | chưa sinh ảnh demo | `python tools/thu_bo_demo.py xuat` |
| Đăng nhập: "Sai tên đăng nhập hoặc mật khẩu" | sai mật khẩu hoặc bị khoá (5 lần / 15 phút) | `python -m backend.tai_khoan mo-khoa gv_an` rồi `dat-lai-mat-khau gv_an` |
| `kiem_truoc_demo.py` báo `#1633` không trống | còn phiếu diễn tập | `python tools/dat_lai_demo.py` (xem trước) rồi `--xac-nhan DAT_LAI` |
