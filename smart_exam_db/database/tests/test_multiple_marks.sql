-- =====================================================================
--  Kiểm thử: phiếu có câu tô nhiều ô phải được đưa vào review (multiple_marks)
--
--  Cách chạy: pgAdmin -> DB smart_exam -> Query Tool -> mở file này -> Execute (F5).
--  Kết quả xem ở tab "Messages" (các dòng NOTICE).
--
--  * An toàn: mọi dữ liệu test nằm trong BEGIN ... ROLLBACK => không để lại gì trong DB.
--  * Độc lập với dữ liệu mẫu: script tự tạo user, môn, mẫu phiếu, kỳ thi, mã đề 901,
--    đáp án, 3 sinh viên và 3 phiếu riêng (không phụ thuộc 04_seed / 05_demo).
--  * Chạy được cả trước và sau khi cập nhật fn_process_sheet: script tự nhận biết
--    đang chạy hàm CŨ hay MỚI và in kết quả mong đợi tương ứng.
--
--  3 trường hợp (đáp án mã 901 = ABCDABCDAB, 10 câu, mỗi câu 1 điểm):
--    A. Đối chứng    : tô đúng cả 10 câu              -> cũ: graded       | mới: graded
--    B. CHỈ tô nhiều : câu 10 tô A+B (state=multiple) -> cũ: graded (LỖI) | mới: needs_review {multiple_marks}
--    C. Backend ghi sai: câu 5 state=filled nhưng 'AC' -> cũ: graded (LỖI) | mới: needs_review {multiple_marks}
--  Cả 3 phiếu: ảnh nét, SBD/mã đề confidence 0.99, ô confidence 0.99, không có ô tô mờ,
--  SBD có trong danh sách thi => lý do review DUY NHẤT có thể có là multiple_marks.
--
--  Nếu script dừng giữa chừng vì lỗi: chạy riêng lệnh  ROLLBACK;  rồi sửa và chạy lại.
-- =====================================================================

BEGIN;

DO $test$
DECLARE
    v_user     BIGINT;
    v_subject  BIGINT;
    v_tpl      BIGINT;
    v_exam     BIGINT;
    v_code     BIGINT;
    v_student  BIGINT;
    v_sheet    BIGINT;
    v_new_fn   BOOLEAN;
    v_details  JSONB;
    v_expect   TEXT;
    v_pass     BOOLEAN;
    v_all_pass BOOLEAN := TRUE;
    tc         RECORD;
    r          RECORD;
BEGIN
    -- Hàm đang cài trong DB là bản cũ hay bản mới?
    v_new_fn := pg_get_functiondef('fn_process_sheet(bigint)'::regprocedure) LIKE '%multiple_marks%';
    RAISE NOTICE '=== fn_process_sheet trong DB: %',
        CASE WHEN v_new_fn THEN 'BẢN MỚI (có kiểm tra multiple_marks)'
             ELSE 'BẢN CŨ (chưa kiểm tra multiple_marks)' END;

    -- ---- Dữ liệu nền cho kỳ thi test ----
    INSERT INTO users (username, email, password_hash, full_name, role)
    VALUES ('test_mm_user', 'test_mm@example.com', 'x', 'GV kiểm thử', 'teacher')
    RETURNING user_id INTO v_user;

    INSERT INTO subjects (subject_code, subject_name) VALUES ('TESTMM', 'Môn kiểm thử')
    RETURNING subject_id INTO v_subject;

    INSERT INTO sheet_templates (template_name, num_questions, options_per_question)
    VALUES ('test_mm_template', 40, 4)
    RETURNING template_id INTO v_tpl;

    INSERT INTO exams (exam_title, subject_id, template_id, num_questions, max_score, created_by)
    VALUES ('Kỳ thi kiểm thử multiple_marks', v_subject, v_tpl, 10, 10, v_user)
    RETURNING exam_id INTO v_exam;

    INSERT INTO exam_codes (exam_id, code) VALUES (v_exam, '901')
    RETURNING exam_code_id INTO v_code;

    INSERT INTO answer_keys (exam_code_id, question_no, correct_option)
    SELECT v_code, i, substr('ABCDABCDAB', i, 1) FROM generate_series(1, 10) i;

    -- ---- 3 trường hợp ----
    --   Ký hiệu trong chuỗi tô: 'A'..'D' = tô rõ 1 ô
    --                           '*'      = tô 2 ô A+B, state = 'multiple'
    --                           '#'      = 2 ô A+C nhưng backend ghi state = 'filled'
    FOR tc IN
        SELECT * FROM (VALUES
            ('A', 'Đối chứng: tô đúng cả 10 câu',        '99990001', 'ABCDABCDAB', 'graded'),
            ('B', 'CHỈ tô nhiều ô ở câu 10 (multiple)',  '99990002', 'ABCDABCDA*', 'needs_review'),
            ('C', 'Câu 5 state=filled nhưng chọn AC',    '99990003', 'ABCD#BCDAB', 'needs_review')
        ) t(case_id, case_name, sbd, pattern, expect_new)
    LOOP
        INSERT INTO students (student_code, full_name)
        VALUES (tc.sbd, 'SV kiểm thử ' || tc.case_id)
        RETURNING student_id INTO v_student;

        INSERT INTO exam_students (exam_id, student_id) VALUES (v_exam, v_student);

        INSERT INTO answer_sheets (exam_id, image_path, blur_score,
                                   detected_sbd, sbd_confidence,
                                   detected_exam_code, exam_code_confidence,
                                   status, uploaded_by)
        VALUES (v_exam, 'test/multiple_marks_' || tc.case_id || '.jpg', 500,
                tc.sbd, 0.99, '901', 0.99, 'processed', v_user)
        RETURNING sheet_id INTO v_sheet;

        INSERT INTO sheet_answers (sheet_id, question_no, state, selected_options, confidence)
        SELECT v_sheet, i,
               CASE WHEN ch = '*' THEN 'multiple' ELSE 'filled' END::bubble_state,
               CASE WHEN ch = '*' THEN 'AB' WHEN ch = '#' THEN 'AC' ELSE ch END,
               0.99
        FROM (SELECT i, substr(tc.pattern, i, 1) AS ch FROM generate_series(1, 10) i) s;

        -- Gọi hàm cần kiểm thử
        SELECT * INTO r FROM fn_process_sheet(v_sheet);

        v_details := NULL;
        IF r.review_id IS NOT NULL THEN
            SELECT details INTO v_details FROM review_queue WHERE review_id = r.review_id;
        END IF;

        -- Kết quả mong đợi phụ thuộc vào phiên bản hàm
        v_expect := CASE WHEN v_new_fn THEN tc.expect_new ELSE 'graded' END;
        v_pass   := r.outcome = v_expect
                    AND (NOT (v_new_fn AND v_expect = 'needs_review')
                         OR r.reasons = ARRAY['multiple_marks']::review_reason[]);
        v_all_pass := v_all_pass AND v_pass;

        RAISE NOTICE '---------------------------------------------------------------';
        RAISE NOTICE '[%] %  (chuỗi tô: %)', tc.case_id, tc.case_name, tc.pattern;
        RAISE NOTICE '    outcome   = %   (mong đợi: %)', r.outcome, v_expect;
        RAISE NOTICE '    reasons   = %', r.reasons;
        RAISE NOTICE '    details   = %', COALESCE(v_details::text, '(không vào review)');
        RAISE NOTICE '    score     = %   | result_id = % | review_id = %', r.score, r.result_id, r.review_id;
        RAISE NOTICE '    => %', CASE WHEN v_pass THEN 'ĐÚNG như mong đợi' ELSE 'KHÁC mong đợi!' END;
    END LOOP;

    RAISE NOTICE '===============================================================';
    IF NOT v_all_pass THEN
        RAISE NOTICE 'KẾT LUẬN: CÓ TRƯỜNG HỢP KHÁC MONG ĐỢI - xem chi tiết ở trên.';
    ELSIF v_new_fn THEN
        RAISE NOTICE 'KẾT LUẬN: ĐÃ SỬA - phiếu B, C vào review với lý do multiple_marks, phiếu A vẫn ghi điểm tự động.';
    ELSE
        RAISE NOTICE 'KẾT LUẬN: ĐÃ TÁI HIỆN LỖI - phiếu B, C có câu tô nhiều ô nhưng vẫn được ghi điểm tự động (status auto).';
    END IF;
END
$test$;

ROLLBACK;
