-- =====================================================================
--  Migration 006 (16/11/2026, lệnh AR – R4): THU HỒI TOKEN KHI ĐĂNG XUẤT.
--  CHỈ THÊM một bảng mới + một chỉ mục; KHÔNG sửa hay xoá bảng / dữ liệu cũ; chạy lại được (IF NOT EXISTS).
--  Phiên là token ký HMAC không trạng thái (backend/auth.py). Đăng xuất ghi BĂM SHA-256 của token (không lưu token thô) vào bảng này;
--  mỗi yêu cầu có xác thực tra bảng: token có trong bảng -> 401. Phiên KHÁC của cùng tài khoản (token khác) không bị ảnh hưởng.
--  expires_at = hạn của token: dòng quá hạn vô hại (token đã hết hạn tự 401) và có thể dọn sau.
--  Xoá tài khoản thì dòng thu hồi của tài khoản đó bị xoá theo (ON DELETE CASCADE).
--  Backend từ lệnh AR trở đi ĐÒI bảng này khi AUTH_MODE=on (thiếu thì không khởi động: lỗi rõ ràng, không "mở" im lặng).
--  Chạy:  python -m backend.migrate        (từ smart_exam_db/) – sao lưu CSDL trước khi áp.
-- =====================================================================

CREATE TABLE IF NOT EXISTS revoked_tokens (
    token_sha256  CHAR(64)     PRIMARY KEY,
    user_id       BIGINT       NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    revoked_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ  NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_revoked_tokens_user ON revoked_tokens (user_id);

COMMENT ON TABLE revoked_tokens IS 'Token phiên đã bị thu hồi khi đăng xuất (lệnh AR – R4). Chỉ lưu băm SHA-256, không lưu token thô.';
