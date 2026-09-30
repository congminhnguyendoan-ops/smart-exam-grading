#!/usr/bin/env bash
# Khởi tạo database Smart Exam (Linux/macOS)
set -e
cd "$(dirname "$0")"
psql -U postgres -v ON_ERROR_STOP=1 -f 00_create_database.sql
export PGPASSWORD=smartexam123
for f in 01_schema.sql 02_functions_triggers.sql 03_views.sql 04_seed.sql; do
  echo ">> $f"; psql -U smart_exam_app -h localhost -d smart_exam -v ON_ERROR_STOP=1 -q -f "$f" >/dev/null
done
psql -U smart_exam_app -h localhost -d smart_exam -v ON_ERROR_STOP=1 -f 05_demo_workflow.sql
