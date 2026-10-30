-- =====================================================================
--  Migration 002 (29/10/2026): LỚP của kỳ thi + quan hệ GIÁO VIÊN – LỚP (phân quyền theo lớp).
--  CHỈ THÊM cột / bảng / chỉ mục; KHÔNG sửa hay xoá dữ liệu cũ; chạy lại được (IF NOT EXISTS).
--  Backend cũ (tag ma-dot2-dong-bang-v3) bỏ qua cột / bảng mới nên vẫn chạy trên CSDL đã áp migration này.
--  Chạy:  python -m backend.migrate        (từ smart_exam_db/)
-- =====================================================================

-- Kỳ thi thuộc một lớp (TUỲ CHỌN: kỳ thi cũ không có lớp vẫn hiện cho người tạo)
ALTER TABLE exams ADD COLUMN IF NOT EXISTS class_id BIGINT NULL REFERENCES classes(class_id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_exams_class      ON exams (class_id);
CREATE INDEX IF NOT EXISTS idx_exams_created_by ON exams (created_by);

-- Giáo viên phụ trách lớp: một GV nhiều lớp, một lớp nhiều GV; môn GV dạy ở lớp đó là tuỳ chọn
CREATE TABLE IF NOT EXISTS teacher_classes (
    user_id     BIGINT      NOT NULL REFERENCES users(user_id)       ON DELETE CASCADE,
    class_id    BIGINT      NOT NULL REFERENCES classes(class_id)    ON DELETE CASCADE,
    subject_id  BIGINT      NULL     REFERENCES subjects(subject_id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, class_id)
);
CREATE INDEX IF NOT EXISTS idx_teacher_classes_class ON teacher_classes (class_id);

COMMENT ON COLUMN exams.class_id IS 'Lớp của kỳ thi (NULL = kỳ thi không gắn lớp; chỉ người tạo thấy). Giáo viên chỉ thấy kỳ thi thuộc lớp mình dạy hoặc do mình tạo';
COMMENT ON TABLE  teacher_classes IS 'Giáo viên phụ trách lớp (phân quyền): chỉ xem lớp / sinh viên / kỳ thi của lớp mình; admin xem tất cả';
