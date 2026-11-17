#!/usr/bin/env bash
# Khởi tạo database Smart Exam (Linux/macOS)
# Mật khẩu của smart_exam_app: biến môi trường SMART_EXAM_DB_PASSWORD, hoặc dòng SMART_EXAM_DB_PASSWORD=... trong smart_exam_db/.env
# (.env nằm trong .gitignore). Thiếu thì DỪNG trước mọi lệnh psql – không có mật khẩu mặc định.
set -e
cd "$(dirname "$0")"
if [ -z "${SMART_EXAM_DB_PASSWORD:-}" ] && [ -f ../.env ]; then
  SMART_EXAM_DB_PASSWORD="$(sed -n 's/^SMART_EXAM_DB_PASSWORD=//p' ../.env | tail -n 1 | tr -d '\r')"
fi
if [ -z "${SMART_EXAM_DB_PASSWORD:-}" ]; then
  echo "LỖI: chưa có mật khẩu CSDL. Đặt biến môi trường SMART_EXAM_DB_PASSWORD hoặc thêm dòng SMART_EXAM_DB_PASSWORD=... vào smart_exam_db/.env rồi chạy lại. Chưa chạy lệnh nào." >&2
  exit 1
fi
psql -U postgres -v ON_ERROR_STOP=1 -v app_password="$SMART_EXAM_DB_PASSWORD" -f 00_create_database.sql
export PGPASSWORD="$SMART_EXAM_DB_PASSWORD"
for f in 01_schema.sql 02_functions_triggers.sql 03_views.sql 04_seed.sql; do
  echo ">> $f"; psql -U smart_exam_app -h localhost -d smart_exam -v ON_ERROR_STOP=1 -q -f "$f" >/dev/null
done
psql -U smart_exam_app -h localhost -d smart_exam -v ON_ERROR_STOP=1 -f 05_demo_workflow.sql
