-- =====================================================================
--  File 04: Dữ liệu mẫu (để demo / test). KHÔNG chạy trên môi trường thật.
--  Mật khẩu mẫu của mọi tài khoản: 123456 (hash bcrypt bên dưới chỉ là ví dụ,
--  khi làm backend hãy tạo lại hash bằng passlib/bcrypt).
-- =====================================================================

-- Users
INSERT INTO users (username, email, password_hash, full_name, role) VALUES
 ('admin',    'admin@smartexam.local',    '$2b$12$KIXQJ6vY0nZ0r8bB1rj3NuQm5YfV1N3x7n0gM1W6xFvX4v2Q9m3yS', 'Quản trị hệ thống', 'admin'),
 ('gv_an',    'an.nguyen@smartexam.local','$2b$12$KIXQJ6vY0nZ0r8bB1rj3NuQm5YfV1N3x7n0gM1W6xFvX4v2Q9m3yS', 'Nguyễn Văn An',     'teacher'),
 ('gv_binh',  'binh.tran@smartexam.local','$2b$12$KIXQJ6vY0nZ0r8bB1rj3NuQm5YfV1N3x7n0gM1W6xFvX4v2Q9m3yS', 'Trần Thị Bình',     'teacher'),
 ('sv220001', 'sv220001@smartexam.local', '$2b$12$KIXQJ6vY0nZ0r8bB1rj3NuQm5YfV1N3x7n0gM1W6xFvX4v2Q9m3yS', 'Lê Minh Khoa',      'student');

-- Lớp, môn
INSERT INTO classes (class_code, class_name, academic_year) VALUES
 ('CNTT-K22A', 'Công nghệ thông tin K22 - Lớp A', '2026-2027'),
 ('CNTT-K22B', 'Công nghệ thông tin K22 - Lớp B', '2026-2027');

INSERT INTO subjects (subject_code, subject_name, credits) VALUES
 ('IT3080', 'Cơ sở dữ liệu', 3),
 ('IT4040', 'Trí tuệ nhân tạo', 3);

-- Import danh sách sinh viên (mô phỏng 1 lần import file Excel)
INSERT INTO student_imports (file_name, imported_by, total_rows, success_rows, status)
VALUES ('danh_sach_CNTT_K22.xlsx', 2, 10, 10, 'success');

-- Mẫu phiếu 40 câu, 4 lựa chọn, SBD 6 chữ số, mã đề 3 chữ số
INSERT INTO sheet_templates (template_name, num_questions, options_per_question, sbd_digits, exam_code_digits,
                             page_width_px, page_height_px, layout_config, created_by)
VALUES ('Phiếu chuẩn 40 câu A4', 40, 4, 6, 3, 2480, 3508,
        '{"markers":"4_corner_squares","sbd_box":{"x":1650,"y":350,"w":600,"h":900},
          "exam_code_box":{"x":1650,"y":1300,"w":300,"h":900},
          "answer_grid":{"x":150,"y":1400,"cols":4,"rows_per_col":10,"bubble_d":55}}'::jsonb, 1);

-- Kỳ thi 10 câu (demo cho gọn)
INSERT INTO exams (exam_title, subject_id, template_id, exam_date, duration_min, num_questions, max_score, pass_score, status, created_by)
VALUES ('Giữa kỳ Cơ sở dữ liệu - HK1 2026', 1, 1, DATE '2026-10-15', 45, 10, 10, 5, 'grading', 2);

-- Sinh viên + đăng ký thi (220010 KHÔNG đăng ký kỳ thi này)
SELECT fn_upsert_student('220001','Lê Minh Khoa',     'CNTT-K22A', DATE '2004-03-12', NULL, 1, 1);
SELECT fn_upsert_student('220002','Phạm Thu Hà',      'CNTT-K22A', DATE '2004-07-01', NULL, 1, 1);
SELECT fn_upsert_student('220003','Đỗ Quang Huy',     'CNTT-K22A', DATE '2004-11-20', NULL, 1, 1);
SELECT fn_upsert_student('220004','Vũ Ngọc Lan',      'CNTT-K22A', DATE '2004-01-05', NULL, 1, 1);
SELECT fn_upsert_student('220005','Hoàng Đức Minh',   'CNTT-K22A', DATE '2004-09-09', NULL, 1, 1);
SELECT fn_upsert_student('220006','Ngô Thanh Tâm',    'CNTT-K22B', DATE '2004-02-14', NULL, 1, 1);
SELECT fn_upsert_student('220007','Bùi Gia Bảo',      'CNTT-K22B', DATE '2004-05-30', NULL, 1, 1);
SELECT fn_upsert_student('220008','Trịnh Mai Anh',    'CNTT-K22B', DATE '2004-08-18', NULL, 1, 1);
SELECT fn_upsert_student('220009','Lý Hoài Nam',      'CNTT-K22B', DATE '2004-12-25', NULL, 1, 1);
SELECT fn_upsert_student('220010','Đặng Khánh Linh',  'CNTT-K22B', DATE '2004-06-06', NULL, NULL, 1);
UPDATE students SET user_id = 4 WHERE student_code = '220001';

-- Câu hỏi gốc: đáp án gốc A B C D A B C D A B
INSERT INTO questions (exam_id, original_no, content, correct_option, topic)
SELECT 1, g, 'Nội dung câu hỏi số ' || g, substr('ABCDABCDAB', g, 1), CASE WHEN g <= 5 THEN 'SQL' ELSE 'Chuẩn hoá' END
FROM generate_series(1, 10) g;

-- 2 mã đề: 101 giữ nguyên thứ tự; 102 đảo ngược thứ tự câu
INSERT INTO exam_codes (exam_id, code, shuffle_seed) VALUES (1, '101', NULL), (1, '102', 42);

INSERT INTO answer_keys (exam_code_id, question_no, question_id, correct_option)
SELECT 1, q.original_no, q.question_id, q.correct_option FROM questions q WHERE q.exam_id = 1;
INSERT INTO answer_keys (exam_code_id, question_no, question_id, correct_option)
SELECT 2, 11 - q.original_no, q.question_id, q.correct_option FROM questions q WHERE q.exam_id = 1;
-- => đáp án mã 102 theo thứ tự trên phiếu: B A D C B A D C B A

-- Model ML
INSERT INTO ml_models (model_name, model_type, version, framework, file_path, train_dataset, metrics, is_active, notes) VALUES
 ('OMR SVM HOG',       'omr_classifier', '1.0', 'sklearn', 'models/omr_svm_v1.joblib', 'omr_cells_v1',
  '{"val_accuracy":0.941,"f1_macro":0.912}', FALSE, 'Baseline SVM trên đặc trưng HOG'),
 ('OMR Small CNN',     'omr_classifier', '2.0', 'keras',   'models/omr_cnn_v2.keras',  'omr_cells_v1+aug',
  '{"val_accuracy":0.987,"f1_macro":0.975}', TRUE,  '4 lớp: blank/filled/faint/multiple'),
 ('Digit CNN baseline','ocr_digit',      '1.0', 'keras',   'models/digit_cnn_v1.keras','MNIST',
  '{"acc_mnist_test":0.992,"acc_real_test":0.861}', FALSE, 'Chưa fine-tune - domain gap lớn'),
 ('Digit CNN finetune','ocr_digit',      '2.0', 'keras',   'models/digit_cnn_v2.keras','MNIST + real_digits_400',
  '{"acc_mnist_test":0.989,"acc_real_test":0.962}', TRUE,  'Fine-tune trên 400 mẫu chữ số thật');

INSERT INTO scan_batches (exam_id, uploaded_by, total_sheets, note) VALUES (1, 2, 9, 'Phòng A101 - ca sáng');

-- ---------------------------------------------------------------------
-- Phiếu trả lời mô phỏng output của pipeline CV/ML
-- ---------------------------------------------------------------------
INSERT INTO answer_sheets (exam_id, batch_id, image_path, image_hash, blur_score,
                           detected_sbd, sbd_confidence, detected_exam_code, exam_code_confidence,
                           omr_model_id, ocr_model_id, processing_time_ms, status, uploaded_by) VALUES
 (1,1,'uploads/exam1/s01.jpg', repeat('a',64), 320.5, '220001', 0.985, '101', 0.990, 2, 4, 850, 'processed', 2), -- chuẩn, 10/10
 (1,1,'uploads/exam1/s02.jpg', repeat('b',64), 280.1, '220002', 0.970, '102', 0.985, 2, 4, 910, 'processed', 2), -- chuẩn, mã 102
 (1,1,'uploads/exam1/s03.jpg', repeat('c',64), 250.0, '220003', 0.720, '101', 0.960, 2, 4, 870, 'processed', 2), -- SBD confidence thấp
 (1,1,'uploads/exam1/s04.jpg', repeat('d',64), 300.0, '220099', 0.950, '101', 0.970, 2, 4, 880, 'processed', 2), -- SBD không có trong DS
 (1,1,'uploads/exam1/s05.jpg', repeat('e',64), 310.0, '220001', 0.980, '101', 0.990, 2, 4, 860, 'processed', 2), -- quét trùng SV 220001
 (1,1,'uploads/exam1/s06.jpg', repeat('f',64), 295.0, '220004', 0.975, '101', 0.980, 2, 4, 890, 'processed', 2), -- có ô tô mờ
 (1,1,'uploads/exam1/s07.jpg', repeat('0',64), 305.0, '220005', 0.960, '999', 0.930, 2, 4, 840, 'processed', 2), -- mã đề sai
 (1,1,'uploads/exam1/s08.jpg', repeat('1',64), 290.0, '220006', 0.990, '102', 0.995, 2, 4, 820, 'processed', 2), -- chuẩn
 (1,1,'uploads/exam1/s09.jpg', repeat('2',64), 275.0, '220007', 0.965, '101', 0.975, 2, 4, 830, 'processed', 2); -- chuẩn

-- Hàm tạm: sinh sheet_answers từ chuỗi
--   'A'..'D' = tô rõ, 'a'..'d' = tô mờ, '-' = bỏ trống, '*' = tô nhiều (AB)
CREATE OR REPLACE FUNCTION pg_temp.seed_answers(p_sheet BIGINT, p_pattern TEXT) RETURNS VOID AS $$
    INSERT INTO sheet_answers (sheet_id, question_no, state, selected_options, confidence)
    SELECT p_sheet, i,
           CASE WHEN c = '-' THEN 'blank' WHEN c = '*' THEN 'multiple'
                WHEN c ~ '[a-f]' THEN 'faint' ELSE 'filled' END::bubble_state,
           CASE WHEN c = '-' THEN '' WHEN c = '*' THEN 'AB' ELSE upper(c) END,
           CASE WHEN c ~ '[a-f]' THEN 0.62 ELSE 0.97 END
    FROM (SELECT i, substr(p_pattern, i, 1) AS c FROM generate_series(1, length(p_pattern)) i) t;
$$ LANGUAGE sql;

SELECT pg_temp.seed_answers(1, 'ABCDABCDAB');   -- 10/10 (mã 101)
SELECT pg_temp.seed_answers(2, 'BADCBACCBA');   -- mã 102: sai câu 7 => 9/10
SELECT pg_temp.seed_answers(3, 'ABCDABCD-B');   -- 9/10
SELECT pg_temp.seed_answers(4, 'ABCAABCDAB');   -- 9/10
SELECT pg_temp.seed_answers(5, 'ABCDABCDAB');   -- trùng
SELECT pg_temp.seed_answers(6, 'ABcDABCDA*');   -- câu 3 tô mờ, câu 10 tô 2 ô
SELECT pg_temp.seed_answers(7, 'ABCDABCDAB');
SELECT pg_temp.seed_answers(8, 'BADCBADCBA');   -- 10/10 (mã 102)
SELECT pg_temp.seed_answers(9, 'ABCDDDDDAB');   -- 6/10

-- Dự đoán từng chữ số SBD (ví dụ cho phiếu 3 và 4)
INSERT INTO ocr_digits (sheet_id, field, position, predicted_digit, confidence, top_k)
SELECT 3, 'sbd', i - 1, substr('220003', i, 1), CASE WHEN i = 6 THEN 0.72 ELSE 0.99 END,
       CASE WHEN i = 6 THEN '[{"d":"3","p":0.72},{"d":"8","p":0.25}]'::jsonb END
FROM generate_series(1, 6) i;
INSERT INTO ocr_digits (sheet_id, field, position, predicted_digit, confidence)
SELECT 4, 'sbd', i - 1, substr('220099', i, 1), 0.95 FROM generate_series(1, 6) i;
