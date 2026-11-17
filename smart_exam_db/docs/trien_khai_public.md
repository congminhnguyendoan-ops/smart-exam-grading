# Triển khai bản công khai (lệnh AU, 17/11/2026)

Từ một máy trắng (Linux có Docker) đến hệ thống chạy sau HTTPS. Cấu hình mẫu: `docker-compose.yml` (caddy → app → postgres:17), `deploy/Caddyfile`, `.env.production.example`.

> **Trạng thái kiểm chứng (đọc trước, cập nhật lệnh AV 17/11/2026):**
> - **Đã chạy thật** trên MỘT máy (Windows 11, Docker Desktop 29.8.0, 16 CPU, 7,6 GiB cấp cho Docker): build image (643 MB), `docker compose up` (db + app + caddy), khởi tạo DB rỗng, tạo admin, đăng nhập, khoá 5 lần sai, giới hạn thân ở Caddy,
>   chấm JPG + HEIC iPhone thật + lô 5 ảnh, HTTPS qua chứng chỉ nội bộ của Caddy (TLS 1.3). Số liệu: mục 11.
> - **CHƯA thử**: máy chủ Linux thật + tên miền + chứng chỉ Let's Encrypt; `X-Forwarded-For` với IP khách thật từ Internet (trên Docker Desktop IP kết nối là cổng NAT `172.28.0.1`); **Render thật** (mục 12);
>   sao lưu / khôi phục bằng lệnh trong mục 5–6 (chưa chạy); chạy nhiều ngày / nhiều người dùng.

## 1. Yêu cầu

| | Tối thiểu | Khuyến nghị |
|---|---|---|
| RAM | **1 GB** (đặt `CHAM_DONG_THOI=2`) | 2 GB (mặc định `CHAM_DONG_THOI=4`) |
| Đĩa | 10 GB trống | 30 GB (ảnh phiếu khoảng 1,5–2 MB mỗi phiếu: 1 000 phiếu ≈ 2 GB; ước lượng, xem mục 9) |
| Mạng | cổng 80 và 443 mở ra Internet; DNS của tên miền trỏ về máy | |
| Phần mềm | Docker Engine + plugin Compose v2, `git` | |

**Về RAM** (đo trong container trên máy phát triển, mục 11): nghỉ ≈ 141 MiB; đỉnh khi chấm 1 ảnh ≈ 290–300 MiB; lô 5 ảnh (một yêu cầu, tuần tự) ≈ 320–345 MiB; 5 ảnh gửi song song ≈ 450–530 MiB.
Cộng PostgreSQL (~100 MB) và Caddy (~30 MB) khi cùng một máy: 1 GB đủ với `CHAM_DONG_THOI=1–2` và ít người dùng đồng thời; 2 GB thoải mái hơn. Đỉnh cgroup gồm cả bộ nhớ đệm tệp (kernel thu hồi được) nên là cận trên.

## 2. Từ máy trắng đến chạy được

```bash
# 1) Cài Docker (xem hướng dẫn của Docker cho hệ điều hành), rồi lấy mã đúng nhánh / tag đã duyệt
git clone https://github.com/congminhnguyendoan-ops/smart-exam-grading.git
cd smart-exam-grading && git checkout <nhánh-hoặc-tag-đã-duyệt>
cd smart_exam_db

# 2) Cấu hình
cp .env.production.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"      # dán kết quả vào AUTH_SECRET
# Sửa .env: DATABASE_URL (cùng mật khẩu với POSTGRES_PASSWORD), POSTGRES_PASSWORD, AUTH_SECRET, PUBLIC_BASE_URL, PUBLIC_HOST.
# KHÔNG commit .env. Mật khẩu CSDL dùng ký tự chữ + số (ký tự đặc biệt trong DATABASE_URL phải mã hoá %xx).

# 3) Dựng image, bật CSDL TRƯỚC (app chưa bật)
docker compose build
docker compose up -d db                      # đợi: docker compose ps  -> db "healthy"

# 4) Khởi tạo CSDL (MỘT lần). KHÔNG có dữ liệu mẫu, KHÔNG có tài khoản mặc định. Chọn tên quản trị viên (không dùng "admin").
docker compose run --rm --no-deps app python tools/khoi_tao_db_san_xuat.py --ap-dung --tao-admin <tên_quản_trị>
#    -> 01–03 + migration 001–006 + mẫu phiếu chuẩn; in mật khẩu ngẫu nhiên MỘT lần. Chép ngay vào nơi an toàn.
#    ĐỪNG bật app trước bước này: backend CỐ Ý từ chối khởi động khi chưa có migration 006 (thấy trong log:
#    "Chưa áp migration 006 …"); container sẽ khởi động lại liên tục cho tới khi CSDL được khởi tạo.

# 4b) Danh sách thí sinh (xem mục 10: chưa có đường nhập qua web) – tối thiểu bảng students cần có SBD của thí sinh, vd:
docker compose exec -T db psql -U smart_exam_app -d smart_exam -c "INSERT INTO students (student_code, full_name) VALUES ('220001', 'Họ tên');"

# 4c) Bật ứng dụng + proxy
docker compose up -d app caddy
docker compose ps                  # app: healthy sau vài giây (đo: ~3 giây tới /health 200); caddy: running

# 5) Kiểm tra
curl -s https://<PUBLIC_HOST>/health            # {"status":"ok","db":"ok"}  (không có phiên bản / SHA mô hình)
curl -s -o /dev/null -w "%{http_code}\n" https://<PUBLIC_HOST>/docs          # 404
```

Mở `https://<PUBLIC_HOST>/` → đăng nhập bằng tài khoản vừa tạo (đã thử bằng `curl`; giao diện web trong container chưa mở bằng trình duyệt). Tạo tài khoản giáo viên / lớp / kỳ thi trong **Quản trị**.

Thử trước không ghi gì: `docker compose run --rm app python tools/khoi_tao_db_san_xuat.py --thu-schema-tam` (chạy toàn bộ trình tự trong schema tạm rồi ROLLBACK).
Xem trạng thái: `... khoi_tao_db_san_xuat.py` (không tham số = xem trước, chỉ đọc). Chạy lại `--ap-dung` an toàn: CSDL đã có bảng thì chỉ áp migration còn thiếu.
**Migration 006 (`revoked_tokens`) bắt buộc**: backend không khởi động khi `AUTH_MODE=on` mà thiếu bảng này.

## 3. Danh sách biến cấu hình

| Biến | Bắt buộc | Mặc định | Ghi chú |
|---|---|---|---|
| `MOI_TRUONG` | production: có | trống | `production` → từ chối khởi động nếu cấu hình không an toàn (dưới) |
| `DATABASE_URL` | **có** | — | `postgresql://smart_exam_app:<mật khẩu>@db:5432/smart_exam` |
| `AUTH_SECRET` | **có** | — | ≥ 32 ký tự; giá trị mẫu `DOI_…` bị từ chối |
| `AUTH_MODE` | production: `on` | `on` | `demo` bỏ đăng nhập – KHÔNG dùng công khai |
| `COOKIE_SECURE` | production: `1` | `0` | cookie chỉ đi qua HTTPS |
| `PUBLIC_BASE_URL` | nên | trống | `https://…` – in trong mã QR trang bìa kỳ thi |
| `PUBLIC_HOST` | compose | `localhost` | tên miền cho Caddy (không có `https://`) |
| `POSTGRES_PASSWORD` | compose | — | chỉ dùng lần ĐẦU khởi tạo volume PostgreSQL (xem mục 6) |
| `FORWARDED_ALLOW_IPS` | khi có proxy | trống | CIDR / IP được tin `X-Forwarded-For`; mẫu `172.28.0.0/24` = mạng compose. KHÔNG dùng `*` nếu cổng 8000 có thể tới trực tiếp từ ngoài |
| `DOCS_ENABLED` | không | `0` | `1` bật `/docs`, `/redoc`, `/openapi.json` (chỉ dev) |
| `HEALTH_CHI_TIET` | không | `0` | `1` thêm phiên bản + SHA mô hình vào `/health` (nội bộ / kiểm thử) |
| `MAX_UPLOAD_MB` | không | 25 | tối đa MỘT ảnh; vượt → 413, dừng đọc ngay |
| `MAX_ANH_MOI_LO` | không | 30 | số ảnh tối đa mỗi lô `/sheets/batch` (giao diện không dùng) |
| `MAX_DIEM_ANH` | không | 60 000 000 | số điểm ảnh tối đa (đọc từ tiêu đề); vượt → 422 |
| `CHAM_DONG_THOI`, `CHAM_CHO_GIAY` | không | 4, 30 | số ảnh chấm cùng lúc **theo từng tiến trình**; quá hạn chờ → 503 |
| `STORAGE_DIR` | không | `storage` (image: `/app/storage`) | thư mục ảnh phiếu = volume `storage` |
| `SESSION_HOURS` | không | 8 | hạn phiên đăng nhập |
| `ANH_XOA_TU_DONG`, `ANH_GIU_GIO`, `ANH_GIU_DEMO` | không | 0, 24, 1 | dọn ảnh tạm – để TẮT |
| `OMR_MODEL`, `OCR_MODEL` | không | `models/omr_m1.json`, `models/ocr_cnn.json` | có sẵn trong image |

**Production từ chối khởi động nếu**: `AUTH_MODE` ≠ `on`; `COOKIE_SECURE` ≠ 1; `AUTH_SECRET` < 32 ký tự hoặc còn là giá trị mẫu; `WEB_CONCURRENCY` > 1. Thông báo gom hết lỗi một lần và không in giá trị bí mật.
Không đặt `MOI_TRUONG` thì hành vi LAN / dev như cũ (không đổi).

## 4. Giới hạn tải lên (hai lớp)

1. **Caddy** (`deploy/Caddyfile`): 26 MB cho `POST /exams/{id}/sheets`, 200 MB cho `/sheets/batch`, 2 MB cho mọi đường dẫn khác.
2. **Ứng dụng** (`backend/kiem_anh.py`): từ chối 413 theo `Content-Length` hoặc khi đếm byte vượt (kể cả thân chunked); đọc từng đoạn 1 MB và dừng khi vượt `MAX_UPLOAD_MB`; nội dung phải đúng chữ ký JPEG / PNG / HEIC
   (không tin đuôi tệp) → 422; số điểm ảnh đọc từ tiêu đề, không giải mã (`MAX_DIEM_ANH`) → 422; lô quá `MAX_ANH_MOI_LO` ảnh → 413. Trong một lô, tệp hỏng chỉ báo lỗi riêng của tệp đó (`error`), không làm hỏng lô.

## 5. Sao lưu

```bash
mkdir -p backups
# CSDL (định dạng custom của pg_dump; mật khẩu không xuất hiện trên dòng lệnh)
docker compose exec -T db pg_dump -U smart_exam_app -Fc smart_exam > backups/smart_exam_$(date +%Y%m%d_%H%M%S).dump
# Ảnh phiếu (volume storage)
docker run --rm -v smart-exam_storage:/s -v "$PWD/backups":/b alpine tar czf /b/storage_$(date +%Y%m%d_%H%M%S).tgz -C /s .
```
Sao lưu CSDL và storage **cùng thời điểm** (CSDL lưu đường dẫn ảnh). Chép `backups/` ra ngoài máy chủ. Nên đặt lịch (cron) hằng ngày và thử khôi phục định kỳ. `.env` sao lưu riêng, ở nơi an toàn (không nằm cùng bản sao lưu ảnh).

## 6. Khôi phục và đổi mật khẩu CSDL

**Khôi phục** (ghi đè dữ liệu hiện có – chỉ làm khi đã chắc chắn):
```bash
docker compose stop app caddy
docker compose exec -T db pg_restore -U smart_exam_app -d smart_exam --clean --if-exists --no-owner < backups/smart_exam_<ngày>.dump
docker run --rm -v smart-exam_storage:/s -v "$PWD/backups":/b alpine sh -c "rm -rf /s/* && tar xzf /b/storage_<ngày>.tgz -C /s"
docker compose start app caddy
```
Trên máy mới: dựng theo mục 2 đến bước 3, **bỏ bước 4** (khởi tạo), rồi khôi phục như trên.

**Đổi mật khẩu CSDL** (`POSTGRES_PASSWORD` chỉ có tác dụng khi volume còn trống; đổi sau đó KHÔNG đổi mật khẩu thật):
```bash
docker compose exec db psql -U smart_exam_app -d smart_exam -c "ALTER ROLE smart_exam_app WITH PASSWORD '<mật khẩu mới>';"
# sửa DATABASE_URL và POSTGRES_PASSWORD trong .env cho khớp, rồi:
docker compose up -d app
```
Nếu mật khẩu CSDL đã từng nằm trong mã / lịch sử git (xem `docs/` báo cáo AT), **phải đổi** trước khi công khai.
Lưu ý: image `postgres` tạo `smart_exam_app` làm quyền cao nhất (superuser) của cụm. Nếu cần tách quyền, tạo một role ứng dụng riêng không có quyền superuser (chưa làm trong mẫu này).

## 7. Vì sao chỉ 1 worker

`auth.gioi_han` (khoá đăng nhập sai 5 lần / 15 phút) và `dong_thoi.CongCham` (giới hạn chấm đồng thời) nằm trong **bộ nhớ từng tiến trình**. N worker nhân giới hạn lên N lần (khoá đăng nhập thực tế 5 × N lần, chấm
cùng lúc 4 × N ảnh, RAM tăng tương ứng) và bộ đếm không chia sẻ. Dockerfile cố định `--workers 1`; `MOI_TRUONG=production` thêm từ chối khi `WEB_CONCURRENCY` > 1 (**không** bắt được cờ `--workers N` nếu bạn tự sửa lệnh khởi động).
Một worker đủ cho lớp học (thông lượng đo ở lệnh AH: ~2,7 ảnh/s bão hoà từ 4 yêu cầu đồng thời).

## 8. Cập nhật phiên bản

```bash
git pull && docker compose up -d --build
docker compose run --rm app python -m backend.migrate        # áp migration mới (an toàn chạy lại)
```
Sao lưu CSDL trước khi cập nhật.

## 9. Điều chưa kiểm / ước lượng

- Chưa thử: Linux + tên miền + Let's Encrypt; IP khách thật qua Internet; sao lưu / khôi phục bằng lệnh mục 5–6; Render thật (mục 12); giao diện web trong container bằng trình duyệt; Android.
- Số RAM / thời gian ở mục 11: **một lần đo mỗi ô**, một máy; `docker stats` lấy mẫu thưa nên dùng đỉnh cgroup, vẫn là n = 1. Không suy ra cho Render (mục 12).
- Dung lượng ảnh mỗi phiếu: ước lượng (~0,8 MB mỗi ảnh gốc + ảnh nắn + 9 ô chữ số); volume thử có 649 tệp sau các lần thử (gồm ảnh gốc, ảnh nắn, ô chữ số).
- Image dùng `python:3.14-slim` và `opencv-python-headless==5.0.0.93`: **ĐÃ build được** (lệnh AV) và cho điểm đúng bằng điểm kỳ vọng ở mọi phép thử.

## 10. Việc đã biết, CHƯA làm (ngoài phạm vi lệnh AU / AV)

| Việc | Hệ quả khi công khai |
|---|---|
| **Nhập danh sách thí sinh qua web** | Bản sạch KHÔNG có sinh viên và web không có chỗ nhập (bảng `students`). Chưa có sinh viên thì phiếu không ghép được SBD, không có điểm chính thức. Tạm thời nhập bằng SQL (bước 4b). **Phát hiện ở lệnh AV.** |
| Pool kết nối CSDL (AH #7) | mỗi yêu cầu mở một kết nối mới; tải cao tốn thời gian / kết nối |
| Rate limit toàn cục | chỉ có khoá đăng nhập theo (tên, IP) và giới hạn chấm; các API khác chưa giới hạn tần suất (Caddy chỉ giới hạn kích thước thân) |
| Batch cùng tệp (R2 không phủ `/sheets/batch`) | cùng một ảnh trong hai lô đồng thời có thể lỗi; giao diện không dùng endpoint này |
| Ép đổi mật khẩu lần đầu | không có; quản trị viên đầu tiên giữ mật khẩu ngẫu nhiên đến khi tự đổi (`python -m backend.tai_khoan dat-lai-mat-khau`) |
| Dọn `revoked_tokens` | bảng token đã thu hồi chỉ lớn lên; chưa có công cụ dọn |
| Khoá đăng nhập theo (tên, IP) trong bộ nhớ | mất khi khởi động lại; chỉ đúng với 1 worker |
| Tách role ứng dụng khỏi superuser PostgreSQL | mục 6 (image `postgres` tạo `smart_exam_app` là superuser) |
| Lỗi khởi động lặp khi CSDL chưa khởi tạo | app tự khởi động lại liên tục tới khi chạy bước 4 (cố ý, nhưng ồn log) |

## 11. Số liệu đo (lệnh AV, 17/11/2026)

**Máy**: Windows 11 Home, Docker Desktop 29.8.0 (Linux VM, 16 CPU, 7,6 GiB), mạng tải về ~250 kB/s. **Không phải Render, không phải máy chủ Linux thật.** Image `python:3.14-slim` + `opencv-python-headless==5.0.0.93`: **643 MB**.
Mỗi ô đo MỘT lần (n = 1), mỗi pha trên container VỪA tạo lại; số đo là **đỉnh cgroup** (`memory.peak`, gồm cả bộ nhớ đệm tệp).

| | `CHAM_DONG_THOI=1` | `CHAM_DONG_THOI=2` |
|---|---|---|
| Nghỉ (sau khởi động, chưa có yêu cầu) | 141 MiB | 141 MiB |
| Chấm 1 ảnh (0,7–0,8 s) | đỉnh 299 MiB | đỉnh 289 MiB |
| Lô 5 ảnh (1 yêu cầu `/batch`, ~3,1 s) | đỉnh 321 MiB | đỉnh 343 MiB |
| 5 ảnh gửi song song (5 yêu cầu, ~3 s; cả 5 trả 201) | đỉnh 453 MiB | đỉnh 529 MiB |
| Sau tải (nghỉ lại) | ~180–280 MiB (Python không trả hết bộ nhớ) | ~200–260 MiB |

- **Thời gian khởi động** tới `/health` 200 (qua Caddy, sau tạo lại container app): **3,0–3,2 s** (gồm nạp mô hình OMR + CNN sâu).
- **Ý nghĩa cho Render Starter (≈ 512 MB)**: đỉnh 300–345 MiB một mình đã chiếm phần lớn; 5 yêu cầu song song (453–529 MiB) **chạm hoặc vượt 512 MB**. Giao diện tải tối đa 2 ảnh song song (`m_hang_doi.js`), nhưng nhiều người dùng cùng lúc có thể đẩy cao hơn.
  Kết luận chắc chắn cần đo TRÊN Render; trước khi nhận người dùng thật, cân nhắc gói bộ nhớ lớn hơn.

## 12. Render (Blueprint `render.yaml` ở GỐC repo) – **CHƯA thử trên Render thật**

Render đã làm TLS + proxy ngược, nên **không dùng Caddy / docker-compose ở đây**: một web service Docker (Dockerfile của repo) + một PostgreSQL do Render quản lý + một đĩa bền cho ảnh.

1. Đẩy repo lên GitHub (kiểm công khai / riêng tư; **đổi mật khẩu CSDL cũ trong lịch sử trước nếu công khai**). Render Dashboard → New → **Blueprint** → chọn repo / nhánh đã duyệt.
2. `render.yaml` tạo: web `smart-exam` (Docker, gói **Starter**, `--workers 1`, đĩa bền gắn **`/app/storage`** = `STORAGE_DIR`, `healthCheckPath: /health`) và database `smart-exam-db`
   (`ipAllowList: []` = chỉ mạng nội bộ). Tên gói / vùng trong tệp có thể đã đổi trên Render: kiểm lại ở dashboard.
3. **Biến môi trường** (đã khai báo trong `render.yaml`; điền / kiểm ở Environment):

| Biến | Giá trị trên Render |
|---|---|
| `DATABASE_URL` | tự lấy từ database (`fromDatabase … connectionString`). Dạng `postgres://…` hay `postgresql://…` đều chạy với psycopg / libpq (có test; không cần chuẩn hoá) |
| `AUTH_SECRET` | `generateValue: true` (Render sinh chuỗi ngẫu nhiên; phải ≥ 32 ký tự – production tự kiểm) |
| `COOKIE_SECURE` | `1` |
| `PUBLIC_BASE_URL` | **điền sau lần deploy đầu**: `https://<tên-dịch-vụ>.onrender.com` (hoặc tên miền riêng) |
| `DOCS_ENABLED` / `HEALTH_CHI_TIET` | `0` / `0` |
| `MOI_TRUONG` | `production` |
| `CHAM_DONG_THOI` | `2` (xem cảnh báo RAM mục 11) |
| `WEB_CONCURRENCY` | `1` (production từ chối nếu > 1) |
| `PORT` | `8000` (khớp lệnh khởi động) |
| `STORAGE_DIR` | `/app/storage` (đĩa bền) |
| `FORWARDED_ALLOW_IPS` | `*` – xem dưới |

4. **Chạy không Caddy**: Render nhận HTTPS, chuyển HTTP→HTTPS, rồi gửi yêu cầu tới cổng `8000` của container kèm `X-Forwarded-For`. Giới hạn thân yêu cầu ở tầng proxy KHÔNG có (Caddy mất đi): chỉ còn lớp ứng dụng
   (`kiem_anh.py`: 413 theo `Content-Length`, dừng đọc ở `MAX_UPLOAD_MB`, `MAX_ANH_MOI_LO`, `MAX_DIEM_ANH`) – đủ chống tệp quá lớn nhưng yêu cầu thân lớn vẫn tới được ứng dụng.
5. **Lệnh khởi động cố định** `uvicorn backend.main:app --host 0.0.0.0 --port 8000 --proxy-headers --workers 1` (`dockerCommand`). **`preDeployCommand`** `python tools/khoi_tao_db_san_xuat.py --ap-dung` mỗi lần deploy:
   khởi tạo DB lần đầu (01–03 + migration + mẫu phiếu), các lần sau chỉ áp migration thiếu; KHÔNG tạo tài khoản. (Tính năng `preDeployCommand` cần gói trả phí.)
6. **Tạo admin đầu tiên + thí sinh**: Render Dashboard → service → **Shell** → `python tools/khoi_tao_db_san_xuat.py --ap-dung --tao-admin <tên>` (mật khẩu in một lần; chép ngay). Nhập thí sinh: mục 10 (hiện bằng SQL qua psql nối vào database Render – dùng
   "External connection" tạm thời hoặc Shell của dịch vụ database nếu có).
7. **`FORWARDED_ALLOW_IPS`** – **CHƯA kiểm**: dải IP của proxy Render không cố định, nên khuyến nghị dùng `*` (cổng ứng dụng của Render chỉ nhận từ proxy Render, không mở thẳng ra Internet). Rủi ro: dịch vụ khác cùng mạng nội bộ Render
   có thể gửi header giả mạo. Kiểm sau deploy: đăng nhập sai 5 lần từ MỘT mạng rồi đăng nhập từ mạng khác (4G): nếu máy thứ hai cũng bị khoá thì header không được dùng đúng (khoá theo IP của proxy).
8. **Chưa thử trên Render thật**: toàn bộ mục này (Blueprint, gói / tên gói, đĩa bền, `preDeployCommand`, health check, `FORWARDED_ALLOW_IPS`, RAM 512 MB của Starter).
