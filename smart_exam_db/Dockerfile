# Lệnh AU – T6. Build từ thư mục smart_exam_db/:  docker build -t smart-exam .
# Chạy qua docker-compose.yml (app + postgres + caddy). Chi tiết: docs/trien_khai_public.md
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Lớp phụ thuộc trước (cache khi chỉ đổi mã)
COPY requirements-prod.txt .
RUN pip install -r requirements-prod.txt

# Mã + mô hình (models/ocr_cnn.json, omr_m1.json) + mẫu định vị / layout / font. Loại trừ: xem .dockerignore (không có data/, storage/, .env*, tests/)
COPY . .

# Người dùng không phải root; storage/ là volume (ảnh phiếu)
RUN useradd --system --uid 10001 --home-dir /app app \
    && mkdir -p /app/storage \
    && chown -R app:app /app/storage
USER app

# MOI_TRUONG=production: backend TỪ CHỐI khởi động nếu AUTH_MODE != on, COOKIE_SECURE != 1, AUTH_SECRET < 32 ký tự (cấu hình qua biến / env_file, không nằm trong image)
ENV MOI_TRUONG=production \
    STORAGE_DIR=/app/storage

EXPOSE 8000

# /health chỉ trả trạng thái (HEALTH_CHI_TIET=0) và nối thử CSDL
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# 1 worker: bộ đếm khoá đăng nhập và giới hạn chấm đồng thời nằm trong bộ nhớ TỪNG tiến trình (docs/trien_khai_public.md mục 7)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--workers", "1"]
