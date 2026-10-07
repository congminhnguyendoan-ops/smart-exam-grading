-- =====================================================================
--  Migration 001 (07/10/2026): cột BỔ SUNG cho backend chấm phiếu. Chỉ thêm, không xoá / sửa cột cũ; chạy lại được.
--  Chạy:  python -m backend.migrate        (từ smart_exam_db/)
-- =====================================================================

-- Từng câu: kết quả "cần xem" của OMR (không bao giờ chấm như câu chắc chắn) + vết giáo viên sửa
ALTER TABLE sheet_answers ADD COLUMN IF NOT EXISTS needs_review         BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE sheet_answers ADD COLUMN IF NOT EXISTS review_reasons       TEXT[]  NOT NULL DEFAULT '{}';
ALTER TABLE sheet_answers ADD COLUMN IF NOT EXISTS omr_state            bubble_state;       -- máy đọc ban đầu (state có thể bị giáo viên sửa)
ALTER TABLE sheet_answers ADD COLUMN IF NOT EXISTS omr_selected_options VARCHAR(6);
ALTER TABLE sheet_answers ADD COLUMN IF NOT EXISTS reviewed_by          BIGINT REFERENCES users(user_id);
ALTER TABLE sheet_answers ADD COLUMN IF NOT EXISTS reviewed_at          TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_sheet_answers_pending ON sheet_answers (sheet_id) WHERE needs_review;

-- Từng phiếu: ảnh bị từ chối (mã lý do của cv_engine.preprocessing.MA_LY_DO; thông báo nằm ở error_message),
-- chi tiết OMR (cột SBD / mã đề, độ dịch định vị, nguồn ảnh, phiên bản mô hình), tên file gốc
ALTER TABLE answer_sheets ADD COLUMN IF NOT EXISTS reject_code       VARCHAR(40);
ALTER TABLE answer_sheets ADD COLUMN IF NOT EXISTS omr_detail        JSONB;
ALTER TABLE answer_sheets ADD COLUMN IF NOT EXISTS original_filename VARCHAR(255);
CREATE INDEX IF NOT EXISTS idx_answer_sheets_reject ON answer_sheets (exam_id) WHERE reject_code IS NOT NULL;

COMMENT ON COLUMN sheet_answers.needs_review IS 'OMR gắn "cần xem" (mờ / nhiều ô / lưng chừng / vị trí): chưa chấm, chờ giáo viên';
COMMENT ON COLUMN answer_sheets.reject_code  IS 'Mã từ chối của preprocess() (anh_mo, thieu_marker, ...); status = rejected';
COMMENT ON COLUMN answer_sheets.raw_score    IS 'Khi status = needs_review: điểm TẠM chỉ tính câu chắc chắn; điểm chính thức nằm ở results';
