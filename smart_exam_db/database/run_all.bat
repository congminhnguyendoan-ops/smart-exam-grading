@echo off
REM ===== Khởi tạo database Smart Exam trên Windows =====
REM Yêu cầu: đã cài PostgreSQL và thêm thư mục bin (VD: C:\Program Files\PostgreSQL\16\bin) vào PATH
chcp 65001 >nul
set PGCLIENTENCODING=UTF8

echo [1/6] Tao database va user...
psql -U postgres -v ON_ERROR_STOP=1 -f 00_create_database.sql || goto :err

set PGPASSWORD=smartexam123
echo [2/6] Tao bang...
psql -U smart_exam_app -h localhost -d smart_exam -v ON_ERROR_STOP=1 -q -f 01_schema.sql || goto :err
echo [3/6] Tao function/trigger...
psql -U smart_exam_app -h localhost -d smart_exam -v ON_ERROR_STOP=1 -q -f 02_functions_triggers.sql || goto :err
echo [4/6] Tao view...
psql -U smart_exam_app -h localhost -d smart_exam -v ON_ERROR_STOP=1 -q -f 03_views.sql || goto :err
echo [5/6] Nap du lieu mau...
psql -U smart_exam_app -h localhost -d smart_exam -v ON_ERROR_STOP=1 -q -f 04_seed.sql >nul || goto :err
echo [6/6] Chay demo luong cham diem...
psql -U smart_exam_app -h localhost -d smart_exam -v ON_ERROR_STOP=1 -f 05_demo_workflow.sql || goto :err
echo.
echo HOAN TAT!
pause
exit /b 0

:err
echo.
echo *** CO LOI - xem thong bao phia tren ***
pause
exit /b 1
