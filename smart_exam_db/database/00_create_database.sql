-- Chạy bằng tài khoản postgres (mật khẩu của smart_exam_app truyền qua biến psql app_password, KHÔNG ghi trong tệp này):
--   psql -U postgres -v ON_ERROR_STOP=1 -v app_password="<mật khẩu>" -f 00_create_database.sql
-- run_all.bat / run_all.sh tự truyền giá trị của SMART_EXAM_DB_PASSWORD (biến môi trường hoặc dòng SMART_EXAM_DB_PASSWORD= trong smart_exam_db/.env).
-- Tạo user riêng cho ứng dụng + database UTF8 (hỗ trợ tiếng Việt). Role đã có thì GIỮ NGUYÊN mật khẩu cũ (không đổi mật khẩu CSDL đang chạy).

-- Chốt: thiếu mật khẩu thì DỪNG TRƯỚC khi xoá / tạo gì (không có giá trị mặc định).
\if :{?app_password}
\else
DO $$ BEGIN RAISE EXCEPTION 'LỖI: thiếu mật khẩu cho smart_exam_app. Đặt SMART_EXAM_DB_PASSWORD (biến môi trường hoặc trong smart_exam_db/.env) rồi chạy lại run_all, hoặc gọi psql với -v app_password=...'; END $$;
\endif
SELECT CASE WHEN length(:'app_password') = 0 THEN 1 / 0 END AS mat_khau_rong_thi_dung;   -- mật khẩu rỗng: lỗi chia cho 0 -> ON_ERROR_STOP dừng

DROP DATABASE IF EXISTS smart_exam;
SELECT format('CREATE ROLE smart_exam_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'smart_exam_app') \gexec

CREATE DATABASE smart_exam
    OWNER smart_exam_app
    ENCODING 'UTF8'
    TEMPLATE template0;
