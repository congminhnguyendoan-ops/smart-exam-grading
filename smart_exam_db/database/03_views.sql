-- =====================================================================
--  File 03: Views - phục vụ màn hình thống kê, tra cứu, đối soát
-- =====================================================================

-- 1. Bảng điểm chi tiết của từng kỳ thi
CREATE OR REPLACE VIEW v_exam_results AS
SELECT r.result_id, e.exam_id, e.exam_title, sj.subject_code, sj.subject_name, e.exam_date,
       s.student_id, s.student_code, s.full_name, cl.class_code,
       ec.code AS exam_code, r.num_correct, e.num_questions,
       r.score, e.max_score, (r.score >= e.pass_score) AS passed,
       r.status, r.sheet_id, r.confirmed_by, r.updated_at
FROM results r
JOIN exams e        ON e.exam_id = r.exam_id
JOIN subjects sj    ON sj.subject_id = e.subject_id
JOIN students s     ON s.student_id = r.student_id
LEFT JOIN classes cl ON cl.class_id = s.class_id
LEFT JOIN exam_codes ec ON ec.exam_code_id = r.exam_code_id
WHERE r.status <> 'void';

-- 2. Tổng quan kỳ thi (dashboard)
CREATE OR REPLACE VIEW v_exam_summary AS
SELECT e.exam_id, e.exam_title, e.status, e.exam_date,
       (SELECT COUNT(*) FROM exam_students es WHERE es.exam_id = e.exam_id)                       AS registered,
       (SELECT COUNT(*) FROM answer_sheets a WHERE a.exam_id = e.exam_id)                         AS sheets_uploaded,
       (SELECT COUNT(*) FROM answer_sheets a WHERE a.exam_id = e.exam_id AND a.status = 'graded') AS sheets_graded,
       (SELECT COUNT(*) FROM answer_sheets a WHERE a.exam_id = e.exam_id AND a.status = 'needs_review') AS sheets_need_review,
       COUNT(r.result_id)                                   AS results_count,
       COUNT(r.result_id) FILTER (WHERE r.status = 'auto')  AS auto_matched,
       ROUND(AVG(r.score), 2)                               AS avg_score,
       MIN(r.score)                                         AS min_score,
       MAX(r.score)                                         AS max_score,
       ROUND(STDDEV_POP(r.score), 2)                        AS stddev_score,
       ROUND(100.0 * COUNT(*) FILTER (WHERE r.score >= e.pass_score) / NULLIF(COUNT(r.result_id), 0), 1) AS pass_rate_pct,
       -- Tỉ lệ match SBD tự động thành công (chỉ số cần báo cáo ở Tuần 11)
       ROUND(100.0 * COUNT(r.result_id) FILTER (WHERE r.status = 'auto')
             / NULLIF((SELECT COUNT(*) FROM answer_sheets a
                       WHERE a.exam_id = e.exam_id AND a.status IN ('graded','needs_review')), 0), 1) AS auto_match_rate_pct
FROM exams e
LEFT JOIN results r ON r.exam_id = e.exam_id AND r.status <> 'void'
GROUP BY e.exam_id;

-- 3. Phổ điểm (histogram theo khoảng 1 điểm)
CREATE OR REPLACE VIEW v_score_distribution AS
SELECT r.exam_id,
       LEAST(FLOOR(r.score), e.max_score - 1)::int                        AS bucket_from,
       LEAST(FLOOR(r.score), e.max_score - 1)::int + 1                    AS bucket_to,
       COUNT(*)                                                           AS num_students
FROM results r JOIN exams e ON e.exam_id = r.exam_id
WHERE r.status <> 'void'
GROUP BY r.exam_id, 2, 3;

-- 4. Độ khó từng câu (theo câu GỐC, gộp qua các mã đề)
--    p_value = tỉ lệ trả lời đúng: >0.7 dễ, 0.3-0.7 trung bình, <0.3 khó
CREATE OR REPLACE VIEW v_question_difficulty AS
WITH ans AS (
    SELECT s.exam_id,
           COALESCE(q.original_no, ak.question_no) AS original_no,
           q.question_id, sa.is_correct, sa.selected_options, ak.correct_option
    FROM results r
    JOIN answer_sheets s  ON s.sheet_id = r.sheet_id
    JOIN answer_keys ak   ON ak.exam_code_id = s.exam_code_id
    LEFT JOIN sheet_answers sa ON sa.sheet_id = s.sheet_id AND sa.question_no = ak.question_no
    LEFT JOIN questions q ON q.question_id = ak.question_id
    WHERE r.status <> 'void'
)
SELECT exam_id, original_no, question_id,
       COUNT(*)                                        AS attempts,
       COUNT(*) FILTER (WHERE is_correct)              AS correct,
       ROUND(COUNT(*) FILTER (WHERE is_correct)::numeric / NULLIF(COUNT(*),0), 3) AS p_value,
       CASE WHEN COUNT(*) FILTER (WHERE is_correct)::numeric / NULLIF(COUNT(*),0) > 0.7 THEN 'Dễ'
            WHEN COUNT(*) FILTER (WHERE is_correct)::numeric / NULLIF(COUNT(*),0) >= 0.3 THEN 'Trung bình'
            ELSE 'Khó' END                              AS difficulty,
       COUNT(*) FILTER (WHERE COALESCE(selected_options,'') = '') AS blank_count
FROM ans
GROUP BY exam_id, original_no, question_id;

-- 5. Hàng đợi review (màn hình đối soát)
CREATE OR REPLACE VIEW v_review_pending AS
SELECT rq.review_id, rq.priority, rq.reasons, rq.details, rq.status, rq.created_at,
       s.sheet_id, s.exam_id, e.exam_title, s.image_path, s.aligned_image_path,
       s.detected_sbd, s.sbd_confidence, s.detected_exam_code, s.exam_code_confidence,
       s.raw_score, s.num_correct,
       st.student_code AS matched_code, st.full_name AS matched_name,
       u.full_name AS assigned_to_name
FROM review_queue rq
JOIN answer_sheets s ON s.sheet_id = rq.sheet_id
JOIN exams e         ON e.exam_id = s.exam_id
LEFT JOIN students st ON st.student_id = s.matched_student_id
LEFT JOIN users u    ON u.user_id = rq.assigned_to
WHERE rq.status IN ('pending','in_progress')
ORDER BY rq.priority, rq.created_at;

-- 6. Tra cứu điểm cho sinh viên (chỉ kỳ thi đã công bố / đóng)
CREATE OR REPLACE VIEW v_student_transcript AS
SELECT s.student_id, s.student_code, s.full_name, s.user_id,
       e.exam_id, e.exam_title, sj.subject_name, e.exam_date,
       r.score, e.max_score, (r.score >= e.pass_score) AS passed, r.status
FROM results r
JOIN students s  ON s.student_id = r.student_id
JOIN exams e     ON e.exam_id = r.exam_id
JOIN subjects sj ON sj.subject_id = e.subject_id
WHERE r.status IN ('auto','confirmed','manual_edited') AND e.status IN ('published','closed');

-- 7. SV đăng ký thi nhưng chưa có điểm (vắng / phiếu đang review)
CREATE OR REPLACE VIEW v_missing_results AS
SELECT es.exam_id, s.student_id, s.student_code, s.full_name, es.is_absent
FROM exam_students es
JOIN students s ON s.student_id = es.student_id
WHERE NOT EXISTS (SELECT 1 FROM results r WHERE r.exam_id = es.exam_id
                  AND r.student_id = es.student_id AND r.status <> 'void');

-- 8. Hiệu năng OCR thực tế: tỉ lệ chữ số bị giáo viên sửa (đo domain gap trên dữ liệu thật)
CREATE OR REPLACE VIEW v_ocr_correction_stats AS
SELECT m.model_id, m.model_name, m.version, d.field,
       COUNT(*)                                                          AS total_digits,
       COUNT(*) FILTER (WHERE d.corrected_digit IS NOT NULL
                          AND d.corrected_digit <> d.predicted_digit)    AS corrected,
       ROUND(1 - COUNT(*) FILTER (WHERE d.corrected_digit IS NOT NULL
                          AND d.corrected_digit <> d.predicted_digit)::numeric / NULLIF(COUNT(*),0), 4) AS real_accuracy,
       ROUND(AVG(d.confidence), 4)                                       AS avg_confidence
FROM ocr_digits d
JOIN answer_sheets s ON s.sheet_id = d.sheet_id
LEFT JOIN ml_models m ON m.model_id = s.ocr_model_id
GROUP BY m.model_id, m.model_name, m.version, d.field;
