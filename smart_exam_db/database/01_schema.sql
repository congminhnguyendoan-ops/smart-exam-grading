-- =====================================================================
--  SMART EXAM GRADING SYSTEM - PostgreSQL 14+ (đã test trên 16)
--  File 01: Schema (kiểu dữ liệu, bảng, ràng buộc, index)
--  Chạy:  psql -U postgres -d smart_exam -f 01_schema.sql
-- =====================================================================

SET client_encoding = 'UTF8';

-- ---------------------------------------------------------------------
-- 0. KIỂU LIỆT KÊ (ENUM)
-- ---------------------------------------------------------------------
CREATE TYPE user_role        AS ENUM ('admin', 'teacher', 'student');
CREATE TYPE exam_status      AS ENUM ('draft', 'published', 'grading', 'closed');
CREATE TYPE bubble_state     AS ENUM ('blank', 'filled', 'faint', 'multiple');   -- 4 lớp của OMR classifier
CREATE TYPE sheet_status     AS ENUM ('uploaded', 'processing', 'processed', 'graded', 'needs_review', 'rejected', 'error');
CREATE TYPE result_status    AS ENUM ('auto', 'confirmed', 'manual_edited', 'void');
CREATE TYPE review_reason    AS ENUM ('sbd_not_found', 'low_ocr_confidence', 'low_omr_confidence',
                                      'exam_code_not_found', 'duplicate_sbd', 'multiple_marks',
                                      'poor_image_quality', 'other');
CREATE TYPE review_status    AS ENUM ('pending', 'in_progress', 'resolved', 'rejected');
CREATE TYPE model_type       AS ENUM ('omr_classifier', 'ocr_digit');
CREATE TYPE ocr_field        AS ENUM ('sbd', 'exam_code');
CREATE TYPE import_status    AS ENUM ('pending', 'success', 'partial', 'failed');

-- ---------------------------------------------------------------------
-- 1. USERS - tài khoản đăng nhập (Admin / Giáo viên / Sinh viên)
-- ---------------------------------------------------------------------
CREATE TABLE users (
    user_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username       VARCHAR(50)  NOT NULL,
    email          VARCHAR(255) NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,              -- bcrypt/argon2 do backend tạo, KHÔNG lưu plain text
    full_name      VARCHAR(150) NOT NULL,
    role           user_role    NOT NULL DEFAULT 'teacher',
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    last_login_at  TIMESTAMPTZ,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT chk_users_email CHECK (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$')
);
CREATE UNIQUE INDEX uq_users_username ON users (lower(username));
CREATE UNIQUE INDEX uq_users_email    ON users (lower(email));

-- ---------------------------------------------------------------------
-- 2. CLASSES - lớp sinh hoạt
-- ---------------------------------------------------------------------
CREATE TABLE classes (
    class_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    class_code   VARCHAR(30)  NOT NULL UNIQUE,          -- VD: CNTT-K20A
    class_name   VARCHAR(150) NOT NULL,
    academic_year VARCHAR(20),                          -- VD: 2026-2027
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 3. STUDENTS - danh sách sinh viên gốc (import trước kỳ thi)
--    student_code chính là SBD được OCR đọc ra từ phiếu
-- ---------------------------------------------------------------------
CREATE TABLE students (
    student_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_code  VARCHAR(20)  NOT NULL UNIQUE,         -- SBD / MSSV, chỉ chứa chữ số
    full_name     VARCHAR(150) NOT NULL,
    date_of_birth DATE,
    gender        VARCHAR(10),
    email         VARCHAR(255),
    class_id      BIGINT REFERENCES classes(class_id) ON DELETE SET NULL,
    user_id       BIGINT UNIQUE REFERENCES users(user_id) ON DELETE SET NULL, -- tài khoản để SV tra cứu điểm
    import_id     BIGINT,                               -- FK thêm sau (student_imports)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_student_code_digits CHECK (student_code ~ '^[0-9]{4,20}$')
);
CREATE INDEX idx_students_class ON students (class_id);
CREATE INDEX idx_students_name  ON students (lower(full_name));

-- ---------------------------------------------------------------------
-- 4. STUDENT_IMPORTS - lịch sử import file Excel/CSV danh sách SV
-- ---------------------------------------------------------------------
CREATE TABLE student_imports (
    import_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_name      VARCHAR(255) NOT NULL,
    imported_by    BIGINT NOT NULL REFERENCES users(user_id),
    exam_id        BIGINT,                              -- import kèm đăng ký vào kỳ thi (tuỳ chọn), FK thêm sau
    total_rows     INT NOT NULL DEFAULT 0,
    success_rows   INT NOT NULL DEFAULT 0,
    failed_rows    INT NOT NULL DEFAULT 0,
    error_details  JSONB,                               -- [{row: 5, error: "SBD trùng"}]
    status         import_status NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE students ADD CONSTRAINT fk_students_import
    FOREIGN KEY (import_id) REFERENCES student_imports(import_id) ON DELETE SET NULL;

-- ---------------------------------------------------------------------
-- 5. SUBJECTS - môn học
-- ---------------------------------------------------------------------
CREATE TABLE subjects (
    subject_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_code  VARCHAR(20)  NOT NULL UNIQUE,
    subject_name  VARCHAR(150) NOT NULL,
    credits       SMALLINT CHECK (credits BETWEEN 0 AND 20),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 6. SHEET_TEMPLATES - mẫu phiếu trả lời (bố cục để OpenCV cắt ROI)
-- ---------------------------------------------------------------------
CREATE TABLE sheet_templates (
    template_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    template_name      VARCHAR(100) NOT NULL UNIQUE,
    num_questions      SMALLINT NOT NULL CHECK (num_questions BETWEEN 1 AND 200),
    options_per_question SMALLINT NOT NULL DEFAULT 4 CHECK (options_per_question BETWEEN 2 AND 6),
    sbd_digits         SMALLINT NOT NULL DEFAULT 6 CHECK (sbd_digits BETWEEN 4 AND 20),
    exam_code_digits   SMALLINT NOT NULL DEFAULT 3 CHECK (exam_code_digits BETWEEN 1 AND 6),
    page_width_px      INT,
    page_height_px     INT,
    layout_config      JSONB NOT NULL DEFAULT '{}'::jsonb,  -- toạ độ vùng SBD, mã đề, lưới câu hỏi...
    pdf_path           VARCHAR(500),                        -- file PDF phiếu trắng sinh ra
    created_by         BIGINT REFERENCES users(user_id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 7. EXAMS - kỳ thi / đề thi gốc
-- ---------------------------------------------------------------------
CREATE TABLE exams (
    exam_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_title     VARCHAR(200) NOT NULL,
    subject_id     BIGINT NOT NULL REFERENCES subjects(subject_id),
    template_id    BIGINT NOT NULL REFERENCES sheet_templates(template_id),
    exam_date      DATE,
    duration_min   SMALLINT CHECK (duration_min > 0),
    num_questions  SMALLINT NOT NULL CHECK (num_questions > 0),
    max_score      NUMERIC(5,2) NOT NULL DEFAULT 10 CHECK (max_score > 0),
    pass_score     NUMERIC(5,2) NOT NULL DEFAULT 5,
    status         exam_status NOT NULL DEFAULT 'draft',
    created_by     BIGINT NOT NULL REFERENCES users(user_id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_pass_le_max CHECK (pass_score <= max_score)
);
CREATE INDEX idx_exams_subject ON exams (subject_id);
CREATE INDEX idx_exams_status  ON exams (status);

ALTER TABLE student_imports ADD CONSTRAINT fk_imports_exam
    FOREIGN KEY (exam_id) REFERENCES exams(exam_id) ON DELETE SET NULL;

-- ---------------------------------------------------------------------
-- 8. EXAM_STUDENTS - danh sách SV dự thi của từng kỳ thi (roster)
--    => match SBD chỉ trong phạm vi SV được đăng ký thi
-- ---------------------------------------------------------------------
CREATE TABLE exam_students (
    exam_id      BIGINT NOT NULL REFERENCES exams(exam_id) ON DELETE CASCADE,
    student_id   BIGINT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    room         VARCHAR(30),
    seat_no      SMALLINT,
    is_absent    BOOLEAN NOT NULL DEFAULT FALSE,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (exam_id, student_id)
);
CREATE INDEX idx_exam_students_student ON exam_students (student_id);

-- ---------------------------------------------------------------------
-- 9. QUESTIONS - câu hỏi gốc của đề (thứ tự gốc, dùng để đảo mã đề
--    và thống kê độ khó theo câu gốc)
-- ---------------------------------------------------------------------
CREATE TABLE questions (
    question_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_id          BIGINT NOT NULL REFERENCES exams(exam_id) ON DELETE CASCADE,
    original_no      SMALLINT NOT NULL CHECK (original_no > 0),
    content          TEXT,
    options          JSONB,                            -- {"A":"...", "B":"...", ...}
    correct_option   CHAR(1) NOT NULL CHECK (correct_option IN ('A','B','C','D','E','F')),
    topic            VARCHAR(100),
    UNIQUE (exam_id, original_no)
);

-- ---------------------------------------------------------------------
-- 10. EXAM_CODES - mã đề (101, 102, ...) sinh ra bằng cách đảo câu/đáp án
-- ---------------------------------------------------------------------
CREATE TABLE exam_codes (
    exam_code_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_id        BIGINT NOT NULL REFERENCES exams(exam_id) ON DELETE CASCADE,
    code           VARCHAR(10) NOT NULL CHECK (code ~ '^[0-9]{1,6}$'),
    shuffle_seed   INT,                                -- seed dùng khi đảo, để tái tạo
    pdf_path       VARCHAR(500),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (exam_id, code)
);

-- ---------------------------------------------------------------------
-- 11. ANSWER_KEYS - đáp án theo từng mã đề
-- ---------------------------------------------------------------------
CREATE TABLE answer_keys (
    answer_key_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_code_id   BIGINT NOT NULL REFERENCES exam_codes(exam_code_id) ON DELETE CASCADE,
    question_no    SMALLINT NOT NULL CHECK (question_no > 0),     -- số thứ tự câu trên phiếu của mã đề này
    question_id    BIGINT REFERENCES questions(question_id) ON DELETE SET NULL, -- ánh xạ về câu gốc
    correct_option CHAR(1) NOT NULL CHECK (correct_option IN ('A','B','C','D','E','F')),
    points         NUMERIC(6,3),                       -- NULL => chia đều max_score / num_questions
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (exam_code_id, question_no)
);

-- ---------------------------------------------------------------------
-- 12. ML_MODELS - quản lý phiên bản model (OMR classifier, OCR CNN)
-- ---------------------------------------------------------------------
CREATE TABLE ml_models (
    model_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_name     VARCHAR(100) NOT NULL,
    model_type     model_type   NOT NULL,
    version        VARCHAR(30)  NOT NULL,
    framework      VARCHAR(50),                        -- keras, sklearn...
    file_path      VARCHAR(500) NOT NULL,              -- models/ocr_digit_v2.keras
    train_dataset  VARCHAR(200),                       -- MNIST, EMNIST, real_digits_v1...
    metrics        JSONB NOT NULL DEFAULT '{}'::jsonb, -- {"acc_mnist":0.99,"acc_real":0.93,"f1":...}
    is_active      BOOLEAN NOT NULL DEFAULT FALSE,
    notes          TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_type, version)
);
-- Mỗi loại model chỉ có tối đa 1 bản đang active
CREATE UNIQUE INDEX uq_ml_models_active ON ml_models (model_type) WHERE is_active;

-- ---------------------------------------------------------------------
-- 13. SCAN_BATCHES - một lần upload nhiều ảnh phiếu
-- ---------------------------------------------------------------------
CREATE TABLE scan_batches (
    batch_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_id       BIGINT NOT NULL REFERENCES exams(exam_id) ON DELETE CASCADE,
    uploaded_by   BIGINT NOT NULL REFERENCES users(user_id),
    total_sheets  INT NOT NULL DEFAULT 0,
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 14. ANSWER_SHEETS - từng ảnh phiếu trả lời + kết quả nhận diện
-- ---------------------------------------------------------------------
CREATE TABLE answer_sheets (
    sheet_id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_id             BIGINT NOT NULL REFERENCES exams(exam_id) ON DELETE CASCADE,
    batch_id            BIGINT REFERENCES scan_batches(batch_id) ON DELETE SET NULL,
    image_path          VARCHAR(500) NOT NULL,
    aligned_image_path  VARCHAR(500),                  -- ảnh sau perspective transform
    image_hash          CHAR(64),                      -- SHA-256, phát hiện upload trùng ảnh
    blur_score          NUMERIC(10,2),                 -- Laplacian variance
    -- Kết quả OCR
    detected_sbd        VARCHAR(20),
    sbd_confidence      NUMERIC(5,4) CHECK (sbd_confidence BETWEEN 0 AND 1),
    detected_exam_code  VARCHAR(10),
    exam_code_confidence NUMERIC(5,4) CHECK (exam_code_confidence BETWEEN 0 AND 1),
    exam_code_id        BIGINT REFERENCES exam_codes(exam_code_id),
    -- Kết quả match SBD
    matched_student_id  BIGINT REFERENCES students(student_id),
    -- Kết quả chấm sơ bộ (kể cả khi chưa ghi vào results)
    num_correct         SMALLINT,
    raw_score           NUMERIC(6,3),
    -- Model đã dùng
    omr_model_id        BIGINT REFERENCES ml_models(model_id),
    ocr_model_id        BIGINT REFERENCES ml_models(model_id),
    processing_time_ms  INT,
    status              sheet_status NOT NULL DEFAULT 'uploaded',
    error_message       TEXT,
    uploaded_by         BIGINT REFERENCES users(user_id),
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at        TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sheets_exam_status ON answer_sheets (exam_id, status);
CREATE INDEX idx_sheets_batch       ON answer_sheets (batch_id);
CREATE INDEX idx_sheets_sbd         ON answer_sheets (exam_id, detected_sbd);
CREATE UNIQUE INDEX uq_sheets_image_hash ON answer_sheets (exam_id, image_hash) WHERE image_hash IS NOT NULL;

-- ---------------------------------------------------------------------
-- 15. SHEET_ANSWERS - kết quả OMR classifier cho từng câu
-- ---------------------------------------------------------------------
CREATE TABLE sheet_answers (
    sheet_id         BIGINT NOT NULL REFERENCES answer_sheets(sheet_id) ON DELETE CASCADE,
    question_no      SMALLINT NOT NULL CHECK (question_no > 0),
    state            bubble_state NOT NULL,
    selected_options VARCHAR(6) NOT NULL DEFAULT '',   -- '' | 'A' | 'AC' (khi multiple)
    confidence       NUMERIC(5,4) CHECK (confidence BETWEEN 0 AND 1),
    option_probs     JSONB,                            -- {"A":0.02,"B":0.95,...} xác suất từng ô
    is_correct       BOOLEAN,                          -- được tính bởi fn_grade_sheet
    manually_edited  BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (sheet_id, question_no),
    CONSTRAINT chk_selected_fmt CHECK (selected_options ~ '^[A-F]{0,6}$')
);

-- ---------------------------------------------------------------------
-- 16. OCR_DIGITS - dự đoán từng chữ số (SBD / mã đề) của CNN
--     => dùng làm dữ liệu fine-tune khi giáo viên sửa (corrected_digit)
-- ---------------------------------------------------------------------
CREATE TABLE ocr_digits (
    ocr_digit_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sheet_id         BIGINT NOT NULL REFERENCES answer_sheets(sheet_id) ON DELETE CASCADE,
    field            ocr_field NOT NULL,
    position         SMALLINT NOT NULL CHECK (position >= 0),
    predicted_digit  CHAR(1) CHECK (predicted_digit ~ '^[0-9]$'),
    confidence       NUMERIC(5,4) CHECK (confidence BETWEEN 0 AND 1),
    top_k            JSONB,                            -- [{"d":"3","p":0.81},{"d":"8","p":0.15}]
    crop_image_path  VARCHAR(500),
    corrected_digit  CHAR(1) CHECK (corrected_digit ~ '^[0-9]$'),
    UNIQUE (sheet_id, field, position)
);

-- ---------------------------------------------------------------------
-- 17. RESULTS - điểm chính thức của SV cho kỳ thi
--     Một SV chỉ có 1 kết quả hợp lệ / kỳ thi (chặn ghi điểm 2 lần)
-- ---------------------------------------------------------------------
CREATE TABLE results (
    result_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exam_id       BIGINT NOT NULL REFERENCES exams(exam_id) ON DELETE CASCADE,
    student_id    BIGINT NOT NULL REFERENCES students(student_id),
    sheet_id      BIGINT NOT NULL UNIQUE REFERENCES answer_sheets(sheet_id),
    exam_code_id  BIGINT REFERENCES exam_codes(exam_code_id),
    num_correct   SMALLINT NOT NULL DEFAULT 0,
    score         NUMERIC(6,3) NOT NULL CHECK (score >= 0),
    status        result_status NOT NULL DEFAULT 'auto',
    confirmed_by  BIGINT REFERENCES users(user_id),
    confirmed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_results_exam_student ON results (exam_id, student_id) WHERE status <> 'void';
CREATE INDEX idx_results_student ON results (student_id);

-- ---------------------------------------------------------------------
-- 18. REVIEW_QUEUE - hàng đợi đối soát thủ công (human-in-the-loop)
-- ---------------------------------------------------------------------
CREATE TABLE review_queue (
    review_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sheet_id       BIGINT NOT NULL REFERENCES answer_sheets(sheet_id) ON DELETE CASCADE,
    reasons        review_reason[] NOT NULL CHECK (cardinality(reasons) > 0),
    details        JSONB,                              -- thông tin thêm: câu nào tô mờ, SV nào bị trùng...
    priority       SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5), -- 1 = gấp nhất
    status         review_status NOT NULL DEFAULT 'pending',
    assigned_to    BIGINT REFERENCES users(user_id),
    resolved_by    BIGINT REFERENCES users(user_id),
    resolution_note TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at    TIMESTAMPTZ
);
-- Mỗi phiếu chỉ có 1 mục review đang mở
CREATE UNIQUE INDEX uq_review_open_sheet ON review_queue (sheet_id) WHERE status IN ('pending','in_progress');
CREATE INDEX idx_review_status ON review_queue (status, priority, created_at);

-- ---------------------------------------------------------------------
-- 19. SCORE_AUDIT_LOGS - lịch sử thay đổi điểm (truy vết)
-- ---------------------------------------------------------------------
CREATE TABLE score_audit_logs (
    audit_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    result_id      BIGINT NOT NULL REFERENCES results(result_id) ON DELETE CASCADE,
    action         VARCHAR(10) NOT NULL CHECK (action IN ('INSERT','UPDATE','DELETE')),
    old_student_id BIGINT,
    new_student_id BIGINT,
    old_score      NUMERIC(6,3),
    new_score      NUMERIC(6,3),
    old_status     result_status,
    new_status     result_status,
    changed_by     BIGINT REFERENCES users(user_id),
    reason         TEXT,
    changed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_result ON score_audit_logs (result_id, changed_at);

-- ---------------------------------------------------------------------
-- 20. SYSTEM_SETTINGS - ngưỡng confidence và cấu hình hệ thống
-- ---------------------------------------------------------------------
CREATE TABLE system_settings (
    setting_key    VARCHAR(60) PRIMARY KEY,
    setting_value  TEXT NOT NULL,
    description    TEXT,
    updated_by     BIGINT REFERENCES users(user_id),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO system_settings (setting_key, setting_value, description) VALUES
 ('ocr_min_confidence', '0.90', 'Ngưỡng confidence tối thiểu của SBD/mã đề để tự động ghi điểm'),
 ('omr_min_confidence', '0.80', 'Ngưỡng confidence tối thiểu của từng ô trả lời'),
 ('min_blur_score',     '100',  'Laplacian variance tối thiểu - thấp hơn coi là ảnh mờ'),
 ('faint_counts_as_answer', 'true', 'Ô tô mờ (faint) có được tính là đáp án không');

COMMENT ON TABLE students      IS 'Danh sách SV gốc, student_code = SBD dùng để match với kết quả OCR';
COMMENT ON TABLE answer_sheets IS 'Mỗi dòng là 1 ảnh phiếu trả lời đã upload và kết quả nhận diện';
COMMENT ON TABLE results       IS 'Điểm chính thức; chỉ được ghi tự động khi match SBD + confidence đạt ngưỡng';
COMMENT ON TABLE review_queue  IS 'Hàng đợi human-in-the-loop cho phiếu không chắc chắn';
