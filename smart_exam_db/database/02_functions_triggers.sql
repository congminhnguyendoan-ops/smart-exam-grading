-- =====================================================================
--  File 02: Functions & Triggers - logic nghiệp vụ
--    * updated_at tự động
--    * Kiểm tra toàn vẹn đáp án / đề
--    * fn_grade_sheet        : chấm 1 phiếu theo đáp án mã đề
--    * fn_process_sheet      : chấm + MATCH SBD -> ghi điểm hoặc đẩy vào review
--    * fn_suggest_students   : gợi ý SV có SBD gần giống (cho màn hình đối soát)
--    * fn_resolve_review     : giáo viên xác nhận SV đúng -> ghi điểm
--    * fn_reject_review      : loại phiếu
--    * fn_regrade_exam       : chấm lại cả kỳ thi khi sửa đáp án
--    * fn_upsert_student     : dùng khi import Excel/CSV
--    * Audit log thay đổi điểm
-- =====================================================================

-- ---------------------------------------------------------------------
-- Helper: đọc setting dạng số
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_setting_num(p_key TEXT, p_default NUMERIC)
RETURNS NUMERIC LANGUAGE sql STABLE AS $$
    SELECT COALESCE((SELECT setting_value::numeric FROM system_settings WHERE setting_key = p_key), p_default);
$$;

CREATE OR REPLACE FUNCTION fn_setting_bool(p_key TEXT, p_default BOOLEAN)
RETURNS BOOLEAN LANGUAGE sql STABLE AS $$
    SELECT COALESCE((SELECT setting_value::boolean FROM system_settings WHERE setting_key = p_key), p_default);
$$;

-- Helper: user hiện tại do backend đặt bằng  SET LOCAL app.current_user_id = '5';
CREATE OR REPLACE FUNCTION fn_current_app_user()
RETURNS BIGINT LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.current_user_id', true), '')::bigint;
$$;

-- ---------------------------------------------------------------------
-- 1. Trigger cập nhật updated_at
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['users','students','exams','answer_keys','answer_sheets','results'] LOOP
        EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON %I
                        FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at()', 'trg_' || t || '_updated_at', t);
    END LOOP;
END $$;

-- ---------------------------------------------------------------------
-- 2. Ràng buộc nghiệp vụ
-- ---------------------------------------------------------------------
-- 2a. Số câu của đề không vượt quá số câu của mẫu phiếu
CREATE OR REPLACE FUNCTION trg_check_exam_template()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_max SMALLINT;
BEGIN
    SELECT num_questions INTO v_max FROM sheet_templates WHERE template_id = NEW.template_id;
    IF NEW.num_questions > v_max THEN
        RAISE EXCEPTION 'Đề có % câu nhưng mẫu phiếu chỉ hỗ trợ % câu', NEW.num_questions, v_max;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_exams_check_template BEFORE INSERT OR UPDATE OF num_questions, template_id ON exams
    FOR EACH ROW EXECUTE FUNCTION trg_check_exam_template();

-- 2b. Đáp án: số câu hợp lệ + đáp án nằm trong số lựa chọn của mẫu phiếu
CREATE OR REPLACE FUNCTION trg_check_answer_key()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_nq SMALLINT; v_opts SMALLINT;
BEGIN
    SELECT e.num_questions, t.options_per_question INTO v_nq, v_opts
    FROM exam_codes c JOIN exams e ON e.exam_id = c.exam_id
         JOIN sheet_templates t ON t.template_id = e.template_id
    WHERE c.exam_code_id = NEW.exam_code_id;

    IF NEW.question_no > v_nq THEN
        RAISE EXCEPTION 'Câu % vượt quá số câu của đề (%)', NEW.question_no, v_nq;
    END IF;
    IF ascii(NEW.correct_option) - ascii('A') + 1 > v_opts THEN
        RAISE EXCEPTION 'Đáp án % không hợp lệ, phiếu chỉ có % lựa chọn', NEW.correct_option, v_opts;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_answer_keys_check BEFORE INSERT OR UPDATE ON answer_keys
    FOR EACH ROW EXECUTE FUNCTION trg_check_answer_key();

-- ---------------------------------------------------------------------
-- 3. Audit log thay đổi điểm
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_results_audit()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO score_audit_logs (result_id, action, new_student_id, new_score, new_status, changed_by, reason)
        VALUES (NEW.result_id, 'INSERT', NEW.student_id, NEW.score, NEW.status,
                fn_current_app_user(), NULLIF(current_setting('app.change_reason', true), ''));
    ELSIF TG_OP = 'UPDATE' THEN
        IF (OLD.score, OLD.student_id, OLD.status) IS DISTINCT FROM (NEW.score, NEW.student_id, NEW.status) THEN
            INSERT INTO score_audit_logs (result_id, action, old_student_id, new_student_id,
                                          old_score, new_score, old_status, new_status, changed_by, reason)
            VALUES (NEW.result_id, 'UPDATE', OLD.student_id, NEW.student_id, OLD.score, NEW.score,
                    OLD.status, NEW.status, fn_current_app_user(),
                    NULLIF(current_setting('app.change_reason', true), ''));
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_results_audit AFTER INSERT OR UPDATE ON results
    FOR EACH ROW EXECUTE FUNCTION trg_results_audit();

-- ---------------------------------------------------------------------
-- 4. fn_grade_sheet: chấm 1 phiếu -> cập nhật is_correct, num_correct, raw_score
--    Trả về raw_score, hoặc NULL nếu không xác định được mã đề
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_grade_sheet(p_sheet_id BIGINT)
RETURNS NUMERIC LANGUAGE plpgsql AS $$
DECLARE
    v_sheet        answer_sheets%ROWTYPE;
    v_code_id      BIGINT;
    v_default_pts  NUMERIC;
    v_faint_ok     BOOLEAN := fn_setting_bool('faint_counts_as_answer', TRUE);
    v_correct      INT;
    v_score        NUMERIC;
BEGIN
    SELECT * INTO v_sheet FROM answer_sheets WHERE sheet_id = p_sheet_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Không tìm thấy phiếu %', p_sheet_id; END IF;

    -- Xác định mã đề: ưu tiên exam_code_id đã gán (sửa tay), nếu không thì tra theo OCR
    v_code_id := v_sheet.exam_code_id;
    IF v_code_id IS NULL THEN
        SELECT exam_code_id INTO v_code_id FROM exam_codes
        WHERE exam_id = v_sheet.exam_id AND code = v_sheet.detected_exam_code;
    END IF;
    IF v_code_id IS NULL THEN RETURN NULL; END IF;

    SELECT max_score / num_questions INTO v_default_pts FROM exams WHERE exam_id = v_sheet.exam_id;

    -- Đánh dấu đúng/sai từng câu
    UPDATE sheet_answers sa
    SET is_correct = (sa.state = 'filled' OR (v_faint_ok AND sa.state = 'faint'))
                     AND sa.selected_options = ak.correct_option
    FROM answer_keys ak
    WHERE sa.sheet_id = p_sheet_id AND ak.exam_code_id = v_code_id AND ak.question_no = sa.question_no;

    -- Câu trên phiếu không có trong đáp án => không tính
    UPDATE sheet_answers sa SET is_correct = FALSE
    WHERE sa.sheet_id = p_sheet_id
      AND NOT EXISTS (SELECT 1 FROM answer_keys ak WHERE ak.exam_code_id = v_code_id AND ak.question_no = sa.question_no);

    SELECT COUNT(*), COALESCE(SUM(COALESCE(ak.points, v_default_pts)), 0)
    INTO v_correct, v_score
    FROM answer_keys ak
    JOIN sheet_answers sa ON sa.sheet_id = p_sheet_id AND sa.question_no = ak.question_no
    WHERE ak.exam_code_id = v_code_id AND sa.is_correct;

    v_score := ROUND(v_score, 3);

    UPDATE answer_sheets
    SET exam_code_id = v_code_id, num_correct = v_correct, raw_score = v_score
    WHERE sheet_id = p_sheet_id;

    RETURN v_score;
END $$;

-- ---------------------------------------------------------------------
-- 5. fn_process_sheet: bước cốt lõi "match SBD tự động điền điểm"
--    Gọi sau khi backend đã ghi kết quả OCR/OMR vào answer_sheets,
--    sheet_answers, ocr_digits.
--    outcome = 'graded'       -> đã ghi điểm tự động vào results
--            = 'needs_review' -> đã đẩy vào review_queue, KHÔNG ghi điểm
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_process_sheet(p_sheet_id BIGINT)
RETURNS TABLE (outcome TEXT, result_id BIGINT, review_id BIGINT, score NUMERIC, reasons review_reason[])
LANGUAGE plpgsql AS $$
#variable_conflict use_column
DECLARE
    v_sheet       answer_sheets%ROWTYPE;
    v_ocr_min     NUMERIC := fn_setting_num('ocr_min_confidence', 0.90);
    v_omr_min     NUMERIC := fn_setting_num('omr_min_confidence', 0.80);
    v_blur_min    NUMERIC := fn_setting_num('min_blur_score', 100);
    v_score       NUMERIC;
    v_student_id  BIGINT;
    v_has_roster  BOOLEAN;
    v_reasons     review_reason[] := '{}';
    v_details     JSONB := '{}'::jsonb;
    v_low_q       SMALLINT[];
    v_dup_sheet   BIGINT;
    v_result_id   BIGINT;
    v_review_id   BIGINT;
BEGIN
    SELECT * INTO v_sheet FROM answer_sheets WHERE sheet_id = p_sheet_id FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Không tìm thấy phiếu %', p_sheet_id; END IF;

    -- (1) Chất lượng ảnh
    IF v_sheet.blur_score IS NOT NULL AND v_sheet.blur_score < v_blur_min THEN
        v_reasons := v_reasons || 'poor_image_quality'::review_reason;
        v_details := v_details || jsonb_build_object('blur_score', v_sheet.blur_score);
    END IF;

    -- (2) Chấm điểm theo mã đề
    v_score := fn_grade_sheet(p_sheet_id);
    IF v_score IS NULL THEN
        v_reasons := v_reasons || 'exam_code_not_found'::review_reason;
        v_details := v_details || jsonb_build_object('detected_exam_code', v_sheet.detected_exam_code);
    END IF;
    SELECT * INTO v_sheet FROM answer_sheets WHERE sheet_id = p_sheet_id;   -- lấy lại exam_code_id

    -- (3) Confidence OCR (SBD + mã đề)
    IF v_sheet.sbd_confidence IS NULL OR v_sheet.sbd_confidence < v_ocr_min
       OR COALESCE(v_sheet.exam_code_confidence, 0) < v_ocr_min THEN
        v_reasons := v_reasons || 'low_ocr_confidence'::review_reason;
        v_details := v_details || jsonb_build_object('sbd_confidence', v_sheet.sbd_confidence,
                                                     'exam_code_confidence', v_sheet.exam_code_confidence);
    END IF;

    -- (4) Confidence OMR (từng ô) + ô tô mờ
    SELECT array_agg(question_no ORDER BY question_no) INTO v_low_q
    FROM sheet_answers
    WHERE sheet_id = p_sheet_id AND (confidence < v_omr_min OR state = 'faint');
    IF v_low_q IS NOT NULL THEN
        v_reasons := v_reasons || 'low_omr_confidence'::review_reason;
        v_details := v_details || jsonb_build_object('low_confidence_questions', to_jsonb(v_low_q));
    END IF;

    -- (5) MATCH SBD với bảng students (trong phạm vi roster của kỳ thi nếu có)
    SELECT EXISTS (SELECT 1 FROM exam_students WHERE exam_id = v_sheet.exam_id) INTO v_has_roster;

    SELECT s.student_id INTO v_student_id
    FROM students s
    WHERE s.student_code = v_sheet.detected_sbd
      AND (NOT v_has_roster OR EXISTS (SELECT 1 FROM exam_students es
                                       WHERE es.exam_id = v_sheet.exam_id AND es.student_id = s.student_id));

    IF v_student_id IS NULL THEN
        v_reasons := v_reasons || 'sbd_not_found'::review_reason;
        v_details := v_details || jsonb_build_object('detected_sbd', v_sheet.detected_sbd);
    ELSE
        -- (6) Trùng SBD: SV này đã có điểm từ 1 phiếu khác trong cùng kỳ thi
        SELECT r.sheet_id INTO v_dup_sheet FROM results r
        WHERE r.exam_id = v_sheet.exam_id AND r.student_id = v_student_id
          AND r.status <> 'void' AND r.sheet_id <> p_sheet_id;
        IF v_dup_sheet IS NOT NULL THEN
            v_reasons := v_reasons || 'duplicate_sbd'::review_reason;
            v_details := v_details || jsonb_build_object('duplicate_with_sheet_id', v_dup_sheet);
        END IF;
    END IF;

    UPDATE answer_sheets SET matched_student_id = v_student_id, processed_at = now()
    WHERE sheet_id = p_sheet_id;

    -- (7) Quyết định
    IF cardinality(v_reasons) = 0 THEN
        INSERT INTO results (exam_id, student_id, sheet_id, exam_code_id, num_correct, score, status)
        VALUES (v_sheet.exam_id, v_student_id, p_sheet_id, v_sheet.exam_code_id,
                v_sheet.num_correct, v_score, 'auto')
        ON CONFLICT (sheet_id) DO UPDATE
            SET score = EXCLUDED.score, num_correct = EXCLUDED.num_correct,
                exam_code_id = EXCLUDED.exam_code_id, student_id = EXCLUDED.student_id
        RETURNING results.result_id INTO v_result_id;

        UPDATE answer_sheets SET status = 'graded' WHERE sheet_id = p_sheet_id;
        RETURN QUERY SELECT 'graded'::text, v_result_id, NULL::bigint, v_score, v_reasons;
    ELSE
        INSERT INTO review_queue (sheet_id, reasons, details, priority)
        VALUES (p_sheet_id, v_reasons, v_details,
                CASE WHEN 'duplicate_sbd' = ANY(v_reasons) OR 'sbd_not_found' = ANY(v_reasons) THEN 1
                     WHEN 'low_ocr_confidence' = ANY(v_reasons) OR 'exam_code_not_found' = ANY(v_reasons) THEN 2
                     ELSE 3 END)
        ON CONFLICT (sheet_id) WHERE status IN ('pending','in_progress')
        DO UPDATE SET reasons = EXCLUDED.reasons, details = EXCLUDED.details, priority = EXCLUDED.priority
        RETURNING review_queue.review_id INTO v_review_id;

        UPDATE answer_sheets SET status = 'needs_review' WHERE sheet_id = p_sheet_id;
        RETURN QUERY SELECT 'needs_review'::text, NULL::bigint, v_review_id, v_score, v_reasons;
    END IF;
END $$;

-- ---------------------------------------------------------------------
-- 6. fn_suggest_students: gợi ý SV có SBD khác tối đa p_max_diff chữ số
--    (OCR đọc sai 1 chữ số là lỗi phổ biến nhất)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_suggest_students(p_sheet_id BIGINT, p_max_diff INT DEFAULT 1)
RETURNS TABLE (student_id BIGINT, student_code VARCHAR, full_name VARCHAR, class_code VARCHAR,
               digit_diff INT, already_graded BOOLEAN)
LANGUAGE sql STABLE AS $$
    WITH sh AS (SELECT exam_id, detected_sbd FROM answer_sheets WHERE sheet_id = p_sheet_id),
    cand AS (
        SELECT s.*, (SELECT COUNT(*) FROM generate_series(1, length(s.student_code)) i
                     WHERE substr(s.student_code, i, 1) <> substr(sh.detected_sbd, i, 1))::int AS diff
        FROM students s, sh
        WHERE length(s.student_code) = length(sh.detected_sbd)
          AND (NOT EXISTS (SELECT 1 FROM exam_students es WHERE es.exam_id = sh.exam_id)
               OR EXISTS (SELECT 1 FROM exam_students es WHERE es.exam_id = sh.exam_id AND es.student_id = s.student_id))
    )
    SELECT c.student_id, c.student_code, c.full_name, cl.class_code, c.diff,
           EXISTS (SELECT 1 FROM results r, sh WHERE r.exam_id = sh.exam_id
                   AND r.student_id = c.student_id AND r.status <> 'void')
    FROM cand c LEFT JOIN classes cl ON cl.class_id = c.class_id
    WHERE c.diff <= p_max_diff
    ORDER BY c.diff, c.student_code;
$$;

-- ---------------------------------------------------------------------
-- 7. fn_resolve_review: giáo viên xác nhận SV đúng cho phiếu
--    p_void_existing = TRUE: huỷ kết quả cũ của SV đó (trường hợp quét trùng)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_resolve_review(
    p_review_id BIGINT, p_student_id BIGINT, p_reviewer_id BIGINT,
    p_note TEXT DEFAULT NULL, p_void_existing BOOLEAN DEFAULT FALSE)
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE
    v_rv        review_queue%ROWTYPE;
    v_sheet     answer_sheets%ROWTYPE;
    v_score     NUMERIC;
    v_other     BIGINT;
    v_result_id BIGINT;
BEGIN
    SELECT * INTO v_rv FROM review_queue WHERE review_id = p_review_id FOR UPDATE;
    IF NOT FOUND OR v_rv.status NOT IN ('pending','in_progress') THEN
        RAISE EXCEPTION 'Review % không tồn tại hoặc đã được xử lý', p_review_id;
    END IF;

    PERFORM set_config('app.current_user_id', p_reviewer_id::text, true);
    PERFORM set_config('app.change_reason', COALESCE(p_note, 'Đối soát thủ công review #' || p_review_id), true);

    v_score := fn_grade_sheet(v_rv.sheet_id);     -- chấm lại (có thể giáo viên đã sửa đáp án tô / mã đề)
    IF v_score IS NULL THEN
        RAISE EXCEPTION 'Phiếu % chưa xác định được mã đề - hãy cập nhật answer_sheets.exam_code_id trước', v_rv.sheet_id;
    END IF;
    SELECT * INTO v_sheet FROM answer_sheets WHERE sheet_id = v_rv.sheet_id;

    -- Kiểm tra trùng
    SELECT r.result_id INTO v_other FROM results r
    WHERE r.exam_id = v_sheet.exam_id AND r.student_id = p_student_id
      AND r.status <> 'void' AND r.sheet_id <> v_sheet.sheet_id;
    IF v_other IS NOT NULL THEN
        IF p_void_existing THEN
            UPDATE results SET status = 'void' WHERE result_id = v_other;
        ELSE
            RAISE EXCEPTION 'Sinh viên % đã có điểm (result_id=%) trong kỳ thi này', p_student_id, v_other;
        END IF;
    END IF;

    INSERT INTO results (exam_id, student_id, sheet_id, exam_code_id, num_correct, score,
                         status, confirmed_by, confirmed_at)
    VALUES (v_sheet.exam_id, p_student_id, v_sheet.sheet_id, v_sheet.exam_code_id,
            v_sheet.num_correct, v_score, 'confirmed', p_reviewer_id, now())
    ON CONFLICT (sheet_id) DO UPDATE
        SET student_id = EXCLUDED.student_id, score = EXCLUDED.score, num_correct = EXCLUDED.num_correct,
            exam_code_id = EXCLUDED.exam_code_id, status = 'confirmed',
            confirmed_by = EXCLUDED.confirmed_by, confirmed_at = now()
    RETURNING result_id INTO v_result_id;

    UPDATE answer_sheets SET matched_student_id = p_student_id, status = 'graded'
    WHERE sheet_id = v_sheet.sheet_id;

    UPDATE review_queue SET status = 'resolved', resolved_by = p_reviewer_id,
           resolution_note = p_note, resolved_at = now()
    WHERE review_id = p_review_id;

    RETURN v_result_id;
END $$;

-- ---------------------------------------------------------------------
-- 8. fn_reject_review: loại phiếu (ảnh hỏng, phiếu nháp...)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_reject_review(p_review_id BIGINT, p_reviewer_id BIGINT, p_note TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE v_sheet BIGINT;
BEGIN
    UPDATE review_queue SET status = 'rejected', resolved_by = p_reviewer_id,
           resolution_note = p_note, resolved_at = now()
    WHERE review_id = p_review_id AND status IN ('pending','in_progress')
    RETURNING sheet_id INTO v_sheet;
    IF v_sheet IS NULL THEN RAISE EXCEPTION 'Review % không hợp lệ', p_review_id; END IF;
    UPDATE answer_sheets SET status = 'rejected' WHERE sheet_id = v_sheet;
END $$;

-- ---------------------------------------------------------------------
-- 9. fn_regrade_exam: chấm lại toàn bộ kỳ thi sau khi sửa đáp án
--    Trả về số kết quả bị thay đổi điểm
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_regrade_exam(p_exam_id BIGINT, p_user_id BIGINT)
RETURNS INT LANGUAGE plpgsql AS $$
DECLARE r RECORD; v_changed INT := 0; v_rows INT;
BEGIN
    PERFORM set_config('app.current_user_id', p_user_id::text, true);
    PERFORM set_config('app.change_reason', 'Chấm lại do sửa đáp án', true);

    FOR r IN SELECT sheet_id FROM answer_sheets
             WHERE exam_id = p_exam_id AND status NOT IN ('rejected','error') LOOP
        PERFORM fn_grade_sheet(r.sheet_id);
    END LOOP;

    UPDATE results res
    SET score = s.raw_score, num_correct = s.num_correct
    FROM answer_sheets s
    WHERE res.sheet_id = s.sheet_id AND res.exam_id = p_exam_id AND res.status <> 'void'
      AND res.score IS DISTINCT FROM s.raw_score;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    v_changed := v_rows;
    RETURN v_changed;
END $$;

-- ---------------------------------------------------------------------
-- 10. fn_upsert_student: dùng cho chức năng import Excel/CSV
--     Tạo lớp nếu chưa có, thêm/cập nhật SV, đăng ký vào kỳ thi (tuỳ chọn)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_upsert_student(
    p_code VARCHAR, p_full_name VARCHAR, p_class_code VARCHAR DEFAULT NULL,
    p_dob DATE DEFAULT NULL, p_email VARCHAR DEFAULT NULL,
    p_exam_id BIGINT DEFAULT NULL, p_import_id BIGINT DEFAULT NULL)
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE v_class BIGINT; v_sid BIGINT;
BEGIN
    IF p_class_code IS NOT NULL AND p_class_code <> '' THEN
        INSERT INTO classes (class_code, class_name) VALUES (p_class_code, p_class_code)
        ON CONFLICT (class_code) DO NOTHING;
        SELECT class_id INTO v_class FROM classes WHERE class_code = p_class_code;
    END IF;

    INSERT INTO students (student_code, full_name, class_id, date_of_birth, email, import_id)
    VALUES (trim(p_code), trim(p_full_name), v_class, p_dob, p_email, p_import_id)
    ON CONFLICT (student_code) DO UPDATE
        SET full_name = EXCLUDED.full_name,
            class_id = COALESCE(EXCLUDED.class_id, students.class_id),
            date_of_birth = COALESCE(EXCLUDED.date_of_birth, students.date_of_birth),
            email = COALESCE(EXCLUDED.email, students.email)
    RETURNING student_id INTO v_sid;

    IF p_exam_id IS NOT NULL THEN
        INSERT INTO exam_students (exam_id, student_id) VALUES (p_exam_id, v_sid)
        ON CONFLICT DO NOTHING;
    END IF;
    RETURN v_sid;
END $$;
