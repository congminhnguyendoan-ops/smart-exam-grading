# Chạy server + tài khoản (máy của bạn, PowerShell) – 27/10/2026

Mọi lệnh dưới đây dán NGUYÊN VĂN vào **PowerShell thường** (trừ mục 0 và mục 7 cần quản trị). Đường dẫn đã kiểm trên máy này (27/10/2026).
Gọi thẳng `python.exe` của venv: chính sách script của máy là *Restricted* nên `Activate.ps1` bị chặn – không cần kích hoạt venv.

## 0. Một lần trước buổi demo – mở tường lửa (PowerShell **Run as Administrator**)
```powershell
New-NetFirewallRule -DisplayName "SmartExam-8000-LAN" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Public,Private -RemoteAddress LocalSubnet
```
Chỉ máy **cùng mạng nội bộ** (LocalSubnet) vào được cổng 8000; không mở ra Internet. **Sau buổi demo xoá luật** (mục 7).

## 1. Vào thư mục dự án
```powershell
Set-Location C:\Users\MSI\PycharmProjects\smart_exam_db_1\smart_exam_db
$py = "C:\Users\MSI\PycharmProjects\smart_exam_db_1\.venv\Scripts\python.exe"
```
Mở cửa sổ PowerShell mới thì chạy lại hai dòng này.

## 2. Kiểm PostgreSQL
```powershell
Get-Service postgresql-x64-17
& "C:\Program Files\PostgreSQL\17\bin\pg_isready.exe" -h localhost -p 5432
& $py tools/db_check.py
& $py -m backend.migrate --kiem
```
Mong đợi: `Running` · `localhost:5432 - accepting connections` · `db_check` in bảng kỳ thi · 001, 002, 003 đều "ĐÃ ÁP".
Dịch vụ dừng → PowerShell **quản trị**: `Start-Service postgresql-x64-17`.

## 3. Đặt lại mật khẩu admin / gv_an / gv_binh
```powershell
& $py -m backend.tai_khoan dat-lai-mat-khau admin
& $py -m backend.tai_khoan dat-lai-mat-khau gv_an
& $py -m backend.tai_khoan dat-lai-mat-khau gv_binh
```
Mỗi lệnh hỏi "Mật khẩu mới:" rồi "Nhập lại:" (gõ không hiện chữ – bình thường), in "Xong.". Mật khẩu tối thiểu 8 ký tự.
Tài khoản bị khoá: `& $py -m backend.tai_khoan mo-khoa gv_an`. Cách khác – đặt cả ba bằng mật khẩu ngẫu nhiên (in MỘT lần, chép lại ngay):
`& $py -m backend.tai_khoan --mau`.

## 4. Khởi động server cho mạng nội bộ (giữ ảnh, không dọn)
```powershell
& $py tools/chay_server_lan.py --khong-xoa-anh
```
Màn hình in: địa chỉ điện thoại `http://<IP>:8000/m` + mã QR + lệnh tường lửa, rồi `Uvicorn running on http://0.0.0.0:8000`. **Để nguyên cửa sổ này** (đóng = tắt server).
Chỉ xem địa chỉ / QR mà không chạy: `& $py tools/chay_server_lan.py --chi-in`.
(Chỉ dùng trên máy này, không cho điện thoại: `& $py -m uvicorn backend.main:app --port 8000`.)

## 5. Mở giao diện
- **Máy tính**: http://127.0.0.1:8000/ → đăng nhập (`gv_an` / `gv_binh` / `admin`) → nút **📱 Kết nối điện thoại** hiện QR.
- **Điện thoại** (cùng Wi‑Fi): quét QR, hoặc gõ `http://192.168.1.142:8000/m` (IP ngày 27/10 – lấy IP đúng ở dòng "ĐIỆN THOẠI mở:" của mục 4; IP đổi khi đổi mạng / hotspot).
- Kỳ thi demo: **1380** (K22A, gv_an), **1381** (K22B, gv_binh). Diễn tập trên **1632 / 1633** `[DEMO-BV-TẬP]` (đang trống). Ảnh dự phòng: `data\_eval\demo_bv\anh_gia\BV01.jpg … BV10.jpg` (xem `README.txt`).

## 6. Tắt server
Bấm **Ctrl+C** trong cửa sổ đang chạy server (mục 4). Nếu cửa sổ đã đóng mà cổng 8000 vẫn bận:
```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess
Stop-Process -Id <số OwningProcess ở trên>
```

## 7. Sau buổi demo (PowerShell **Run as Administrator**)
```powershell
Remove-NetFirewallRule -DisplayName "SmartExam-8000-LAN"
```
Rồi xoá ảnh phiếu trong thư viện ảnh của điện thoại (cả "Đã xoá gần đây" / "Thùng rác"); nên đổi mật khẩu các tài khoản đã gõ qua Wi‑Fi (mục 3).

## 8. Lỗi thường gặp
| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| `& $py …` báo không nhận ra lệnh | chưa chạy 2 dòng của mục 1 trong cửa sổ này | chạy lại mục 1 |
| `[Errno 10048]` / "only one usage of each socket address" | cổng 8000 đang bị server khác chiếm | mục 6, hoặc `& $py tools/chay_server_lan.py --khong-xoa-anh --cong 8080` (tường lửa: đổi `8000` → `8080` trong lệnh mục 0) |
| `Chưa đặt DATABASE_URL` / `AUTH_SECRET` | thiếu `.env` trong `smart_exam_db\` | chép `.env.example` thành `.env`, điền giá trị (không commit `.env`) |
| `connection refused` / `db_check` lỗi | PostgreSQL chưa chạy | mục 2: `Start-Service postgresql-x64-17` (quản trị) |
| `DỪNG: migration chưa áp …` | CSDL thiếu migration | `& $py -m backend.migrate` (chỉ thêm cột / bảng) |
| Đăng nhập: "Sai tên đăng nhập hoặc mật khẩu." | sai mật khẩu / tài khoản bị khoá (cùng một thông báo) | mục 3 (`dat-lai-mat-khau`, `mo-khoa`) |
| Đăng nhập: "Thử đăng nhập sai quá nhiều lần…" (429) | sai 5 lần trong 15 phút | chờ 15 phút hoặc tắt / bật lại server (mục 6 → 4) |
| Hộp thoại máy tính báo vàng "chỉ nghe 127.0.0.1" | đang chạy `uvicorn` thường | tắt, chạy mục 4 |
| Điện thoại: trang không tải được | khác Wi‑Fi; chưa mở tường lửa (mục 0); sai IP; Wi‑Fi chặn thiết bị nói chuyện với nhau | cùng Wi‑Fi → mục 0 → IP ở mục 4 → vẫn không được: bật **hotspot trên điện thoại**, máy tính nối vào, chạy lại mục 4 (IP mới, QR mới) |
| Điện thoại: "Ảnh không dùng được" | thiếu sáng, nghiêng, mất góc phiếu | làm theo "Cách chụp lại" hiện ngay dưới; vẫn không được → máy tính "Tải ảnh & chấm" ảnh dự phòng (mục 5) |
| Điện thoại: "Ảnh này đã tải trước đó" | gửi lại đúng tệp ảnh cũ | bình thường – hiện phiếu cũ, không chấm lại |
| Điện thoại: "Không tìm thấy kỳ thi (hoặc bạn không phụ trách lớp này)" | đăng nhập sai giáo viên (gv_an chỉ thấy K22A, gv_binh chỉ K22B) | Đăng xuất, đăng nhập đúng giáo viên |
| Ảnh phiếu trên máy tính hiện "(ảnh không còn – đã xoá sau khi chốt phiếu)" | server chạy KHÔNG có `--khong-xoa-anh`, phiếu đã chốt > 24 giờ | đúng chính sách ảnh tạm; điểm vẫn giữ. Muốn giữ ảnh: luôn dùng `--khong-xoa-anh` |
