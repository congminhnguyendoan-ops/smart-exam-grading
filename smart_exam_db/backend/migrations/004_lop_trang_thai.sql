-- =====================================================================
--  Migration 004 (29/10/2026, lệnh I): TRẠNG THÁI của lớp (vô hiệu hoá / kích hoạt lại ở trang Quản trị → Lớp học).
--  CHỈ THÊM một cột có giá trị mặc định; KHÔNG sửa hay xoá dữ liệu cũ; chạy lại được (IF NOT EXISTS).
--  Mọi lớp đang có -> is_active = TRUE (hành vi không đổi). Quan hệ giáo viên – lớp (teacher_classes, migration 002) đã là
--  nhiều – nhiều nên KHÔNG đổi. Backend cũ (tag ma-dot2-dong-bang-v3, lệnh H) không đọc cột này nên vẫn chạy trên CSDL đã áp.
--  Chạy:  python -m backend.migrate        (từ smart_exam_db/) – sao lưu CSDL trước khi áp.
-- =====================================================================

ALTER TABLE classes ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN classes.is_active IS 'FALSE = lớp đã vô hiệu hoá: không chọn được cho kỳ thi mới / gán giáo viên mới; giáo viên đã gán vẫn xem được kỳ thi cũ của lớp';
