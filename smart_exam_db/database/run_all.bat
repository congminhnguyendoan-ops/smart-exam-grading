@echo off
REM ===== Khởi tạo database Smart Exam trên Windows =====
REM Yêu cầu: đã cài PostgreSQL và thêm thư mục bin (VD: C:\Program Files\PostgreSQL\17\bin) vào PATH
REM Mật khẩu của smart_exam_app: biến môi trường SMART_EXAM_DB_PASSWORD, hoặc dòng SMART_EXAM_DB_PASSWORD=... trong smart_exam_db\.env
REM (.env nằm trong .gitignore). Thiếu thì DỪNG trước mọi lệnh psql – không có mật khẩu mặc định.
chcp 65001 >nul
set PGCLIENTENCODING=UTF8

if not defined SMART_EXAM_DB_PASSWORD if exist "%~dp0..\.env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%~dp0..\.env") do if /i "%%a"=="SMART_EXAM_DB_PASSWORD" set "SMART_EXAM_DB_PASSWORD=%%b"
)
if not defined SMART_EXAM_DB_PASSWORD (
    echo *** LOI: chua co mat khau CSDL. Dat bien moi truong SMART_EXAM_DB_PASSWORD
    echo     hoac them dong SMART_EXAM_DB_PASSWORD=... vao smart_exam_db\.env roi chay lai. Chua chay lenh nao.
    exit /b 1
)

echo [1/6] Tao database va user...
psql -U postgres -v ON_ERROR_STOP=1 -v app_password="%SMART_EXAM_DB_PASSWORD%" -f 00_create_database.sql || goto :err

set "PGPASSWORD=%SMART_EXAM_DB_PASSWORD%"
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
