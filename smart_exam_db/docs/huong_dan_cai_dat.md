# Hướng dẫn cài đặt từ đầu trên một máy Windows mới – lệnh U, 30/10/2026

Dựng hệ thống Smart Exam (CSDL + backend + giao diện web + trang điện thoại) từ mã nguồn, dựa trên các script có sẵn trong dự án.
Mỗi bước có nhãn kiểm chứng:
- **[ĐÃ KIỂM]**: đã chạy thật trên máy hiện tại (ghi ngày / nguồn).
- **[SUY RA]**: chỉ suy ra từ mã / tài liệu, **chưa chạy thật** theo đúng thứ tự này trên một máy mới.

Lưu ý chung: **chưa từng dựng lại toàn bộ trên một máy Windows mới**. Máy hiện tại được dựng dần từ 30/09/2026, nên thứ tự dưới đây là thứ tự suy ra từ mã.
Trong các lệnh, `<GOC>` = thư mục gốc dự án (ví dụ `C:\Users\<tên>\PycharmProjects\smart_exam_db_1`). Mọi lệnh Python chạy từ `<GOC>\smart_exam_db`.

## 1. Phần mềm cần cài
| Phần mềm | Phiên bản đang dùng | Ghi chú | Kiểm chứng |
|---|---|---|---|
| Python | 3.14 (venv `<GOC>\.venv`) | python.org; tick "Add to PATH" | [ĐÃ KIỂM] máy hiện tại chạy 3.14 |
| PostgreSQL | 17 (dịch vụ `postgresql-x64-17`, cổng 5432) | bộ cài EDB; nhớ mật khẩu `postgres`; pgAdmin đi kèm | [ĐÃ KIỂM] PostgreSQL 17.11 (`kiem_truoc_demo.py` 30/10) |
| Git | bất kỳ | chép mã nguồn (hoặc chép nguyên thư mục) | [ĐÃ KIỂM] |
| Trình duyệt | Chrome / Edge | giao diện `/app/`; điện thoại: Safari / Chrome | [ĐÃ KIỂM] iPhone Safari 27/10; **Android chưa thử** |

## 2. Mã nguồn + dữ liệu không nằm trong git
1. Chép mã: `git clone <kho>` hoặc chép nguyên thư mục `<GOC>`. **[SUY RA]** (chưa có remote GitHub).
   Lưu ý: `core.autocrlf=true` làm đổi kết thúc dòng khi checkout. Một số kiểm tra theo SHA (đăng ký đợt 2, phép thử H3) phải chạy trên cây làm việc gốc – xem `CLAUDE.md` mục 4f.
2. `data\` **không có trong git** (ảnh chụp thật, kết quả đánh giá, sao lưu). Muốn chạy test cần dữ liệu và có ảnh demo dự phòng: chép `data\` từ bản sao lưu (Google Drive).
   Ảnh demo giả hoá tạo lại được: `python tools/thu_bo_demo.py tao-anh` rồi `python tools/thu_bo_demo.py xuat` (→ `data\_eval\demo_bv\anh_gia\`), `python tools/thu_dien_thoai.py tao-anh` (→ `gia_12mp\`). **[SUY RA]**
3. Có sẵn trong git (không cần sinh lại): `models\omr_m1.json`, `models\ocr_cnn.json`, `answer_sheet\output\layout.json`, `phieu_trang_300dpi.png`, `update_template.sql`, các PDF phiếu, `answer_sheet\demo_bv\*`. **[ĐÃ KIỂM]** (`git ls-files`; SHA mô hình khớp `docs/dong_bang_ma_dot2.json` – `kiem_truoc_demo.py` 30/10).

## 3. Môi trường Python
```powershell
cd <GOC>
py -3.14 -m venv .venv
$py = "<GOC>\.venv\Scripts\python.exe"
& $py -m pip install -r smart_exam_db\answer_sheet\requirements.txt
```
- `requirements.txt` có cả gói chỉ dùng để **huấn luyện / sinh tài liệu** (`torch`, `scikit-learn`, `playwright`) – chạy hệ thống không cần; bỏ được nếu cài chậm / lỗi.
  Chương trình chính cần: opencv-python, numpy, pillow, pillow-heif, psycopg[binary], fastapi, uvicorn[standard], python-dotenv, python-multipart, openpyxl, segno, ifaddr,
  reportlab, pymupdf (và pytest, httpx để kiểm thử).
- Chính sách script của Windows có thể chặn `Activate.ps1`: không cần kích hoạt venv, gọi thẳng `& $py …` (`docs/chay_server_va_tai_khoan.md`).
- Kiểm chứng: venv `<GOC>\.venv` đang dùng được **[ĐÃ KIỂM]**; cài lại từ đầu bằng lệnh trên trên máy mới **[SUY RA]** (Python 3.14 rất mới – nếu `torch` không có bản cho 3.14 thì bỏ `torch`, hệ thống vẫn chạy vì suy luận CNN là NumPy + JSON).

## 4. Tạo cơ sở dữ liệu
**XOÁ SẠCH CSDL `smart_exam` cũ nếu có** (`00_create_database.sql` chạy `DROP DATABASE`).
```powershell
$env:Path += ";C:\Program Files\PostgreSQL\17\bin"     # psql chưa có trong PATH
$env:SMART_EXAM_DB_PASSWORD = "<mật khẩu tự chọn cho smart_exam_app>"   # chỉ sống trong cửa sổ PowerShell này; GHI LẠI để điền .env ở mục 5
cd <GOC>\smart_exam_db\database
.\run_all.bat                                          # [1/6] hỏi mật khẩu postgres; tạo role smart_exam_app + DB; 01→05
psql -U smart_exam_app -h localhost -d smart_exam -f ..\answer_sheet\output\update_template.sql    # ghi toạ độ phiếu vào sheet_templates (PHẢI chạy sau run_all)
```
- Mật khẩu của `smart_exam_app` **không còn ghi cứng** trong script (lệnh W, 30/10/2026). `run_all.bat` / `run_all.sh` lấy từ biến môi trường `SMART_EXAM_DB_PASSWORD`,
  không có thì đọc dòng `SMART_EXAM_DB_PASSWORD=` trong `smart_exam_db\.env` (đã nằm trong `.gitignore`). Thiếu cả hai thì **dừng ngay, chưa chạy lệnh psql nào**
  ("LOI: chua co mat khau CSDL…"). `00_create_database.sql` cũng tự dừng trước `DROP DATABASE` nếu không được truyền mật khẩu (`-v app_password=…`).
- Role `smart_exam_app` **đã có** thì `run_all` giữ nguyên mật khẩu cũ của nó (không đổi mật khẩu CSDL đang chạy) – khi đó `SMART_EXAM_DB_PASSWORD` phải là mật khẩu hiện tại để bước [2/6]→[6/6] nối được.
- Kiểm chứng script: `tests/test_mat_khau_csdl.py` (chạy bản chép của run_all với psql giả; chốt SQL chạy bằng psql thật trong `--single-transaction`, không xoá được gì) **[ĐÃ KIỂM]**. Chạy `run_all.bat` thật trên máy mới **[SUY RA]**.
- `04_seed.sql` nạp: tài khoản `admin`, `gv_an`, `gv_binh`, `sv220001` (mật khẩu trong seed là chuỗi giả – **phải đặt lại**, mục 6), lớp CNTT-K22A / K22B, môn IT3080 / IT4040,
  10 sinh viên 220001–220010, mẫu phiếu. `05_demo_workflow.sql` chạy thử luồng chấm (để lại dữ liệu mẫu).
- Kiểm chứng: **[SUY RA]**. `run_all.bat` chưa chạy trên máy này trong giai đoạn có ghi chép (psql không có trong PATH, `CLAUDE.md` mục 8). `update_template.sql` đã chạy qua pgAdmin (30/09, "UPDATE 1") **[ĐÃ KIỂM]**.

## 5. Cấu hình `.env` + migration
```powershell
cd <GOC>\smart_exam_db
Copy-Item .env.example .env
& $py -c "import secrets; print(secrets.token_urlsafe(48))"     # dán vào AUTH_SECRET
notepad .env                                                     # DATABASE_URL + SMART_EXAM_DB_PASSWORD (cùng mật khẩu smart_exam_app ở mục 4), AUTH_SECRET; để AUTH_MODE=on
& $py -m backend.migrate                                         # áp 001 → 005 (mỗi tệp một giao dịch; chạy lại an toàn)
& $py -m backend.migrate --kiem                                  # phải in "ĐÃ ÁP" cho cả 5 tệp
& $py tools/db_check.py                                          # in bảng kỳ thi = nối CSDL được
```
- KHÔNG đặt `ANH_XOA_TU_DONG=1` trong `.env` (`chay_server_lan.py` tự bật). `PUBLIC_BASE_URL` để trống hoặc `http://<IP LAN>:8000` (mã QR trang bìa).
- Kiểm chứng: migration 001–005 đã áp trên máy này (001 từ bản demo backend 07/10, 002 27/10, 003 27/10, 004 29/10, 005 30/10 – nhật ký quản trị, lệnh V – các lần sau có sao lưu trong `data\_backup\`) **[ĐÃ KIỂM]**; `.env` đang có đủ khoá **[ĐÃ KIỂM]**.
  Áp liền 001→005 lên một CSDL vừa tạo bằng `run_all.bat` **[SUY RA]**.

## 6. Tài khoản + dữ liệu demo
```powershell
& $py -m backend.tai_khoan --mau                 # đặt mật khẩu NGẪU NHIÊN cho admin, gv_an, gv_binh – in MỘT lần, chép lại ngay
& $py tools/nap_giao_vien_demo.py --ap-dung      # gán gv_an → CNTT-K22A (IT3080), gv_binh → CNTT-K22B (IT4040)
& $py tools/kiem_bo_demo.py                       # kiểm kịch bản 10 phiếu BV (khớp 10/10)
& $py tools/nap_bo_demo.py --ap-dung              # 2 kỳ thi [DEMO-BV] + đáp án + danh sách dự thi
& $py tools/nap_bo_demo.py --ban-tap --ap-dung    # 2 kỳ thi [DEMO-BV-TẬP] để diễn tập
```
- Bỏ `--ap-dung` để XEM TRƯỚC (chỉ đọc). Chạy lại không tạo trùng.
- **Khác máy hiện tại:** `exam_id` sinh mới. Máy này là 1380 / 1381 / 1632 / 1633; máy mới sẽ ra số khác, và kỳ thi tập không có các phiếu nền 3878 … 6028.
  `tools/kiem_truoc_demo.py` và `tools/dat_lai_demo.py` đang **cố định các id của máy này** (theo lệnh U), nên trên máy mới phải sửa hằng `KY_THI_*` / `NEN_TAP`
  ở đầu hai tệp trước khi dùng.
- Kiểm chứng: `tai_khoan`, `nap_giao_vien_demo`, `nap_bo_demo` (bản chính 27/10, bản tập 27/10) đã chạy trên máy này **[ĐÃ KIỂM]**; chạy liền sau `run_all.bat` trên CSDL mới **[SUY RA]**.

## 7. Chạy server + mở cho điện thoại
```powershell
# một lần, PowerShell Run as Administrator:
New-NetFirewallRule -DisplayName "SmartExam-8000-LAN" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Public,Private -RemoteAddress LocalSubnet
# mỗi lần chạy (PowerShell thường):
& $py tools/chay_server_lan.py --khong-xoa-anh   # in http://<IP>:8000/m + QR + lệnh tường lửa; giữ cửa sổ mở
```
- Máy tính: `http://<IP LAN>:8000/` (hoặc `http://127.0.0.1:8000/` nếu không in trang bìa); điện thoại cùng Wi‑Fi: quét QR.
- Chỉ dùng trên máy tính: `& $py -m uvicorn backend.main:app --port 8000`.
- Kiểm chứng: `chay_server_lan.py` + iPhone thật cùng Wi‑Fi (27/10) **[ĐÃ KIỂM]**; luật tường lửa có trên máy này (`kiem_truoc_demo.py` 30/10) **[ĐÃ KIỂM]**; Android **chưa thử**.

## 8. Kiểm tra sau khi cài
```powershell
& $py tools/kiem_truoc_demo.py           # bảng ĐẠT / KHÔNG ĐẠT; mã thoát 0 = sẵn sàng (xem lưu ý id kỳ thi ở mục 6)
& $py -m pytest tests                     # 465 đạt + 1 bỏ qua có chủ đích trên máy này (30/10); thiếu data\ thì nhiều test tự SKIP
& $py tools/kiem_backend_dau_cuoi.py     # hồi quy đầu-cuối 56 ảnh dev (cần data\raw); đặt PYTHONIOENCODING=utf-8 nếu ghi ra tệp
```
- Kiểm chứng: cả ba lệnh chạy trên máy này 30/10 **[ĐÃ KIỂM]** (`kiem_truoc_demo.py`: 27 ĐẠT, 1 CẢNH BÁO PUBLIC_BASE_URL). Trên máy mới **[SUY RA]**.

## 9. Sao lưu
`& $py tools/sao_luu_demo.py` → `data\_backup\smart_exam_<ngày giờ>_demo.dump` (pg_dump -Fc, kiểm bằng `pg_restore -l`). **[ĐÃ KIỂM]** 30/10 (229 mục).
Khôi phục: `docs/kich_ban_demo.md` mục 4 – **[SUY RA]**, chưa thử khôi phục thật.
