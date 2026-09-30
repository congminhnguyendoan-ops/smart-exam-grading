-- Chạy bằng tài khoản postgres:  psql -U postgres -f 00_create_database.sql
-- Tạo user riêng cho ứng dụng + database UTF8 (hỗ trợ tiếng Việt)
-- ĐỔI mật khẩu 'smartexam123' trước khi dùng thật!

DROP DATABASE IF EXISTS smart_exam;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smart_exam_app') THEN
        CREATE ROLE smart_exam_app LOGIN PASSWORD 'smartexam123';
    END IF;
END $$;

CREATE DATABASE smart_exam
    OWNER smart_exam_app
    ENCODING 'UTF8'
    TEMPLATE template0;
