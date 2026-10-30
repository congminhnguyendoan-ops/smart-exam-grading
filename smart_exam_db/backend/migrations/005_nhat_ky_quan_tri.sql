-- =====================================================================
--  Migration 005 (30/10/2026, lệnh V4): NHẬT KÝ THAO TÁC QUẢN TRỊ (trang Quản trị → Nhật ký, API GET /admin/audit).
--  CHỈ THÊM một bảng mới + một chỉ mục; KHÔNG sửa hay xoá bảng / dữ liệu cũ; chạy lại được (IF NOT EXISTS).
--  Backend cũ (trước lệnh V) không đọc / ghi bảng này nên vẫn chạy được trên CSDL đã áp.
--  Một dòng = một thao tác quản trị THÀNH CÔNG (kỳ thi / tài khoản giáo viên / lớp), ghi trong CÙNG giao dịch với thay đổi.
--  details: JSON mô tả (tên, mã, giá trị cũ → mới) – KHÔNG BAO GIỜ chứa mật khẩu, mã băm mật khẩu hay token (backend/nhat_ky.py lọc thêm một lớp).
--  Chạy:  python -m backend.migrate        (từ smart_exam_db/) – sao lưu CSDL trước khi áp.
-- =====================================================================

CREATE TABLE IF NOT EXISTS admin_audit_log (
    log_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    actor_user_id  BIGINT       REFERENCES users(user_id) ON DELETE SET NULL,   -- người thao tác (admin); xoá tài khoản thì giữ dòng nhật ký
    action         VARCHAR(40)  NOT NULL,
    object_type    VARCHAR(20)  NOT NULL CHECK (object_type IN ('exam', 'user', 'class')),
    object_id      BIGINT,                                                       -- không FK: đối tượng có thể đã bị xoá (xoá kỳ thi / lớp)
    details        JSONB        NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_moi ON admin_audit_log (created_at DESC, log_id DESC);

COMMENT ON TABLE admin_audit_log IS 'Nhật ký thao tác quản trị thành công (lệnh V4). Không chứa mật khẩu / token.';
