# Triển khai bản công khai (lệnh AU, 17/11/2026)

Từ một máy trắng (Linux có Docker) đến hệ thống chạy sau HTTPS. Cấu hình mẫu: `docker-compose.yml` (caddy → app → postgres:17), `deploy/Caddyfile`, `.env.production.example`.

> **Trạng thái kiểm chứng (đọc trước):** các tệp Docker / compose / Caddy **CHƯA BUILD THỬ** và **CHƯA CHẠY thật** (máy phát triển có Docker CLI nhưng engine không chạy; không có
> máy chủ + tên miền). Đã kiểm: `docker compose config` đọc được tệp compose; test tĩnh trong `tests/test_trien_khai.py`; logic ứng dụng (giới hạn tải, proxy, production) có test chạy thật.
> Lần dựng đầu tiên trên máy thật có thể lộ lỗi (phiên bản gói, tên miền, chứng chỉ). Hãy thử trên máy tạm trước khi nhận người dùng thật.

## 1. Yêu cầu

| | Tối thiểu | Khuyến nghị |
|---|---|---|
| RAM | **1 GB** (đặt `CHAM_DONG_THOI=2`) | 2 GB (mặc định `CHAM_DONG_THOI=4`) |
| Đĩa | 10 GB trống | 30 GB (ảnh phiếu khoảng 1,5–2 MB mỗi phiếu: 1 000 phiếu ≈ 2 GB; ước lượng, xem mục 9) |
| Mạng | cổng 80 và 443 mở ra Internet; DNS của tên miền trỏ về máy | |
| Phần mềm | Docker Engine + plugin Compose v2, `git` | |

**Về RAM** (đo trên máy phát triển Windows, một tiến trình, KHÔNG phải trong container Linux): import backend → ~90 MB; nạp mô hình OMR + CNN sâu → ~96 MB, mất ~0,3 s.
Mỗi ảnh đang chấm thêm khoảng 150 MB (lệnh AR); 4 ảnh cùng lúc ≈ 600 MB đỉnh. Cộng PostgreSQL (~100 MB) và Caddy (~30 MB): 1 GB chỉ đủ khi `CHAM_DONG_THOI=2`; từ 2 GB dùng mặc định.

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

# 3) Dựng và chạy
docker compose up -d --build
docker compose ps                  # db: healthy; app: healthy sau ~40 giây; caddy: running

# 4) Khởi tạo CSDL (MỘT lần). KHÔNG có dữ liệu mẫu, KHÔNG có tài khoản mặc định. Chọn tên quản trị viên (không dùng "admin").
docker compose run --rm app python tools/khoi_tao_db_san_xuat.py --ap-dung --tao-admin <tên_quản_trị>
#    -> in mật khẩu ngẫu nhiên MỘT lần. Chép ngay vào nơi an toàn.

# 5) Kiểm tra
curl -s https://<PUBLIC_HOST>/health            # {"status":"ok","db":"ok"}  (không có phiên bản / SHA mô hình)
curl -s -o /dev/null -w "%{http_code}\n" https://<PUBLIC_HOST>/docs          # 404
```

Mở `https://<PUBLIC_HOST>/` → đăng nhập bằng tài khoản vừa tạo. Tạo tài khoản giáo viên / lớp / kỳ thi trong **Quản trị**.

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

- Chưa build image, chưa chạy compose, chưa chạy Caddy, chưa thử HTTPS / chứng chỉ thật, chưa thử `X-Forwarded-For` qua Caddy thật (chỉ test bằng ASGI giả lập).
- RAM / thời gian khởi động đo trên Windows ngoài container (mục 1). Dung lượng ảnh mỗi phiếu là ước lượng từ bộ demo (~0,8 MB / ảnh gốc + ảnh nắn + 9 ô chữ số).
- Trang đăng nhập của giao diện còn liên kết `/docs` ("API (Swagger)"): khi `DOCS_ENABLED=0` liên kết đó trả 404 (không lỗi, chỉ cụt).
- Image dùng `python:3.14-slim` và `opencv-python-headless==5.0.0.93`; hai điều này suy từ môi trường phát triển và chưa xác nhận được bằng build.

## 10. Việc đã biết, CHƯA làm (ngoài phạm vi lệnh AU)

| Việc | Hệ quả khi công khai |
|---|---|
| Pool kết nối CSDL (AH #7) | mỗi yêu cầu mở một kết nối mới; tải cao tốn thời gian / kết nối |
| Rate limit toàn cục | chỉ có khoá đăng nhập theo (tên, IP) và giới hạn chấm; các API khác chưa giới hạn tần suất (Caddy chỉ giới hạn kích thước thân) |
| Batch cùng tệp (R2 không phủ `/sheets/batch`) | cùng một ảnh trong hai lô đồng thời có thể lỗi; giao diện không dùng endpoint này |
| Ép đổi mật khẩu lần đầu | không có; quản trị viên đầu tiên giữ mật khẩu ngẫu nhiên đến khi tự đổi (`python -m backend.tai_khoan dat-lai-mat-khau`) |
| Dọn `revoked_tokens` | bảng token đã thu hồi chỉ lớn lên; chưa có công cụ dọn (dòng quá hạn phiên có thể xoá tay) |
| Khoá đăng nhập theo (tên, IP) trong bộ nhớ | mất khi khởi động lại; chỉ đúng với 1 worker |
| Tách role ứng dụng khỏi superuser PostgreSQL | mục 6 |
