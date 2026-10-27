-- =====================================================================
--  Migration 003 (27/10/2026): ẢNH TẠM – ghi thời điểm ảnh của phiếu đã chốt bị xoá (backend/don_anh.py).
--  CHỈ THÊM một cột NULL + một chỉ mục một phần; KHÔNG sửa hay xoá dữ liệu cũ (mọi phiếu cũ: NULL = ảnh còn); chạy lại được (IF NOT EXISTS).
--  Backend cũ (tag ma-dot2-dong-bang-v3) bỏ qua cột mới nên vẫn chạy trên CSDL đã áp migration này.
--  Chạy:  python -m backend.migrate        (từ smart_exam_db/)
-- =====================================================================

ALTER TABLE answer_sheets ADD COLUMN IF NOT EXISTS image_deleted_at TIMESTAMPTZ NULL;

-- Việc dọn chỉ quét phiếu ĐÃ CHỐT (graded) hoặc BỊ TỪ CHỐI mà ảnh còn: chỉ mục một phần, nhỏ, theo mốc thời gian.
CREATE INDEX IF NOT EXISTS idx_sheets_anh_con_cho_don ON answer_sheets (updated_at)
    WHERE image_deleted_at IS NULL AND status IN ('graded', 'rejected');

COMMENT ON COLUMN answer_sheets.image_deleted_at IS 'Lúc ảnh gốc / ảnh nắn / ảnh ô viết tay bị xoá theo chính sách ảnh tạm (NULL = ảnh còn). Điểm, đáp án, lý do, image_hash giữ nguyên';
